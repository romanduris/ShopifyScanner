"use strict";
(() => {
  const table = document.querySelector("#market-table-body");
  if (!table) return;
  const form = document.querySelector("#market-filters");
  const rows = Array.from(table.querySelectorAll(".market-record"));
  const search = document.querySelector("#market-search");
  const category = document.querySelector("#market-category");
  const verdict = document.querySelector("#market-verdict");
  const sort = document.querySelector("#market-sort");
  const direction = document.querySelector("#sort-direction");
  const thresholds = Array.from(document.querySelectorAll("[data-filter]"));
  const textColumns = new Set(["name", "category", "native", "pricing", "confidence", "verdict"]);
  let sortKey = sort.value;
  const params = new URLSearchParams(location.search);
  for (const input of [search, category, verdict, sort, direction]) {
    if (params.has(input.id)) input.value = params.get(input.id);
  }
  if (!sort.value) sort.value = "overall";
  if (!direction.value) direction.value = "desc";
  sortKey = sort.value;
  for (const input of thresholds) {
    const value = params.get(input.dataset.filter);
    if (value !== null && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= Number(input.max)) input.value = value;
  }
  if (thresholds.some(input => input.value !== "")) document.querySelector(".advanced-filters").open = true;
  function numeric(value) { return value === undefined || value === "" ? null : Number(value); }
  function apply() {
    const query = search.value.trim().toLocaleLowerCase();
    const ascending = direction.value === "asc";
    rows.sort((a, b) => {
      if (sortKey === "overall" && !ascending && (a.dataset.verdict === "reject") !== (b.dataset.verdict === "reject")) return a.dataset.verdict === "reject" ? 1 : -1;
      const x = a.dataset[sortKey], y = b.dataset[sortKey];
      // Unknowns always sort last, in either direction.
      if (!textColumns.has(sortKey)) {
        const nx = numeric(x), ny = numeric(y);
        if (nx === null && ny !== null) return 1;
        if (ny === null && nx !== null) return -1;
        if (nx !== null && ny !== null && nx !== ny) return (nx - ny) * (ascending ? 1 : -1);
      } else {
        const difference = (x || "").localeCompare(y || "");
        if (difference) return difference * (ascending ? 1 : -1);
      }
      return Number(a.dataset.rank) - Number(b.dataset.rank);
    });
    let count = 0;
    const fragment = document.createDocumentFragment();
    for (const row of rows) {
      const matches = row.dataset.search.includes(query)
        && (!category.value || row.dataset.category === category.value)
        && (!verdict.value || row.dataset.verdict === verdict.value)
        && thresholds.every(input => {
          if (input.value === "") return true;
          const value = numeric(row.dataset[input.dataset.filter]);
          return value !== null && (input.dataset.op === "min" ? value >= Number(input.value) : value <= Number(input.value));
        });
      row.hidden = !matches;
      count += Number(matches);
      fragment.append(row);
    }
    table.append(fragment);
    document.querySelector("#market-result-count").textContent = `Showing ${count} of ${rows.length} marketplaces`;
    document.querySelector("#no-market-results").hidden = count !== 0;
    for (const button of document.querySelectorAll("[data-sort]")) {
      const th = button.closest("th");
      if (button.dataset.sort === sortKey) th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    }
    const next = new URLSearchParams();
    for (const input of [search, category, verdict, sort, direction]) if (input.value) next.set(input.id, input.value);
    for (const input of thresholds) if (input.value !== "") next.set(input.dataset.filter, input.value);
    try { history.replaceState(null, "", `${location.pathname}?${next}${location.hash}`); } catch (_) { /* Local file access does not require History API support. */ }
  }
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("input", event => {
    if (event.target === sort) sortKey = sort.value;
    apply();
  });
  form.addEventListener("change", event => {
    if (event.target === sort) sortKey = sort.value;
    apply();
  });
  form.addEventListener("reset", () => { setTimeout(() => { sortKey = "overall"; apply(); }, 0); });
  document.querySelector("#asymmetric-preset").addEventListener("click", () => {
    for (const input of thresholds) input.value = ({codex: 8, saturation: 5, entry: 7})[input.dataset.filter] ?? "";
    apply();
  });
  for (const button of document.querySelectorAll("[data-sort]")) button.addEventListener("click", () => {
    const key = button.dataset.sort;
    direction.value = sortKey === key && direction.value === "desc" ? "asc" : "desc";
    sortKey = key;
    if (!Array.from(sort.options).some(option => option.value === key)) sort.add(new Option(button.textContent, key));
    sort.value = key;
    apply();
  });
  apply();
})();
