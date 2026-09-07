(function () {
  const input = document.getElementById("site-search-q");
  const out = document.getElementById("site-search-results");
  if (!input || !out) return;
  const idxUrl = input.getAttribute("data-index") || "search-index.json";
  let index = [];
  fetch(idxUrl)
    .then((r) => r.json())
    .then((data) => {
      index = data;
      input.disabled = false;
      input.placeholder = "Sök i synteser…";
    })
    .catch(() => {
      out.innerHTML = "<p class='empty'>Kunde inte ladda sökindex.</p>";
    });

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function search() {
    const q = (input.value || "").trim().toLowerCase();
    if (q.length < 2) {
      out.innerHTML = "<p class='empty'>Skriv minst två tecken.</p>";
      return;
    }
    const terms = q.split(/\s+/).filter(Boolean);
    const hits = [];
    for (const item of index) {
      const hay = (item.search || "").toLowerCase();
      if (terms.every((t) => hay.includes(t))) hits.push(item);
      if (hits.length >= 50) break;
    }
    if (!hits.length) {
      out.innerHTML = "<p class='empty'>Inga träffar.</p>";
      return;
    }
    out.innerHTML =
      '<ul class="list-links">' +
      hits
        .map((h) => {
          const badge = h.id
            ? '<span class="id">' + esc(h.id) + "</span>"
            : "";
          const tier = h.tier
            ? '<span class="tier-pill tier-' +
              esc(String(h.tier).replace(/\//g, "-")) +
              '">' +
              esc(h.tier) +
              "</span>"
            : "";
          return (
            "<li><a href=\"" +
            esc(h.href) +
            '">' +
            badge +
            esc(h.title) +
            "</a> " +
            tier +
            "</li>"
          );
        })
        .join("") +
      "</ul>";
  }

  input.addEventListener("input", search);
})();
