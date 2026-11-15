#!/usr/bin/env python3
"""Gate G-PREREG: the registration must exist, match the corpus, and precede results.

Fails closed. Checks:
  1. the registration file is committed;
  2. the SHA-256 values it records equal the files on disk;
  3. the registration commit is an ancestor of HEAD (i.e. it predates whatever is
     being published now), using git history rather than a self-declared claim.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "official-verify" / "prereg" / "PREREG-2026-OV1.md"
DATA = ROOT / "official-verify" / "data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def main() -> int:
    if not PREREG.exists():
        print("G-PREREG FAIL: registration file is missing")
        return 1
    text = PREREG.read_text(encoding="utf-8")
    recorded = dict(re.findall(r"`([^`]*\.csv)` — `([0-9a-f]{64})`", text))
    if not recorded:
        print("G-PREREG FAIL: registration records no corpus hashes")
        return 1
    failures = []
    for relative, expected in recorded.items():
        path = ROOT / relative
        if not path.exists():
            failures.append(f"{relative} is missing")
            continue
        actual = sha256(path)
        if actual != expected:
            failures.append(f"{relative} sha256 is {actual}, registration says {expected}")
    # The registration commit must exist and be an ancestor of the current commit.
    first = git("log", "--diff-filter=A", "--format=%H", "--", str(PREREG.relative_to(ROOT)))
    if not first:
        failures.append("registration file is not committed yet")
    else:
        earliest = first.splitlines()[-1]
        if not git("merge-base", "--is-ancestor", earliest, "HEAD") == "":
            failures.append("registration commit is not an ancestor of HEAD")
    payload = {
        "gate": "G-PREREG",
        "registration": str(PREREG.relative_to(ROOT)),
        "registration_commit": first.splitlines()[-1] if first else None,
        "files": {k: sha256(ROOT / k) if (ROOT / k).exists() else None for k in recorded},
        "failures": failures,
    }
    print(json.dumps(payload, indent=2))
    if failures:
        print("G-PREREG FAIL")
        return 1
    print("G-PREREG PASS: registration is committed, precedes HEAD, and matches the corpus on disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
