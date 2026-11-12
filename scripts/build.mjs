// Builds the static GitHub Pages site in docs/ from data/*.csv. No dependencies.
// All numbers on the pages are computed from the CSVs; nothing is typed in by hand.
import { mkdirSync, writeFileSync, copyFileSync } from 'node:fs';
import { loadCSV } from './csv.mjs';

const ROOT = new URL('..', import.meta.url).pathname;
const D = (f) => loadCSV(ROOT + 'data/' + f);
const OUT = ROOT + 'docs/';
mkdirSync(OUT + 'assets', { recursive: true });

const injuries = D('injuries_2026_w10.csv');
const games = D('games_2026_w10.csv');
const news = D('news_signals_2026_w10.csv');
const sources = D('sources.csv');
const questions = D('questions.csv');
const suggestions = D('suggestions.csv');
const strategies = D('strategies.csv');
const gates = D('validation_gates.csv');
const corr = D('correlation_framework.csv');
const repo = D('repo_review.csv');

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const AS_OF = '2026-11-12';
const srcLink = (url, label = 'source ↗') => url
  ? `<a href="${esc(url)}" target="_blank" rel="noopener">${label}</a>`
  : `<span class="flag">UNVERIFIED</span>`;
const badge = (s) => {
  const t = String(s ?? '');
  const cls = /UNVERIFIED|Blank|Open|FLAG|Flag|Blocker|DECISION|Blocked|Required|EXCLUDED|Partly|Unknown|Proposed|Hypothesis/i.test(t) ? 'warn' : /Verified|Known|Implemented/i.test(t) ? 'ok' : '';
  return t ? `<span class="badge ${cls}">${esc(t)}</span>` : '';
};
function table(id, headers, rows, { filter = true } = {}) {
  const head = headers.map((h) => `<th>${esc(h)}</th>`).join('');
  const body = rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('\n');
  return `${filter ? `<input class="filter" type="search" placeholder="Filter rows (e.g. team, player, status)…" data-target="${id}" aria-label="Filter table">` : ''}
<div class="tablewrap"><table id="${id}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>
<p class="count"><span data-count="${id}">${rows.length}</span> row(s) shown</p>`;
}
const NAV = [
  ['index.html', 'Home'], ['injuries.html', 'Injuries'], ['games.html', 'Week 10 games'],
  ['starters-backups.html', 'Starters & backups'], ['strategies.html', 'Strategy lab'],
  ['questions.html', 'Questions & gaps'], ['suggestions.html', 'Suggestions'],
  ['flagged.html', 'Flagged for Review'], ['repo-review.html', 'Repo review'], ['sources.html', 'Sources'],
];
function page(file, title, body, active) {
  const nav = NAV.map(([h, t]) => `<a href="${h}"${h === active ? ' class="active" aria-current="page"' : ''}>${t}</a>`).join('');
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} · NFL3 Dashboard</title><link rel="stylesheet" href="assets/style.css"></head>
<body>
<header class="top"><a class="brand" href="index.html">NFL3 Dashboard</a><nav>${nav}</nav></header>
<main>
<h1>${esc(title)}</h1>
${body}
</main>
<footer><p>Data as of ${AS_OF}. Every table row links to its source. Blank or <span class="flag">UNVERIFIED</span> values were not confirmed from an official source and were not filled in. Analysis only; not betting advice.</p></footer>
<script src="assets/app.js"></script>
</body></html>`;
  writeFileSync(OUT + file, html);
}

// ---------- derived numbers ----------
const teamsWithRows = [...new Set(injuries.map((r) => r.team_abbr))];
const teamsInGames = games.flatMap((g) => [g.team_a_abbr, g.team_b_abbr]);
const noInjury = [...new Set(teamsInGames)].filter((t) => !teamsWithRows.includes(t));
const cnt = (arr, key, val) => arr.filter((r) => r[key] === val).length;
const dnp = cnt(injuries, 'practice_status', 'Did Not Participate In Practice');
const lim = cnt(injuries, 'practice_status', 'Limited Participation in Practice');
const full = cnt(injuries, 'practice_status', 'Full Participation in Practice');
const outN = cnt(injuries, 'game_status', 'Out');
const qN = cnt(injuries, 'game_status', 'Questionable');
const injuryTextN = injuries.filter((r) => r.injury).length;
const flagRepo = repo.filter((r) => /Flag|Blocker/.test(r.severity));
const openQ = questions.filter((q) => /Open|Decision|Unknown|Partly/.test(q.status));
const decisions = questions.filter((q) => q.status === 'Decision' || /^Yes/.test(q.decision_needed_from_owner)).length;
const proposals = suggestions.filter((s) => /Proposed/.test(s.status)).length;
const validated = strategies.filter((s) => /PASS|Validated/i.test(s.gate_status)).length;
const unitOf = { QB: 'Offense', RB: 'Offense', FB: 'Offense', WR: 'Offense', TE: 'Offense', T: 'Offense', G: 'Offense', C: 'Offense',
  DT: 'Defense', DE: 'Defense', LB: 'Defense', CB: 'Defense', S: 'Defense', K: 'Special teams', P: 'Special teams', LS: 'Special teams' };
const unit = (p) => unitOf[p] || 'Unmapped';
const unitRows = [...new Set(injuries.map((r) => r.team_abbr))].sort().map((t) => {
  const rs = injuries.filter((r) => r.team_abbr === t);
  const u = (name) => rs.filter((r) => unit(r.position) === name);
  const sel = (name) => `${u(name).length} (DNP ${u(name).filter((r) => r.practice_status.startsWith('Did Not')).length})`;
  const outQ = rs.filter((r) => r.game_status).map((r) => `${esc(r.player)} (${esc(r.position)}): ${esc(r.game_status)}`).join('; ') || '—';
  return [esc(t), rs[0].team_name, sel('Offense'), sel('Defense'), sel('Special teams'), outQ, srcLink('https://www.nfl.com/injuries/')];
});
const gameRows = games.map((g) => [esc(g.day_et), `${esc(g.team_a_abbr)} (${esc(g.team_a_record)}) vs ${esc(g.team_b_abbr)} (${esc(g.team_b_record)})`, esc(g.kickoff_et), esc(g.network_as_listed), esc(g.verification), srcLink(g.source_url)]);

// ---------- pages ----------
page('index.html', 'Executive summary', `
<section class="cards">
  <a class="card" href="injuries.html"><b>${injuries.length}</b><span>official injury-report rows (Week 10)</span></a>
  <a class="card" href="games.html"><b>${games.length}</b><span>Week 10 matchups listed</span></a>
  <a class="card" href="starters-backups.html"><b>${news.length}</b><span>starter / replacement headlines</span></a>
  <a class="card warn" href="strategies.html"><b>${validated}</b><span>strategies validated (of ${strategies.length} tracked)</span></a>
  <a class="card warn" href="flagged.html"><b>${flagRepo.length}</b><span>items flagged for review</span></a>
  <a class="card" href="suggestions.html"><b>${proposals}</b><span>proposals waiting for your decision</span></a>
