#!/usr/bin/env python3
"""Offline unit tests for the price-store ingestion gate (synthetic fixtures only).

Run: python3 pricing/test_pricing.py
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

VALID_ROW = {
    'market_id': '2026-W10-NE@DET-side',
    'game_id': '2026-REG10-NE@DET',
    'season': '2026',
    'week': '10',
    'market_type': 'side',
    'market_side': 'NE',
    'price': '-3.0',
    'price_format': 'line',
    'price_as_of': '',
    'fetched_at_utc': '2026-11-15T12:00:00Z',
    'supersedes': '',
}


def payload_bytes(row: dict) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(row.keys()))
    w.writeheader()
    w.writerow(row)
    return buf.getvalue().encode()


class IngestGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.orig_sources = ingest.SNAPSHOTS
        ingest.PRICING = self.tmp
        ingest.SNAPSHOTS = self.tmp / 'snapshots'
        (self.tmp / 'sources.csv').write_text(
            'source_id,class,example,terms_status,permitted_use,status,source_link\n'
            'PS-01,Licensed operator feed,,terms on file,store quotes,licensed,https://example.org/terms\n'
            'PS-02,Unlicensed feed,,none,none,excluded,https://example.org/x\n', encoding='utf-8')
        self.terms = self.tmp / 'terms.txt'
        self.terms.write_text('written terms for test fixture', encoding='utf-8')

    def write(self, row: dict) -> Path:
        p = self.tmp / 'payload.csv'
        p.write_bytes(payload_bytes(row))
        return p

    def test_valid_payload_is_filed_with_hash(self):
        out = ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', 'LIC-1', self.terms, 'open')
        self.assertTrue(out.exists())
        line = json.loads(out.read_text().splitlines()[0])
        self.assertTrue(line['capture_hash'].startswith('sha256:'))
        self.assertEqual(line['licence_id'], 'LIC-1')

    def test_missing_terms_file_rejects(self):
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', 'LIC-1', self.tmp / 'missing.txt', 'open')

    def test_blank_terms_file_rejects(self):
        blank = self.tmp / 'blank.txt'
        blank.write_text('   ', encoding='utf-8')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', 'LIC-1', blank, 'open')

    def test_unlicensed_source_rejects(self):
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-02', 'LIC-2', self.terms, 'open')

    def test_unknown_source_rejects(self):
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-99', 'LIC-3', self.terms, 'open')

    def test_blank_licence_rejects(self):
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', '', self.terms, 'open')

    def test_bad_timestamp_rejects(self):
        row = dict(VALID_ROW, fetched_at_utc='2026-11-15 12:00')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(row), 'PS-01', 'LIC-1', self.terms, 'open')

    def test_non_numeric_price_rejects(self):
        row = dict(VALID_ROW, price='minus three')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(row), 'PS-01', 'LIC-1', self.terms, 'open')

    def test_bad_market_type_rejects(self):
        row = dict(VALID_ROW, market_type='prop', market_id='2026-W10-NE@DET-prop')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(row), 'PS-01', 'LIC-1', self.terms, 'open')

    def test_missing_required_field_rejects(self):
        row = dict(VALID_ROW)
        del row['market_side']
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(row), 'PS-01', 'LIC-1', self.terms, 'open')

    def test_duplicate_capture_rejects(self):
        ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', 'LIC-1', self.terms, 'open')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(self.write(dict(VALID_ROW)), 'PS-01', 'LIC-1', self.terms, 'open')

    def test_empty_payload_rejects(self):
        p = self.tmp / 'empty.csv'
        p.write_bytes(b'market_id,game_id,season,week,market_type,market_side,price,price_format,price_as_of,fetched_at_utc,supersedes\n')
        with self.assertRaises(ingest.Reject):
            ingest.ingest(p, 'PS-01', 'LIC-1', self.terms, 'open')


class SchemaTests(unittest.TestCase):
    def test_schema_requires_both_times_and_hash(self):
        req = ingest.REQUIRED
        for field in ('fetched_at_utc', 'capture_hash', 'source_id', 'licence_id', 'market_type'):
            self.assertIn(field, req)

    def test_market_id_pattern_examples(self):
        pat = ingest.SCHEMA['price_snapshot_row']['properties']['market_id']['pattern']
        import re
        self.assertTrue(re.match(pat, '2026-W10-NE@DET-side'))
        self.assertTrue(re.match(pat, '2026-W1-NE@SEA-total-over'))
        self.assertFalse(re.match(pat, 'NE-DET'))
        self.assertFalse(re.match(pat, '2026-W10-NE@DET'))


if __name__ == '__main__':
    unittest.main(verbosity=1)
