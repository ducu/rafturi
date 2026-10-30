# Rafturi

Ce citesc și ce am citit, cu recenziile mele, luate direct de pe Goodreads.

Pagina: https://ducu.github.io/rafturi/

## Cum se actualizează

De mână, după ce termini o carte sau scrii o recenzie. (Până pe 27 octombrie 2026 se actualiza singur din feed-urile RSS de pe Goodreads; Goodreads le-a scos, iar `list_rss` dă acum 404.)

1. Pe Goodreads: *My Books → Import and export → Export Library*. Salvează CSV-ul ca `data/goodreads_library_export.csv` (e în `.gitignore`: conține și raftul *to-read*).
2. `python3 import_csv.py` — scrie `data/books.json` și descarcă coperțile cărților noi în `covers/`.
3. `python3 build.py` și `open _site/index.html` ca să verifici pagina.
4. `git add -A && git commit -m "Goodreads: actualizare" && git push` — GitHub Action-ul (`.github/workflows/pages.yml`) construiește și publică pagina.

Cartea trebuie să fie pe raftul anului (ex. `2026`) ca să apară în secțiunea anului, altfel ajunge la *Alte lecturi*.

Ce nu vine din CSV: media Goodreads (se păstrează cea veche, la cărțile noi lipsește), linkul recenziei (la cărțile noi e pagina cărții) și coperta (se ia de pe pagina cărții de pe Goodreads, sau de pe Open Library după ISBN). Mențiunile `[a:Nume|…]` din recenzii devin simplu numele.

## Ce e în repo

- `data/books.json`: rafturile, generate de `import_csv.py` din exportul Goodreads. Istoricul git arată ce s-a schimbat de la o zi la alta.
- `data/overrides.json`: corecturi manuale pentru o carte, după `book_id`. De exemplu `{"12345": {"hide": true}}` o ascunde, iar `{"12345": {"user_review": "…"}}` îi înlocuiește textul.
- `covers/`: coperțile, descărcate o singură dată.
- `review.py`: împarte o recenzie în comentariile mele și citatele din carte (logica rafinată în multe runde; citește docstring-urile înainte să schimbi ceva) și pliază recenziile lungi după ~100 de cuvinte.
- `build.py` + `template.html`: pagina. Designul e în `template.html`.

Secțiuni: *În curs* (raftul `currently-reading`), câte una pe fiecare raft anual, cu cărțile sortate după data citirii, și *Alte lecturi* (cărțile de pe `read` care nu sunt pe niciun raft anual).

## Local

```
python3 import_csv.py   # după un export nou
python3 build.py
open _site/index.html
```
