(function () {
  "use strict";

  // 1. Instant client-side table search across all tables on the active page
  const searchInput = document.getElementById("global-table-search");
  const countBadge = document.getElementById("filter-row-count");

  function applyFilters() {
    const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    const activeChip = document.querySelector(".filter-btn.active");
    const chipFilter = activeChip ? activeChip.getAttribute("data-filter") : "all";

    let visible = 0;
    let total = 0;
    document.querySelectorAll("tbody tr").forEach((row) => {
      total += 1;
      const text = row.textContent.toLowerCase();
      const rowTag = (row.getAttribute("data-tag") || "all").toLowerCase();
      const matchesQuery = !query || text.includes(query);
      const matchesChip = !chipFilter || chipFilter === "all" || rowTag.includes(chipFilter);
      const show = matchesQuery && matchesChip;
      row.style.display = show ? "" : "none";
      if (show) visible += 1;
    });
    if (countBadge) {
      countBadge.textContent = visible + " / " + total + " rows shown";
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
  }

  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      applyFilters();
    });
  });

  // 2. Non-mutating Suggestions Path Selector (persisted in localStorage for human review)
  const STORAGE_KEY = "nfl3_decision_hub_suggestion_choices_v1";
  let savedChoices = {};
  try {
    savedChoices = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (_) {
    savedChoices = {};
  }

  function updateSummaryBanner() {
    const el = document.getElementById("suggestion-selection-summary");
    if (!el) return;
    const vals = Object.values(savedChoices);
    const approvedA = vals.filter((v) => v === "Path A").length;
    const approvedB = vals.filter((v) => v === "Path B").length;
    const deferred = vals.filter((v) => v === "Defer").length;
    el.textContent =
      "Reviewer Selections (Client-Side Only — 0 Repo Changes Executed): " +
      approvedA +
      " Path A · " +
      approvedB +
      " Path B · " +
      deferred +
      " Deferred";
  }

  document.querySelectorAll(".path-select").forEach((sel) => {
    const id = sel.getAttribute("data-sug-id");
    if (id && savedChoices[id]) {
      sel.value = savedChoices[id];
    }
    sel.addEventListener("change", () => {
      if (!id) return;
      savedChoices[id] = sel.value;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(savedChoices));
      } catch (_) {}
      updateSummaryBanner();
    });
  });

  const exportBtn = document.getElementById("export-decisions-btn");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const payload = {
        exported_at_utc: new Date().toISOString(),
        note: "Human decision selection sheet exported from NFL3 Decision Hub before implementation.",
        selections: savedChoices
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "nfl3-suggestion-decisions.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }

  const resetBtn = document.getElementById("reset-decisions-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      savedChoices = {};
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (_) {}
      document.querySelectorAll(".path-select").forEach((sel) => {
        sel.value = "Pending Review";
      });
      updateSummaryBanner();
    });
  }

  applyFilters();
  updateSummaryBanner();
})();
