#!/usr/bin/env python3
"""Fail the data refresh when an official source could not be fetched and verified."""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--min-files", type=int, default=1)
    ap.add_argument("--allow-missing", default="", help="comma-separated names tolerated as missing")
    args = ap.parse_args()
    with open(args.manifest, encoding="utf-8") as f:
        m = json.load(f)
    allowed = {s for s in args.allow_missing.split(",") if s}
    files = m.get("files", {})
    hard = [f for f in m.get("failures", []) if f.get("name") not in allowed]
    print(f"verified files: {len(files)} (minimum {args.min_files})")
    for name, rec in sorted(files.items()):
        print(f"  OK  {name:20s} {rec['bytes']:>10d} B  {rec['sha256'][:23]}...  {rec['asset_url']}")
    for f in hard:
        print(f"  ERR {f['name']}: {f['reason']}")
    if hard or len(files) < args.min_files:
        print("RESULT: FAILED - official sources missing or unverified")
        return 1
    print("RESULT: OK - every ingested file matches its official SHA-256 digest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
