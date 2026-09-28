#!/usr/bin/env python3
"""Build the Rafturi page: data/books.json + template.html -> _site/.

Usage: python3 build.py [out_dir]   (default: _site)
"""
import html
import json
import os
import re
import shutil
import sys
from email.utils import parsedate_to_datetime

from review import RO_MONTHS, build_review_block, fmt_date, review_to_paragraphs

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_site')
OTHER_ID, OTHER_LABEL = 'fara-recenzie', 'Alte lecturi'


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(s or '')).strip()


def read_date(book):
    try:
        return parsedate_to_datetime(book['user_read_at']).date().isoformat()
    except (TypeError, ValueError):
        return ''


def rating_caption(book, with_note):
    cap = f'{clean(book["author_name"])} — {clean(book["title"])}'
    if with_note and book['user_rating'] not in ('', '0'):
        cap += f' · notă {book["user_rating"]}/5'
    if book['average_rating']:
        cap += f' · medie {book["average_rating"]}'
    return cap


def build_entry(book):
    title, author = clean(book['title']), clean(book['author_name'])
    rating, avg = book['user_rating'] or '0', book['average_rating']
    date = fmt_date(book['user_read_at'])
    date_html = f'<time class="entry-date">{date}</time>' if date else ''
    cover = f'<img class="entry-cover" src="covers/{book["book_id"]}.jpg" alt="" loading="lazy">'
    meta = f'<div class="entry-meta"><span class="entry-kind">Recenzie</span>{date_html}</div>'
    source = ('<p class="entry-source"><a href="%s" target="_blank" rel="noopener">%s — %s</a></p>'
              % (html.escape(book['link'], quote=True), html.escape(author, quote=False), html.escape(title, quote=False)))
    review = build_review_block(review_to_paragraphs(book['user_review']))
    if rating != '0':
        note = f'<p class="entry-note">Notă: {rating}/5 · medie Goodreads {avg}</p>'
    elif avg:
        note = f'<p class="entry-note">Medie Goodreads: {avg}</p>'
    else:
        note = ''
    return (f'<article class="entry entry--review">\n{cover}\n{meta}\n{source}\n{review}\n{note}\n'
            f'<div class="clear"></div>\n</article>\n')


def current_grid(books):
    files = [f'covers/{b["book_id"]}.jpg' for b in books]
    files_json = html.escape(json.dumps(files, ensure_ascii=False), quote=True)
    caps_json = html.escape(json.dumps([rating_caption(b, False) for b in books], ensure_ascii=False), quote=True)
    buttons = ''.join(
        f'<button type="button" class="thumb-btn" data-gallery=\'{files_json}\' data-captions=\'{caps_json}\' '
        f'data-index="{i}"><img src="{f}" alt="" loading="lazy"></button>'
        for i, f in enumerate(files))
    return f'<div class="reading-grid">{buttons}</div>\n'


def other_grid(books):
    caps = [rating_caption(b, True) for b in books]
    caps_json = html.escape(json.dumps(caps, ensure_ascii=False), quote=True)
    buttons = ''.join(
        f'<button type="button" class="thumb-btn" data-index="{i}" title="{html.escape(c, quote=True)}">'
        f'<img src="covers/{b["book_id"]}.jpg" '
        f'alt="{html.escape(clean(b["author_name"]) + " — " + clean(b["title"]), quote=True)}" loading="lazy"></button>'
        for i, (b, c) in enumerate(zip(books, caps)))
    return f'<div class="reading-grid" data-inline-gallery="1" data-captions=\'{caps_json}\'>{buttons}</div>\n'


def apply_overrides(books):
    """data/overrides.json: {"<book_id>": {"hide": true} | {"user_review": "..."} | any field}"""
    path = os.path.join(ROOT, 'data', 'overrides.json')
    overrides = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    out = []
    for b in books:
        o = overrides.get(b['book_id'], {})
        if not o.get('hide'):
            out.append({**b, **{k: v for k, v in o.items() if k != 'hide'}})
    return out


def main():
    data = json.load(open(os.path.join(ROOT, 'data', 'books.json'), encoding='utf-8'))
    currently = apply_overrides(data['currently'])
    read = apply_overrides(data['read'])

    by_id = {b['book_id']: b for b in read}
    by_year = {y: [by_id[i] for i in ids if i in by_id] for y, ids in data['years'].items()}
    for books in by_year.values():
        books.sort(key=read_date, reverse=True)  # newest first; stable, so ties keep shelf order
    on_year_shelf = {i for ids in data['years'].values() for i in ids}
    other = [b for b in read if b['book_id'] not in on_year_shelf]

    sections = []  # (id, label, count, html)
    if currently:
        sections.append(('currently', 'În curs', len(currently), current_grid(currently)))
    for y in sorted(by_year, reverse=True):
        sections.append((y, y, len(by_year[y]), '\n    '.join(build_entry(b) for b in by_year[y])))
    if other:
        note = (f'<p class="shelf-note">Cărți de pe raftul „read” fără recenzie și fără raft anual — '
                f'{len(other)} titluri, de la cele adăugate recent la cele vechi.</p>\n    ')
        sections.append((OTHER_ID, OTHER_LABEL, len(other), note + other_grid(other)))

    nav = ''.join(f'      <a href="#{i}" class="ynav-item" data-target="{i}"><strong>{label}</strong> ({n})</a>\n'
                  for i, label, n, _ in sections)
    nav = f'    <nav class="ynav" aria-label="Navigare pe rafturi">\n{nav}    </nav>\n'
    timeline = '\n'.join(f'    <div class="year-marker" id="{i}" aria-hidden="true">{label}</div>\n    {body}'
                         for i, label, _, body in sections)

    fetched = data.get('fetched') or ''
    if fetched:
        y, m, d = (int(x) for x in fetched.split('-'))
        fetched = f'{d} {RO_MONTHS[m - 1]} {y}'
    page = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
    page = page.replace('{{NAV}}', nav).replace('{{TIMELINE}}', timeline).replace('{{FETCHED}}', fetched)

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'covers'))
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(page)
    shutil.copy(os.path.join(ROOT, 'avatar.jpg'), OUT)
    missing = []
    for b in currently + read:
        src = os.path.join(ROOT, 'covers', f'{b["book_id"]}.jpg')
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, 'covers'))
        else:
            missing.append(b['book_id'])
    if missing:
        print('coperți lipsă (rulează fetch.py):', ', '.join(missing))
    print(f'{len(currently)} în curs, {sum(len(v) for v in by_year.values())} pe ani, {len(other)} alte lecturi -> {OUT}')


if __name__ == '__main__':
    main()
