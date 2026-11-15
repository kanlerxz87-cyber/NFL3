#!/usr/bin/env python3
"""Derive the decision-readiness landing page's headline metrics.

The shared root landing page now summarizes requirements, their states,
validated strategies, open questions and proposals. Availability counts belong
on the separate ops-centre page. This script derives each root metric from the
same committed registers used by those pages and rewrites index.html in place.

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
CATALOG = ROOT / "decision-lab" / "data" / "catalog.json"

LABEL_REQUIREMENTS = "REQUIREMENTS TRACKED"
LABEL_IMPLEMENTED = "IMPLEMENTED"
LABEL_PARTIAL = "PARTIAL"
LABEL_BLOCKED = "BLOCKED"
LABEL_QUESTIONS = "OPEN QUESTIONS"
LABEL_PROPOSALS = "PROPOSALS AWAITING DECISION"
LABEL_VALIDATED = "VALIDATED STRATEGIES"


def derive() -> dict[str, str]:
    derived = json.loads(DERIVED.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    requirements = catalog.get("requirements", [])
    states = {state: sum(1 for row in requirements if row.get("state") == state)
              for state in ("implemented", "partial", "blocked")}
    if sum(states.values()) != len(requirements):
        raise SystemExit("landing metrics: requirement has a missing or unrecognized state")
    strategies = derived.get("strategies", [])
    validated = sum(1 for strategy in strategies if strategy.get("validated") is True)

    if not requirements or not derived.get("questions") or not derived.get("suggestions"):
        raise SystemExit("landing metrics: required source register is empty")
    return {
        LABEL_REQUIREMENTS: f"{len(requirements):,}",
        LABEL_IMPLEMENTED: f"{states['implemented']:,}",
        LABEL_PARTIAL: f"{states['partial']:,}",
        LABEL_BLOCKED: f"{states['blocked']:,}",
        LABEL_VALIDATED: f"{validated:,}",
        LABEL_QUESTIONS: f"{len(derived['questions']):,}",
        LABEL_PROPOSALS: f"{len(derived['suggestions']):,}",
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
            raise SystemExit(f"landing page: required decision-readiness metric label not found: {label}")
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
