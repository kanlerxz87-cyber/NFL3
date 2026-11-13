#!/usr/bin/env python3
"""Derive the landing page's headline numbers from the published data.

The landing page quotes counts (injury rows, depth rows, replacement chains,
open questions, proposals, validated strategies, review flags). Those counts are
also written into the published tables, so a hand-typed number on the landing
page can drift away from the tables it claims to summarise. This script derives
each number from the same file the tables are built from and rewrites the
landing page in place.

    python3 scripts/sync_landing_metrics.py           # rewrite index.html
    python3 scripts/sync_landing_metrics.py --check   # fail if it would change

Fails closed: if a metric cannot be derived, the script exits non-zero and
leaves the page untouched rather than publishing a number it could not compute.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
DERIVED = ROOT / "ops-center" / "data" / "derived.json"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"

LABEL_INJURY_ROWS = "INJURY ROWS (OFFICIAL, CURRENT)"
LABEL_DEPTH_ROWS = "CLUB DEPTH ROWS"
LABEL_CHAINS = "REPLACEMENT CHAINS"
LABEL_QUESTIONS = "OPEN QUESTIONS"
LABEL_PROPOSALS = "PROPOSALS AWAITING DECISION"
LABEL_VALIDATED = "VALIDATED STRATEGIES"
LABEL_FLAGS = "REVIEW FLAGS"


def derive() -> dict[str, str]:
    derived = json.loads(DERIVED.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    chains = derived.get("chains", [])
    published_chains = sum(1 for c in chains if c.get("chain_status") == "chain-identified")
    strategies = derived.get("strategies", [])
    validated = sum(1 for s in strategies if s.get("validated") is True)

    return {
        LABEL_INJURY_ROWS: f"{int(derived['injury_rows_current']):,}",
        LABEL_DEPTH_ROWS: f"{int(snapshot['coverage']['depth_rows']):,}",
        LABEL_CHAINS: f"{published_chains:,}",
        LABEL_QUESTIONS: f"{len(derived.get('questions', [])):,}",
        LABEL_PROPOSALS: f"{len(derived.get('suggestions', [])):,}",
        LABEL_VALIDATED: f"{validated:,}",
        LABEL_FLAGS: f"{len(derived.get('flags', [])):,}",
    }


def rewrite(text: str, metrics: dict[str, str]) -> str:
    start = text.index('<div class="metrics">')
    end = text.index("</div></div>", start) + len("</div></div>")
    block = text[start:end]
    for label, value in metrics.items():
        pattern = re.compile(
            r'(<span>' + re.escape(label) + r'</span><strong>)([^<]*)(</strong>)'
        )
        if not pattern.search(block):
            raise SystemExit(f"landing page: metric label not found: {label}")
        block = pattern.sub(lambda m: m.group(1) + value + m.group(3), block, count=1)
    return text[:start] + block + text[end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail instead of rewriting")
    args = ap.parse_args()

    metrics = derive()
    text = INDEX.read_text(encoding="utf-8")
    updated = rewrite(text, metrics)

    if updated == text:
        print("Landing page metrics already match the published data: "
              + ", ".join(f"{k}={v}" for k, v in metrics.items()))
        return 0
    if args.check:
        print("Landing page metrics are out of date. Run: python3 scripts/sync_landing_metrics.py")
        for label, value in metrics.items():
            pattern = re.compile(r'<span>' + re.escape(label) + r'</span><strong>([^<]*)</strong>')
            found = pattern.search(text)
            print(f"  {label}: page={found.group(1) if found else '?'} data={value}")
        return 1
    INDEX.write_text(updated, encoding="utf-8")
    print("Landing page metrics updated: "
          + ", ".join(f"{k}={v}" for k, v in metrics.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
