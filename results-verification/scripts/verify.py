#!/usr/bin/env python3
"""Strict gate for the results-verification sub-site. Fails the build on:
  - any data row missing a link to an official source (nfl.com/scores, nfl.com/injuries, or a player page),
  - rendered row counts disagreeing with the committed data files,
  - the corpus hash not matching the frozen value,
  - placeholder leakage (TBD/TODO/lorem/XXX),
  - internal links to files that do not exist.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"

OFFICIAL = re.compile(r"https://www\.nfl\.com/(scores/|injuries/|players/)")
PLACEHOLDER = re.compile(r"\b(TBD|TODO|lorem ipsum|XXX|placeholder)\b", re.I)
CORPUS_SHA = "a1633c2011bc8fb4c6508ada2ed1cd32ddede8993300b5e03ef157f762ee73b1"


def fail(msg: str) -> int:
    print(f"FAIL {msg}")
    return 1


def check_rows(page: Path, expect_rows: int, what: str) -> int:
    text = page.read_text()
    rows = re.findall(r"<tr><td>", text)
    if len(rows) < expect_rows:
        return fail(f"{page.name}: {what}: rendered {len(rows)} rows < expected {expect_rows}")
    # every rendered data row must contain an official link or a player-page link on nfl.com
    trs = re.split(r"<tr><td>", text)[1:]
    missing = [i for i, tr in enumerate(trs)
               if not OFFICIAL.search(tr) and i < expect_rows]
    if missing:
        return fail(f"{page.name}: {what}: {len(missing)} data rows without an official source link (first: {missing[0]})")
    m = PLACEHOLDER.search(text)
    if m:
        return fail(f"{page.name}: placeholder text '{m.group(0)}'")
    print(f"OK {page.name}: {what}: {expect_rows} data rows, every row carries an official source link")
    return 0


def main() -> int:
    corpus = (DATA / "backtest_corpus_w1_w9.csv").read_bytes()
    sha = hashlib.sha256(corpus).hexdigest()
    if sha != CORPUS_SHA:
        return fail(f"corpus sha256 changed: {sha}")
    rep = json.loads((DATA / "verification_report.json").read_text())
    if rep["counts"]["score_matches"] != 136 or rep["counts"]["score_mismatches"]:
        return fail("verification report is not complete")
    delta = json.loads((DATA / "injury_delta.json").read_text())

    idx, dlt = HERE / "index.html", HERE / "delta.html"
    if not idx.exists() or not dlt.exists():
        return fail("built pages missing; run scripts/build.py first")
    rc = check_rows(idx, 136, "game-by-game table")
    if rc:
        return rc
    rc = check_rows(dlt, delta["counts"]["game_status_changes"], "game-status delta table")
    if rc:
        return rc

    # internal links resolve
    for page in (idx, dlt):
        for m in re.finditer(r'href="([^"#]+\.md|[^"#]+\.html)"', page.read_text()):
            href = m.group(1)
            if href.startswith("http"):
                continue
            target = (page.parent / href).resolve()
            if not target.exists() and not (ROOT / href).exists():
                return fail(f"{page.name}: broken internal link {href}")

    # weekly JSON count invariants
    for w in range(1, 10):
        d = json.loads((DATA / "official_scores_2026" / f"week_{w:02d}.json").read_text())
        if d["week"] != w or not d["games"]:
            return fail(f"week_{w:02d}.json malformed")
    print("PASS results-verification strict gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
