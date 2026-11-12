#!/usr/bin/env python3
"""Prepare the decision lab for publication without ever publishing a broken site.

Sequence:
  1. regenerate the availability artifact and rebuild every page from the live
     capture that the deployment job just refreshed;
  2. run the fail-closed lab gate;
  3. if the live capture cannot produce a passing, complete build, restore the
     committed snapshot and rebuild from it, then gate again;
  4. if the committed snapshot also fails the gate, exit non-zero so the deploy
     stops rather than publishing an unverified site.

Every fallback is printed with a ``::warning::`` annotation, so a degraded run is
visible in the Actions summary instead of being silent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DATA = LAB / "data"
SNAPSHOT = DATA / "official_snapshot.json"
AVAILABILITY = DATA / "availability.json"


def run(*args: str) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=LAB, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def py(script: str, *extra: str) -> tuple[int, str]:
    return run(sys.executable, f"scripts/{script}", *extra)


def snapshot_shape() -> tuple[bool, str]:
    """A refreshed capture is only usable if it still carries the sections we publish."""
    try:
        doc = json.loads(SNAPSHOT.read_text())
    except Exception as exc:  # noqa: BLE001 - any parse failure is a fail-closed case
        return False, f"snapshot is not valid JSON: {exc}"
    missing = [k for k in ("injury_rows", "depth_rows", "coverage", "observed_at") if not doc.get(k)]
    if missing:
        return False, f"snapshot is missing {', '.join(missing)}"
    return True, f'{doc["coverage"].get("injury_rows", 0)} injury rows, {doc["coverage"].get("depth_rows", 0)} depth rows'


def build_and_gate(stage: str) -> tuple[bool, str]:
    ok, msg = snapshot_shape()
    if not ok:
        return False, f"{stage}: {msg}"
    code, out = py("availability.py")
    if code != 0:
        return False, f"{stage}: availability.py failed\n{out}"
    code, out = py("build.py")
    if code != 0:
        return False, f"{stage}: build.py failed\n{out}"
    code, out = py("audit.py")
    if code != 0:
        return False, f"{stage}: lab gate failed\n{out}"
    return True, f"{stage}: {msg}; {out.splitlines()[0] if out else 'built'}"


def restore(paths: list[str]) -> None:
    run("git", "checkout", "HEAD", "--", *paths)


def main() -> int:
    codes: list[str] = []

    ok, msg = build_and_gate("live capture")
    print(msg)
    if not ok:
        codes.append(msg)
        print("::warning::the refreshed official capture could not produce a passing build; "
              "falling back to the committed snapshot so the last verified site stays live")
        restore(["data/official_snapshot.json"])
        ok, msg = build_and_gate("committed snapshot")
        print(msg)
        if not ok:
            codes.append(msg)
            print("::error::the committed snapshot also fails the lab gate; refusing to publish")
            for line in codes:
                print(line)
            return 1

    report = DATA / "verification.json"
    if report.exists():
        doc = json.loads(report.read_text())
        print(f'verification mode={doc.get("mode")} status={doc.get("status")}')
        for fam in doc.get("families", []):
            print(f'  {fam["id"]:<10} {fam["status"]:<16} {fam["matched"]}/{fam["rows_checked"]} mismatched={fam["mismatched"]}')
        if doc.get("status") == "partial":
            print("::warning::live verification could not compare every family; unreachable sources are recorded on the integrity page")
    else:
        print("::warning::no verification report was produced in this run")

    # the built pages must not contain conflict markers
    code, out = run("git", "diff", "--check")
    if code != 0:
        print("::error::whitespace/conflict-markup errors in the built tree")
        print(out[:4000])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
