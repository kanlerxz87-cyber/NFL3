#!/usr/bin/env python3
"""Cross-check the 2026 official corpus against itself.

Two independent things are compared:

1.  Every game row is checked for structural integrity (both scores present,
    both clubs among the 32 official abbreviations, no duplicate fixture).
2.  The game log is recomputed into a league table and compared, club by club
    and field by field, with the official standings table (OV-S10).

The second check is a real test, not a formality. Standings arithmetic
(W, L, T, PF, PA) is an independent official rendering of the same results. If a
single transcribed score is wrong, the affected clubs' PF/PA move, so the check
catches transcription errors without re-reading the source.

Exit status is non-zero if any mismatch is found, and the mismatches are printed
so they can be corrected at the source rather than papered over.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
GAMES = DATA / "games_2026_official.csv"
STANDINGS = DATA / "standings_2026_official.csv"


def read_games():
    with GAMES.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_standings():
    with STANDINGS.open(newline="", encoding="utf-8") as fh:
        return {row["team"]: row for row in csv.DictReader(fh)}


def recompute(games):
    table = {}

    def slot(team):
        return table.setdefault(team, {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "g": 0})

    for g in games:
        away, home = g["away_team"], g["home_team"]
        a, h = int(g["away_score"]), int(g["home_score"])
        for team in (away, home):
            slot(team)
        slot(away)["pf"] += a
        slot(away)["pa"] += h
        slot(away)["g"] += 1
        slot(home)["pf"] += h
        slot(home)["pa"] += a
        slot(home)["g"] += 1
        if a > h:
            slot(away)["w"] += 1
            slot(home)["l"] += 1
        elif h > a:
            slot(home)["w"] += 1
            slot(away)["l"] += 1
        else:
            slot(away)["t"] += 1
            slot(home)["t"] += 1
    return table


def main() -> int:
    games = read_games()
    standings = read_standings()
    problems = []

    # --- structural checks -------------------------------------------------
    # 136 completed games in Weeks 1-9 (official weekly schedule pages) plus the
    # one Week 10 game that had been played when the corpus was captured. The
    # expected total is pinned so a silently dropped or duplicated row fails CI.
    if len(games) != 137:
        problems.append(f"corpus has {len(games)} rows, expected 137")
    seen = set()
    for g in games:
        key = (g["week"], g["away_team"], g["home_team"])
        if key in seen:
            problems.append(f"duplicate fixture: {key}")
        seen.add(key)
        for field in ("away_score", "home_score"):
            if not g[field].strip():
                problems.append(f"blank {field} in {g['game_id']}")
            elif not g[field].strip().lstrip("-").isdigit():
                problems.append(f"non-integer {field} in {g['game_id']}")
        for team in (g["away_team"], g["home_team"]):
            if team not in standings:
                problems.append(f"{g['game_id']}: club {team} is not in the official standings table")
        if not g["source_url"].startswith("https://www.nfl.com/"):
            problems.append(f"{g['game_id']}: source is not an nfl.com page")

    # --- standings arithmetic ---------------------------------------------
    table = recompute(games)
    if set(table) != set(standings):
        problems.append(
            "club sets differ: corpus %d clubs, standings %d clubs" % (len(table), len(standings))
        )
    mismatches = []
    for team in sorted(set(table) & set(standings)):
        calc, off = table[team], standings[team]
        checks = {
            "wins": (calc["w"], int(off["wins"])),
            "losses": (calc["l"], int(off["losses"])),
            "ties": (calc["t"], int(off["ties"])),
            "points_for": (calc["pf"], int(off["points_for"])),
            "points_against": (calc["pa"], int(off["points_against"])),
        }
        for field, (mine, theirs) in checks.items():
            if mine != theirs:
                mismatches.append((team, field, mine, theirs))
        if calc["pf"] - calc["pa"] != int(off["net_points"]):
            mismatches.append((team, "net_points", calc["pf"] - calc["pa"], int(off["net_points"])))

    total_games_played = sum(v["g"] for v in table.values())
    if total_games_played != 2 * len(games):
        problems.append(f"games-played total {total_games_played} != 2x{len(games)}")

    report = {
        "games": len(games),
        "clubs_in_corpus": len(table),
        "clubs_in_standings": len(standings),
        "field_comparisons": len(standings) * 6,
        "mismatches": len(mismatches),
        "problems": len(problems),
    }
    print(f"Corpus: {report['games']} games, {report['clubs_in_corpus']} clubs.")
    print(
        f"Standings cross-check: {report['field_comparisons']} club-field comparisons, "
        f"{report['mismatches']} mismatch(es)."
    )
    for team, field, mine, theirs in mismatches:
        print(f"  MISMATCH {team} {field}: corpus={mine} official={theirs}")
    for problem in problems:
        print(f"  PROBLEM {problem}")
    return 1 if (mismatches or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
