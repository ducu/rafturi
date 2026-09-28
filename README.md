# Rafturi

Ce citesc și ce am citit, cu recenziile mele, luate direct de pe Goodreads.

Pagina: https://ducu.github.io/rafturi/

## Cum se actualizează

Singur. În fiecare dimineață, GitHub Action-ul din `.github/workflows/pages.yml`:

1. rulează `fetch.py`, care ia de pe Goodreads rafturile `currently-reading`, `read` și rafturile pe ani (`2016`, `2017`, …) și le salvează în `data/books.json`, plus coperțile noi în `covers/`;
2. dacă s-a schimbat ceva, face commit cu schimbările;
3. rulează `build.py` și publică pagina.

Deci ajunge să scrii recenzia pe Goodreads și să pui cartea pe raftul anului (ex. `2026`). A doua zi apare aici.
Poți porni actualizarea și imediat, din tab-ul *Actions → Actualizează și publică → Run workflow*.

Action-ul are nevoie de două secrete (*Settings → Secrets and variables → Actions*):
- `GOODREADS_USER`: id-ul numeric al contului (`7653898`);
- `GOODREADS_KEY`: parametrul `key=` din linkul RSS al unui raft de pe Goodreads.

## Ce e în repo

- `data/books.json`: rafturile, așa cum le dă Goodreads. Istoricul git arată ce s-a schimbat de la o zi la alta.
- `data/overrides.json`: corecturi manuale pentru o carte, după `book_id`. De exemplu `{"12345": {"hide": true}}` o ascunde, iar `{"12345": {"user_review": "…"}}` îi înlocuiește textul.
- `covers/`: coperțile, descărcate o singură dată.
- `review.py`: împarte o recenzie în comentariile mele și citatele din carte (logica rafinată în multe runde; citește docstring-urile înainte să schimbi ceva) și pliază recenziile lungi după ~100 de cuvinte.
- `build.py` + `template.html`: pagina. Designul e în `template.html`.

Secțiuni: *În curs* (raftul `currently-reading`), câte una pe fiecare raft anual, cu cărțile sortate după data citirii, și *Alte lecturi* (cărțile de pe `read` care nu sunt pe niciun raft anual).

## Local

```
GOODREADS_USER=7653898 GOODREADS_KEY=… python3 fetch.py   # opțional
python3 build.py
open _site/index.html
```
