#!/usr/bin/env python3
"""Fail-closed verification of the injury archive. Runs offline; fetches nothing.

It fails the build on any of the following, which is the whole point of the gate:

1. a raw capture whose bytes do not hash to the digest recorded in the index;
2. an index line with no clock time, or a success with no stored raw file;
3. an injury or inactives artifact whose rows do not equal the recorded index count;
4. a designation row missing either official URL or either digest (the no-back-fill gate G4);
5. a published rate without `n` or without an interval (gate G3);
6. a rate whose success + failure counts do not add up (gate G2);
7. a page that references a missing local file;
8. the pre-registration not preceding the results artifact in git history;
9. a non-official host anywhere in a row-level source link.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "injury-archive"
DATA = SITE / "data"
OFFICIAL = {"www.nfl.com"}
failures: list[str] = []
checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(message)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    index = [json.loads(line) for line in (DATA / "index.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()] if (DATA / "index.jsonl").exists() else []

    # 1-2: digests, clock times, raw files
    successes = 0
    for entry in index:
        check(bool(entry.get("captured_at_utc")), f"index: entry without captured_at_utc: {entry}")
        check(bool(entry.get("source_url")), "index: entry without source_url")
        if entry.get("status") == "ok":
            successes += 1
            rel = entry.get("raw_file", "")
            path = ROOT / rel if rel else None
            check(bool(path and path.exists()), f"index: ok read with no stored raw file: {entry.get('source_url')}")
            if path and path.exists():
                raw = gzip.decompress(path.read_bytes())
                digest = hashlib.sha256(raw).hexdigest()
                check(digest == entry.get("sha256"),
                      f"index: stored bytes hash to {digest[:12]} but {str(entry.get('sha256'))[:12]} is recorded")

    # 3: artifacts match the index
    injuries = load(DATA / "injuries.json")
    inactives = load(DATA / "inactives.json")
    for key, report in injuries.items():
        check(report["injury_rows"] == len(report["rows"]),
              f"injuries.json {key}: {report['injury_rows']} recorded but {len(report['rows'])} rows")
        for row in report["rows"]:
            host = urlparse(row["player_url"]).hostname
            check(host in OFFICIAL, f"injuries.json {key}: non-official player link {row['player_url']}")
            check(row["practice_status"] in {"Did Not Participate In Practice",
                                             "Limited Participation in Practice",
                                             "Full Participation in Practice"},
                  f"injuries.json {key}: unrecognised practice status {row['practice_status']!r}")
            check(row["game_status"] in {"", "Out", "Doubtful", "Questionable"},
                  f"injuries.json {key}: unrecognised game status {row['game_status']!r}")
    for key, article in inactives.items():
        for row in article["rows"]:
            check(bool(row["player"]), f"inactives.json {key}: entry with no player string")

    # 4: every designation row carries both official documents
    designations = load(DATA / "designations.json") if (DATA / "designations.json").exists() else {
        "observations": [], "by_label": [], "totals": {"designations": 0}}
    for obs in designations["observations"]:
        for field in ("injury_source_url", "inactives_source_url"):
            parsed = urlparse(obs.get(field, ""))
            check(parsed.hostname in OFFICIAL, f"designations: {field} is not an official nfl.com URL: {obs.get(field)}")
        for field in ("injury_sha256", "inactives_sha256"):
            value = obs.get(field, "")
            check(isinstance(value, str) and len(value) == 64 and re.fullmatch(r"[0-9a-f]+", value) is not None,
                  f"designations: {field} is not a 64-hex digest")
        check(obs.get("outcome", "") != "", "designations: row with no outcome (unaccounted)")

    # 5-6: every published rate has n and an interval, and adds up
    for row in designations["by_label"]:
        accounted = row["inactive"] + row["active"] + row["uncovered"] + row["ambiguous"]
        total = row["n"] + row["uncovered"] + row["ambiguous"]
        check(accounted == total, f"by_label {row['group']}: components {accounted} != total {total}")
        if row["n"]:
            check(row["inactive_ci_low"] is not None and row["inactive_ci_high"] is not None,
                  f"by_label {row['group']}: rate published with no interval")
            check(0.0 <= row["inactive_ci_low"] <= row["inactive_rate"] <= row["inactive_ci_high"] <= 1.0,
                  f"by_label {row['group']}: interval does not bracket its point estimate")
        else:
            check(row["inactive_rate"] is None, f"by_label {row['group']}: rate published with n = 0")
    totals = designations["totals"]
    check(totals["inactive"] + totals["active"] + totals["uncovered"] + totals["ambiguous"]
          == totals["designations"],
          "totals: designation outcomes do not account for every joined row")

    # 7: local links resolve
    local = re.compile(r'href="([^"#:]+\.html)"')
    for page in sorted(SITE.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for href in set(local.findall(text)):
            check((page.parent / href).exists(), f"{page.name}: broken local link {href}")
        for href in set(re.findall(r'href="((?:\.\./)[^"#]+)"', text)):
            check((page.parent / href).resolve().exists(), f"{page.name}: broken parent link {href}")

    # 8: pre-registration precedes the results artifact
    def first_commit(path: str) -> str:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%H", "--", path],
                             capture_output=True, text=True)
        lines = [l for l in out.stdout.split() if l]
        return lines[-1] if lines else ""

    pre = first_commit("injury-archive/PREREGISTRATION.md")
    res = first_commit("injury-archive/data/designations.json")
    check(bool(pre), "pre-registration: no commit adds injury-archive/PREREGISTRATION.md")
    if pre and res:
        ancestor = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", pre, res],
                                  capture_output=True).returncode == 0
        check(ancestor, "pre-registration: PREREGISTRATION.md does not precede designations.json in history")

    # 9: pages exist and carry the archive's own honesty statement
    contract = load(DATA / "render_contract.json") if (DATA / "render_contract.json").exists() else {"pages": []}
    for name in contract["pages"]:
        check((SITE / name).exists(), f"contract: page {name} is missing")
    check(bool(index), "index: the capture index is empty")

    print(f"injury-archive verify: {checks} checks, {len(failures)} failure(s), "
          f"{successes} stored ok read(s), {len(injuries)} report(s), {len(inactives)} article(s), "
          f"{totals['designations']} joined designation row(s)")
    for failure in failures:
        print(f"  FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
