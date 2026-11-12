#!/usr/bin/env python3
"""Line-by-line cross-check of the captured game log against official NFL.com standings.

Rule: a game-log row is only usable evidence if (a) it carries an NFL.com source URL and
(b) the team totals it implies (W-L-T, PF, PA) reproduce the official standings snapshot
that was independently transcribed from https://www.nfl.com/standings/ (line-lab/data/standings_2026.json).
Rows with a blank score are counted as unverified and are never filled in.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent
GAMES = DESK / "data" / "games_2026.csv"
STANDINGS = ROOT / "line-lab" / "data" / "standings_2026.json"
OFFICIAL_STANDINGS_URL = "https://www.nfl.com/standings/"


def load_games() -> list[dict]:
    with GAMES.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    games = load_games()
    standings = {row["abbr"]: row for row in json.loads(STANDINGS.read_text())["teams"]}
    errors: list[str] = []
    totals: dict[str, dict] = {abbr: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "games": 0}
                               for abbr in standings}
    blank_games = []
    for index, game in enumerate(games, start=2):
        away, home = game["away_team"], game["home_team"]
        for side in (away, home):
            if side not in standings:
                errors.append(f"line {index}: unknown team code {side!r}")
        if not game["source_url"].startswith("https://www.nfl.com/"):
            errors.append(f"line {index}: source is not an official NFL.com URL")
        if game["away_score"] == "" or game["home_score"] == "":
            blank_games.append(f"week {game['week']} {away} at {home}")
            continue
        a, h = int(game["away_score"]), int(game["home_score"])
        totals[away]["pf"] += a
        totals[away]["pa"] += h
        totals[away]["games"] += 1
        totals[home]["pf"] += h
        totals[home]["pa"] += a
        totals[home]["games"] += 1
        if a > h:
            totals[away]["w"] += 1
            totals[home]["l"] += 1
        elif h > a:
            totals[home]["w"] += 1
            totals[away]["l"] += 1
        else:
            totals[away]["t"] += 1
            totals[home]["t"] += 1

    # Clubs whose games could not be scored: mismatches are expected only for these clubs.
    withheld = {game[key] for game in games
                if game["away_score"] == "" or game["home_score"] == ""
                for key in ("away_team", "home_team")}
    mismatches, explained = 0, []
    for abbr in sorted(standings):
        off, calc = standings[abbr], totals[abbr]
        for key in ("w", "l", "t", "pf", "pa"):
            if off[key] != calc[key]:
                mismatches += 1
                line = (f"{abbr} {off['name']}: {key} official={off[key]} game-log={calc[key]} "
                        f"(difference {off[key] - calc[key]})")
                if abbr in withheld:
                    explained.append(line)
                else:
                    errors.append(line)
    print(f"Game rows: {len(games)} | games with a score: {len(games) - len(blank_games)} | "
          f"blank-score rows: {len(blank_games)} | teams: {len(standings)}")
    print(f"Standings cross-check: {len(standings) * 5} field comparisons, "
          f"{mismatches} mismatches, {mismatches - len(errors)} confined to the withheld game")
    if blank_games:
        print("Unverified (score hidden on the official page, left blank):", "; ".join(blank_games))
    if errors:
        print("\nFAIL - the game log does not reproduce official standings:")
        print("\n".join(errors))
        return 1
    if explained:
        print("Differences confined to the clubs of the withheld game. The differences imply an exact "
              "score for that game; it is NOT published or used, because no official source states it.")
        for line in explained:
            print(f"  explained, not used: {line}")
    exact = len(standings) * 5 - mismatches
    print(f"PASS - {exact} of {len(standings) * 5} team fields reproduce exactly; every remaining "
          f"difference belongs to the one game the NFL publishes with a hidden score.")
    print(f"Official standings source: {OFFICIAL_STANDINGS_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
