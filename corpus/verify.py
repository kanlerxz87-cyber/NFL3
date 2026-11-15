#!/usr/bin/env python3
"""Verify the frozen pre-registered backtest corpus (all offline).

Fails when: the frozen file hash differs from the manifest; row/week/split counts
move; splits overlap or leave rows uncovered; a row lacks an official source URL;
more than one score is blank; the blank score is ever filled in the frozen copy
without a manifest amendment; or the registration fields hold malformed hashes.

Warns (does not fail) when the upstream source file has moved since the freeze:
the corpus is frozen by design; upstream movement is a review flag, not a change
to the corpus.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'corpus'
MANIFEST = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))
HEX = re.compile(r'^[0-9a-f]{40}$')

errors: list[str] = []
warnings: list[str] = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frozen = ROOT / MANIFEST['frozen_file']
    if not frozen.is_file():
        print('FAIL corpus: frozen file missing: ' + MANIFEST['frozen_file'])
        return 1
    got = sha256(frozen)
    if got != MANIFEST['frozen_sha256']:
        errors.append(f'corpus: frozen file hash {got} != manifest {MANIFEST["frozen_sha256"]}')

    source = ROOT / MANIFEST['source_file']
    if source.is_file():
        if sha256(source) != MANIFEST['source_sha256_at_freeze']:
            warnings.append('FLAG: upstream ' + MANIFEST['source_file'] +
                            ' changed after the freeze; the corpus stays frozen. Review the diff.')
    else:
        warnings.append('FLAG: upstream source file is absent; the frozen copy stands alone.')

    rows = list(csv.DictReader(frozen.open(newline='', encoding='utf-8')))
    if len(rows) != MANIFEST['window']['games']:
        errors.append(f'corpus: {len(rows)} rows != manifest games {MANIFEST["window"]["games"]}')
    weeks = [int(r['week']) for r in rows]
    if min(weeks) != 1 or max(weeks) != 9:
        errors.append(f'corpus: weeks span {min(weeks)}–{max(weeks)}, expected 1–9')
    no_src = [r for r in rows if not r.get('source_url', '').startswith('https://')]
    if no_src:
        errors.append(f'corpus: {len(no_src)} rows lack an official source URL')
    blank = [r for r in rows if not r['away_score'] or not r['home_score']]
    if len(blank) != MANIFEST['window']['unsettled_hidden_score']:
        errors.append(f'corpus: {len(blank)} blank-score rows != manifest {MANIFEST["window"]["unsettled_hidden_score"]}')

    split = MANIFEST['split']
    train = {i for i, r in enumerate(rows) if int(r['week']) <= split['train']['weeks'][1]}
    val = {i for i, r in enumerate(rows) if split['validation']['weeks'][0] <= int(r['week']) <= split['validation']['weeks'][1]}
    hold = {i for i, r in enumerate(rows) if int(r['week']) >= split['holdout']['weeks'][0]}
    if train & val or train & hold or val & hold:
        errors.append('corpus: split blocks overlap')
    if train | val | hold != set(range(len(rows))):
        errors.append('corpus: split blocks do not cover the corpus')
    for name, block in (('train', train), ('validation', val), ('holdout', hold)):
        if len(block) != split[name]['games']:
            errors.append(f'corpus: {name} block has {len(block)} rows != manifest {split[name]["games"]}')

    rules = re.sub(r'\s+', ' ', (CORPUS / 'PRE_REGISTRATION.md').read_text(encoding='utf-8'))
    for needle, why in [
        ('**Status:** registered', 'the rules file must record its registration'),
        ('the commit that created this file is the registration', 'the registration rule'),
        ('Holdout', 'the holdout block'),
        ('leaderboard result cell', 'the leaderboard ban'),
        ('recorded **before kickoff**', 'the prospective-only leaderboard rule'),
    ]:
        if needle not in rules:
            errors.append(f'corpus: PRE_REGISTRATION.md is missing {why}')

    for field in ('corpus_registration', 'policy_registration'):
        value = MANIFEST.get(field, '')
        if value and not HEX.match(value):
            errors.append(f'corpus: manifest {field} is not a commit hash: {value!r}')
        if not value:
            warnings.append(f'NOTE: manifest {field} is blank (filled by the commit after registration)')

    for w in warnings:
        print(w)
    if errors:
        for err in errors:
            print('FAIL ' + err)
        return 1
    print(f'corpus verify: PASS ({len(rows)} rows; train {len(train)} / validation {len(val)} / holdout {len(hold)}; '
          f'frozen hash matches; {len(warnings)} notices)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
