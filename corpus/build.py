#!/usr/bin/env python3
"""Build corpus.html: the published pre-registered backtest corpus.

Deterministic; renders only committed artifacts. The full 136-row log is shown
with its official schedule-page link on every row. Blank scores render as blanks.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'corpus'
OUT = ROOT / 'corpus.html'
REPO_BLOB = 'https://github.com/kanlerxz87-cyber/NFL3/blob/main/'


def e(text) -> str:
    return html.escape(str(text if text is not None else ''))


def table(headers, rows, caption) -> str:
    head = ''.join('<th scope="col">' + e(h) + '</th>' for h in headers)
    return ('<div class="table-wrap"><table><caption>' + e(caption) + '</caption><thead><tr>' + head +
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')


def blob(path: str, label: str = '') -> str:
    return ('<a href="' + REPO_BLOB + e(path) + '" target="_blank" rel="noopener noreferrer">' +
            e(label or path) + ' ↗</a>')


def cell(value: str, blank_label: str = '') -> str:
    if value == '':
        return '<td><span class="blank">' + e(blank_label or '\u2014') + '</span></td>'
    return '<td>' + e(value) + '</td>'


def build() -> str:
    manifest = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
    rows = list(csv.DictReader((ROOT / manifest['frozen_file']).open(newline='', encoding='utf-8')))
    frozen_hash = hashlib.sha256((ROOT / manifest['frozen_file']).read_bytes()).hexdigest()

    prefix = (ROOT / 'index.html').read_text(encoding='utf-8')
    prefix = prefix[: prefix.index('<div class="content">')]
    prefix = prefix.replace('<title>A clearer view of the game | NFL3</title>',
                            '<title>Backtest corpus | NFL3</title>')
    prefix = prefix.replace('<a aria-current=page href="index.html"><span>01</span>Overview</a>',
                            '<a href="index.html"><span>01</span>Overview</a>')
    prefix = prefix.replace('<a href="readiness.html"><span>D</span>Decision readiness</a>',
                            '<a href="readiness.html"><span>D</span>Decision readiness</a>'
                            '<a aria-current=page href="corpus.html"><span>C</span>Backtest corpus</a>')

    b = ['<div class="content">']
    b.append('<div class="eyebrow"><span></span> PRE-REGISTERED BACKTEST CORPUS</div>')
    b.append('<h1>The 136-game log, frozen before any evaluation existed.</h1>')
    b.append('<p class="lede">Weeks 1\u20139 of the 2026 season, copied once from the verified game log '
             'and frozen with a hash. The split and the evaluation gates were committed before any '
             'backtest ran \u2014 there are still <b>0 evaluations</b>. Backtest numbers from this '
             'corpus never appear on the <a href="ops-center/leaderboard.html">leaderboard</a>; the '
             'leaderboard admits only pre-registered strategies with forecasts recorded before kickoff.</p>')
    b.append('<div class="notice"><b>Registration.</b> ' + blob('corpus/PRE_REGISTRATION.md', 'The rules file') +
             ' was committed 2026-11-15; its creating commit is the registration. The frozen copy hash is '
             '<code>' + e(frozen_hash[:16]) + '\u2026</code>. One game (Week 2, Washington at Dallas) is '
             'published as a hidden score on the official pages; its cells stay blank and any evaluation '
             'skips it. ' + blob('pricing/PRICE_DATA_POLICY.md', 'Price-dependent output is fail-closed') +
             ' until a licensed price source exists.</div>')
    chips = [('Games', str(len(rows))), ('Settled', str(manifest['window']['settled'])),
             ('Hidden score', str(manifest['window']['unsettled_hidden_score'])),
             ('Evaluations', '0'), ('Leaderboard numbers', '0')]
    b.append('<div class="notice"><b>State:</b> ' +
             ''.join('<span class="chip">' + e(k) + ': <b>' + e(v) + '</b></span>' for k, v in chips) + '</div>')

    b.append('<div class="section-head"><div><div class="section-label">01 / SPLIT</div>'
             '<h2>Train, validation, holdout \u2014 frozen before fitting.</h2>'
             '<p>Chronological within the only verified season. The holdout is touched once per '
             'frozen rule set; a decision made after seeing holdout results invalidates it.</p></div></div>')
    split = manifest['split']
    rows_html = []
    for name, use in (('train', 'fitting, feature decisions'), ('validation', 'model/threshold selection only'),
                      ('holdout', 'touched once, after the rule is frozen')):
        blk = split[name]
        rows_html.append('<tr><td><b>' + e(name) + '</b></td>' + cell('Weeks ' + str(blk['weeks'][0]) + '\u2013' + str(blk['weeks'][-1])) +
                         cell(str(blk['games'])) + cell(use) +
                         '<td>' + blob('corpus/PRE_REGISTRATION.md', 'PRE_REGISTRATION §2') + '</td></tr>')
    b.append(table(['Block', 'Window', 'Games', 'Use', 'Source'], rows_html,
                   'Frozen split of the 136-game corpus.'))

    b.append('<div class="section-head"><div><div class="section-label">02 / THE LOG</div>'
             '<h2>Every game in the corpus, with its official source on the row.</h2>'
             '<p>Final scores were read from the official NFL schedule pages. The hidden-score game '
             'keeps blank cells \u2014 it is never inferred.</p></div></div>')
    rows_html = []
    for r in rows:
        settled = r['away_score'] != '' and r['home_score'] != ''
        rows_html.append('<tr>' + cell(r['week']) + cell(r['kickoff_date_et']) + cell(r['away_team']) +
                         cell(r['away_score'], 'hidden' if not settled else '') + cell(r['home_team']) +
                         cell(r['home_score'], 'hidden' if not settled else '') +
                         ('<td>' + e(r['verification']) + '</td>' if r['verification'] else
                          '<td><span class="blank">not recorded</span></td>') +
                         '<td><a class="source" href="' + e(r['source_url']) +
                         '" target="_blank" rel="noopener noreferrer">official schedule ↗</a></td></tr>')
    b.append(table(['Wk', 'Kickoff (ET)', 'Away', 'Score', 'Home', 'Score', 'Verification note', 'Source'],
                   rows_html, 'The frozen 136-game backtest corpus (corpus/games_2026_w1_9.csv).'))

    b.append('<div class="section-head"><div><div class="section-label">03 / RULES</div>'
             '<h2>What may be computed, and what is forbidden.</h2></div></div>')
    rules = [('Allowed', 'descriptive counts, labelled backtest-corpus output, pre-registered ablations on the split above',
              'always labelled "backtest corpus \u2014 not a leaderboard result"'),
             ('Forbidden', 'ROI, profit, edge or CLV of any kind',
              'blocked by ' + 'the price-data policy until licensed prices exist'),
             ('Forbidden', 'any corpus number in a leaderboard result cell',
              'the leaderboard admits only pre-kickoff forecasts settled from official results'),
             ('Forbidden', 'ranking strategies by realised return',
              'rejected in the brief; proper scores with uncertainty are the rank basis'),
             ('Holdout rule', 'the holdout is evaluated once per frozen rule set',
              'a post-holdout decision invalidates the holdout')]
    rows_html = ['<tr>' + cell(a) + cell(b2) + cell(c) + '<td>' + blob('corpus/PRE_REGISTRATION.md', 'PRE_REGISTRATION §3') +
                 '</td></tr>' for a, b2, c in rules]
    b.append(table(['Rule', 'What', 'Condition', 'Source'], rows_html,
                   'Evaluation rules frozen with the registration.'))

    b.append('<div class="section-head"><div><div class="section-label">04 / GATES</div>'
             '<h2>Every claim of skill from this corpus passes these first.</h2></div></div>')
    gates = [('Pre-registration', 'rule text and threshold committed before the evaluated window opened'),
             ('Proper scoring', 'Brier or log score with a game-cluster interval; win rate is not a skill measure'),
             ('Multiplicity', 'one correction across every rule tried'),
             ('Luck removal', 'the same evaluation run against both controls: random side and favourites-only'),
             ('Label', 'the output says "backtest corpus" wherever it appears')]
    rows_html = ['<tr>' + cell(g) + cell(t) + '<td>' + blob('corpus/PRE_REGISTRATION.md', 'PRE_REGISTRATION §4') +
                 '</td></tr>' for g, t in gates]
    b.append(table(['Gate', 'Test', 'Source'], rows_html, 'Evaluation gates.'))

    b.append('<footer>NFL3 RESEARCH DESK <span>Built for informed decisions, not guaranteed outcomes.</span>'
             '</footer></div></main></div></body></html>')
    return prefix + '\n'.join(b)


def main() -> int:
    OUT.write_text(build(), encoding='utf-8')
    print('wrote corpus.html')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
