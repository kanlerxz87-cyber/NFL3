(() => {
  const pages = [
    ['index.html','Overview','◫'],['suggestions.html','Suggestions','✦'],['questions.html','Decision questions','?'],
    ['strategies.html','Strategies & signals','⌁'],['availability.html','Injuries & depth','＋'],['leaderboard.html','Leaderboard & gates','↗'],
    ['flagged.html','Flagged for review','⚑'],['sources.html','Sources & audit','↗']
  ];
  const file = location.pathname.split('/').pop() || 'index.html';
  const title = document.body.dataset.title || 'NFL decision lab';
  const app = document.querySelector('.app');
  const content = document.querySelector('.page-content');
  if (!app || !content) return;
  app.className = 'shell';
  app.innerHTML = `<aside aria-label="Main navigation"><a class="brand" href="index.html"><span class="brand-mark">NFL</span><span><strong>Decision Lab</strong><small>Evidence-first research</small></span></a><div><div class="nav-label">Workspace</div><nav class="nav-list">${pages.map(([href,label,icon])=>`<a href="${href}" ${file===href?'aria-current="page"':''}><span class="nav-icon" aria-hidden="true">${icon}</span>${label}</a>`).join('')}</nav></div><div class="aside-note"><b>Evidence standard</b><br>Official source links only. Unconfirmed values stay blank and are flagged, never estimated into the record.</div></aside><main class="main"><header class="topbar"><div style="display:flex;align-items:center;gap:10px"><button class="mobile-toggle" aria-label="Open navigation" aria-expanded="false">☰</button><div class="crumb">NFL decision lab <span aria-hidden="true">/</span> <strong>${title}</strong></div></div><div class="top-actions"><span class="pill warn">Research blueprint · not betting advice</span></div></header></main>`;
  const main = app.querySelector('main');
  main.appendChild(content);
  const footer = document.createElement('footer');
  footer.className = 'footer';
  footer.innerHTML = `NFL decision research workspace · Evidence checked 12 Nov 2026 · <a href="flagged.html">Review unresolved issues</a>. No line, model edge, injury impact, correlation estimate, or performance claim is currently verified.`;
  main.appendChild(footer);
  const button = app.querySelector('.mobile-toggle');
  button.addEventListener('click', () => {
    const opened = app.classList.toggle('nav-open');
    button.setAttribute('aria-expanded', String(opened));
    button.setAttribute('aria-label', opened ? 'Close navigation' : 'Open navigation');
  });
  document.querySelectorAll('[data-table-search]').forEach(input => {
    const target = document.getElementById(input.dataset.tableSearch);
    if (!target) return;
    input.addEventListener('input', () => {
      const q = input.value.trim().toLocaleLowerCase();
      target.querySelectorAll('tbody tr').forEach(row => row.hidden = !row.textContent.toLocaleLowerCase().includes(q));
    });
  });
})();
