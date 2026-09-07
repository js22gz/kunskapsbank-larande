#!/usr/bin/env python3
"""Bygg statisk sajt från /home/box/kunskapsbank/ till docs/ (GitHub Pages)."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

try:
    import markdown
except ImportError as e:
    raise SystemExit(
        "Saknar paketet 'markdown'. Kör: python3 -m venv .venv && "
        ".venv/bin/pip install -r requirements.txt"
    ) from e

ROOT = Path(__file__).resolve().parent
KB = Path("/home/box/kunskapsbank")
OUT = ROOT / "docs"
ASSETS_SRC = OUT / "assets"  # style/filter live under docs/assets and are kept

THEME_LABELS = {
    "ai-och-larande": "AI och lärande",
    "analogt-vs-digitalt": "Analogt vs digitalt",
    "lasning-och-skrivande": "Läsning och skrivande",
    "papper-vs-skarm": "Papper vs skärm",
    "penna-vs-tangentbord": "Penna vs tangentbord",
    "uppmarksamhet-och-minne": "Uppmärksamhet och minne",
}

AGE_LABELS = {
    "foralder-tidig-barndom": "Förälder / tidig barndom",
    "grundskola-lag": "Grundskola låg (åk 1–6)",
    "grundskola-hog": "Grundskola hög (åk 7–9)",
    "gymnasium": "Gymnasium",
    "vuxen-livslangt": "Vuxen / livslångt lärande",
    "overgripande": "Övergripande",
}

AGE_ORDER = [
    "foralder-tidig-barndom",
    "grundskola-lag",
    "grundskola-hog",
    "gymnasium",
    "vuxen-livslangt",
    "overgripande",
]

MD_EXT = ["tables", "fenced_code", "sane_lists", "smarty", "toc"]


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=MD_EXT)


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def slug_from_syntes(name: str) -> str:
    # SYNTES-foo.md -> foo
    base = Path(name).name
    if base.startswith("SYNTES-"):
        base = base[len("SYNTES-") :]
    return Path(base).stem


def parse_metadata(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key and val and key not in data:
                data[key] = val
    return data


def load_all_metadata() -> dict[str, dict]:
    """Map catalog ID -> metadata dict; also index by folder name."""
    by_id: dict[str, dict] = {}
    by_folder: dict[str, dict] = {}
    base = KB / "01-originaldokument"
    if not base.is_dir():
        return by_id
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        meta = parse_metadata(folder / "METADATA.md")
        meta["_folder"] = folder.name
        by_folder[folder.name] = meta
        cid = meta.get("ID")
        if cid:
            by_id[cid] = meta
    return by_id


def extract_links(field: str) -> list[tuple[str, str]]:
    """Return (label, relative_md_path) from markdown link field."""
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", field)


def parse_katalog(path: Path) -> list[dict]:
    rows: list[dict] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 7:
            continue
        if parts[0] in ("ID", "----") or parts[0].startswith("-"):
            continue
        if not re.match(r"^[A-Z]+-\d+", parts[0]):
            continue
        cid, title, year, age, themes, syntes_field, original_field = parts[:7]
        theme_list = [t.strip() for t in themes.split(";") if t.strip()]
        syntes_links = extract_links(syntes_field)
        original_links = extract_links(original_field)
        # Prefer tema link for canonical synthesis page
        tema_path = None
        age_paths: list[str] = []
        for label, href in syntes_links:
            # normalize ../03-teman/... or similar
            clean = href.replace("\\", "/")
            if "03-teman/" in clean:
                tema_path = clean
            elif "02-synteser/" in clean:
                age_paths.append(clean)
        orig_folder = None
        for _, href in original_links:
            m = re.search(r"01-originaldokument/([^/]+)/?", href)
            if m:
                orig_folder = m.group(1)
                break
        rows.append(
            {
                "id": cid,
                "title": title,
                "year": year,
                "age": age,
                "themes": theme_list,
                "syntes_links": syntes_links,
                "tema_path": tema_path,
                "age_paths": age_paths,
                "orig_folder": orig_folder,
            }
        )
    return rows


def resolve_kb_path(rel_from_katalog: str) -> Path | None:
    """Katalog links are relative to 00-index/."""
    p = (KB / "00-index" / rel_from_katalog).resolve()
    try:
        p.relative_to(KB.resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def pick_syntes_sources(katalog: list[dict]) -> dict[str, Path]:
    """Map synthesis slug -> best source markdown path."""
    chosen: dict[str, Path] = {}
    # 1) From catalog tema paths
    for row in katalog:
        if row["tema_path"]:
            p = resolve_kb_path(row["tema_path"])
            if p:
                chosen[slug_from_syntes(p.name)] = p
        for ap in row["age_paths"]:
            p = resolve_kb_path(ap)
            if p:
                slug = slug_from_syntes(p.name)
                chosen.setdefault(slug, p)
    # 2) All theme syntheses
    themes_dir = KB / "03-teman"
    if themes_dir.is_dir():
        for p in themes_dir.glob("*/SYNTES-*.md"):
            chosen.setdefault(slug_from_syntes(p.name), p)
    # 3) Age syntheses
    ages_dir = KB / "02-synteser"
    if ages_dir.is_dir():
        for p in ages_dir.glob("*/SYNTES-*.md"):
            chosen.setdefault(slug_from_syntes(p.name), p)
    return chosen


def slug_to_katalog_id(katalog: list[dict], slug: str) -> str | None:
    for row in katalog:
        for _, href in row["syntes_links"]:
            if slug_from_syntes(Path(href).name) == slug:
                return row["id"]
        if row["tema_path"] and slug_from_syntes(Path(row["tema_path"]).name) == slug:
            return row["id"]
    return None


def rewrite_md_links(md: str, page_depth: int) -> str:
    """Rewrite relative .md links inside content to site HTML where possible."""
    prefix = "../" * page_depth

    def repl(m: re.Match) -> str:
        label, href = m.group(1), m.group(2)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        name = Path(href.split("#")[0]).name
        if name.startswith("SYNTES-") and name.endswith(".md"):
            return f"[{label}]({prefix}synteser/{slug_from_syntes(name)}.html)"
        if name == "UTKAST.md":
            return f"[{label}]({prefix}riktning.html)"
        if name == "KATALOG.md":
            return f"[{label}]({prefix}katalog.html)"
        # theme folders
        if "/03-teman/" in href.replace("\\", "/"):
            parts = href.replace("\\", "/").split("/")
            try:
                i = parts.index("03-teman")
                theme = parts[i + 1]
                if theme in THEME_LABELS:
                    return f"[{label}]({prefix}teman/{theme}.html)"
            except (ValueError, IndexError):
                pass
        if "/02-synteser/" in href.replace("\\", "/"):
            parts = href.replace("\\", "/").split("/")
            try:
                i = parts.index("02-synteser")
                age = parts[i + 1]
                if age in AGE_LABELS:
                    return f"[{label}]({prefix}alder/{age}.html)"
            except (ValueError, IndexError):
                pass
        return m.group(0)

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl, md)


def page_shell(
    title: str,
    body: str,
    *,
    depth: int = 0,
    current: str = "",
    description: str = "",
    extra_head: str = "",
) -> str:
    prefix = "../" * depth
    nav = [
        ("index.html", "Start", "start"),
        ("katalog.html", "Katalog", "katalog"),
        ("teman/index.html", "Teman", "teman"),
        ("alder/index.html", "Ålder", "alder"),
        ("riktning.html", "Riktning", "riktning"),
    ]
    nav_html = []
    for href, label, key in nav:
        cur = ' aria-current="page"' if current == key else ""
        nav_html.append(f'<a href="{prefix}{href}"{cur}>{esc(label)}</a>')
    desc = description or "Kunskapsbank om evidens kring lärande, skärmar och AI."
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Kunskapsbank lärande</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="{prefix}assets/style.css">
{extra_head}
</head>
<body>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{prefix}index.html">Kunskapsbank <span>lärande</span></a>
    <nav>{" ".join(nav_html)}</nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>Statisk sajt genererad från kunskapsbanken. Inga PDF:er kopieras — se DOI/URL i respektive syntes.</p>
  </div>
</footer>
</body>
</html>
"""


