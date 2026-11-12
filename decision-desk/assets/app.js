(() => {
  const tables = new Map();
  document.querySelectorAll('table[id]').forEach(t => tables.set(t.id, t));

  const applyFilters = (id) => {
    const table = tables.get(id);
    if (!table) return;
    const controls = [...document.querySelectorAll(`[data-table="${id}"]`)];
    const rows = [...table.querySelectorAll('tbody tr')];
    let shown = 0;
    rows.forEach(row => {
      let ok = true;
      controls.forEach(c => {
        const value = (c.value || '').trim().toLowerCase();
        if (!value) return;
        const key = c.dataset.filterKey;
        if (key === 'search') {
          const hay = (row.dataset.search || row.textContent).toLowerCase();
          if (!hay.includes(value)) ok = false;
        } else {
          const val = (row.dataset[key] || '').toLowerCase();
          if (val !== value) ok = false;
        }
      });
      row.hidden = !ok;
      if (ok) shown++;
    });
    const counter = document.querySelector(`[data-count="${id}"]`);
    if (counter) counter.textContent = `${shown} of ${rows.length} rows`;
  };

  document.querySelectorAll('[data-table]').forEach(c => {
    c.addEventListener('input', () => applyFilters(c.dataset.table));
    c.addEventListener('change', () => applyFilters(c.dataset.table));
    applyFilters(c.dataset.table);
  });

  // Suggestion review console: browser-local only, nothing is written back to the repo.
  const KEY = 'nfl3-decision-desk-review-v1';
  const state = JSON.parse(localStorage.getItem(KEY) || '{}');
  const selects = [...document.querySelectorAll('select[data-suggestion-id]')];
  const summary = document.getElementById('review-summary');
  const render = () => {
    const counts = { approve: 0, defer: 0, reject: 0 };
    selects.forEach(s => { const v = s.value; if (counts[v] !== undefined) counts[v]++; });
    if (summary) {
      summary.textContent = `${counts.approve} approved · ${counts.defer} deferred · ${counts.reject} rejected · ${selects.length - counts.approve - counts.defer - counts.reject} unreviewed`;
    }
  };
  selects.forEach(s => {
    const id = s.dataset.suggestionId;
    if (state[id]) s.value = state[id];
    s.addEventListener('change', () => {
      if (s.value) state[id] = s.value; else delete state[id];
      localStorage.setItem(KEY, JSON.stringify(state));
      render();
    });
  });
  render();

  const exportBtn = document.getElementById('export-review');
  if (exportBtn) exportBtn.addEventListener('click', () => {
    const out = selects.map(s => ({ id: s.dataset.suggestionId, title: s.dataset.title, decision: s.value || 'unreviewed' }));
    const blob = new Blob([JSON.stringify({ generated_at: new Date().toISOString(), note: 'Browser-local review of decision-desk suggestions. Does not change the repository.', decisions: out }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'nfl3-suggestion-review.json';
    a.click();
    URL.revokeObjectURL(a.href);
  });
  const resetBtn = document.getElementById('reset-review');
  if (resetBtn) resetBtn.addEventListener('click', () => {
    localStorage.removeItem(KEY);
    selects.forEach(s => { s.value = ''; });
    render();
  });

  // Sorting on numeric/data-sortable columns.
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.title = 'Sort';
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const idx = [...th.parentElement.children].indexOf(th);
      const body = table.tBodies[0];
      const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
      th.dataset.dir = dir;
      const val = tr => {
        const cell = tr.children[idx];
        if (!cell) return '';
        const raw = cell.dataset.value || cell.textContent.trim();
        const num = parseFloat(raw.replace(/,/g, ''));
        return Number.isNaN(num) ? raw.toLowerCase() : num;
      };
      [...body.rows].sort((a, b) => {
        const x = val(a), y = val(b);
        if (x === y) return 0;
        return (x > y ? 1 : -1) * (dir === 'asc' ? 1 : -1);
      }).forEach(r => body.appendChild(r));
    });
  });
})();
