#!/usr/bin/env python3
"""Bygg statisk sajt från /home/box/kunskapsbank/ till docs/ (GitHub Pages).

Epistemiskt kontrakt: N=96 från KATALOG; Tier obligatorisk; ingen tema-räkningsinflation
på startsidan; ram = Människans lärande i en tid av digitala intelligenser.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

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

FRAME = "Människans lärande i en tid av digitala intelligenser"
CURATOR = "Chiron (kurator) + Jonatan Skäryd (redaktör)"
CONTACT_MAIL = "jonatan.skaryd@gmail.com"
LICENSE = "CC BY 4.0"

THEME_LABELS = {
    "ai-och-larande": "AI och lärande",
    "analogt-vs-digitalt": "Analogt vs digitalt",
    "feedback-bedomning": "Feedback och bedömning",
    "lasning-och-skrivande": "Läsning och skrivande",
    "optimalt-larande-grunder": "Grunder",
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

SYNTH_SECTION_ALIASES = {
    "metadata": ("Metadata", "metadata"),
    "finding": ("Finding", "Fynd", "finding", "fynd"),
    "mechanism": ("Mechanism", "Mekanism", "mechanism", "mekanism"),
    "limits": ("Limits", "Begränsningar", "limits", "begränsningar"),
    "dies": (
        "This claim dies if …",
        "This claim dies if...",
        "This claim dies if",
        "Claim dies if",
    ),
    "sweden": (
        "Swedish implication",
        "Implikation",
        "Implikation: *Höjer det lärandet?*",
        "Relevans för svensk skola / *Höjer det lärandet?*",
    ),
    "links": ("Links", "Länkar", "links"),
}


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=MD_EXT)


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def slug_from_syntes(name: str) -> str:
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


def load_all_metadata() -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_folder: dict[str, dict] = {}
    base = KB / "01-originaldokument"
    if not base.is_dir():
        return by_id, by_folder
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        meta = parse_metadata(folder / "METADATA.md")
        meta["_folder"] = folder.name
        by_folder[folder.name] = meta
        cid = meta.get("ID")
        if cid:
            by_id[cid] = meta
    return by_id, by_folder


def extract_links(field: str) -> list[tuple[str, str]]:
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
        tema_path = None
        age_paths: list[str] = []
        for _label, href in syntes_links:
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
    p = (KB / "00-index" / rel_from_katalog).resolve()
    try:
        p.relative_to(KB.resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


def pick_syntes_sources(katalog: list[dict]) -> dict[str, Path]:
    chosen: dict[str, Path] = {}
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
    themes_dir = KB / "03-teman"
    if themes_dir.is_dir():
        for p in themes_dir.glob("*/SYNTES-*.md"):
            chosen.setdefault(slug_from_syntes(p.name), p)
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
    prefix = "../" * page_depth

    def repl(m: re.Match) -> str:
        label, href = m.group(1), m.group(2)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        name = Path(href.split("#")[0]).name
        if name.startswith("SYNTES-") and name.endswith(".md"):
            return f"[{label}]({prefix}synteser/{slug_from_syntes(name)}.html)"
        mapping = {
            "UTKAST.md": "riktning.html",
            "PRAKTIK.md": "praktik.html",
            "MOTARGUMENT.md": "motargument.html",
            "METOD.md": "metod.html",
            "KATALOG.md": "katalog.html",
            "ANDRINGSSLOGG.md": "changelog.html",
        }
        if name in mapping:
            return f"[{label}]({prefix}{mapping[name]})"
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
        ("riktning.html", "Riktning", "riktning"),
        ("praktik.html", "Praktik", "praktik"),
        ("metod.html", "Metod", "metod"),
        ("motargument.html", "Motargument", "motargument"),
        ("katalog.html", "Katalog", "katalog"),
        ("sok.html", "Sök", "sok"),
    ]
    nav_html = []
    for href, label, key in nav:
        cur = ' aria-current="page"' if current == key else ""
        nav_html.append(f'<a href="{prefix}{href}"{cur}>{esc(label)}</a>')
    desc = description or f"{FRAME}. Evidens för svensk skola."
    footer_links = [
        (f"{prefix}metod.html", "Metod"),
        (f"{prefix}changelog.html", "Ändringslogg"),
        (f"{prefix}metod.html#citera", "Citera"),
        (f"{prefix}metod.html#licens", "Licens"),
        (f"mailto:{CONTACT_MAIL}", "Kontakt"),
    ]
    fl = " ".join(
        f'<a href="{esc(h)}">{esc(lab)}</a>' for h, lab in footer_links
    )
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
    <nav class="nav-primary">{" ".join(nav_html)}</nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-links">{fl}</div>
    <p>{esc(CURATOR)} · {esc(LICENSE)} · <a href="mailto:{esc(CONTACT_MAIL)}">{esc(CONTACT_MAIL)}</a></p>
    <p>Statisk sajt. Primär-PDF:er kopieras inte — se DOI/URL i respektive syntes. Unikt N från katalog.</p>
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


def tier_pill(tier: str) -> str:
    if not tier:
        return ""
    cls = "tier-" + re.sub(r"[^A-Za-z0-9]+", "-", tier)
    return f'<span class="tier-pill {esc(cls)}">{esc(tier)}</span>'


def source_box(meta: dict, cid: str | None) -> str:
    if not meta and not cid:
        return ""
    rows = []
    if cid:
        rows.append(f'<dt>ID</dt><dd><span class="id-badge">{esc(cid)}</span></dd>')
    tier = meta.get("Tier", "")
    if tier:
        rows.append(f"<dt>Tier</dt><dd>{tier_pill(tier)}</dd>")
    for key, label in [
        ("Titel", "Titel"),
        ("Författare", "Författare"),
        ("År", "År"),
        ("Typ", "Typ"),
        ("Closed-book follow-up", "Closed-book"),
        ("HE vs K–12", "HE vs K–12"),
        ("Källa/DOI", "Källa/DOI"),
        ("URL", "URL"),
        ("URL (författar-PDF)", "URL"),
        ("URL (SSRN)", "URL"),
    ]:
        val = meta.get(key)
        if not val:
            continue
        if key.startswith("URL") or "doi.org" in val.lower() or val.startswith("http"):
            urls = re.findall(r"https?://[^\s;]+", val)
            if urls:
                links = " · ".join(
                    f'<a href="{esc(u)}" rel="noopener noreferrer">{esc(u)}</a>' for u in urls
                )
                rows.append(f"<dt>{esc(label)}</dt><dd>{links}</dd>")
            else:
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


def split_md_sections(raw: str) -> tuple[str, dict[str, str], str]:
    """Return (title, sections_by_canonical_key, leftover_md)."""
    title = ""
    m = re.search(r"^#\s+(.+)$", raw, re.M)
    if m:
        title = m.group(1).strip()
    parts = re.split(r"(?m)^(##\s+.+)$", raw)
    preamble = parts[0] if parts else raw
    sections: dict[str, str] = {}
    leftover_chunks = [preamble]
    i = 1
    while i < len(parts) - 1:
        header = parts[i].strip()
        body = parts[i + 1]
        htext = re.sub(r"^##\s+", "", header).strip()
        matched = None
        for key, aliases in SYNTH_SECTION_ALIASES.items():
            for a in aliases:
                if htext.lower().startswith(a.lower().rstrip("…").rstrip(".")):
                    matched = key
                    break
            if matched:
                break
        if matched:
            sections[matched] = body.strip()
        else:
            leftover_chunks.append(header + "\n" + body)
        i += 2
    leftover = "\n".join(leftover_chunks).strip()
    # Drop leading H1 from leftover to avoid duplicate
    leftover = re.sub(r"^#\s+.+\n?", "", leftover, count=1).strip()
    return title, sections, leftover


def first_bullet_block(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith(("-", "*")):
            lines.append(line.strip().lstrip("-* ").strip())
        elif lines and not line.strip():
            break
        elif lines and line.strip() and not line.strip().startswith(("#",)):
            # continuation
            lines[-1] = lines[-1] + " " + line.strip()
    return " · ".join(lines[:8]) if lines else text.strip().split("\n\n")[0][:400]


def synthesize_card_html(
    *,
    cid: str | None,
    meta: dict,
    sections: dict[str, str],
    leftover: str,
    related_ids: list[str],
) -> str:
    """Build structured synthesis sections; fill placeholders from meta/leftover."""
    tier = meta.get("Tier", "")
    n = meta.get("N") or meta.get("Stickprov") or ""
    # Try pull N from Typ
    if not n and meta.get("Typ"):
        n = meta.get("Typ", "")
    pop = meta.get("Åldersgrupp") or meta.get("Population") or ""
    country = meta.get("Land") or meta.get("Country") or ""
    subject = meta.get("Ämne") or meta.get("Subject") or meta.get("Titel") or ""
    duration = meta.get("Duration") or meta.get("Varaktighet") or ""

    def sec_html(key: str, heading: str, body_md: str, extra_class: str = "") -> str:
        if not body_md.strip():
            return ""
        return (
            f'<section class="synth-card {extra_class}" id="{esc(key)}">'
            f"<h2>{esc(heading)}</h2>"
            f'<div class="prose">{md_to_html(body_md)}</div></section>'
        )

    # Metadata card
    meta_bits = []
    if cid:
        meta_bits.append(f"- **ID:** `{cid}`")
    if tier:
        meta_bits.append(f"- **Tier:** {tier}")
    if n:
        meta_bits.append(f"- **N / design:** {n}")
    if pop:
        meta_bits.append(f"- **Population:** {pop}")
    if country:
        meta_bits.append(f"- **Country:** {country}")
    if subject:
        meta_bits.append(f"- **Subject:** {subject}")
    if duration:
        meta_bits.append(f"- **Duration:** {duration}")
    # closed-book from synthesis bold lines or meta
    cb = meta.get("Closed-book follow-up", "")
    if not cb:
        m = re.search(r"\*\*Closed-book follow-up:\*\*\s*(.+)", leftover + "\n" + sections.get("finding", ""))
        if m:
            cb = m.group(1).strip()
    if cb:
        meta_bits.append(f"- **Closed-book follow-up:** {cb}")
        if re.match(r"(?i)^nej", cb.strip()):
            meta_bits.append("- **Utfallslabel:** prestation, inte lärande")

    meta_md = sections.get("metadata") or "\n".join(meta_bits) or "_Metadata saknas — fylls vid nästa revison._"
    finding_md = sections.get("finding")
    if not finding_md:
        # placeholder from leftover Fynd-ish paragraphs
        finding_md = (
            first_bullet_block(leftover)
            if leftover
            else "_Finding sammanfattas vid nästa revision från källans abstrakt; inga effektstorlekar inventeras här._"
        )
    mechanism_md = sections.get("mechanism") or (
        "_Mekanism: en mening tilläggs vid revision — undvik author-voice utan konkurrerande mekanism._"
    )
    limits_md = sections.get("limits") or (
        "_Begränsningar dokumenteras i källans METADATA/Typ; svensk klassrumsreplikation kan saknas._"
    )
    dies_md = sections.get("dies") or (
        "_This claim dies if: motstridig closed-book-evidens i relevant population publiceras och överlever peer review._"
    )
    sweden_md = sections.get("sweden") or (
        "_Swedish implication: **measure** closed-book och distraktionsfri tid — verbmening fylls per källa._"
    )
    links_md = sections.get("links")
    if not links_md:
        doi = meta.get("Källa/DOI") or meta.get("URL") or ""
        link_lines = []
        if doi:
            link_lines.append(f"- Källa: {doi}")
        if related_ids:
            link_lines.append("- Relaterade: " + ", ".join(f"`{r}`" for r in related_ids))
        links_md = "\n".join(link_lines) if link_lines else "_Se DOI i metadata-box._"

    flags = ""
    if tier == "position":
        flags += '<span class="flag-warn">Tier = position — inte jämlik med RCT/meta</span>'
    if cb and re.match(r"(?i)^nej", cb.strip()):
        flags += '<span class="flag-warn">prestation, inte lärande</span>'

    cards = [
        flags,
        sec_html("metadata", "Metadata", meta_md),
        sec_html("finding", "Finding", finding_md),
        sec_html("mechanism", "Mechanism", mechanism_md),
        sec_html("limits", "Limits", limits_md),
        sec_html("dies", "This claim dies if …", dies_md, "dies"),
        sec_html("sweden", "Swedish implication", sweden_md, "sweden"),
        sec_html("links", "Links", links_md),
    ]
    # Cap leftover prose roughly — show only if substantial unique content remains
    extra = ""
    if leftover and len(leftover) > 80:
        # Avoid dumping entire duplicate if sections already captured
        trimmed = leftover
        if len(trimmed) > 2400:
            trimmed = trimmed[:2400] + "\n\n… *(kortad i bygget; se källfil)*"
        extra = f'<article class="prose section"><h2>Övrig syntestext</h2>{md_to_html(trimmed)}</article>'

    return '<div class="synth-grid">' + "".join(c for c in cards if c) + "</div>" + extra


def related_ids_for(cid: str | None, katalog: list[dict]) -> list[str]:
    if not cid:
        return []
    row = next((r for r in katalog if r["id"] == cid), None)
    if not row:
        return []
    themes = set(row["themes"])
    related = []
    for r in katalog:
        if r["id"] == cid:
            continue
        if themes & set(r["themes"]):
            related.append(r["id"])
        if len(related) >= 6:
            break
    return related


def render_kb_page(src: Path, *, depth: int, current: str, crumb_label: str, page_title: str | None = None) -> str:
    raw = src.read_text(encoding="utf-8")
    raw = rewrite_md_links(raw, depth)
    title_m = re.search(r"^#\s+(.+)$", raw, re.M)
    title = page_title or (title_m.group(1).strip() if title_m else crumb_label)
    body = (
        crumbs([("Start", "index.html"), (crumb_label, None)], depth)
        + f'<h1 class="page-title">{esc(title)}</h1>'
        + f'<article class="prose">{md_to_html(raw)}</article>'
    )
    # strip duplicate h1 inside article
    body = re.sub(
        r'(<article class="prose">)\s*<h1>[^<]+</h1>',
        r"\1",
        body,
        count=1,
    )
    return page_shell(title, body, depth=depth, current=current)


def build() -> None:
    if not KB.is_dir():
        raise SystemExit(f"Kunskapsbank saknas: {KB}")

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

    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    static = ROOT / "static"
    for name in ("style.css", "filter.js", "search.js"):
        src = static / name
        if not src.is_file():
            raise SystemExit(f"Saknar static/{name}")
        shutil.copy2(src, assets / name)

    katalog_all = parse_katalog(KB / "00-index" / "KATALOG.md")
    by_id, by_folder = load_all_metadata()

    # Rule: no Tier → does not render
    katalog = []
    skipped = []
    for row in katalog_all:
        meta = by_id.get(row["id"]) or (
            by_folder.get(row["orig_folder"], {}) if row.get("orig_folder") else {}
        )
        tier = (meta or {}).get("Tier", "").strip()
        if not tier:
            skipped.append(row["id"])
            continue
        row = dict(row)
        row["tier"] = tier
        row["_meta"] = meta
        katalog.append(row)

    unique_n = len(katalog)
    if unique_n != 96:
        print(f"VARNING: förväntat N=96, fick {unique_n} (katalog_all={len(katalog_all)}, skipped={skipped})")

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

    search_index = []

    # --- Synthesis pages ---
    for slug, src in sorted(syntes_map.items()):
        cid = slug_to_katalog_id(katalog, slug)
        # Skip render if catalog id known but no tier
        if cid and cid in skipped:
            continue
        meta = by_id.get(cid or "", {})
        if not meta and cid:
            for row in katalog:
                if row["id"] == cid:
                    meta = row.get("_meta") or by_folder.get(row.get("orig_folder") or "", {})
                    break
        # If this syntes maps to an id without tier, skip
        if cid and not (meta or {}).get("Tier"):
            # allow orphan syntes without id? only if we can infer — skip safer
            if cid in {r["id"] for r in katalog_all}:
                continue

        raw = src.read_text(encoding="utf-8")
        title, sections, leftover = split_md_sections(raw)
        page_title = title or slug
        related = related_ids_for(cid, katalog)
        for k in list(sections.keys()):
            sections[k] = rewrite_md_links(sections[k], 1)
        card_html = synthesize_card_html(
            cid=cid,
            meta=meta or {},
            sections=sections,
            leftover=rewrite_md_links(leftover, 1),
            related_ids=related,
        )
        box = source_box(meta or {}, cid)
        body = (
            crumbs([("Start", "index.html"), ("Synteser", None), (cid or slug, None)], 1)
            + f'<h1 class="page-title">{esc(page_title)}</h1>'
            + box
            + card_html
        )
        (OUT / "synteser" / f"{slug}.html").write_text(
            page_shell(page_title, body, depth=1, current="katalog"),
            encoding="utf-8",
        )
        # search index
        search_blob = " ".join(
            [
                cid or "",
                page_title,
                (meta or {}).get("Tier", ""),
                (meta or {}).get("Författare", ""),
                sections.get("finding", "")[:500],
                leftover[:500],
            ]
        )
        search_index.append(
            {
                "id": cid or "",
                "title": page_title,
                "tier": (meta or {}).get("Tier", ""),
                "href": f"synteser/{slug}.html",
                "search": search_blob,
            }
        )

    # --- Theme pages (unique IDs, no fake stacked totals as unique N) ---
    themes_dir = KB / "03-teman"
    theme_slugs = (
        sorted(d.name for d in themes_dir.iterdir() if d.is_dir()) if themes_dir.is_dir() else []
    )

    for theme in theme_slugs:
        tdir = themes_dir / theme
        label = THEME_LABELS.get(theme, theme)
        readme = tdir / "README.md"
        intro = ""
        if readme.is_file():
            intro = md_to_html(rewrite_md_links(readme.read_text(encoding="utf-8"), 1))
        # Unique catalog IDs in this theme
        ids_in_theme = [r for r in katalog if theme in r["themes"]]
        items = []
        for row in ids_in_theme:
            slug = id_to_slug.get(row["id"])
            if not slug:
                continue
            t = row["title"]
            badge = f'<span class="id">{esc(row["id"])}</span>'
            items.append(
                f'<li><a href="../synteser/{esc(slug)}.html">{badge}{tier_pill(row["tier"])} {esc(t)}</a></li>'
            )
        list_html = (
            f'<ul class="list-links">{"".join(items)}</ul>'
            if items
            else '<p class="empty">Inga källor med tier i temat.</p>'
        )
        body = (
            crumbs([("Start", "index.html"), ("Teman", "teman/index.html"), (label, None)], 1)
            + f'<h1 class="page-title">{esc(label)}</h1>'
            + f'<p class="meta-bar">{len(ids_in_theme)} unika käll-ID i temat (av totalt {unique_n})</p>'
            + (f'<article class="prose">{intro}</article>' if intro else "")
            + '<section class="section"><h2>Källor</h2>'
            + list_html
            + "</section>"
        )
        (OUT / "teman" / f"{theme}.html").write_text(
            page_shell(label, body, depth=1, current="katalog"),
            encoding="utf-8",
        )

    tiles = []
    for theme in theme_slugs:
        label = THEME_LABELS.get(theme, theme)
        n_unique = sum(1 for r in katalog if theme in r["themes"])
        tiles.append(
            f'<a class="tile" href="{esc(theme)}.html"><strong>{esc(label)}</strong>'
            f"<span>{n_unique} unika ID</span></a>"
        )
    body = (
        crumbs([("Start", "index.html"), ("Teman", None)], 1)
        + '<h1 class="page-title">Teman</h2>'  # typo fix below
    )
    body = (
        crumbs([("Start", "index.html"), ("Teman", None)], 1)
        + '<h1 class="page-title">Teman</h1>'
        + f'<p class="meta-bar">Routing-teman. Unikt N i banken är {unique_n} (räknas en gång på katalog/start).</p>'
        + f'<div class="grid-3">{"".join(tiles)}</div>'
    )
    (OUT / "teman" / "index.html").write_text(
        page_shell("Teman", body, depth=1, current="katalog"),
        encoding="utf-8",
    )

    # --- Age pages ---
    ages_dir = KB / "02-synteser"
    age_slugs = [a for a in AGE_ORDER if (ages_dir / a).is_dir()]
    for extra in (
        sorted(d.name for d in ages_dir.iterdir() if d.is_dir()) if ages_dir.is_dir() else []
    ):
        if extra not in age_slugs:
            age_slugs.append(extra)

    for age in age_slugs:
        adir = ages_dir / age
        label = AGE_LABELS.get(age, age)
        files = sorted(adir.glob("SYNTES-*.md"))
        items = []
        seen = set()
        for f in files:
            slug = slug_from_syntes(f.name)
            cid = slug_to_katalog_id(katalog, slug)
            if cid and cid in skipped:
                continue
            if slug in seen:
                continue
            seen.add(slug)
            title_m = re.search(r"^#\s+(.+)$", f.read_text(encoding="utf-8"), re.M)
            t = title_m.group(1).strip() if title_m else slug
            badge = f'<span class="id">{esc(cid)}</span>' if cid else ""
            tier = ""
            if cid and cid in by_id:
                tier = tier_pill(by_id[cid].get("Tier", ""))
            items.append(
                f'<li><a href="../synteser/{esc(slug)}.html">{badge}{tier}{esc(t)}</a></li>'
            )
        list_html = (
            f'<ul class="list-links">{"".join(items)}</ul>'
            if items
            else '<p class="empty">Inga synteser ännu.</p>'
        )
        body = (
            crumbs([("Start", "index.html"), ("Ålder", "alder/index.html"), (label, None)], 1)
            + f'<h1 class="page-title">{esc(label)}</h1>'
            + f'<p class="meta-bar">Synteser i åldersmappen (routing — unikt N = {unique_n})</p>'
            + '<section class="section"><h2>Synteser</h2>'
            + list_html
            + "</section>"
        )
        (OUT / "alder" / f"{age}.html").write_text(
            page_shell(label, body, depth=1, current="katalog"),
            encoding="utf-8",
        )

    tiles = []
    for age in age_slugs:
        label = AGE_LABELS.get(age, age)
        tiles.append(
            f'<a class="tile" href="{esc(age)}.html"><strong>{esc(label)}</strong>'
            f"<span>åldersrouting</span></a>"
        )
    body = (
        crumbs([("Start", "index.html"), ("Ålder", None)], 1)
        + '<h1 class="page-title">Åldersgrupper</h1>'
        + f'<p class="meta-bar">Routing efter ålder. Unikt N = {unique_n}.</p>'
        + f'<div class="grid-3">{"".join(tiles)}</div>'
    )
    (OUT / "alder" / "index.html").write_text(
        page_shell("Åldersgrupper", body, depth=1, current="katalog"),
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
            syn_link = '<span class="empty">—</span>'
        theme_chips = "".join(
            f'<a class="chip" href="teman/{esc(t)}.html">{esc(THEME_LABELS.get(t, t))}</a>'
            for t in row["themes"]
            if t in THEME_LABELS or (themes_dir / t).is_dir()
        )
        search = " ".join(
            [row["id"], row["title"], row["year"], row["age"], row["tier"], " ".join(row["themes"])]
        )
        trs.append(
            "<tr data-katalog-row "
            f'data-search="{esc(search)}" '
            f'data-teman="{esc("|".join(row["themes"]))}">'
            f'<td data-label="ID"><span class="id-badge">{esc(row["id"])}</span></td>'
            f'<td data-label="Titel"><strong>{esc(row["title"])}</strong> {tier_pill(row["tier"])}</td>'
            f'<td data-label="År">{esc(row["year"])}</td>'
            f'<td data-label="Teman">{theme_chips or esc(", ".join(row["themes"]))}</td>'
            f'<td data-label="Syntes">{syn_link}</td>'
            "</tr>"
        )
    body = (
        crumbs([("Start", "index.html"), ("Katalog", None)], 0)
        + '<h1 class="page-title">Katalog</h1>'
        + f'<p class="meta-bar">Unikt N = <strong>{unique_n}</strong> källor (från KATALOG.md, med Tier).</p>'
        + '<div class="filters">'
        + '<input id="filter-q" type="search" placeholder="Filtrera ID, titel, år, tier…" aria-label="Filtrera katalog">'
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

    # --- Stance / method pages ---
    (OUT / "riktning.html").write_text(
        render_kb_page(
            KB / "04-riktning" / "UTKAST.md",
            depth=0,
            current="riktning",
            crumb_label="Riktning",
        ),
        encoding="utf-8",
    )
    (OUT / "praktik.html").write_text(
        render_kb_page(
            KB / "04-riktning" / "PRAKTIK.md",
            depth=0,
            current="praktik",
            crumb_label="Praktik",
        ),
        encoding="utf-8",
    )
    (OUT / "motargument.html").write_text(
        render_kb_page(
            KB / "04-riktning" / "MOTARGUMENT.md",
            depth=0,
            current="motargument",
            crumb_label="Motargument",
        ),
        encoding="utf-8",
    )
    # Metod with cite/license anchors
    metod_raw = (KB / "00-index" / "METOD.md").read_text(encoding="utf-8")
    metod_raw = rewrite_md_links(metod_raw, 0)
    metod_html = md_to_html(metod_raw)
    metod_html = metod_html.replace("<h2>Citera denna bank</h2>", '<h2 id="citera">Citera denna bank</h2>')
    metod_html = metod_html.replace("<h2>Licens</h2>", '<h2 id="licens">Licens</h2>')
    metod_html = re.sub(r"<h1>[^<]+</h1>", "", metod_html, count=1)
    body = (
        crumbs([("Start", "index.html"), ("Metod", None)], 0)
        + '<h1 class="page-title">Metod</h1>'
        + f'<article class="prose">{metod_html}</article>'
    )
    (OUT / "metod.html").write_text(
        page_shell("Metod", body, depth=0, current="metod"),
        encoding="utf-8",
    )

    # Changelog
    clog = KB / "00-index" / "ANDRINGSSLOGG.md"
    if clog.is_file():
        (OUT / "changelog.html").write_text(
            render_kb_page(clog, depth=0, current="metod", crumb_label="Ändringslogg", page_title="Ändringslogg"),
            encoding="utf-8",
        )

    # Search page + index
    (OUT / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, indent=0),
        encoding="utf-8",
    )
    body = (
        crumbs([("Start", "index.html"), ("Sök", None)], 0)
        + '<h1 class="page-title">Sök</h1>'
        + '<p class="meta-bar">Fulltextsök i synteser (klientindex).</p>'
        + '<div class="filters">'
        + '<input id="site-search-q" type="search" data-index="search-index.json" '
        + 'placeholder="Laddar index…" disabled aria-label="Sök synteser" style="min-width:min(100%,28rem)">'
        + "</div>"
        + '<div id="site-search-results" class="section"></div>'
        + '<script src="assets/search.js" defer></script>'
    )
    (OUT / "sok.html").write_text(
        page_shell("Sök", body, depth=0, current="sok"),
        encoding="utf-8",
    )

    # --- Homepage: frame + conclusion; riktning/praktik first; library second; N once; no theme count inflation ---
    theme_tiles = "".join(
        f'<a class="tile" href="teman/{esc(t)}.html"><strong>{esc(THEME_LABELS.get(t, t))}</strong>'
        f"<span>öppna tema</span></a>"
        for t in theme_slugs
    )
    conclusion = (
        "Optimalt lärande är bestående kunskap, uppmärksamhet och metakognition — mätt utan genvägar. "
        "Skolan som skyddad kognitiv zon är en hypotes att mäta (distraktionsfri tid, closed-book), "
        "inte metafysik om papper; förbud är nödvändiga men otillräckliga."
    )
    body = f"""
