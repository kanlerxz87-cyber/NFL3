/* Suggestion review desk - reviewer choices.
 *
 * Everything here is browser-local. Nothing writes to the repository, nothing is sent anywhere, and no
 * choice changes what the site publishes. That is deliberate: the register at ops-center/data/derived.json
 * is the source of truth, and an approval that silently edited files is the failure mode the register's
 * own question Q-94 asks about. The buttons below turn a set of choices into a JSON block that a person
 * can paste into an issue, a commit message or a review note.
 */
(() => {
  const KEY = 'nfl3.suggestion-desk.v1';
  const table = document.getElementById('choices');
  if (!table) return;
  const tbody = table.querySelector('tbody');
  const inputs = Array.from(document.querySelectorAll('.path input[type=radio]'));
  const decisions = Array.from(document.querySelectorAll('.decision')).map(d => d.id);

  const read = () => {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (_) { return {}; }
  };
  const write = (obj) => {
    try { localStorage.setItem(KEY, JSON.stringify(obj)); } catch (_) { /* private mode: keep in memory */ }
  };

  const render = () => {
    const picked = read();
    const rows = [];
    for (const id of decisions) {
      const chosen = picked[id];
      if (!chosen) continue;
      rows.push(`<tr><td><a href="#${id}"><code>${id}</code></a> ${chosen.title}</td>` +
        `<td><code>${chosen.id}</code> ${chosen.path}</td>` +
        `<td>${chosen.adopts}</td></tr>`);
    }
    tbody.innerHTML = rows.length
      ? rows.join('')
      : `<tr class="empty"><td colspan="3">No path chosen yet — 0 of ${decisions.length} decisions recorded.</td></tr>`;
  };

  for (const input of inputs) {
    input.addEventListener('change', () => {
      const picked = read();
      const label = input.closest('.path');
      const adopts = Array.from(label.querySelectorAll('.kv dd'))[1];
      picked[input.dataset.decision] = {
        id: input.id,
        title: input.dataset.title,
        path: input.dataset.path,
        adopts: (adopts ? adopts.textContent : '').trim()
      };
      write(picked);
      render();
    });
  }

  const restore = () => {
    const picked = read();
    for (const input of inputs) input.checked = picked[input.dataset.decision] &&
      picked[input.dataset.decision].id === input.id;
    render();
  };

  document.querySelectorAll('[data-act]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.act === 'reset') { write({}); restore(); return; }
      const picked = read();
      const payload = {
        artifact: 'nfl3.suggestion-desk review',
        storage_key: KEY,
        note: 'Browser-local reviewer choices. Not a repository change; ops-center/data/derived.json remains the source of truth.',
        decisions: decisions.map(id => ({
          decision: id,
          path: picked[id] ? picked[id].id : null,
          label: picked[id] ? picked[id].path : 'no path chosen'
        }))
      };
      const text = JSON.stringify(payload, null, 2);
      const done = (ok) => { btn.textContent = ok ? 'Copied' : 'Copy failed - select manually';
        setTimeout(() => { btn.textContent = 'Copy JSON'; }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => done(true), () => done(fallback(text)));
      } else { done(fallback(text)); }
    });
  });

  function fallback(text) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  restore();
})();
