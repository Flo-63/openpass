/*
===============================================================================
Project   : openpass
Module    : static/js/members_manage.js
Created   : 2025-10-18
Author    : Florian
Purpose   : Member table search/sort and CSV import form handling.
===============================================================================
*/

function initMemberTable() {
  const list = document.getElementById("members-list");
  if (!list) return;

  const searchInput = list.querySelector("#member-search");
  const tbody = list.querySelector("tbody");
  const countEl = list.querySelector("#member-count");
  if (!tbody) return;

  let currentSortCol = -1;
  let sortAsc = true;

  function getRows() {
    return Array.from(tbody.querySelectorAll("tr"));
  }

  function updateCount() {
    if (!countEl) return;
    const total = getRows().length;
    const visible = getRows().filter((r) => r.style.display !== "none").length;
    countEl.textContent =
      visible === total
        ? `${total} Mitglieder`
        : `${visible} von ${total} Mitgliedern`;
  }

  function applyFilter() {
    const query = searchInput ? searchInput.value.toLowerCase() : "";
    getRows().forEach((row) => {
      const text = row.textContent.toLowerCase();
      row.style.display = !query || text.includes(query) ? "" : "none";
    });
    updateCount();
  }

  function sortRows(colIndex, asc) {
    const rows = getRows();
    rows.sort((a, b) => {
      const av = (a.cells[colIndex]?.textContent || "").trim().toLowerCase();
      const bv = (b.cells[colIndex]?.textContent || "").trim().toLowerCase();
      const an = parseFloat(av);
      const bn = parseFloat(bv);
      if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
      return asc ? av.localeCompare(bv, "de") : bv.localeCompare(av, "de");
    });
    rows.forEach((row) => tbody.appendChild(row));
    applyFilter();
  }

  if (searchInput) {
    searchInput.addEventListener("input", applyFilter);
  }

  const headers = list.querySelectorAll("th[data-sort-col]");
  headers.forEach((th) => {
    th.addEventListener("click", () => {
      const col = parseInt(th.dataset.sortCol);
      if (currentSortCol === col) {
        sortAsc = !sortAsc;
      } else {
        currentSortCol = col;
        sortAsc = true;
      }
      headers.forEach((h) => {
        h.classList.remove("text-blue-700");
        const ind = h.querySelector(".sort-indicator");
        if (ind) ind.remove();
      });
      th.classList.add("text-blue-700");
      const indicator = document.createElement("span");
      indicator.className = "sort-indicator ml-1 text-xs";
      indicator.textContent = sortAsc ? "▲" : "▼";
      th.appendChild(indicator);
      sortRows(col, sortAsc);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initMemberTable();

  const form = document.getElementById("csv-import-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
  });
});