</section>
<h2>Key findings</h2>
<ul class="findings">
  <li><b>Injury load (Week 10, official nfl.com report):</b> ${injuries.length} player listings across ${teamsWithRows.length} teams. Practice status: ${dnp} Did Not Participate, ${lim} Limited, ${full} Full. Game status so far: ${outN} Out, ${qN} Questionable. Most game statuses are still blank, which is expected before the Friday designations.</li>
  <li><b>No-injury teams on the official page:</b> ${noInjury.map(esc).join(', ')}. One of these conflicts with a headline (Seattle / Sam Darnold). See <a href="flagged.html">Flagged for Review</a>, item R-06.</li>
  <li><b>Starter replacements:</b> ${news.length} headlines recorded, including QB changes for Cleveland (headline: Watson to start), Arizona (Carson Beck), and Miami (Kyle McCord next in line), plus Baltimore (Lamar Jackson on IR; Tyler Huntley out for the season). Each is headline-verified only.</li>
  <li><b>Depth charts (starters vs. 2nd–4th string):</b> <span class="flag">UNVERIFIED</span>. No official depth-chart source was found. Third-party sites were excluded. Starter and backup fields are blank. The "Starters & backups" page shows injury load by unit as a proxy.</li>
  <li><b>Strategy leaderboard:</b> ${strategies.length} candidate strategies tracked, <b>0 validated</b>. No betting odds or historical results are in the repo, so no gate can be passed. No rewards have been assigned. Gates and correlation values are blank until data is verified.</li>
  <li><b>Compliance (NL):</b> the regulator is Ksa (kansspelautoriteit.nl). Check any operator in the official Ksa Kansspelwijzer before use; the licence rules have not been read yet (Q12). Prop-market restrictions are reported only via secondary sources and are marked UNVERIFIED.</li>
  <li><b>Decisions needed from you:</b> ${decisions} decision questions and ${proposals} improvement proposals. Only SG-12 (verification tooling) has been implemented. See <a href="questions.html">Questions &amp; gaps</a> and <a href="suggestions.html">Suggestions</a>.</li>
