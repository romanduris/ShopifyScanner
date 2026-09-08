"use strict";

// Keep the generated table usable without a backend or a fetch request.
const records = Array.from(document.querySelectorAll(".app-record"));
const table = document.querySelector("#analysis-table");
const search = document.querySelector("#app-search");
const sort = document.querySelector("#app-sort");
const complexity = document.querySelector("#complexity-filter");
const minimum = document.querySelector("#min-reviews");
const paid = document.querySelector("#paid-only");
const categoryButtons = Array.from(document.querySelectorAll(".category-filter"));
let category = "all";
let peerGroup = null;

function applyFilters() {
  const query = search.value.trim().toLocaleLowerCase();
  const threshold = Math.max(0, Number(minimum.value) || 0);
  const order = sort.value;
  records.sort((a, b) => {
    const difference = Number(a.dataset[order]) - Number(b.dataset[order]);
    return (order === "complexity" || order === "peers" ? difference : -difference)
      || a.dataset.search.localeCompare(b.dataset.search);
  });
  let count = 0;
  for (const row of records) {
    const data = row.dataset;
    const effort = Number(data.complexity);
    const effortMatches = complexity.value === "all"
      || (complexity.value === "unknown" ? effort === 99 : effort <= Number(complexity.value));
    const visible = (category === "all" || data.categories.split(" ").includes(category))
      && (!peerGroup || data.group === peerGroup)
      && data.search.includes(query) && effortMatches
      && (threshold === 0 || Number(data.reviews) >= threshold) && (!paid.checked || data.paid === "true");
    row.hidden = !visible;
    count += Number(visible);
    table.append(row);
  }
  document.querySelector("#app-result-count").textContent = `Showing ${count} of ${records.length} apps`;
  document.querySelector("#no-app-results").hidden = count !== 0;
  for (const button of categoryButtons) {
    const selected = button.dataset.category === category;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  const peerLabel = document.querySelector("#active-peer-filter");
  peerLabel.hidden = !peerGroup;
  peerLabel.replaceChildren();
  if (peerGroup) {
    peerLabel.append(document.createTextNode(`Comparing ${peerGroup.replaceAll("_", " ")} · `));
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "Clear peer filter";
    clear.addEventListener("click", () => { peerGroup = null; applyFilters(); });
    peerLabel.append(clear);
  }
}

if (table) {
  for (const input of [search, minimum]) input.addEventListener("input", applyFilters);
  for (const input of [sort, complexity, paid]) input.addEventListener("change", applyFilters);
  for (const button of categoryButtons) button.addEventListener("click", () => {
    category = button.dataset.category;
    peerGroup = null;
    applyFilters();
  });
  document.querySelector("#reset-app-filters").addEventListener("click", () => {
    category = "all"; peerGroup = null; search.value = ""; minimum.value = "0";
    sort.value = "priority"; complexity.value = "all"; paid.checked = false;
    applyFilters();
  });
  for (const button of document.querySelectorAll(".group-filter")) {
    button.disabled = button.dataset.group === "unknown";
    button.addEventListener("click", () => {
      peerGroup = button.dataset.group;
      category = "all"; search.value = ""; minimum.value = "0";
      complexity.value = "all"; paid.checked = false;
      applyFilters();
      document.querySelector("#app-result-count").scrollIntoView({block: "center"});
    });
  }
  for (const button of document.querySelectorAll(".row-toggle")) button.addEventListener("click", () => {
    const detail = document.getElementById(button.getAttribute("aria-controls"));
    detail.hidden = !detail.hidden;
    button.setAttribute("aria-expanded", String(!detail.hidden));
    button.setAttribute("aria-label", button.getAttribute("aria-label").replace(detail.hidden ? "Hide" : "Show", detail.hidden ? "Show" : "Hide"));
  });
  applyFilters();
}

function addCollapse(header, content, key) {
  content.id = content.id || `section-content-${key}`;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "section-toggle";
  button.innerHTML = '<span aria-hidden="true">›</span>';
  button.setAttribute("aria-controls", content.id);
  const title = header.querySelector("h1, h2")?.textContent || "statistics";
  function update(closed) {
    content.hidden = closed;
    button.setAttribute("aria-expanded", String(!closed));
    button.setAttribute("aria-label", `${closed ? "Expand" : "Collapse"} ${title}`);
  }
  let closed = false;
  try { closed = localStorage.getItem(`scanner-section-${key}`) === "closed"; } catch (_) { /* Storage is optional. */ }
  update(closed);
  button.addEventListener("click", () => {
    update(!content.hidden);
    try { localStorage.setItem(`scanner-section-${key}`, content.hidden ? "closed" : "open"); } catch (_) { /* Storage is optional. */ }
  });
  header.prepend(button);
}

for (const [index, panel] of Array.from(document.querySelectorAll("section.panel")).entries()) {
  const header = panel.querySelector(":scope > .section-header");
  if (!header) continue;
  const content = document.createElement("div");
  content.className = "section-content";
  for (const child of Array.from(panel.childNodes)) if (child !== header) content.append(child);
  panel.append(content);
  addCollapse(header, content, panel.id || String(index));
}
for (const [index, grid] of Array.from(document.querySelectorAll(".summary-grid")).entries()) {
  addCollapse(grid.previousElementSibling, grid, `statistics-${index}`);
}
// Navigation also opens a section previously collapsed by the reader.
document.querySelector('nav a[href="#apps"]')?.addEventListener("click", () => {
  const toggle = document.querySelector("#apps > .section-header .section-toggle");
  if (toggle?.getAttribute("aria-expanded") === "false") toggle.click();
});