def crumbs(items: list[tuple[str, str | None]], depth: int) -> str:
    prefix = "../" * depth
    parts = []
    for label, href in items:
        if href:
            parts.append(f'<a href="{prefix}{href}">{esc(label)}</a>')
        else:
            parts.append(f"<span>{esc(label)}</span>")
    return '<nav class="breadcrumb" aria-label="Brödsmula">' + " · ".join(parts) + "</nav>"


def source_box(meta: dict, cid: str | None) -> str:
    if not meta and not cid:
        return ""
    rows = []
    if cid:
        rows.append(f"<dt>ID</dt><dd><span class=\"id-badge\">{esc(cid)}</span></dd>")
    for key, label in [
        ("Titel", "Titel"),
        ("Författare", "Författare"),
        ("År", "År"),
        ("Typ", "Typ"),
        ("Källa/DOI", "Källa/DOI"),
        ("URL", "URL"),
        ("URL (författar-PDF)", "URL"),
        ("URL (SSRN)", "URL"),
    ]:
        val = meta.get(key)
        if not val:
            continue
        if key.startswith("URL") or "doi.org" in val.lower() or val.startswith("http"):
            # may contain multiple URLs
            urls = re.findall(r"https?://[^\s;]+", val)
            if urls:
                links = " · ".join(
                    f'<a href="{esc(u)}" rel="noopener noreferrer">{esc(u)}</a>' for u in urls
                )
                rows.append(f"<dt>{esc(label)}</dt><dd>{links}</dd>")
            else:
                # DOI-like without scheme
                doi = re.search(r"10\.\d{4,}/\S+", val)
                if doi:
                    u = "https://doi.org/" + doi.group(0).rstrip(".,;")
                    rows.append(
                        f'<dt>{esc(label)}</dt><dd><a href="{esc(u)}" rel="noopener noreferrer">{esc(val)}</a></dd>'
                    )
                else:
                    rows.append(f"<dt>{esc(label)}</dt><dd>{esc(val)}</dd>")
        elif "DOI" in key or "Källa" in key:
            urls = re.findall(r"https?://[^\s;]+", val)
            dois = re.findall(r"10\.\d{4,}/\S+", val)
            if urls:
                links = " · ".join(
                    f'<a href="{esc(u)}" rel="noopener noreferrer">{esc(u)}</a>' for u in urls
                )
                rows.append(f"<dt>{esc(label)}</dt><dd>{links}</dd>")
            elif dois:
                u = "https://doi.org/" + dois[0].rstrip(".,;")
                rows.append(
                    f'<dt>{esc(label)}</dt><dd><a href="{esc(u)}" rel="noopener noreferrer">{esc(val)}</a></dd>'
                )
            else:
                rows.append(f"<dt>{esc(label)}</dt><dd>{esc(val)}</dd>")
        else:
            rows.append(f"<dt>{esc(label)}</dt><dd>{esc(val)}</dd>")
    if not rows:
        return ""
    return (
        '<aside class="source-box"><h2>Källa (metadata)</h2><dl>'
        + "".join(rows)
        + "</dl><p style=\"margin:0.75rem 0 0;font-size:0.9rem;color:var(--muted)\">"
        "PDF kopieras inte till sajten — öppna DOI/URL ovan.</p></aside>"
    )