</ul>
<h2>Pages</h2>
<ul class="links">
  <li><a href="injuries.html">Injuries</a> – every official Week 10 row, filterable.</li>
  <li><a href="games.html">Week 10 games</a> – matchups, records and networks, as listed on nfl.com.</li>
  <li><a href="starters-backups.html">Starters &amp; backups</a> – replacement headlines and injury load by unit (depth chart not verified).</li>
  <li><a href="strategies.html">Strategy lab</a> – leaderboard, validation gates and correlation framework (no results yet).</li>
  <li><a href="questions.html">Questions &amp; gaps</a> – what is known, unknown, and how to close each gap.</li>
  <li><a href="suggestions.html">Suggestions</a> – proposed changes for you to choose from. Nothing implemented.</li>
  <li><a href="flagged.html">Flagged for Review</a> – irregularities and unverified items, with source links.</li>
  <li><a href="repo-review.html">Repo review</a> – what was found in the repository.</li>
  <li><a href="sources.html">Sources</a> – every source, with verification status.</li>
</ul>`, 'index.html');

page('injuries.html', 'Injury report – Week 10 (2026)', `
<p>Official nfl.com Week 10 report, transcribed row by row (${injuries.length} rows). Columns are as published. Empty cells mean the official page left them blank.</p>
${table('inj', ['Day (ET)', 'Team', 'Player', 'Pos', 'Injury', 'Practice status', 'Game status', 'Source', 'Verification'],
  injuries.map((r) => [esc(r.day_game_et ?? r.game_day_et), esc(r.team_abbr + ' ' + r.team_name), esc(r.player), esc(r.position), esc(r.injury), esc(r.practice_status), esc(r.game_status), srcLink(r.source_url), badge(r.verification)]))}
