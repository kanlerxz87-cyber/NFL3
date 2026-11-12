// Verification gate. Fails (exit 1) if any row lacks a source, a link is broken,
// or an external link is not https. Run after scripts/build.mjs.
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { loadCSV } from './csv.mjs';
const ROOT = new URL('..', import.meta.url).pathname;
const errors = []; const notes = [];
const fail = (m) => errors.push(m);

// 1) Data rules: every verified/listed row carries an https source URL.
const needSource = { 'injuries_2026_w10.csv': 'source_url', 'games_2026_w10.csv': 'source_url', 'news_signals_2026_w10.csv': 'source_url' };
for (const [f, col] of Object.entries(needSource)) {
  const rows = loadCSV(ROOT + 'data/' + f);
  rows.forEach((r, i) => { if (!/^https:\/\//.test(r[col] || '')) fail(`${f} row ${i + 2}: missing https source`); });
  notes.push(`${f}: ${rows.length} rows checked`);
}
for (const r of loadCSV(ROOT + 'data/sources.csv')) if (r.url && !/^https:\/\//.test(r.url)) fail(`sources ${r.source_id}: non-https url`);
const FLAG = /UNVERIFIED|Blank|Open|FLAG|Flag|Blocker|DECISION|Blocked|Required|EXCLUDED|Partly|Unknown|Proposed|Hypothesis|Decision|Implemented|Partially/i;
for (const [f, col] of [['questions.csv', 'source_link'], ['suggestions.csv', 'source_link'], ['strategies.csv', 'source_link'], ['correlation_framework.csv', 'source_link'], ['repo_review.csv', 'evidence_link']]) {
  loadCSV(ROOT + 'data/' + f).forEach((r, i) => {
    const link = r[col] || '';
    if (link && !/^https:\/\//.test(link)) fail(`${f} row ${i + 2}: ${col} not https`);
    if (!link && !FLAG.test(Object.values(r).join(' '))) fail(`${f} row ${i + 2}: blank source without UNVERIFIED/Open/Blank flag`);
  });
}

// 2) Injury totals reconcile with teams on the official page.
const inj = loadCSV(ROOT + 'data/injuries_2026_w10.csv');
const games = loadCSV(ROOT + 'data/games_2026_w10.csv');
const teamsInGames = new Set(games.flatMap((g) => [g.team_a_abbr, g.team_b_abbr]));
const teamsInInj = new Set(inj.map((r) => r.team_abbr));
if (teamsInGames.size !== 28) fail(`expected 28 teams in 14 games, found ${teamsInGames.size}`);
for (const t of teamsInInj) if (!teamsInGames.has(t)) fail(`injury team ${t} not in games`);
if (inj.length !== 254) fail(`injury rows ${inj.length} != 254 (reconciled count)`);
if (inj.some((r) => !/^Verified/.test(r.verification))) fail('injury row without Verified status');
notes.push(`injury rows ${inj.length}; teams with rows ${teamsInInj.size}; games ${games.length}; teams ${teamsInGames.size}`);

// 3) HTML: internal links resolve; external links are https; table rows carry a source or UNVERIFIED flag.
const docs = ROOT + 'docs/';
const pages = readdirSync(docs).filter((f) => f.endsWith('.html'));
for (const p of pages) {
  const html = readFileSync(docs + p, 'utf8');
  for (const m of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    const u = m[1];
    if (/^https?:\/\//.test(u)) { if (!u.startsWith('https://')) fail(`${p}: non-https link ${u}`); continue; }
    if (u.startsWith('#') || u.startsWith('mailto:')) continue;
    const path = u.split('#')[0].split('?')[0];
    if (!existsSync(docs + path)) fail(`${p}: broken internal link ${u}`);
  }
  const tbodies = [...html.matchAll(/<table id="([^"]+)"[\s\S]*?<tbody>([\s\S]*?)<\/tbody>/g)];
  for (const [, id, body] of tbodies) {
    if (id === 'gates') continue;
    const rows = body.split('<tr>').slice(1);
    rows.forEach((row, i) => { if (!/href="https:\/\//.test(row) && !/UNVERIFIED|n\/a/.test(row)) fail(`${p} table ${id} row ${i + 1}: no source link or UNVERIFIED flag`); });
    notes.push(`${p} #${id}: ${rows.length} rows checked`);
  }
}
console.log(notes.join('\n'));
if (errors.length) { console.error('\nVERIFICATION FAILED:\n' + errors.join('\n')); process.exit(1); }
console.log(`\nOK – ${pages.length} pages, no broken internal links, all external links https, all rows sourced or flagged.`);
