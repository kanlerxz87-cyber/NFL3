#!/usr/bin/env python3
"""Build the whole origination workspace in dependency order.

Every step is deterministic and reads only committed artifacts plus the repository's verified raw
snapshot, so running this twice must produce byte-identical output. `verify.py` checks exactly that.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ("prices.py", "price-snapshot store: snapshots, ledger, policy hash"),
    ("results.py", "verified results feed reconciled to official standings"),
    ("model.py", "origination: side, total, moneyline (walk-forward and in-season)"),
    ("elo.py", "second estimator"),
    ("leaderboard.py", "strategy registry and proper-score leaderboard"),
    ("luck.py", "removal-of-luck panel"),
    ("correlations.py", "official-input correlations with n"),
    ("availability.py", "availability graph and depth from playing time"),
    ("ablation.py", "injury and personnel ablation"),
    ("gates.py", "validation gates and demotions"),
    ("content.py", "requirements, questions, suggestions, flags, sources"),
    ("build_site.py", "render the pages"),
]


def main() -> int:
    for script, what in STEPS:
        print(f"\n=== {script}: {what}")
        proc = subprocess.run([sys.executable, str(HERE / script)], cwd=str(HERE))
        if proc.returncode:
            print(f"BUILD FAILED at {script}")
            return proc.returncode
    print("\nOrigination workspace built.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
