#!/usr/bin/env python3
"""Fail closed if readiness data or the generated landing-page table is incomplete."""
from __future__ import annotations

import sys
from pathlib import Path

from build import END, INDEX_PATH, START, load_data, render_section

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        catalog, criteria_doc, criteria, _ = load_data()
        requirements = catalog["requirements"]
        if not requirements:
            raise ValueError("canonical requirement register is empty")
        if criteria_doc.get("classification", "").strip() == "":
            raise ValueError("proposed-criteria/non-fact classification is missing")

        text = INDEX_PATH.read_text(encoding="utf-8")
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("index.html must contain exactly one generated readiness section")
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        expected = before + render_section() + after
        if expected != text:
            raise ValueError("index.html readiness section differs from the source registers; run decision-readiness/scripts/build.py")
        nav = '<a href="#decision-readiness"><span>D</span>Decision readiness</a>'
        if text.count(nav) != 1:
            raise ValueError("root navigation must contain exactly one Decision readiness anchor")
        flagged = (ROOT / "flagged.html").read_text(encoding="utf-8")
        if flagged.count('id="DATA-USE-01"') != 1 or "static.www.nfl.com/image/upload/v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf" not in flagged:
            raise ValueError("root Flagged for Review must retain DATA-USE-01 and its official Game Book citation")

        print(
            f"Decision readiness check passed: {len(requirements)} requirements, "
            f"{len(criteria)} proposed clearance criteria, all gates and official-source hosts valid; "
            "generated landing table is current."
        )
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Decision readiness check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