def meta_for_row(row: dict, by_id: dict, by_folder: dict) -> dict:
    if row["id"] in by_id:
        return by_id[row["id"]]
    if row.get("orig_folder") and row["orig_folder"] in by_folder:
        return by_folder[row["orig_folder"]]
    return {}


def build() -> None:
    if not KB.is_dir():
        raise SystemExit(f"Kunskapsbank saknas: {KB}")

    # Clean generated HTML/dirs but keep assets
    if OUT.exists():
        for child in OUT.iterdir():
            if child.name == "assets":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "teman").mkdir(exist_ok=True)
    (OUT / "alder").mkdir(exist_ok=True)
    (OUT / "synteser").mkdir(exist_ok=True)

    # Copy static assets into docs/assets
    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    static = ROOT / "static"
    for name in ("style.css", "filter.js"):
        src = static / name
        if not src.is_file():
            raise SystemExit(f"Saknar static/{name}")
        shutil.copy2(src, assets / name)

    katalog = parse_katalog(KB / "00-index" / "KATALOG.md")
    by_id = load_all_metadata()
    by_folder = {
        m["_folder"]: m
        for m in by_id.values()
        if "_folder" in m
    }
    # also folders without ID
    od = KB / "01-originaldokument"
    for folder in od.iterdir() if od.is_dir() else []:
        if folder.is_dir() and not folder.name.startswith("_"):
            meta = parse_metadata(folder / "METADATA.md")
            meta["_folder"] = folder.name
            by_folder.setdefault(folder.name, meta)
            if meta.get("ID"):
                by_id.setdefault(meta["ID"], meta)

    syntes_map = pick_syntes_sources(katalog)
    id_to_slug: dict[str, str] = {}
    for row in katalog:
        for _, href in row["syntes_links"]:
            slug = slug_from_syntes(Path(href).name)
            if slug in syntes_map:
                id_to_slug[row["id"]] = slug
                break
        if row["id"] not in id_to_slug and row["tema_path"]:
            slug = slug_from_syntes(Path(row["tema_path"]).name)
            if slug in syntes_map:
                id_to_slug[row["id"]] = slug

    # --- Synthesis pages ---
    for slug, src in sorted(syntes_map.items()):
        cid = slug_to_katalog_id(katalog, slug)
        meta = by_id.get(cid or "", {})
        if not meta and cid:
            # try folder from katalog
            for row in katalog:
                if row["id"] == cid and row.get("orig_folder"):
                    meta = by_folder.get(row["orig_folder"], {})
                    break
        raw = src.read_text(encoding="utf-8")
        raw = rewrite_md_links(raw, page_depth=1)
        body_html = md_to_html(raw)
        # strip duplicate h1 if present — keep page title
        title_m = re.search(r"^#\s+(.+)$", src.read_text(encoding="utf-8"), re.M)
        page_title = title_m.group(1).strip() if title_m else slug
        box = source_box(meta, cid)
        body = (
            crumbs([("Start", "index.html"), ("Synteser", None), (cid or slug, None)], 1)
            + f'<h1 class="page-title">{esc(page_title)}</h1>'
            + box
            + f'<article class="prose">{body_html}</article>'
        )
        (OUT / "synteser" / f"{slug}.html").write_text(
            page_shell(page_title, body, depth=1, current="katalog"),
            encoding="utf-8",
        )

    # --- Theme pages ---
    themes_dir = KB / "03-teman"
    theme_slugs = sorted(
        d.name for d in themes_dir.iterdir() if d.is_dir()
    ) if themes_dir.is_dir() else []

    for theme in theme_slugs:
        tdir = themes_dir / theme
        label = THEME_LABELS.get(theme, theme)
        readme = tdir / "README.md"
        intro = ""
        if readme.is_file():
            intro = md_to_html(rewrite_md_links(readme.read_text(encoding="utf-8"), 1))
        files = sorted(tdir.glob("SYNTES-*.md"))
        items = []
        for f in files:
            slug = slug_from_syntes(f.name)
            cid = slug_to_katalog_id(katalog, slug)
            title_m = re.search(r"^#\s+(.+)$", f.read_text(encoding="utf-8"), re.M)
            t = title_m.group(1).strip() if title_m else slug
            badge = f'<span class="id">{esc(cid)}</span>' if cid else ""
            items.append(
                f'<li><a href="../synteser/{esc(slug)}.html">{badge}{esc(t)}</a></li>'
            )
        list_html = (
            f'<ul class="list-links">{"".join(items)}</ul>'
            if items
            else '<p class="empty">Inga synteser ännu.</p>'
        )
        body = (
            crumbs([("Start", "index.html"), ("Teman", "teman/index.html"), (label, None)], 1)
            + f'<h1 class="page-title">{esc(label)}</h1>'
            + f'<p class="meta-bar">{len(files)} synteser i temat</p>'
            + (f'<article class="prose">{intro}</article>' if intro else "")
            + '<section class="section"><h2>Synteser</h2>'
            + list_html
            + "</section>"
        )
        (OUT / "teman" / f"{theme}.html").write_text(
            page_shell(label, body, depth=1, current="teman"),
            encoding="utf-8",
        )

    # Themes index
    tiles = []
    for theme in theme_slugs:
        label = THEME_LABELS.get(theme, theme)
        n = len(list((themes_dir / theme).glob("SYNTES-*.md")))
        tiles.append(
            f'<a class="tile" href="{esc(theme)}.html"><strong>{esc(label)}</strong>'
            f"<span>{n} synteser</span></a>"
        )
    body = (
        crumbs([("Start", "../index.html"), ("Teman", None)], 1)
        + '<h1 class="page-title">Teman</h1>'
        + '<p class="meta-bar">Tvärgående teman i kunskapsbanken.</p>'
        + f'<div class="grid-3">{"".join(tiles)}</div>'
    )
    # fix crumb depth - crumbs uses prefix ../ * depth, and we passed ../index which is wrong
    body = (
        crumbs([("Start", "index.html"), ("Teman", None)], 1)
        + '<h1 class="page-title">Teman</h1>'
        + '<p class="meta-bar">Tvärgående teman i kunskapsbanken.</p>'
        + f'<div class="grid-3">{"".join(tiles)}</div>'
    )
    (OUT / "teman" / "index.html").write_text(
        page_shell("Teman", body, depth=1, current="teman"),
        encoding="utf-8",
    )

    # --- Age pages ---
    ages_dir = KB / "02-synteser"
    age_slugs = [a for a in AGE_ORDER if (ages_dir / a).is_dir()]
    for extra in sorted(d.name for d in ages_dir.iterdir() if d.is_dir()) if ages_dir.is_dir() else []:
        if extra not in age_slugs:
            age_slugs.append(extra)

    for age in age_slugs:
        adir = ages_dir / age
        label = AGE_LABELS.get(age, age)
        files = sorted(adir.glob("SYNTES-*.md"))
        items = []
        for f in files:
            slug = slug_from_syntes(f.name)
            cid = slug_to_katalog_id(katalog, slug)
            title_m = re.search(r"^#\s+(.+)$", f.read_text(encoding="utf-8"), re.M)
            t = title_m.group(1).strip() if title_m else slug
            badge = f'<span class="id">{esc(cid)}</span>' if cid else ""
            items.append(
                f'<li><a href="../synteser/{esc(slug)}.html">{badge}{esc(t)}</a></li>'
            )
        list_html = (
            f'<ul class="list-links">{"".join(items)}</ul>'
            if items
            else '<p class="empty">Inga synteser ännu.</p>'
        )
        body = (
            crumbs([("Start", "index.html"), ("Ålder", "alder/index.html"), (label, None)], 1)
            + f'<h1 class="page-title">{esc(label)}</h1>'
            + f'<p class="meta-bar">{len(files)} synteser för åldersgruppen</p>'
            + '<section class="section"><h2>Synteser</h2>'
            + list_html
            + "</section>"
        )
        (OUT / "alder" / f"{age}.html").write_text(
            page_shell(label, body, depth=1, current="alder"),
            encoding="utf-8",
        )

    tiles = []
    for age in age_slugs:
        label = AGE_LABELS.get(age, age)
        n = len(list((ages_dir / age).glob("SYNTES-*.md")))
        tiles.append(
            f'<a class="tile" href="{esc(age)}.html"><strong>{esc(label)}</strong>'
            f"<span>{n} synteser</span></a>"
        )
    body = (
        crumbs([("Start", "index.html"), ("Ålder", None)], 1)
        + '<h1 class="page-title">Åldersgrupper</h1>'
        + '<p class="meta-bar">Synteser sorterade efter ålder och mognad.</p>'
        + f'<div class="grid-3">{"".join(tiles)}</div>'
    )
    (OUT / "alder" / "index.html").write_text(
        page_shell("Åldersgrupper", body, depth=1, current="alder"),
        encoding="utf-8",
    )

    # --- Katalog ---
    all_themes = sorted({t for row in katalog for t in row["themes"]})
    options = ['<option value="">Alla teman</option>'] + [
        f'<option value="{esc(t)}">{esc(THEME_LABELS.get(t, t))}</option>' for t in all_themes
    ]
    trs = []
    for row in katalog:
        slug = id_to_slug.get(row["id"])
        if slug:
            syn_link = f'<a href="synteser/{esc(slug)}.html">Läs syntes</a>'
        else:
            syn_link = "<span class=\"empty\">—</span>"
        theme_chips = "".join(
            f'<a class="chip" href="teman/{esc(t)}.html">{esc(THEME_LABELS.get(t, t))}</a>'
            for t in row["themes"]
            if t in THEME_LABELS or (themes_dir / t).is_dir()
        )
        search = " ".join(
            [row["id"], row["title"], row["year"], row["age"], " ".join(row["themes"])]
        )
        trs.append(
            "<tr data-katalog-row "
            f'data-search="{esc(search)}" '
            f'data-teman="{esc("|".join(row["themes"]))}">'
            f'<td data-label="ID"><span class="id-badge">{esc(row["id"])}</span></td>'
            f'<td data-label="Titel"><strong>{esc(row["title"])}</strong></td>'
            f'<td data-label="År">{esc(row["year"])}</td>'
            f'<td data-label="Teman">{theme_chips or esc(", ".join(row["themes"]))}</td>'
            f'<td data-label="Syntes">{syn_link}</td>'
            "</tr>"
        )
    body = (
        crumbs([("Start", "index.html"), ("Katalog", None)], 0)
        + '<h1 class="page-title">Katalog</h1>'
        + f'<p class="meta-bar">{len(katalog)} källor från KATALOG.md</p>'
        + '<div class="filters">'
        + '<input id="filter-q" type="search" placeholder="Filtrera ID, titel, år…" aria-label="Filtrera katalog">'
        + f'<select id="filter-tema" aria-label="Filtrera tema">{"".join(options)}</select>'
        + '<span id="filter-count" class="meta-bar"></span>'
        + "</div>"
        + '<div style="overflow-x:auto">'
        + '<table class="katalog-table">'
        + "<thead><tr><th>ID</th><th>Titel</th><th>År</th><th>Teman</th><th>Syntes</th></tr></thead>"
        + f'<tbody>{"".join(trs)}</tbody></table></div>'
        + '<script src="assets/filter.js" defer></script>'
    )
    (OUT / "katalog.html").write_text(
        page_shell("Katalog", body, depth=0, current="katalog"),
        encoding="utf-8",
    )

    # --- Riktning ---
    utkast = (KB / "04-riktning" / "UTKAST.md").read_text(encoding="utf-8")
    utkast = rewrite_md_links(utkast, 0)
    body = (
        crumbs([("Start", "index.html"), ("Riktning", None)], 0)
        + '<h1 class="page-title">Riktning</h1>'
        + '<p class="meta-bar">Utkast utifrån evidensen i kunskapsbanken.</p>'
        + f'<article class="prose">{md_to_html(utkast)}</article>'
    )
    (OUT / "riktning.html").write_text(
        page_shell("Riktning", body, depth=0, current="riktning"),
        encoding="utf-8",
    )

    # --- Index ---
    theme_tiles = "".join(
        f'<a class="tile" href="teman/{esc(t)}.html"><strong>{esc(THEME_LABELS.get(t, t))}</strong>'
        f"<span>{len(list((themes_dir / t).glob('SYNTES-*.md')))} synteser</span></a>"
        for t in theme_slugs
    )
    age_tiles = "".join(
        f'<a class="tile" href="alder/{esc(a)}.html"><strong>{esc(AGE_LABELS.get(a, a))}</strong>'
        f"<span>{len(list((ages_dir / a).glob('SYNTES-*.md')))} synteser</span></a>"
        for a in age_slugs
    )
    body = f"""
<section class="hero">
  <h1>Evidens kring lärande, skärmar och AI</h1>
  <p class="lede">Kuraterad kunskapsbank för svensk skola. Två ledfrågor styr urval, syntes och riktning.</p>
  <div class="lead-grid">
    <a class="card lead-card" href="riktning.html">
      <span class="lead-num">1</span>
      <h2>Vad är optimalt lärande?</h2>
      <p>Kognition, ålder/mognad och pedagogik — oberoende av medium. Bestående kunskap, uppmärksamhet och metakognition.</p>
      <span class="more">Se riktning →</span>
    </a>
    <a class="card lead-card" href="riktning.html">
      <span class="lead-num">2</span>
      <h2>Hur när AI och skärmar är överallt?</h2>
      <p>Hur gör vi optimalt lärande i en verklighet där AI och skärmar redan finns i svensk skola?</p>
      <span class="more">Se riktning →</span>
    </a>
  </div>
</section>
<section class="section">
  <h2>Utforska</h2>
  <div class="grid-3">
    <a class="tile" href="katalog.html"><strong>Katalog</strong><span>{len(katalog)} källor med ID, år och teman</span></a>
    <a class="tile" href="teman/index.html"><strong>Teman</strong><span>{len(theme_slugs)} tvärgående teman</span></a>
    <a class="tile" href="alder/index.html"><strong>Åldersgrupper</strong><span>{len(age_slugs)} nivåer från tidig barndom till vuxen</span></a>
  </div>
</section>
<section class="section">
  <h2>Teman</h2>
  <div class="grid-3">{theme_tiles}</div>
</section>
<section class="section">
  <h2>Ålder</h2>
  <div class="grid-3">{age_tiles}</div>
</section>
"""
    (OUT / "index.html").write_text(
        page_shell(
            "Start",
            body,
            depth=0,
            current="start",
            description="Vad är optimalt lärande — och hur gör vi det när AI och skärmar är överallt?",
        ),
        encoding="utf-8",
    )

    html_pages = list(OUT.rglob("*.html"))
    ids_ok = all(row["id"] for row in katalog)
    print(f"Byggde {len(html_pages)} HTML-sidor i {OUT}")
    print(f"Katalogposter: {len(katalog)} (IDs: {', '.join(r['id'] for r in katalog)})")
    print(f"Unika synteser: {len(syntes_map)}")
    if not ids_ok:
        raise SystemExit("Katalog saknar ID")


if __name__ == "__main__":
    build()
