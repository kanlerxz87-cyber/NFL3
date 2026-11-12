#!/usr/bin/env python3
"""Validate local links and source links for the generated static site."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = {'www.nfl.com','support.nfl.com','static.clubs.nfl.com','tsapps.nist.gov','docs.github.com'}

class Check(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path = path; self.links = []; self.ids = set(); self.in_tbody = False; self.row = None; self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        if tag in ('a','link','script'):
            value = attrs.get('href') if tag in ('a','link') else attrs.get('src')
            if value: self.links.append(value)
            if tag == 'a' and self.row is not None and value: self.row.append(value)
        if tag == 'tbody': self.in_tbody = True
        if tag == 'tr' and self.in_tbody: self.row = []
    def handle_endtag(self, tag):
        if tag == 'tr' and self.row is not None: self.rows.append(self.row); self.row = None
        if tag == 'tbody': self.in_tbody = False

pages = [ROOT/'index.html', *sorted((ROOT/'pages').glob('*.html'))]
assert len(pages) == 6, f'Expected six pages; got {len(pages)}'
parsed = {}
for path in pages:
    parser = Check(path); parser.feed(path.read_text(encoding='utf-8')); parsed[path] = parser
errors = []
for path, page in parsed.items():
    for i, row in enumerate(page.rows, 1):
        if not any(urlparse(link).scheme == 'https' and urlparse(link).hostname in OFFICIAL for link in row):
            errors.append(f'{path.relative_to(ROOT)}: row {i} missing official source')
    for link in page.links:
        u = urlparse(link)
        if u.scheme or u.netloc:
            if u.scheme != 'https' or u.hostname not in OFFICIAL: errors.append(f'{path.relative_to(ROOT)}: unexpected external link {link}')
            continue
        target = (path.parent / unquote(u.path)).resolve() if u.path else path
        if not target.is_relative_to(ROOT) or not target.is_file(): errors.append(f'{path.relative_to(ROOT)}: broken link {link}'); continue
        if u.fragment and target in parsed and u.fragment not in parsed[target].ids: errors.append(f'{path.relative_to(ROOT)}: missing fragment {link}')
if errors: raise SystemExit('\n'.join(errors))
print(f'Checked {len(pages)} pages, {sum(len(p.rows) for p in parsed.values())} sourced rows and all local links.')
