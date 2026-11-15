#!/usr/bin/env python3
"""Build pricing.html (the published price-snapshot store and policy page) and
regenerate the flat price view from the immutable snapshot files.

Deterministic: nothing here reads the wall clock or the network. The page renders
the policy decision, the source register, the store schema, the empty registers
and the residual schedule exactly as committed. Empty registers render as explicit
empty states; a zero never appears where an unknown does.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / 'pricing'
OUT = ROOT / 'pricing.html'
REPO_BLOB = 'https://github.com/kanlerxz87-cyber/NFL3/blob/main/'
NFL_FAQ = ('https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-'
           'or-the-NFL-app-am-I-betting-with-the-NFL')

PUBLISHED_COLS = ['market_id', 'game_id', 'season', 'week', 'market_type', 'market_side', 'price',
                  'price_format', 'price_as_of', 'fetched_at_utc', 'phase', 'source_id', 'licence_id',
                  'capture_hash', 'supersedes']


def e(text) -> str:
    return html.escape(str(text if text is not None else ''))


def read_csv(rel: str) -> list:
    with (ROOT / rel).open(newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def snapshot_rows() -> list:
    rows = []
    for p in sorted((PRICING / 'snapshots').glob('*.jsonl')):
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_prices_csv(rows: list) -> None:
    with (PRICING / 'prices.csv').open('w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=PUBLISHED_COLS, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in PUBLISHED_COLS})


def table(headers: list, rows: list, caption: str) -> str:
    head = ''.join('<th scope="col">' + e(h) + '</th>' for h in headers)
    return ('<div class="table-wrap"><table><caption>' + e(caption) + '</caption><thead><tr>' + head +
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')


def blob(path: str, label: str = '') -> str:
    return ('<a href="' + REPO_BLOB + e(path) + '" target="_blank" rel="noopener noreferrer">' +
            e(label or path) + ' ↗</a>')


def faq(label: str = 'NFL odds FAQ') -> str:
    return ('<a class="source" href="' + NFL_FAQ + '" target="_blank" rel="noopener noreferrer">' +
            e(label) + ' ↗</a>')


def td(value: str) -> str:
    if value == '':
        return '<td><span class="blank">—</span></td>'
    return '<td>' + e(value) + '</td>'


def build() -> str:
    prices = snapshot_rows()
    write_prices_csv(prices)
    sources = read_csv('pricing/sources.csv')
    originated = read_csv('pricing/originated_markets.csv')
    residuals = read_csv('pricing/residuals.csv')
    schema = json.loads((PRICING / 'schema.json').read_text(encoding='utf-8'))
    licensed = [s for s in sources if s['status'] == 'licensed']

    prefix = (ROOT / 'index.html').read_text(encoding='utf-8')
    prefix = prefix[: prefix.index('<div class="content">')]
    prefix = prefix.replace('<title>A clearer view of the game | NFL3</title>',
                            '<title>Pricing &amp; price store | NFL3</title>')
    prefix = prefix.replace('<a aria-current=page href="index.html"><span>01</span>Overview</a>',
                            '<a href="index.html"><span>01</span>Overview</a>')
    prefix = prefix.replace('<a href="readiness.html"><span>D</span>Decision readiness</a>',
                            '<a href="readiness.html"><span>D</span>Decision readiness</a>'
                            '<a aria-current=page href="pricing.html"><span>$</span>Price store</a>')

    b = ['<div class="content">']
    b.append('<div class="eyebrow"><span></span> PRICING &amp; PRICE STORE</div>')
    b.append('<h1>Price snapshots, the price-data policy, and the residual table.</h1>')
    b.append('<p class="lede">The store records an opening and a closing number for every market this '
             'project originates, with the quote\u2019s own time and the capture clock time. The policy '
             'decides, before any backtest exists, what price data may be used and what may be '
             'published from it. Today the store holds zero rows because zero sources are licensed. '
             'That is the correct state, and it is why every result cell on the '
             '<a href="ops-center/leaderboard.html">leaderboard</a> is blank.</p>')
    b.append('<div class="notice"><b>Fail-closed by policy.</b> '
             '<a href="pricing/PRICE_DATA_POLICY.md">The adopted price-data policy</a> forbids publishing '
             'any backtest, ROI, closing-line-value or ranking number until every price row behind it '
             'carries a named source, a named licence with permitted use, and both the quote\u2019s own '
             'as-of time and the capture clock time. The undated moneyline columns in the community file '
             'are not price data under this policy. ' + faq() + '</div>')

    chips = [('Store rows', str(len(prices))), ('Licensed sources', str(len(licensed))),
             ('Markets originated', str(len(originated))), ('Residual rows', str(len(residuals))),
             ('Backtests published', '0')]
    b.append('<div class="notice"><b>State:</b> ' +
             ''.join('<span class="chip">' + e(k) + ': <b>' + e(v) + '</b></span>' for k, v in chips) + '</div>')

    b.append('<div class="section-head"><div><div class="section-label">01 / SOURCE REGISTER</div>'
             '<h2>Every candidate price source, its terms and its permitted use.</h2>'
             '<p>A blank licence means the source may not be used. Only a row whose status is '
             '<b>licensed</b> may be ingested into the store.</p></div></div>')
    rows = []
    for s in sources:
        rows.append('<tr>' + td(s['source_id']) + td(s['class']) + td(s['example']) +
                    td(s['terms_status']) + td(s['permitted_use']) +
                    '<td><b>' + e(s['status']) + '</b></td>' +
                    '<td><a href="' + e(s['source_link']) + '" target="_blank" rel="noopener noreferrer">source ↗</a></td></tr>')
    b.append(table(['ID', 'Class', 'Example', 'Terms in writing', 'Permitted use', 'Status', 'Source'],
                   rows, 'Price source register (from pricing/sources.csv). 0 licensed sources.'))

    b.append('<div class="section-head"><div><div class="section-label">02 / STORE SCHEMA</div>'
             '<h2>What every snapshot row records.</h2>'
             '<p>The row format is fixed by the adopted policy. Corrections are new rows that point '
             'back at the row they replace; captures are never rewritten.</p></div></div>')
    rows = []
    for field, spec in schema['price_snapshot_row']['properties'].items():
        required = 'required' if field in schema['price_snapshot_row']['required'] else 'optional'
        meaning = spec.get('description') or spec.get('pattern') or str(spec.get('enum', '')) or ''
        rows.append('<tr><td><code>' + e(field) + '</code></td>' + td(spec.get('type', '')) +
                    td(required) + td(meaning) + '<td>' + blob('pricing/schema.json', 'schema.json') + '</td></tr>')
    b.append(table(['Field', 'Type', 'Rule', 'Meaning', 'Source'], rows,
                   'price_snapshot_row schema (pricing/schema.json).'))

    b.append('<div class="section-head"><div><div class="section-label">03 / ORIGINATED MARKETS</div>'
             '<h2>Every market we originate, in order: side, then total, then moneyline.</h2>'
             '<p>The register is empty because no market has been originated yet: origination needs a '
             'verified model comparison, which needs prices, which need a licensed source.</p></div></div>')
    if originated:
        cols = ['market_id', 'game_id', 'market_type', 'originated_at_utc', 'our_fair_line', 'inputs_ref', 'status']
        rows = ['<tr>' + ''.join(td(r.get(c, '')) for c in cols) +
                '<td>' + blob('pricing/originated_markets.csv', 'register') + '</td></tr>' for r in originated]
    else:
        rows = ['<tr><td colspan="8"><b>0 rows.</b> No market has been originated. '
                'The register stays empty rather than being filled with a placeholder. ' +
                blob('pricing/originated_markets.csv', 'originated_markets.csv') + ' ' +
                blob('pricing/PRICE_DATA_POLICY.md', 'policy §3') + '</td></tr>']
    b.append(table(['Market', 'Game', 'Type', 'Originated (UTC)', 'Our fair line', 'Probability + inputs',
                    'Status', 'Source'], rows, 'Originated-market register.'))

    b.append('<div class="section-head"><div><div class="section-label">04 / PRICE SNAPSHOTS</div>'
             '<h2>Opening and closing numbers, with the capture clock time beside each quote.</h2>'
             '<p>Append-only. Each row keeps its capture hash so the quote can be replayed byte for byte.</p></div></div>')
    if prices:
        cols = ['market_id', 'market_side', 'price', 'price_format', 'price_as_of',
                'fetched_at_utc', 'phase', 'licence_id', 'capture_hash']
        rows = ['<tr>' + ''.join(td(r.get(c, '')) for c in cols) +
                '<td>' + blob('pricing/prices.csv', 'prices.csv') + '</td></tr>' for r in prices]
    else:
        rows = ['<tr><td colspan="10"><b>0 rows.</b> No licensed price source exists, so the store is '
                'open but unpopulated. Ingestion is fail-closed: '
                '<code>python3 pricing/ingest.py</code> refuses a payload without source, licence, '
                'capture time and hash. ' +
                blob('pricing/prices.csv', 'prices.csv') + ' ' +
                blob('pricing/snapshots/README.md', 'snapshots/') + '</td></tr>']
    b.append(table(['Market', 'Side', 'Price', 'Format', 'Quote as-of', 'Fetched (UTC)', 'Phase',
                    'Licence', 'Capture hash', 'Source'], rows,
                   'Price-snapshot register (flat view of pricing/snapshots/).'))

    b.append('<div class="section-head"><div><div class="section-label">05 / RESIDUALS</div>'
             '<h2>Our fair line, the market line, and the difference \u2014 separate columns.</h2>'
             '<p>Published on the schedule below from day one. The market and difference columns are '
             'blank until a licensed market line exists; a blank is not a zero.</p></div></div>')
    if residuals:
        cols = ['run_id', 'run_at_utc', 'game_id', 'market_id', 'our_fair_line',
                'market_line', 'difference', 'our_line_ref']
        rows = ['<tr>' + ''.join(td(r.get(c, '')) for c in cols) +
                '<td>' + blob('pricing/residuals.csv', 'residuals.csv') + '</td></tr>' for r in residuals]
    else:
        rows = ['<tr><td colspan="9"><b>0 rows.</b> No scheduled run has produced a residual, because '
                'no licensed market line exists to take a residual against. ' +
                blob('pricing/residuals.csv', 'residuals.csv') + ' ' + faq('what the market line is not') + '</td></tr>']
    b.append(table(['Run', 'Run time (UTC)', 'Game', 'Market', 'Our fair line', 'Market line',
                    'Difference', 'Model + inputs', 'Source'], rows,
                   'Residual register: our line, market line, difference.'))

    b.append('<div class="section-head"><div><div class="section-label">06 / SCHEDULE</div>'
             '<h2>When residuals and prices are captured.</h2>'
             '<p>The schedule is decided by the policy now, before any price exists.</p></div></div>')
    sched = [('Pre-kickoff', 'T\u221224h of kickoff', 'market quote + our fair line', 'residual row'),
             ('Final pre-kickoff', 'T\u22121h of kickoff', 'market quote + our fair line', 'residual row'),
             ('Market close', 'first capture \u2265 30 min after scheduled kickoff', 'closing quote',
              'closing residual row + store close_price'),
             ('Weekly summary', 'Tuesdays 14:00 UTC', 'the week\u2019s rows', 'one diff row per market')]
    rows = ['<tr>' + td(a) + td(a2) + td(a3) + td(a4) + '<td>' + blob('pricing/PRICE_DATA_POLICY.md', 'policy §5') + '</td></tr>'
            for a, a2, a3, a4 in sched]
    b.append(table(['Run', 'Time', 'Captured', 'Published', 'Source'], rows,
                   'Residual and price capture schedule (adopted 2026-11-15).'))

    b.append('<div class="section-head"><div><div class="section-label">07 / GATES</div>'
             '<h2>What this policy blocks, and the number that would clear it.</h2></div></div>')
    gates = [('Backtest / ROI / CLV publication',
              'every backtest number anywhere on the site',
              'store rows cover the whole evaluation sample under a licence that permits derived publication'),
             ('Residual market and difference columns', 'each residual row',
              'a licensed store row at the stated run time'),
             ('Leaderboard rank / reward / edge cells', 'any ranking',
              'pre-registered gates passed on prospective results; corpus backtests never fill these cells'),
             ('Vig-free consensus decomposition', 'the decomposition view',
              'at least two licensed two-sided sources at the same capture time'),
             ('Store ingestion', 'any payload',
              'named source + named licence with permitted use + as-of time + capture clock time + hash')]
    rows = ['<tr>' + td(g) + td(blocks) + td(clears) +
            '<td>' + blob('pricing/PRICE_DATA_POLICY.md', 'policy §4') + ' ' + faq() + '</td></tr>'
            for g, blocks, clears in gates]
    b.append(table(['Gate', 'Blocks', 'Clears when', 'Source'], rows, 'Publication gates.'))

    b.append('<div class="section-head"><div><div class="section-label">08 / OPEN QUESTIONS</div>'
             '<h2>Decisions this record does not make.</h2></div></div>')
    opens = [('Which book or vendor supplies the licensed feed',
              '0 signed agreements', 'one signed agreement naming feed, fields, depth and publication rights'),
             ('Subscription budget and redistribution rights', 'blank \u2014 owner decision',
              'a written budget and rights grant recorded before ingestion'),
             ('Operator void/push rules for combo settlement', '0 rules captured',
              'the operator\u2019s published rules for each offered combo')]
    rows = ['<tr>' + td(q) + td(now) + td(clears) +
            '<td><a href="readiness.html">readiness register</a> ' + blob('pricing/PRICE_DATA_POLICY.md', 'policy §6') + '</td></tr>'
            for q, now, clears in opens]
    b.append(table(['Open question', 'Now', 'Clears when', 'Source'], rows,
                   'Open decisions with their blocking gates.'))
    b.append('<footer>NFL3 RESEARCH DESK <span>Built for informed decisions, not guaranteed outcomes.</span>'
             '</footer></div></main></div></body></html>')
    return prefix + '\n'.join(b)


def main() -> int:
    OUT.write_text(build(), encoding='utf-8')
    prices = snapshot_rows()
    print('wrote pricing.html; store rows: ' + str(len(prices)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
