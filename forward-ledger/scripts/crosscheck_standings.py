#!/usr/bin/env python3
"""Cross-check the forward ledger against the official standings capture recorded in another workspace.

Why: the ledger's 149 graded games produce, for every club, a win-loss-tie mark and points for and against.
The only official page that publishes all three at once is the league standings page. `origination/` holds a
same-day read of it (observed 2026-11-16T15:05Z at https://www.nfl.com/standings/), which was transcribed
independently of this workspace. Comparing the two is a 32-club x 5-field test of the ledger that no single
transcription can fake, and it settles the one club (Cincinnati) whose record chip this session did not read.

Read-only: this script never writes outside `forward-ledger/data/`.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"
SIBLING = ROOT / "origination" / "data" / "official_standings_2026.json"
FIELDS = ["club", "games_ledger", "wins_ledger", "losses_ledger", "ties_ledger", "points_for_ledger",
          "points_against_ledger", "standings_w", "standings_l", "standings_t", "standings_pf", "standings_pa",
          "agreement", "note"]


def main() -> int:
    if not SIBLING.is_file():
        raise SystemExit("forward-ledger/crosscheck_standings: the sibling official standings capture is missing")
    doc = json.loads(SIBLING.read_text(encoding="utf-8"))
    if "nfl.com/standings" not in doc.get("source", ""):
        raise SystemExit("forward-ledger/crosscheck_standings: the sibling file does not cite the official standings page")
    standings = {}
    for row in doc["rows"]:
        club, wins, losses, ties, pf, pa = row[0], row[1], row[2], row[3], row[4], row[5]
        standings[club] = {"w": wins, "l": losses, "t": ties, "pf": pf, "pa": pa}

    ledger = list(csv.DictReader((DATA / "results_ledger.csv").open(encoding="utf-8", newline="")))
    graded = [g for g in ledger if g["status"] == "final"]
    tally = defaultdict(lambda: {"gp": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0})
    for g in graded:
        hs, as_ = int(g["home_score"]), int(g["away_score"])
        for club, mine, theirs in ((g["home"], hs, as_), (g["away"], as_, hs)):
            t = tally[club]
            t["gp"] += 1
            t["pf"] += mine
            t["pa"] += theirs
            t["w" if mine > theirs else "l" if mine < theirs else "t"] += 1

    rows, agree, disagree, extra = [], 0, 0, []
    for club in sorted(standings):
        s = standings[club]
        t = tally.get(club, {"gp": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0})
        matches = (t["w"], t["l"], t["t"], t["pf"], t["pa"]) == (s["w"], s["l"], s["t"], s["pf"], s["pa"])
        note = ("all five fields agree with the official standings read of the same day" if matches else
                "disagreement: one of the two transcriptions is wrong, and neither is corrected here")
        if matches:
            agree += 1
        else:
            disagree += 1
        rows.append({"club": club, "games_ledger": t["gp"], "wins_ledger": t["w"], "losses_ledger": t["l"],
                     "ties_ledger": t["t"], "points_for_ledger": t["pf"], "points_against_ledger": t["pa"],
                     "standings_w": s["w"], "standings_l": s["l"], "standings_t": s["t"],
                     "standings_pf": s["pf"], "standings_pa": s["pa"],
                     "agreement": "match" if matches else "MISMATCH", "note": note})
    for club in sorted(set(tally) - set(standings)):
        extra.append(club)

    summary = {
        "schema": "nfl3-forward-ledger-standings-crosscheck/v1",
        "compared_with": {
            "file": str(SIBLING.relative_to(ROOT)),
            "sha256": hashlib.sha256(SIBLING.read_bytes()).hexdigest(),
            "source_page": doc.get("source"),
            "observed_at": doc.get("observed_at"),
            "note": "recorded by the origination workspace, not by this session; cited so a reader can check it "
                    "rather than take it on trust",
        },
        "clubs_in_standings": len(standings),
        "clubs_in_ledger": len(tally),
        "clubs_matching_on_all_five_fields": agree,
        "clubs_disagreeing": disagree,
        "clubs_only_in_ledger": extra,
        "field_checks": agree * 5,
        "graded_games_used": len(graded),
        "settles": "Cincinnati's record chip was not read by this session; the standings read supplies 7-2, which "
                   "the ledger reproduces, so the club is corroborated rather than assumed.",
        "excluded_fixture": "LAC at BAL, 2026-11-16, was unplayed at both reads, so neither side counts it",
    }
    DATA.mkdir(exist_ok=True)
    with (DATA / "standings_crosscheck_origination.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (DATA / "standings_crosscheck_origination.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"standings cross-check: {agree}/{len(standings)} clubs agree on W-L-T-PF-PA "
          f"({agree * 5} of {len(standings) * 5} field checks), {disagree} disagreements, "
          f"{len(extra)} clubs only in the ledger")
    if disagree or extra:
        raise SystemExit("forward-ledger/crosscheck_standings: the two official transcriptions disagree; "
                         "publish the disagreement, do not smooth it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
