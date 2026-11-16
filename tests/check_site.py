from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
class Check(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path = path; self.in_row = False; self.header = False; self.source = False; self.errors = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'tr': self.in_row = True; self.header = False; self.source = False
        if self.in_row and tag == 'th': self.header = True
        if tag in ('a', 'link'):
            href = a.get('href', '')
            if self.in_row and href.startswith('https://'): self.source = True
            if href and not urlsplit(href).scheme and not href.startswith('#'):
                if not (self.path.parent / urlsplit(href).path).is_file(): self.errors.append(f'broken local link: {href}')
    def handle_endtag(self, tag):
        if tag == 'tr':
            if self.in_row and not self.header and not self.source: self.errors.append('table row missing source')
            self.in_row = False

class ReviewRows(HTMLParser):
    """Collect the first flagged-review table's data rows and their evidence links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tbody_depth = 0
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs_map = dict(attrs)
        if tag == 'tbody':
            self.tbody_depth += 1
        elif tag == 'tr' and self.tbody_depth:
            self.row = {'cells': [], 'links': set()}
        elif tag == 'td' and self.row is not None:
            self.cell = []
        elif tag == 'a' and self.row is not None:
            href = attrs_map.get('href')
            if href:
                self.row['links'].add(href)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.row is not None and self.cell is not None:
            self.row['cells'].append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
            self.cell = None
        elif tag == 'tbody' and self.tbody_depth:
            self.tbody_depth -= 1

errors = []
for path in ROOT.rglob('*.html'):
    content = path.read_text(encoding='utf-8')
    for line_number, line in enumerate(content.splitlines(), 1):
        if line.startswith(('<<<<<<<', '=======', '>>>>>>>')):
            errors.append(f'{path.relative_to(ROOT)}:{line_number}: unresolved merge-conflict marker')
    if path.parent == ROOT:
        p = Check(path); p.feed(content); errors += [f'{path.name}: {e}' for e in p.errors]
metrics = subprocess.run(
    [sys.executable, str(ROOT / 'scripts' / 'sync_landing_metrics.py'), '--check'],
    cwd=ROOT, capture_output=True, text=True,
)
if metrics.returncode:
    errors.append('landing metrics are stale: ' + (metrics.stdout or metrics.stderr).strip())
ops = subprocess.run(
    [sys.executable, str(ROOT / 'ops-center' / 'scripts' / 'verify.py')],
    cwd=ROOT, capture_output=True, text=True,
)
if ops.returncode:
    errors.append('ops-centre verification failed: ' + (ops.stdout or ops.stderr).strip())
# The questions and suggestion-review surfaces are explicit product requirements.
# Keep them reachable from both the public landing page and the repository quick start;
# the review controls are a hand-off only and must never imply that a choice edits the repo.
landing = (ROOT / 'index.html').read_text(encoding='utf-8')
readme = (ROOT / 'README.md').read_text(encoding='utf-8')
suggestion_page = ROOT / 'ops-center' / 'suggestions.html'
questions_page = ROOT / 'ops-center' / 'questions.html'
derived = json.loads((ROOT / 'ops-center' / 'data' / 'derived.json').read_text(encoding='utf-8'))
proposal_count = len(derived.get('suggestions', []))
question_count = len(derived.get('questions', []))
for label, target in (
    ('suggestion review', 'ops-center/suggestions.html'),
    ('decision questions', 'ops-center/questions.html'),
    ('full decision readiness', 'readiness.html'),
):
    if f'href="{target}"' not in landing:
        errors.append(f'index.html: missing direct {label} link ({target})')
if 'ops-center/suggestions.html' not in readme:
    errors.append('README.md: missing direct suggestion-review link')
if not suggestion_page.is_file() or not questions_page.is_file():
    errors.append('ops-center: question or suggestion-review page is missing')
else:
    suggestion_text = suggestion_page.read_text(encoding='utf-8')
    for action in ('Approve', 'Defer', 'Reject', 'Export decisions (JSON)'):
        if action not in suggestion_text:
            errors.append(f'ops-center/suggestions.html: missing review action {action!r}')
    if 'No selection on this page changes a file in the repository.' not in suggestion_text:
        errors.append('ops-center/suggestions.html: missing hand-off-only disclaimer')
if f'{proposal_count} proposals' not in landing or f'{proposal_count} proposals' not in readme:
    errors.append(f'suggestions count is not represented on both entry points ({proposal_count})')
if f'{question_count} questions' not in landing:
    errors.append(f'index.html: questions count does not match the consolidated register ({question_count})')
review = (ROOT / 'review.html').read_text(encoding='utf-8')
review_rows = ReviewRows()
review_rows.feed(review)
flag_rows = {}
for row in review_rows.rows:
    cells = row['cells']
    if cells and cells[0] in ('F-FI01', 'F-FI02'):
        flag_rows.setdefault(cells[0], []).append(row)
integration_rows = [
    row for row in review_rows.rows
    if row['cells'] and row['cells'][0].startswith('F-FI')
]
integration_ids = [row['cells'][0] for row in integration_rows]
if len(integration_rows) > 2:
    errors.append(f'review.html: expected no more than two integration flags, found {len(integration_rows)}')
if sorted(integration_ids) != ['F-FI01', 'F-FI02']:
    errors.append(f'review.html: expected only F-FI01 and F-FI02, found {integration_ids}')

required_flag_links = {
    'F-FI01': (
        'origination/leaderboard.html', 'origination/data/leaderboard.json',
        'pricing/PRICE_DATA_POLICY.md', 'https://www.nfl.com/standings/',
        'https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL',
    ),
    'F-FI02': (
        'origination/requirements.html', 'origination/correlations.html',
        'origination/data/correlations.json', 'readiness.html',
        'https://www.nfl.com/standings/',
    ),
}
for flag, required_links in required_flag_links.items():
    matches = flag_rows.get(flag, [])
    if len(matches) != 1:
        errors.append(f'review.html: expected exactly one data row for {flag}, found {len(matches)}')
        continue
    row = matches[0]
    if len(row['cells']) != 6:
        errors.append(f'review.html: {flag} row has {len(row["cells"])} cells, expected 6')
    missing = [href for href in required_links if href not in row['links']]
    if missing:
        errors.append(f'review.html: {flag} row is missing evidence links: {missing}')
    text = ' '.join(row['cells']).casefold()
    required_text = (
        ('titled “leaderboard”', 'retrospective brier-skill', 'prospective performance', 'no row is validated')
        if flag == 'F-FI01' else
        ('official/official', 'community/official', 'official-only', 'game-level descriptive',
         'readiness r4', 'leg-level settlement history', 'does not clear r4')
    )
    for phrase in required_text:
        if phrase not in text:
            errors.append(f'review.html: {flag} row is missing the qualification {phrase!r}')

for stale_callout in (
    'No strategy has passed eligibility gates or been approved for wagering.',
    'No current lines, injury assignments, projections, correlations, strategy returns or leaderboard winners are published.',
    'This repository contains no collected market dataset, model, or verified strategy results.',
):
    if stale_callout in review:
        errors.append(f'review.html: superseded no-results callout remains: {stale_callout}')
for phrase in (
    'No strategy has demonstrated all prospective eligibility gates for live use',
    'Retrospective probabilities and scores are published for research',
):
    if phrase not in review:
        errors.append(f'review.html: corrected status callout is missing {phrase!r}')
for phrase in (
    'retrospective Brier-skill benchmark', 'community inputs',
    'do not establish prospective performance',
):
    if phrase not in readme:
        errors.append(f'README.md: missing retrospective-origination caveat {phrase!r}')
for phrase in (
    'one 2026 Week 10 injury/inactives pair', '15 designations uncovered',
    'descriptive sample fractions', 'not forecasts of whether players will play',
    'raw_bytes_retained: false', 'reconstructed markup', 'not byte-exact NFL captures',
):
    if phrase not in readme:
        errors.append(f'README.md: missing injury-archive coverage/provenance caveat {phrase!r}')

if errors: raise SystemExit('\n'.join(errors))
print('Site checks passed: local links, row citations, readiness/ops metrics, and decision-review routes.')
