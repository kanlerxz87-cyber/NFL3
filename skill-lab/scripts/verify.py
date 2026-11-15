#!/usr/bin/env python3
"""Fail-closed checks on the published skill-lab artifact and pages.

Run:  python3 skill-lab/scripts/verify.py

Fails (exit 1) when a published number cannot be reproduced from the committed artifact, when a
page contains a placeholder, when a table row lacks a source link, or when the pre-registration
commit recorded in the artifact does not exist in the repository history.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "skill-lab"
RESULTS = LAB / "data" / "results.json"
PAGES = ["index.html", "leaderboard.html", "controls.html", "staking.html", "dependence.html",
         "graded.html", "methodology.html", "flagged.html", "sources.html"]

errors: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def main() -> int:
    if not RESULTS.exists():
        fail(f"missing artifact: {RESULTS.relative_to(ROOT)}")
        print("\n".join(errors))
        return 1
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    meta = res.get("meta", {})

    # 1. the protocol and its commit must exist
    reg = meta.get("pre_registration_commit") or ""
    if not reg:
        fail("artifact does not record a pre-registration commit")
    else:
        out = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{reg}^{{commit}}"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            fail(f"pre-registration commit {reg} is not in the repository history")
        else:
            show = subprocess.run(["git", "-C", str(ROOT), "show", "--stat", "--oneline", reg],
                                  capture_output=True, text=True).stdout.strip()
            notes.append(f"pre-registration commit {reg[:12]} exists: {show.splitlines()[0] if show else ''}")
            has_doc = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{reg}:docs/SKILL_LAB_PRE_REGISTRATION.md"],
                capture_output=True, text=True)
            if has_doc.returncode != 0:
                fail("the registered commit does not contain docs/SKILL_LAB_PRE_REGISTRATION.md")

    # 2. corpus arithmetic
    primary = res["runs"]["primary"]
    expected = meta["primary_corpus"]["expected_games"]
    observed = meta["primary_corpus"]["observed_games"]
    if observed != expected:
        fail(f"primary corpus has {observed} games, the registration expected {expected}")
    for key, run in res["runs"].items():
        for row in run["rows"]:
            if "bootstrap" not in row:
                continue
            n = row["n_games"]
            graded = [g for g in run["graded"] if g["strategy"] == row["strategy"]]
            if key == "primary" and len(graded) != n:
                fail(f"{key}/{row['strategy']}: n_games {n} does not match {len(graded)} graded rows")
            if row["gates_passed"] != sum(1 for ok, _ in row["gates"].values() if ok):
                fail(f"{key}/{row['strategy']}: gate arithmetic does not match the gate table")
            if row["gates_total"] != len(row["gates"]):
                fail(f"{key}/{row['strategy']}: gate count does not match the gate table")
            if row["eligible_for_ranking"] != all(ok for ok, _ in row["gates"].values()):
                fail(f"{key}/{row['strategy']}: eligibility does not match the gates")
            if row["skill_brier"] > 0 and row["bootstrap"]["lower95"] is not None \
                    and row["bootstrap"]["lower95"] > 0 and not row["bh_pass"]:
                fail(f"{key}/{row['strategy']}: positive skill with a positive lower bound but a failing "
                     "multiplicity gate")

    # 3. every page exists, has no placeholder and no broken internal link
    for name in PAGES:
        path = LAB / name
        if not path.exists():
            fail(f"missing page: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in ("None", "nan", "{", "}"):
            if token in text and not (token == "{" and "style=" in text):
                fail(f"{name}: placeholder token {token!r} found in the published page")
                break
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith("http"):
                continue
            target = (LAB / href).resolve()
            if not target.exists():
                fail(f"{name}: broken internal link {href}")
        if name not in ("index.html",):
            if "NFL3 skill lab" not in text:
                fail(f"{name}: page is missing the shared layout")

    # 4. every table row on a data page carries a link
    for name in ("leaderboard.html", "graded.html", "dependence.html", "flagged.html", "sources.html"):
        text = (LAB / name).read_text(encoding="utf-8")
        rows = re.findall(r"<tr>(.*?)</tr>", text, re.S)
        body_rows = [r for r in rows if "<td" in r]
        for row in body_rows:
            if 'href="http' not in row:
                fail(f"{name}: a table row has no source link")
                break

    # 5. the graded page must link every game to an official scores page
    graded_text = (LAB / "graded.html").read_text(encoding="utf-8")
    official_links = re.findall(r'href="(https://www\.nfl\.com/scores/2026/week-\d+)"', graded_text)
    if len(official_links) != len([g for g in primary["graded"]]):
        fail(f"graded.html: {len(official_links)} official scores links for "
             f"{len(primary['graded'])} graded forecasts")
    if len(re.findall(r'href="https://www\.nfl\.com/', graded_text)) != len(official_links):
        fail("graded.html: contains a non-scores nfl.com link in the graded table")

    for note in notes:
        print(f"note: {note}")
    if errors:
        print("skill-lab verification FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Skill-lab checks passed: protocol commit, corpus arithmetic, gate arithmetic, page "
          "placeholders, internal links and per-row source links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
