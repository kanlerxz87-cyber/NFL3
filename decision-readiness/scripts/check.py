#!/usr/bin/env python3
"""Fail closed if the enhanced root readiness matrix is stale or incomplete."""
from __future__ import annotations

import re
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
        if "proposed" not in criteria_doc.get("classification", "").lower():
            raise ValueError("proposed-criteria/non-fact classification is missing")
        if not criteria_doc.get("criteria_date", "").strip():
            raise ValueError("proposed acceptance-criteria date is missing")

        text = INDEX_PATH.read_text(encoding="utf-8")
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("index.html must contain exactly one generated readiness matrix section")
        before, rest = text.split(START, 1)
        matrix, after = rest.split(END, 1)
        expected = before + render_section() + after
        if expected != text:
            raise ValueError("index.html readiness matrix differs from the source registers; run decision-readiness/scripts/build.py")

        table_start = matrix.find('<table id="decision-readiness-table">')
        table_end = matrix.find("</table>", table_start)
        if table_start < 0 or table_end < 0 or matrix.count('id="decision-readiness-table"') != 1:
            raise ValueError("generated root matrix table is missing or duplicated")
        ids = re.findall(r"<tr><td>(R\d{2})</td>", matrix[table_start:table_end])
        expected_ids = [row["id"] for row in requirements]
        if ids != expected_ids:
            raise ValueError(f"root matrix IDs/order differ from canonical requirements: {ids}")
        if 'href="readiness.html"' not in text:
            raise ValueError("landing page must retain its link to the existing full-scope gate register")

        flagged = (ROOT / "flagged.html").read_text(encoding="utf-8")
        if (
            flagged.count('id="DATA-USE-01"') != 1
            or "static.www.nfl.com/image/upload/v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf" not in flagged
        ):
            raise ValueError("root Flagged for Review must retain DATA-USE-01 and its official Game Book citation")

        print(
            f"Decision readiness check passed: {len(requirements)} canonical rows, "
            f"{len(criteria)} proposed criteria, mapped blocking gates and registered source links; "
            "the single root matrix is current."
        )
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"Decision readiness check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
