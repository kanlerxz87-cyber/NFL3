#!/usr/bin/env python3
"""Fail-closed verification of the Week 11 venue register.

Checks, each of which fails the build with the row or file named:
  1. the CSV holds exactly the 13 fixtures the official Week 11 schedule lists, once each
  2. every venue matches the stored game-centre 'Game Info' lines for that fixture
  3. every kickoff, network and matchup matches the stored official schedule list; 13 games + 6 bye clubs = 32 clubs
  4. every row links the official game-centre page for that slug and the official schedule page
  5. the dated announcement is an official NFL page, dated, and states 272 fixtures
  6. every table row on the generated pages carries an https source link; no placeholder text; no broken local link
  7. the generated pages are reproducible (a second build is byte-identical)
  8. every flag carries an https source link and a unique id
Exit 0 only if every check passes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DATA = OUT / "data"
PLACEHOLDERS = ("TODO", "TBD", "FIXME", "XXX", "lorem ipsum", "PLACEHOLDER")
ERRORS: list[str] = []


def fail(msg: str) -> None:
    ERRORS.append(msg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with (DATA / "week11_venues.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    game_info = {r["game_slug"]: r for r in json.loads((DATA / "evidence/week11_game_centre_info.json").read_text(encoding="utf-8"))["records"]}
    schedule = json.loads((DATA / "evidence/week11_schedule_list.json").read_text(encoding="utf-8"))
    sched_by_slug = {g["game_slug"]: g for g in schedule["games"]}
    announcement = json.loads((DATA / "announcement.json").read_text(encoding="utf-8"))
    flags = json.loads((DATA / "flags.json").read_text(encoding="utf-8"))

    # 1. fixture set
    slugs = [r["game_slug"] for r in rows]
    if len(rows) != 13:
        fail(f"week11_venues.csv holds {len(rows)} rows; the official Week 11 schedule lists 13")
    if len(set(slugs)) != len(slugs):
        fail("duplicate game_slug in week11_venues.csv")
    if set(slugs) != set(sched_by_slug):
        fail(f"CSV slugs differ from the schedule list: only in CSV {sorted(set(slugs) - set(sched_by_slug))}, "
             f"only in schedule {sorted(set(sched_by_slug) - set(slugs))}")
    if schedule["listed_games"] != len(schedule["games"]) or len(schedule["games"]) != 13:
        fail("schedule evidence does not hold 13 listed games")
    clubs = {g["away_team"] for g in schedule["games"]} | {g["home_team"] for g in schedule["games"]}
    clubs |= set(schedule["bye_teams"])
    if len(clubs) != 32 or len(schedule["bye_teams"]) != 6 or len(clubs - set(schedule["bye_teams"])) != 26:
        fail(f"Week 11 club count wrong: {len(clubs)} distinct clubs (expected 32 = 26 playing + 6 bye)")

    for r in rows:
        slug = r["game_slug"]
        # 2. venue against the game-centre record
        gi = game_info.get(slug)
        if gi is None:
            fail(f"{slug}: no game-centre evidence record")
            continue
        if r["venue_stadium"] != gi["stadium"]:
            fail(f"{slug}: venue_stadium '{r['venue_stadium']}' != game centre '{gi['stadium']}'")
        if r["venue_city_state"] != gi["location"]:
            fail(f"{slug}: venue_city_state '{r['venue_city_state']}' != game centre '{gi['location']}'")
        if gi["raw_lines"] != [f"LocationLOCATION{gi['location']}", f"StadiumSTADIUM{gi['stadium']}"]:
            fail(f"{slug}: stored raw lines do not match the recorded location and stadium")
        # 3. kickoff, network, matchup against the schedule list
        s = sched_by_slug.get(slug)
        if s:
            if (r["kickoff_et"], r["network"], r["away_team"], r["home_team"]) != (
                s["kickoff_et"], s["network"], s["away_team"], s["home_team"]):
                fail(f"{slug}: kickoff/network/matchup differ from the official schedule list")
        # 4. source links
        if r["venue_source_url"] != f"https://www.nfl.com/games/{slug}-2026-reg-11":
            fail(f"{slug}: venue_source_url is not the official game-centre page for this slug")
        if r["schedule_source_url"] != schedule["source_url"]:
            fail(f"{slug}: schedule_source_url is not the official Week 11 schedule page")
        if not r["verification"].startswith("Verified"):
            fail(f"{slug}: verification column does not start with 'Verified'")
        if r["season"] != "2026" or r["week"] != "11":
            fail(f"{slug}: season/week is not 2026 week 11")

    # 5. announcement
    if not announcement["url"].startswith("https://media.nfl.com/"):
        fail("announcement url is not on media.nfl.com (official)")
    if announcement["published"] != "May 14, 2026":
        fail("announcement date not as recorded on the page")
    if announcement["fixtures_in_announcement"] != 272:
        fail("announcement does not state 272 fixtures")
    if not announcement["live_schedule_url"].startswith("https://www.nfl.com/"):
        fail("live schedule url is not on nfl.com")

    # 8. flags
    seen = set()
    for f in flags:
        if f["id"] in seen:
            fail(f"duplicate flag id {f['id']}")
        seen.add(f["id"])
        if not f["source"].startswith("https://"):
            fail(f"flag {f['id']}: source is not https")
        if not f.get("source_label"):
            fail(f"flag {f['id']}: no source label")

    # 6/7. generated pages
    build = HERE / "build.py"
    first = subprocess.run([sys.executable, str(build)], capture_output=True, text=True)
    if first.returncode:
        fail("build.py failed: " + (first.stderr or first.stdout)[-800:])
    pages = [OUT / "index.html", OUT / "flagged.html"]
    digest1 = {p.name: sha(p) for p in pages if p.exists()}
    second = subprocess.run([sys.executable, str(build)], capture_output=True, text=True)
    if second.returncode:
        fail("second build.py run failed")
    digest2 = {p.name: sha(p) for p in pages if p.exists()}
    if digest1 != digest2:
        fail("build is not reproducible: pages differ between two runs")

    for p in pages:
        if not p.exists():
            fail(f"missing generated page {p.name}")
            continue
        text = p.read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            if re.search(rf"\b{re.escape(token)}\b", text):
                fail(f"{p.name}: placeholder token '{token}' present")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith("http"):
                if not href.startswith("https://"):
                    fail(f"{p.name}: non-https external link {href}")
                continue
            if href.startswith("#"):
                continue
            target = (OUT / href.split("#")[0]).resolve()
            if not target.exists():
                fail(f"{p.name}: broken local link {href}")
        body = text.split("<tbody>", 1)[-1]
        for i, row in enumerate(re.findall(r"<tr>(.*?)</tr>", body, flags=re.S), 1):
            if not re.search(r'href="https://(www\.nfl\.com|media\.nfl\.com|github\.com)/', row):
                fail(f"{p.name}: table body row {i} has no official source link")

    if ERRORS:
        print("Venue register verification FAILED")
        for e in ERRORS:
            print(" -", e)
        return 1
    print(f"Venue register verification PASSED: {len(rows)} fixtures matched to game-centre and schedule records; "
          f"announcement dated {announcement['published']}; {len(flags)} flags with sources; pages reproducible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