<section class="hero">
  <h1>{esc(FRAME)}</h1>
  <p class="lede">Kunskapsbank för svensk skola. Under ramen ligger två lastbärande frågor — allt annat är routing.</p>
  <p class="conclusion">{esc(conclusion)}</p>
  <div class="hero-actions">
    <a class="primary" href="riktning.html">Riktning</a>
    <a class="primary" href="praktik.html">Praktik</a>
    <a href="metod.html">Metod</a>
    <a href="motargument.html">Motargument</a>
  </div>
  <div class="lead-grid">
    <a class="card lead-card" href="riktning.html">
      <span class="lead-num">1</span>
      <h2>Vad är optimalt lärande?</h2>
      <p>Mediumoberoende: bestående kunskap, uppmärksamhet, metakognition — closed-book.</p>
      <span class="more">Se riktning →</span>
    </a>
    <a class="card lead-card" href="praktik.html">
      <span class="lead-num">2</span>
      <h2>Hur när AI och skärmar är överallt?</h2>
      <p>Stop / start / measure per stadium. Designad digital ≠ genväg; papper ≠ pedagogik.</p>
      <span class="more">Se praktik →</span>
    </a>
  </div>
</section>
<section class="section">
  <h2>Bibliotek</h2>
  <p class="library-note">Unikt N = <strong>{unique_n}</strong> källor (från KATALOG.md). Teman nedan är routing — räknas inte upp som separata totaler.</p>
  <div class="grid-3">
    <a class="tile" href="katalog.html"><strong>Katalog</strong><span>ID, tier, år och synteslänkar</span></a>
    <a class="tile" href="sok.html"><strong>Sök</strong><span>Fulltext i synteser</span></a>
    <a class="tile" href="teman/index.html"><strong>Teman</strong><span>Routing, inte parallella banker</span></a>
  </div>
</section>
<section class="section">
  <h2>Teman</h2>
  <div class="grid-3">{theme_tiles}</div>
</section>
"""
    (OUT / "index.html").write_text(
        page_shell(
            "Start",
            body,
            depth=0,
            current="start",
            description=f"{FRAME}. Vad är optimalt lärande — och hur när AI och skärmar är överallt?",
        ),
        encoding="utf-8",
    )

    html_pages = list(OUT.rglob("*.html"))
    must = ["metod.html", "motargument.html", "praktik.html", "riktning.html", "index.html"]
    for m in must:
        if not (OUT / m).is_file():
            raise SystemExit(f"Saknar {m}")
    print(f"Byggde {len(html_pages)} HTML-sidor i {OUT}")
    print(f"Unikt N={unique_n}; skipped_no_tier={skipped}")
    print(f"Synteser i index: {len(search_index)}")


if __name__ == "__main__":
    build()