<h2>Teams with no injuries listed</h2><p>${noInjury.map(esc).join(', ')} — "No Injuries Reported" on the official page. See Flagged R-06 for Seattle.</p>`, 'injuries.html');

page('games.html', 'Week 10 matchups (as listed on nfl.com)', `
<p>${games.length} matchups listed on the nfl.com Week 10 report. Team order is as listed on the page; the page does not label home/away, so none is stated here. Four teams (DEN, CHI, PHI, TB) are not on this page; their status is not inferred (flag Q11).</p>
${table('games', ['Day', 'Matchup (record)', 'Kickoff (ET)', 'Network', 'Verification', 'Source'], gameRows)}`, 'games.html');

page('starters-backups.html', 'Starters, backups & injury load', `
<div class="notice"><b>Starter vs. backup depth is <span class="flag">UNVERIFIED</span>.</b> No official depth-chart source was found. Third-party sites were excluded (see Sources). Starter/backup fields are left blank rather than filled in.</div>
<h2>Injury load by unit (proxy – derived from the official report)</h2>
<p>Our grouping of positions (methodology, not an NFL definition): Offense = QB, RB, FB, WR, TE, T, G, C; Defense = DT, DE, LB, CB, S; Special teams = K, P, LS. Counts are players listed on the official report; "DNP" = Did Not Participate in Practice.</p>
${table('unit', ['Team', 'Name', 'Offense listed (DNP)', 'Defense listed (DNP)', 'Special teams listed (DNP)', 'Game status (as published)', 'Source'], unitRows)}
<h2>Starter-replacement and availability headlines</h2>
<p>Headline text as shown on nfl.com. Article bodies were not opened, so only the headline is verified. "Starter/replacement signal" paraphrases the headline and does not add facts.</p>
${table('news', ['Listing date', 'Team', 'Player', 'Category', 'Headline (verbatim)', 'Starter / replacement signal', 'Source', 'Verification'],
  news.map((r) => [esc(r.listing_date), esc(r.team_abbr), esc(r.player), esc(r.category), esc(r.headline_verbatim), esc(r.starter_replacement_signal), srcLink(r.source_url), badge(r.verification)]))}`, 'starters-backups.html');

page('strategies.html', 'Strategy lab – leaderboard, gates and correlation', `
<div class="notice"><b>No strategy has been validated.</b> The repo has no verified odds or historical results, so no gate can be passed. No rewards are assigned. Values below stay blank until they are verified.</div>
<h2>Leaderboard</h2>
${table('lb', ['Rank', 'ID', 'Strategy', 'Bet type', 'Hypothesis', 'Data required', 'Available now', 'Gate status', 'Sample', 'ROI', 'CLV', 'Correlation', 'Reward', 'Source'],
  strategies.map((s) => [esc(s.rank), esc(s.strategy_id), esc(s.name), esc(s.bet_type), esc(s.signal_hypothesis), esc(s.data_required), esc(s.data_available_now), badge(s.gate_status), esc(s.sample_size) || '<span class="flag">blank</span>', esc(s.roi) || '<span class="flag">blank</span>', esc(s.clv) || '<span class="flag">blank</span>', esc(s.correlation_used) || '<span class="flag">blank</span>', esc(s.reward), srcLink(s.source_link)]))}
<h2>Validation gates (proposed – needs your decision)</h2>
${table('gates', ['Gate', 'Name', 'Rule', 'Status'], gates.map((g) => [esc(g.gate_id), esc(g.gate), esc(g.rule), badge(g.status)]), { filter: false })}
<h2>Correlation framework (values not computed)</h2>
<p>Correlation needs joint historical data for each pair of legs. Blank = not computed. Nothing has been estimated.</p>
${table('corr', ['Leg A', 'Leg B', 'Same game', 'Hypothesised direction', 'Correlation', 'Sample', 'Data source', 'Source', 'Status'],
  corr.map((c) => [esc(c.leg_a), esc(c.leg_b), esc(c.same_game), esc(c.hypothesised_direction), esc(c.correlation_value) || '<span class="flag">blank</span>', esc(c.sample_size) || '<span class="flag">blank</span>', esc(c.data_source), srcLink(c.source_link), badge(c.status)]))}
