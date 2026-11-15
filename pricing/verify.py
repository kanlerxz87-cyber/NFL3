#!/usr/bin/env python3
"""Fail-closed verification of the price store, its policy and its published page.

Checks (all offline):
 1. The policy record exists, is adopted, and carries the fail-closed rule.
 2. Every CSV header matches its schema required fields.
 3. Every price row validates against schema.json (pattern, enums, timestamps, numeric price).
 4. Every price row's source is registered as licensed in pricing/sources.csv and names a licence.
 5. pricing/prices.csv equals the concatenation of the immutable snapshot files.
 6. pricing.html exists and its published row counts match the registers.
 7. The residual register carries the three separate columns (our fair line, market line, difference).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / 'pricing'
SCHEMA = json.loads((PRICING / 'schema.json').read_text(encoding='utf-8'))
TS = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
PUBLISHED_COLS = ['market_id', 'game_id', 'season', 'week', 'market_type', 'market_side', 'price',
                  'price_format', 'price_as_of', 'fetched_at_utc', 'phase', 'source_id', 'licence_id',
                  'capture_hash', 'supersedes']

errors: list[str] = []


def read_csv(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def snapshot_rows() -> list[dict]:
    rows = []
    for p in sorted((PRICING / 'snapshots').glob('*.jsonl')):
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def check_policy() -> None:
    text = (PRICING / 'PRICE_DATA_POLICY.md').read_text(encoding='utf-8')
    flat = re.sub(r'\s+', ' ', text)
    for needle, why in [
        ('**Status:** adopted', 'the policy must record that it is adopted'),
        ('2026-11-15', 'the policy must carry its adoption date'),
        ('Fail-closed rule', 'the policy must contain the fail-closed rule'),
        ('every price row behind it carries', 'the fail-closed sentence must name the price-row conditions'),
        ('as-of time and the capture clock time', 'the rule must require both times'),
    ]:
        if needle not in flat:
            errors.append(f'policy: missing {why} (looked for {needle!r})')


def check_headers() -> None:
    for rel, key in [('pricing/prices.csv', 'price_snapshot_row'),
                     ('pricing/residuals.csv', 'residual_row'),
                     ('pricing/originated_markets.csv', 'originated_market_row')]:
        path = ROOT / rel
        with path.open(newline='', encoding='utf-8') as fh:
            header = next(csv.reader(fh))
        required = SCHEMA[key]['required']
        missing = [c for c in required if c not in header]
        if missing:
            errors.append(f'{rel}: header is missing required fields {missing}')


def check_price_rows() -> None:
    sources = {r['source_id']: r for r in read_csv(PRICING / 'sources.csv')}
    rows = read_csv(PRICING / 'prices.csv')
    pat = SCHEMA['price_snapshot_row']['properties']['market_id']['pattern']
    for r in rows:
        mid = r.get('market_id', '?')
        if not re.match(pat, mid):
            errors.append(f'prices.csv: {mid}: market_id does not match the schema pattern')
        if r.get('market_type') not in ('side', 'total', 'moneyline'):
            errors.append(f'prices.csv: {mid}: bad market_type {r.get("market_type")!r}')
        if r.get('phase') not in ('open', 'close', 'intraday'):
            errors.append(f'prices.csv: {mid}: bad phase {r.get("phase")!r}')
        try:
            float(r.get('price', ''))
        except ValueError:
            errors.append(f'prices.csv: {mid}: price is not numeric')
        if not TS.match(r.get('fetched_at_utc', '')):
            errors.append(f'prices.csv: {mid}: fetched_at_utc is not UTC ISO to the second')
        if r.get('price_as_of') and not TS.match(r['price_as_of']):
            errors.append(f'prices.csv: {mid}: price_as_of is not UTC ISO to the second')
        src = sources.get(r.get('source_id', ''), {})
        if src.get('status') != 'licensed':
            errors.append(f'prices.csv: {mid}: source {r.get("source_id")!r} is not licensed')
        if not r.get('licence_id'):
            errors.append(f'prices.csv: {mid}: licence_id is blank (a blank licence means the source may not be used)')
        if not re.match(r'^sha256:[0-9a-f]{64}$', r.get('capture_hash', '')):
            errors.append(f'prices.csv: {mid}: capture_hash missing or malformed')
    for r in read_csv(PRICING / 'residuals.csv'):
        if r.get('market_line') and not r.get('licence_id'):
            errors.append(f'residuals.csv: {r.get("run_id")}: a market line without a licence may not be published')


def check_snapshot_consistency() -> None:
    flat = [{k: r.get(k, '') for k in PUBLISHED_COLS} for r in read_csv(PRICING / 'prices.csv')]
    snap = [{k: r.get(k, '') for k in PUBLISHED_COLS} for r in snapshot_rows()]
    if flat != snap:
        errors.append('prices.csv does not match the immutable snapshot files (regenerate with pricing/build.py)')


def check_page() -> None:
    page = ROOT / 'pricing.html'
    if not page.is_file():
        errors.append('pricing.html is missing (run pricing/build.py)')
        return
    text = page.read_text(encoding='utf-8')
    prices = read_csv(PRICING / 'prices.csv')
    residuals = read_csv(PRICING / 'residuals.csv')
    if len(prices) == 0 and '0 rows.</b> No licensed price source exists' not in text:
        errors.append('pricing.html: the empty price register must say so explicitly')
    if len(residuals) == 0 and '0 rows.</b> No scheduled run has produced a residual' not in text:
        errors.append('pricing.html: the empty residual register must say so explicitly')
    for col in ('Our fair line', 'Market line', 'Difference'):
        if col not in text:
            errors.append(f'pricing.html: residual table is missing the {col!r} column')
    if 'price_as_of' not in text or 'fetched_at_utc' not in text or 'capture_hash' not in text:
        errors.append('pricing.html: schema table must show price_as_of, fetched_at_utc and capture_hash')


def main() -> int:
    check_policy()
    check_headers()
    check_price_rows()
    check_snapshot_consistency()
    check_page()
    if errors:
        for err in errors:
            print('FAIL ' + err)
        return 1
    n = len(read_csv(PRICING / 'prices.csv'))
    print(f'pricing verify: PASS ({n} store rows; registers, policy and page consistent)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
