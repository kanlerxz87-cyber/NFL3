/* Ops centre client behaviour.
   Filtering, the suggestion review tally, and a local-only export.
   Nothing here sends data anywhere. */
(function () {
  "use strict";

  var KEY = "nfl3-ops-center-decisions-v1";

  /* ---------- table filtering ---------- */
  document.querySelectorAll("input[data-filter]").forEach(function (input) {
    var id = input.getAttribute("data-filter");
    var table = document.getElementById(id);
    if (!table) return;
    var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
    var counter = document.querySelector('[data-count-for="' + id + '"]');

    function apply() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (tr) {
        var match = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
        tr.style.display = match ? "" : "none";
        if (match) shown++;
      });
      if (counter) {
        counter.textContent = q
          ? shown + " of " + rows.length + " rows shown"
          : rows.length + " rows";
      }
    }

    input.addEventListener("input", apply);
    apply();
  });

  /* ---------- suggestion review ---------- */
  var table = document.getElementById("sg-table");
  if (!table) return;

  var stored = {};
  try {
    stored = JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch (err) {
    stored = {};
  }

  var selects = Array.prototype.slice.call(table.querySelectorAll("select[data-decision]"));
  var radios = Array.prototype.slice.call(table.querySelectorAll('input[type="radio"][name^="path-"]'));

  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(stored));
    } catch (err) {
      /* storage unavailable; the page still works, the export still works */
    }
  }

  function collect() {
    var out = [];
    table.querySelectorAll("tbody tr[data-id]").forEach(function (tr) {
      var id = tr.getAttribute("data-id");
      var decision = tr.querySelector("select[data-decision]");
      var checked = tr.querySelector('input[type="radio"][name="path-' + id + '"]:checked');
      var state = stored[id] || {};
      out.push({
        id: id,
        title: tr.getAttribute("data-title"),
        path: checked ? checked.value : "",
        decision: decision ? decision.value : "Unreviewed",
        decided_at: state.at || ""
      });
    });
    return out;
  }

  function tally() {
    var counts = { Approve: 0, Defer: 0, Reject: 0, Unreviewed: 0 };
    selects.forEach(function (sel) {
      var v = sel.value in counts ? sel.value : "Unreviewed";
      counts[v]++;
    });
    Object.keys(counts).forEach(function (k) {
      var node = document.querySelector('[data-tally="' + k + '"]');
      if (node) node.textContent = counts[k];
    });
  }

  selects.forEach(function (sel) {
    var tr = sel.closest("tr");
    var id = tr ? tr.getAttribute("data-id") : null;
    var prior = id && stored[id] ? stored[id].decision : null;
    if (prior && (prior === "Approve" || prior === "Defer" || prior === "Reject")) {
      sel.value = prior;
    }
    sel.setAttribute("data-state", sel.value);

    sel.addEventListener("change", function () {
      sel.setAttribute("data-state", sel.value);
      if (id) {
        stored[id] = stored[id] || {};
        stored[id].decision = sel.value;
        stored[id].at = new Date().toISOString();
        save();
      }
      tally();
    });
  });

  radios.forEach(function (radio) {
    var id = radio.name.replace("path-", "");
    var prior = stored[id] ? stored[id].path : null;
    if (prior && radio.value === prior) radio.checked = true;

    radio.addEventListener("change", function () {
      if (!radio.checked) return;
      stored[id] = stored[id] || {};
      stored[id].path = radio.value;
      stored[id].at = new Date().toISOString();
      save();
    });
  });

  tally();

  function payload() {
    var rows = collect();
    var decided = rows.filter(function (r) { return r.decision !== "Unreviewed"; });
    return {
      exported_at: new Date().toISOString(),
      source_page: window.location.href,
      note: "Reviewer decisions only. No proposal on this page has been implemented.",
      summary: {
        total: rows.length,
        approved: decided.filter(function (r) { return r.decision === "Approve"; }).length,
        deferred: decided.filter(function (r) { return r.decision === "Defer"; }).length,
        rejected: decided.filter(function (r) { return r.decision === "Reject"; }).length,
        unreviewed: rows.length - decided.length
      },
      decisions: rows
    };
  }

  document.querySelectorAll("[data-action]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var action = btn.getAttribute("data-action");
      var data = payload();
      var text = JSON.stringify(data, null, 2);

      if (action === "reset") {
        if (!window.confirm("Clear every decision recorded on this page?")) return;
        localStorage.removeItem(KEY);
        selects.forEach(function (sel) {
          sel.value = "Unreviewed";
          sel.setAttribute("data-state", "Unreviewed");
        });
        tally();
        return;
      }

      if (action === "copy") {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            btn.textContent = "Copied";
            setTimeout(function () { btn.textContent = "Copy to clipboard"; }, 1600);
          });
        }
        return;
      }

      if (action === "export") {
        var blob = new Blob([text], { type: "application/json" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "nfl3-suggestion-decisions.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    });
  });
})();
