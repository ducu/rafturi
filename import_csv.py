#!/usr/bin/env python3
"""Export CSV de pe Goodreads -> data/books.json (+ coperți noi în covers/).

Goodreads a scos feed-urile RSS, deci rafturile se actualizează din exportul CSV
(Goodreads -> My Books -> Import and export -> Export Library). Folosire:

    python3 import_csv.py [data/goodreads_library_export.csv] [--out data/books.json]

CSV-ul nu conține media Goodreads, linkul recenziei și coperta. Pentru cărțile care erau deja în
books.json se păstrează valorile vechi; la cărțile noi linkul e pagina cărții, media rămâne goală,
iar coperta se ia de pe pagina cărții de pe Goodreads (sau de pe Open Library, după ISBN).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data', 'books.json')
COVERS = os.path.join(ROOT, 'covers')
UA = {'User-Agent': 'Mozilla/5.0 (rafturi; +https://ducu.github.io/rafturi/)'}


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            if attempt == 2:
                raise
            print(f'  retry after {e}', file=sys.stderr)
            time.sleep(3 * (attempt + 1))


def rfc_date(s):
    """'2026/09/27' (sau '2026/09', '2026') -> data RFC 2822, ca în feed-ul RSS vechi; '' dacă lipsește."""
    parts = [int(p) for p in re.findall(r'\d+', s or '')]
    if not parts:
        return ''
    y, m, d = (parts + [1, 1])[:3]
    return format_datetime(datetime(y, m, d, tzinfo=timezone.utc))


def clean_review(s):
    """Goodreads pune mențiunile de autori/cărți ca [a:Nume|id|Nume|url]; rămâne doar numele."""
    return re.sub(r'\[[ab]:([^|\]]*)\|[^\]]*\]', r'\1', s).strip()


def book(row, old):
    bid = row['Book Id']
    rating = str(int(float(row['My Rating'] or 0)))
    shelves = ', '.join(s.strip() for s in row['Bookshelves'].split(',') if s.strip())
    return {
        'book_id': bid,
        'title': row['Title'],
        'author_name': row['Author'],
        'link': old.get('link') or f'https://www.goodreads.com/book/show/{bid}',
        'user_rating': rating,
        'average_rating': old.get('average_rating', ''),
        # dacă în CSV lipsește data citirii, rămâne cea veche
        'user_read_at': rfc_date(row['Date Read']) or old.get('user_read_at', ''),
        'user_date_added': old.get('user_date_added') or rfc_date(row['Date Added']),
        'user_shelves': shelves,
        'user_review': clean_review(row['My Review']),
        'book_medium_image_url': old.get('book_medium_image_url', ''),
    }


def ordered(items, old_ids):
    """Cărțile care erau deja în books.json își păstrează locul; cele noi merg în față, cele mai recente primele."""
    pos = {i: n for n, i in enumerate(old_ids)}
    new = sorted((b for b in items if b['book_id'] not in pos),
                 key=lambda b: b['_added'], reverse=True)
    known = sorted((b for b in items if b['book_id'] in pos), key=lambda b: pos[b['book_id']])
    return new + known


def fetch_cover(b, isbn13):
    path = os.path.join(COVERS, f'{b["book_id"]}.jpg')
    if os.path.exists(path):
        return False
    url = b['book_medium_image_url']
    if not url:
        try:
            page = get(f'https://www.goodreads.com/book/show/{b["book_id"]}').decode('utf-8', 'replace')
            m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
            url = m.group(1) if m else ''
        except Exception as e:
            print(f'  nu am găsit coperta pentru {b["title"]}: {e}', file=sys.stderr)
    if not url and isbn13:
        url = f'https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg?default=false'
    if not url:
        return False
    try:
        data = get(url)
    except Exception as e:
        print(f'  nu am putut descărca coperta pentru {b["title"]}: {e}', file=sys.stderr)
        return False
    open(path, 'wb').write(data)
    b['book_medium_image_url'] = b['book_medium_image_url'] or url
    return True


def main(argv):
    out = DATA
    if '--out' in argv:
        i = argv.index('--out')
        out = argv[i + 1]
        del argv[i:i + 2]
    csv_path = argv[0] if argv else os.path.join(ROOT, 'data', 'goodreads_library_export.csv')

    rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig')))
    old = json.load(open(DATA, encoding='utf-8')) if os.path.exists(DATA) else {}
    old_by_id = {b['book_id']: b for b in old.get('currently', []) + old.get('read', [])}

    currently, read, years = [], [], {}
    isbn = {}
    for row in rows:
        shelf = row['Exclusive Shelf']
        if shelf not in ('read', 'currently-reading'):
            continue
        b = book(row, old_by_id.get(row['Book Id'], {}))
        b['_added'] = row['Date Added']  # AAAA/LL/ZZ, se sortează ca text
        isbn[b['book_id']] = re.sub(r'\D', '', row['ISBN13'])
        (read if shelf == 'read' else currently).append(b)
        if shelf == 'read':
            # "2026 (#7)": poziția în raftul anual; mai mare = mai recent
            for y, n in re.findall(r'(\d{4}) \(#(\d+)\)', row['Bookshelves with positions']):
                years.setdefault(y, []).append((int(n), b['book_id']))

    if not read:
        sys.exit('Niciun rând „read” în CSV — nu actualizez nimic')

    currently = ordered(currently, [b['book_id'] for b in old.get('currently', [])])
    read = ordered(read, [b['book_id'] for b in old.get('read', [])])
    new_covers = sum(fetch_cover(b, isbn[b['book_id']]) for b in currently + read)
    for b in currently + read:
        b.pop('_added', None)

    books = {
        'currently': currently,
        'read': read,
        'years': {y: [i for _, i in sorted(v, reverse=True)] for y, v in sorted(years.items(), reverse=True)},
    }
    unchanged = {k: old.get(k) for k in books} == books
    books['fetched'] = old.get('fetched') if unchanged else datetime.now(timezone.utc).strftime('%Y-%m-%d')

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'în curs: {len(currently)}, citite: {len(read)}, ani: {len(books["years"])}, '
          f'coperți noi: {new_covers}, {"nimic nou" if unchanged else "actualizat"} -> {out}')


if __name__ == '__main__':
    main(sys.argv[1:])
