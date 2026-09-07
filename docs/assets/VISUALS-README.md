# Visuella tillgångar

Professionella figurer för kunskapsbankens startsida och evidenssidor.
Genererade från KATALOG.md + METADATA.md (N=96) och PRAKTIK.md.

| Fil | Syfte |
|-----|--------|
| `ramkarta.svg` / `ramkarta.png` | Ram → ledfrågor → routing (Riktning, Praktik, Motargument, Metod, Katalog). Markerar att banken är en falsifierbar brief, inte ett bibliotek. |
| `evidenslandskap.svg` / `evidenslandskap.png` | Unikt N=96 fördelat på primärtema × evidenstier. ★ = load-bearing. Position ritas ljusare/lägre. |
| `praktikfigur.svg` / `praktikfigur.png` | Stop / Start / Measure × F–3 · Åk 4–6 · Åk 7–9 · Gymnasium. |

## Föreslagna embeds (startsidan)

```html
<section class="section" id="visuellt">
  <h2>Visuellt</h2>
  <figure class="card">
    <img src="assets/ramkarta.svg" alt="Ramkarta — falsifierbar brief" width="1600" loading="lazy">
    <figcaption>Ram → ledfrågor → destinationer. Teman är endast routing.</figcaption>
  </figure>
  <figure class="card">
    <img src="assets/evidenslandskap.svg" alt="Evidenslandskap unikt N=96" width="1600" loading="lazy">
    <figcaption>Primärtema × tier. ★ load-bearing (Bastani, Delgado, IFAU, ITS, Abrahamsson).</figcaption>
  </figure>
  <figure class="card">
    <img src="assets/praktikfigur.svg" alt="Praktik Stop Start Measure" width="1600" loading="lazy">
    <figcaption>Mät distraktionsfri tid och closed-book, inte policyetikett.</figcaption>
  </figure>
</section>
```

PNG-varianter finns för social/print; SVG är primär för webben.
