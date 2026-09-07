# Kunskapsbank — statisk webbplats

Svensk, snabb statisk sajt genererad från kunskapsbanken på `/home/box/kunskapsbank/`.

**Ram:** Människans lärande i en tid av digitala intelligenser.

Publicering: **GitHub Pages från `/docs`**.

## Ledfrågor

1. Vad är optimalt lärande? (mediumoberoende)
2. Hur när AI och skärmar redan är överallt?

## Sidor

- `index.html` — slutsats + länkar (riktning/praktik först; katalog N=88 en gång)
- `riktning.html` — hållning
- `praktik.html` — stop/start/measure per stadium
- `metod.html` — PICO-ish, exklusionslogg, tier, cite, licens
- `motargument.html` — steelman mot papper-default-dogm
- `katalog.html` — 88 källor med Tier
- `sok.html` — klient-fulltext via `search-index.json`

## Bygga

```bash
cd /workspace/kunskapsbank-site
.venv/bin/python build.py
```

Regel: källa utan `Tier:` i METADATA renderas inte. Inga nya forskningsteman. Unikt N från KATALOG.md.
