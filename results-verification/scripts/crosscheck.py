#!/usr/bin/env python3
"""Cross-check the official NFL.com score pages against the community game file.

Reads results-verification/data/official_scores_2026/week_*.json (values transcribed from the
official https://www.nfl.com/scores/2026/week-N pages on 2026-11-15 UTC) and compares every
final score with data/raw/games.csv (community nflverse file, digest-verified, NOT official).

Writes results-verification/data/verification_report.json. Fails loudly (exit 1) if:
  - any week JSON is missing or has the wrong game count,
  - an official game does not match exactly one community row,
  - a community Week 1-9 final row is never matched,
  - a score disagrees.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DATA = HERE / "data"
SCORES = DATA / "official_scores_2026"
GAMES = HERE.parent / "data" / "raw" / "games.csv"

EXPECTED_COUNTS = {1: 16, 2: 16, 3: 16, 4: 16, 5: 15, 6: 14, 7: 14, 8: 14, 9: 15}

# Documented normalization: the official NFL.com score pages render Arizona's club logo code as "AZ"
# and its game-URL slug as "cardinals", while the community nflverse file uses the franchise code "ARI".
# Official values are kept verbatim ("AZ") in the week JSON files; this map is applied only when
# forming the join key against data/raw/games.csv. No other club code required a mapping.
TEAM_ALIASES = {"AZ": "ARI"}


def code(team: str) -> str:
    return TEAM_ALIASES.get(team, team)


def month_day(context: str) -> str | None:
    months = {
        "January": "01", "February": "02", "March": "03", "April": "04", "May": "05", "June": "06",
        "July": "07", "August": "08", "September": "09", "October": "10", "November": "11", "December": "12",
    }
    import re

    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})",
                  context)
    if not m:
        return None
    return f"{months[m.group(1)]}-{int(m.group(2)):02d}"


def main() -> int:
    weeks: dict[int, dict] = {}
    for wk in range(1, 10):
        p = SCORES / f"week_{wk:02d}.json"
        if not p.exists():
            print(f"FAIL missing week file {p.name}")
            return 1
        d = json.loads(p.read_text())
        if d["week"] != wk or len(d["games"]) != EXPECTED_COUNTS[wk]:
            print(f"FAIL week {wk}: expected {EXPECTED_COUNTS[wk]} games, file says {len(d['games'])}")
            return 1
        weeks[wk] = d

    with GAMES.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["season"] == "2026" and r["game_type"] == "REG"]
    community = {}
    for r in rows:
        wk = int(r["week"])
        if 1 <= wk <= 9:
            community[(wk, r["away_team"], r["home_team"])] = r

    per_game, mismatches, unmatched, duplicate_hits = [], [], [], []
    matched_community_keys = set()
    total = matched_score = matched_date = 0
    for wk in range(1, 10):
        d = weeks[wk]
        for g in d["games"]:
            total += 1
            key = (wk, code(g["away_team"]), code(g["home_team"]))
            hits = [k for k in community if k[0] == wk and {k[1], k[2]} == {code(g["away_team"]), code(g["home_team"])}]
            entry = {
                "week": wk,
                "away_team": g["away_team"], "home_team": g["home_team"],
                "official_away_score": g["away_score"], "official_home_score": g["home_score"],
                "official_context": g["context"],
                "source_url": d["url"],
                "observed_at": d["observed_at"],
            }
            if key in community:
                row = community[key]
                entry["game_id"] = row["game_id"]
                entry["community_away_score"] = int(row["away_score"])
                entry["community_home_score"] = int(row["home_score"])
                entry["community_gameday"] = row["gameday"]
                entry["score_match"] = (
                    entry["community_away_score"] == g["away_score"]
                    and entry["community_home_score"] == g["home_score"]
                )
                md = month_day(g["context"])
                entry["official_month_day"] = md
                entry["date_match"] = md is not None and row["gameday"].endswith(md)
                matched_community_keys.add(key)
                if not entry["score_match"]:
                    mismatches.append(entry)
                else:
                    matched_score += 1
                if entry["date_match"]:
                    matched_date += 1
            else:
                entry["score_match"] = None
                entry["community_away_score"] = None
                entry["community_home_score"] = None
                if len(hits) == 1:
                    # same pair found with reversed home/away: flag, do not silently accept
                    alt = hits[0]
                    entry["reversed_pair_found"] = True
                    entry["reversed_pair_game_id"] = community[alt]["game_id"]
                unmatched.append(entry)
                matched_community_keys.add(key) if False else None
            per_game.append(entry)

    never_matched = [k for k in community if k not in matched_community_keys]

    report = {
        "schema_version": 1,
        "generated_by": "results-verification/scripts/crosscheck.py (session arena/16183225-nfl3)",
        "official_source": "https://www.nfl.com/scores/2026/week-1 .. week-9 (official NFL publisher)",
        "observed_window": "2026-11-15T12:59:59Z .. 2026-11-15T13:46:00Z",
        "community_file": "data/raw/games.csv (nflverse community data; digest-verified in data/raw/manifest.json; NOT official)",
        "counts": {
            "official_games": total,
            "community_rows_w1_w9": len(community),
            "score_matches": matched_score,
            "score_mismatches": len(mismatches),
            "date_matches": matched_date,
            "official_games_without_community_match": len(unmatched),
            "community_rows_never_matched_officially": len(never_matched),
        },
        "mismatches": mismatches,
        "unmatched": unmatched,
        "community_never_matched": [
            {"week": k[0], "away_team": k[1], "home_team": k[2], "game_id": community[k]["game_id"],
             "away_score": community[k]["away_score"], "home_score": community[k]["home_score"]}
            for k in sorted(never_matched)
        ],
        "games": per_game,
    }
    (DATA / "verification_report.json").write_text(json.dumps(report, indent=2))

    ok = (total == 136 and len(community) == 136 and not mismatches
          and not unmatched and not never_matched and matched_score == 136)
    print(f"official games: {total} | community rows: {len(community)} | score matches: {matched_score} "
          f"| date matches: {matched_date} | mismatches: {len(mismatches)} | unmatched: {len(unmatched)} "
          f"| community-never-matched: {len(never_matched)}")
    if mismatches:
        for m in mismatches:
            print("  MISMATCH:", m["game_id"], m["community_away_score"], "vs", m["official_away_score"], "/",
                  m["community_home_score"], "vs", m["official_home_score"])
    if not ok:
        print("FAIL: verification is not complete; see counts above.")
        return 1
    print("PASS: all 136 Week 1-9 finals agree between the official NFL.com score pages and data/raw/games.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