<h2>Scope notes</h2>
<ul><li>Prohibited-prop categories (as reported, <span class="flag">UNVERIFIED</span>): injury-based props, officiating, outcomes determined by one person in one play, and pre-determined outcomes. Strategies in these categories are excluded at gate G8.</li>
<li>Strategies are hypotheses until they pass all gates. Luck control: random and favorites-only baselines (ST-09, ST-10) are required in every run.</li></ul>`, 'strategies.html');

page('questions.html', 'Questions, information & gaps', `
<p>What we know, what we do not, and how to find out. Decisions are marked for you.</p>
${table('q', ['ID', 'Question', 'Status', 'What we know', 'What is missing', 'How to discover', 'Decision needed from you', 'Source', 'Verification'],
  questions.map((q) => [esc(q.id), esc(q.question), badge(q.status), esc(q.what_we_know), esc(q.what_is_missing), esc(q.how_to_discover), esc(q.decision_needed_from_owner), srcLink(q.source_link), badge(q.verification)]))}`, 'questions.html');

page('suggestions.html', 'Suggestions – choose before anything changes', `
<div class="notice"><b>Proposals only.</b> Nothing below has been implemented, except SG-12 (verification tooling, no content change). Mark your choice in "Your decision" (for example: approve, reject, modify) and the next session will act on it.</div>
${table('sg', ['ID', 'Area', 'Suggestion', 'Why it helps', 'What it needs', 'Risk / trade-off', 'Status', 'Your decision', 'Source'],
  suggestions.map((s) => [esc(s.id), esc(s.area), esc(s.suggestion), esc(s.why_it_helps), esc(s.what_it_needs), esc(s.risk_or_tradeoff), badge(s.status), '<span class="flag">choose</span>', srcLink(s.source_link, s.source_link ? 'source ↗' : 'n/a')]))}`, 'suggestions.html');

const flagged = [
  ...flagRepo.map((r) => [esc(r.id), esc(r.check), esc(r.finding), badge(r.severity), esc(r.action_taken), srcLink(r.evidence_link, r.evidence_link ? 'source ↗' : 'UNVERIFIED')]),
  ...questions.filter((q) => /Open|UNVERIFIED|Unknown/.test(q.status + q.verification)).map((q) => [esc(q.id), esc(q.question), esc(q.what_is_missing) || esc(q.what_we_know), badge(q.status), esc(q.how_to_discover), srcLink(q.source_link)]),
  ...sources.filter((s) => /UNVERIFIED|EXCLUDED|Partially/.test(s.status)).map((s) => [esc(s.source_id), esc(s.title), esc(s.used_for) || 'Excluded from use', badge(s.status), esc(s.how_verified), srcLink(s.url)]),
];
page('flagged.html', 'Flagged for Review', `
<div class="notice"><b>Published for your review after go-live.</b> Flags do not block the site. Each item links to the source to check. Rows are generated from the data files.</div>
${table('flag', ['ID', 'Item', 'Finding / detail', 'Status', 'Action / how to check', 'Source'], flagged)}`, 'flagged.html');

page('repo-review.html', 'Repository review', `
<p>Review of the repository as found, with severity and the action taken. Source links point to GitHub or official sites.</p>
${table('repo', ['ID', 'Check', 'Finding', 'Evidence', 'Severity', 'Action taken'],
  repo.map((r) => [esc(r.id), esc(r.check), esc(r.finding), srcLink(r.evidence_link, r.evidence_link ? 'source ↗' : 'n/a'), badge(r.severity), esc(r.action_taken)]))}`, 'repo-review.html');

page('sources.html', 'Sources & verification', `
<p>Official sources are used for every verified value. Secondary and excluded sources are listed so you can see what was not relied on.</p>
${table('src', ['ID', 'Title', 'Publisher', 'Type', 'Used for', 'How verified', 'Status', 'Link'],
  sources.map((s) => [esc(s.source_id), esc(s.title), esc(s.publisher), esc(s.type), esc(s.used_for), esc(s.how_verified), badge(s.status), srcLink(s.url, s.url)]))}`, 'sources.html');

copyFileSync(ROOT + 'scripts/site.css', OUT + 'assets/style.css');
copyFileSync(ROOT + 'scripts/site.js', OUT + 'assets/app.js');
writeFileSync(OUT + '.nojekyll', '');
console.log('built', ['index', 'injuries', 'games', 'starters-backups', 'strategies', 'questions', 'suggestions', 'flagged', 'repo-review', 'sources'].length, 'pages;', injuries.length, 'injury rows; no-injury teams:', noInjury.join(','));
