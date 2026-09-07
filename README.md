# Kunskapsbank — statisk webbplats

Svensk, snabb statisk sajt genererad från kunskapsbanken på `/home/box/kunskapsbank/`.

Publicering: **GitHub Pages från `/docs`** (denna repos `docs/`-mapp).

## Ledfrågor

1. Vad är optimalt lärande?
2. Hur gör vi det i en verklighet där AI och skärmar är överallt?

## Bygga

```bash
cd /workspace/kunskapsbank-site
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py
```

`build.py` läser källorna under `/home/box/kunskapsbank/` och regenererar `docs/`:

| Källa | Sida |
|-------|------|
| Ledfrågor + översikt | `docs/index.html` |
| `00-index/KATALOG.md` | `docs/katalog.html` |
| `03-teman/*` | `docs/teman/*.html` |
| `02-synteser/*` | `docs/alder/*.html` |
| `04-riktning/UTKAST.md` | `docs/riktning.html` |
| Alla `SYNTES-*.md` | `docs/synteser/*.html` |

Stora PDF:er från `01-originaldokument/` **kopieras inte**. DOI/URL från respektive `METADATA.md` visas på syntessidorna.

## GitHub Pages

1. Pusha repot till GitHub.
2. Settings → Pages → Source: **Deploy from a branch**.
3. Branch: `main` (eller motsvarande), folder: **/docs**.
4. Sajten publiceras från `docs/index.html`.

Lokal förhandsvisning:

```bash
.venv/bin/python -m http.server 8000 --directory docs
# öppna http://127.0.0.1:8000/
```

## Teknik

- Ren HTML/CSS, systemtypsnitt
- Minimal filter-JS på katalogsidan
- Python + `markdown` för markdown→HTML
