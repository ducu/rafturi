#!/usr/bin/env python3
"""Fetch my Goodreads shelves (RSS) -> data/books.json, and download missing covers.

Runs daily from the GitHub Action; can also be run by hand. Needs GOODREADS_USER and
GOODREADS_KEY (the "key" from the shelf RSS link on Goodreads) in the environment.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data', 'books.json')
COVERS = os.path.join(ROOT, 'covers')
UA = {'User-Agent': 'Mozilla/5.0 (rafturi; +https://ducu.github.io/rafturi/)'}
FIELDS = ['book_id', 'title', 'author_name', 'link', 'user_rating', 'average_rating',
          'user_read_at', 'user_date_added', 'user_shelves', 'user_review', 'book_medium_image_url']


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:
            if attempt == 3:
                raise
            print(f'  retry after {e}', file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def field(item, tag):
    m = re.search(rf'<{tag}>(.*?)</{tag}>', item, re.S)
    if not m:
        return ''
    v = m.group(1).strip()
    if v.startswith('<![CDATA[') and v.endswith(']]>'):
        return v[9:-3].strip()
    # plain (non-CDATA) XML text is entity-escaped once
    return html.unescape(v)


def shelf(user, key, name):
    """All items on a shelf, in Goodreads order (most recently added first)."""
    items = []
    for page in range(1, 50):
        url = f'https://www.goodreads.com/review/list_rss/{user}?key={key}&shelf={name}&page={page}'
        xml = get(url).decode('utf-8')
        if '<channel>' not in xml:
            sys.exit(f'Goodreads nu a răspuns cu un feed RSS pentru raftul {name}')
        page_items = re.findall(r'<item>(.*?)</item>', xml, re.S)
        if not page_items:
            break
        items += [{f: field(it, f) for f in FIELDS} for it in page_items]
    return items


def main():
    user, key = os.environ.get('GOODREADS_USER'), os.environ.get('GOODREADS_KEY')
    if not user or not key:
        sys.exit('Setează GOODREADS_USER și GOODREADS_KEY')

    books = {'currently': shelf(user, key, 'currently-reading'), 'read': shelf(user, key, 'read')}
    # never publish an empty page because of a hiccup on Goodreads' side
    if not books['read']:
        sys.exit('Raftul "read" a venit gol — nu actualizez nimic')
    # year shelves ("2016", "2017", ...) say which year each book belongs to; the book
    # data itself comes from "read"
    read_ids = {b['book_id'] for b in books['read']}
    years = sorted({s.strip() for b in books['read'] for s in b['user_shelves'].split(',')
                    if re.fullmatch(r'\d{4}', s.strip())}, reverse=True)
    books['years'] = {}
    for y in years:
        items = shelf(user, key, y)
        books['years'][y] = [b['book_id'] for b in items]
        books['read'] += [b for b in items if b['book_id'] not in read_ids]
        read_ids |= {b['book_id'] for b in items}

    old = json.load(open(DATA, encoding='utf-8')) if os.path.exists(DATA) else {}
    unchanged = {k: old.get(k) for k in books} == books
    if not unchanged:
        books['fetched'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    else:
        books['fetched'] = old.get('fetched')

    os.makedirs(COVERS, exist_ok=True)
    new_covers = 0
    for b in books['currently'] + books['read']:
        path = os.path.join(COVERS, f'{b["book_id"]}.jpg')
        if b['book_id'] and not os.path.exists(path) and b['book_medium_image_url']:
            open(path, 'wb').write(get(b['book_medium_image_url']))
            new_covers += 1

    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'în curs: {len(books["currently"])}, citite: {len(books["read"])}, ani: {len(books["years"])}, '
          f'coperți noi: {new_covers}, {"nimic nou" if unchanged else "actualizat"}')


if __name__ == '__main__':
    main()
