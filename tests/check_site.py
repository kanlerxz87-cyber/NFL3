from html.parser import HTMLParser
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
if errors: raise SystemExit('\n'.join(errors))
print('Site checks passed: local links, row citations, decision-readiness and ops-centre metrics.')
