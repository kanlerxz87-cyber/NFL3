/* NFL3 — table filter + sort. No dependencies. */
(function () {
  "use strict";

  function rowsOf(table) {
    return Array.prototype.slice.call(table.tBodies[0] ? table.tBodies[0].rows : []);
  }

  function applyFilter(table, q) {
    var needle = (q || "").trim().toLowerCase();
    var shown = 0;
    rowsOf(table).forEach(function (tr) {
      if (tr.classList.contains("sub")) { tr.classList.toggle("hidden", needle !== ""); return; }
      var hit = needle === "" || tr.textContent.toLowerCase().indexOf(needle) !== -1;
      tr.classList.toggle("hidden", !hit);
      if (hit) shown++;
    });
    var out = document.querySelector('[data-count-for="' + table.id + '"]');
    if (out) out.textContent = needle === "" ? "" : shown + " matching row" + (shown === 1 ? "" : "s");
  }

  function cellValue(tr, idx) {
    var td = tr.cells[idx];
    if (!td) return "";
    var raw = td.getAttribute("data-sort");
    if (raw !== null) return raw;
    return td.textContent.trim();
  }

  function sortBy(table, idx, dir) {
    var body = table.tBodies[0];
    if (!body) return;
    var rows = rowsOf(table);
    var subs = [], data = [], current = null;
    rows.forEach(function (tr) {
      if (tr.classList.contains("sub")) { current = { sub: tr, items: [] }; subs.push(current); }
      else if (current) current.items.push(tr);
      else data.push(tr);
    });
    var numeric = rows.some(function (tr) {
      var v = cellValue(tr, idx);
      return v !== "" && !isNaN(parseFloat(v));
    });
    function cmp(a, b) {
      var x = cellValue(a, idx), y = cellValue(b, idx);
      if (numeric) {
        var nx = parseFloat(x), ny = parseFloat(y);
        if (isNaN(nx)) return 1;
        if (isNaN(ny)) return -1;
        return dir * (nx - ny);
      }
      return dir * x.localeCompare(y);
    }
    if (subs.length) {
      subs.forEach(function (g) { g.items.sort(cmp); });
      subs.sort(function (a, b) { return -1; });
      body.innerHTML = "";
      subs.forEach(function (g) {
        body.appendChild(g.sub);
        g.items.forEach(function (tr) { body.appendChild(tr); });
      });
    } else {
      data.sort(cmp);
      body.innerHTML = "";
      data.forEach(function (tr) { body.appendChild(tr); });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input[data-filter]").forEach(function (input) {
      var table = document.getElementById(input.getAttribute("data-filter"));
      if (!table) return;
      input.addEventListener("input", function () { applyFilter(table, input.value); });
    });

    document.querySelectorAll("table").forEach(function (table) {
      var ths = table.querySelectorAll("thead th");
      Array.prototype.forEach.call(ths, function (th, idx) {
        th.classList.add("sortable");
        th.addEventListener("click", function () {
          var dir = th.getAttribute("data-dir") === "asc" ? -1 : 1;
          Array.prototype.forEach.call(ths, function (o) { o.removeAttribute("data-dir"); });
          th.setAttribute("data-dir", dir === 1 ? "asc" : "desc");
          sortBy(table, idx, dir);
        });
      });
    });
  });
})();
