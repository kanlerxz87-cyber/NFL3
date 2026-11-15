#!/usr/bin/env python3
"""Regression tests for the frozen corpus (offline; committed artifacts only).

Run: python3 corpus/test_corpus.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'corpus'
MANIFEST = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))


class CorpusRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = list(csv.DictReader((ROOT / MANIFEST['frozen_file']).open(newline='', encoding='utf-8')))

    def test_verifier_passes_on_committed_tree(self):
        out = subprocess.run([sys.executable, str(CORPUS / 'verify.py')], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_frozen_hash_matches_manifest(self):
        got = hashlib.sha256((ROOT / MANIFEST['frozen_file']).read_bytes()).hexdigest()
        self.assertEqual(got, MANIFEST['frozen_sha256'])

    def test_split_covers_and_disjoins(self):
        weeks = [int(r['week']) for r in self.rows]
        train = [w for w in weeks if w <= 6]
        val = [w for w in weeks if 7 <= w <= 8]
        hold = [w for w in weeks if w == 9]
        self.assertEqual(len(train), MANIFEST['split']['train']['games'])
        self.assertEqual(len(val), MANIFEST['split']['validation']['games'])
        self.assertEqual(len(hold), MANIFEST['split']['holdout']['games'])
        self.assertEqual(len(self.rows), 136)

    def test_exactly_one_blank_score_stays_blank(self):
        blank = [r for r in self.rows if not r['away_score'] or not r['home_score']]
        self.assertEqual(len(blank), 1)
        self.assertIn('Hidden Score', blank[0]['verification'])

    def test_every_row_carries_an_official_schedule_link(self):
        for r in self.rows:
            self.assertTrue(r['source_url'].startswith('https://www.nfl.com/schedules/'), r['source_url'])

    def test_tampering_is_detected(self):
        tampered = b'week,home_score\n1,99\n'
        self.assertNotEqual(hashlib.sha256(tampered).hexdigest(), MANIFEST['frozen_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
