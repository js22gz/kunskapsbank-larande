(function () {
  const q = document.getElementById("filter-q");
  const tema = document.getElementById("filter-tema");
  const rows = Array.from(document.querySelectorAll("[data-katalog-row]"));
  const count = document.getElementById("filter-count");
  if (!q || !rows.length) return;

  function apply() {
    const needle = (q.value || "").trim().toLowerCase();
    const temaVal = (tema && tema.value) || "";
    let shown = 0;
    for (const row of rows) {
      const hay = (row.getAttribute("data-search") || "").toLowerCase();
      const temas = row.getAttribute("data-teman") || "";
      const okQ = !needle || hay.includes(needle);
      const okT = !temaVal || temas.split("|").includes(temaVal);
      const show = okQ && okT;
      row.classList.toggle("is-hidden", !show);
      if (show) shown += 1;
    }
    if (count) count.textContent = shown + " av " + rows.length + " källor";
  }

  q.addEventListener("input", apply);
  if (tema) tema.addEventListener("change", apply);
  apply();
})();
