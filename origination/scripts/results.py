#!/usr/bin/env python3
"""Verified results feed.

A backtest is only as good as the number that settles it. This script builds the settlement feed and
then *reconciles the whole of it* against the official NFL standings, so a wrong score fails the build
instead of quietly grading a bet.

Reconciliation rule (mechanical, no judgement)
----------------------------------------------
For all 32 clubs, over every played game in the schedule:
    wins, losses, points-for and points-against must equal the official standings row exactly.
Summing points-for across both teams equals the league total, so a single transposed score breaks at
least two club rows. If any club disagrees the build exits non-zero and says which club and which field.

Official label vs community label
---------------------------------
* The **official** total (wins/losses/points for/points against per club) is transcribed once from
  nfl.com/standings into `data/official_standings_2026.json` with its observation timestamp.
* The **game-level** score is the community `schedules` release. It is not official. It is accepted as
  the settlement source *only* because the full 32-club reconciliation passes; that is the check that
  makes it trustworthy as a grader, and it is published on every row.
"""
from __future__ import annotations

import datetime as dt

import common as C
import inputs

FEED = C.DATA / "results.json"


def official_slug(code: str) -> str:
    """nfl.com's 2026 standings publish AZ for Arizona. Los Angeles keeps LA on both sides."""
    return {"ARI": "AZ"}.get(code, code)


def build() -> dict:
    games = inputs.games()
    rows = []
    for g in games:
        played = inputs.played(g)
        diff = (g["home_score"] - g["away_score"]) if played else None
        rows.append({
            "event_id": g["game_id"], "week": g["week"], "gameday": g["gameday"],
            "away": g["away"], "home": g["home"],
            "away_official_code": official_slug(g["away"]), "home_official_code": official_slug(g["home"]),
            "away_score": g["away_score"], "home_score": g["home_score"],
            "total": (g["away_score"] + g["home_score"]) if played else None,
            "margin_home": diff,
            "winner": (None if not played else
                       (g["home"] if diff > 0 else g["away"] if diff < 0 else "TIE")),
            "played": played,
            "community_source_url": C.G["schedules"],
            "official_source_url": C.S["standings"],
        })

    official = {row["code"]: row for row in inputs.standings()}  # keyed by official code
    agg = {code: {"gp": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0} for code in official}
    feed_to_official = {code: official_slug(code) for code in C.FULL_NAME}
    for g in rows:
        if not g["played"]:
            continue
        for side, opp in (("away", "home"), ("home", "away")):
            code = feed_to_official[g[side]]
            agg[code]["gp"] += 1
            agg[code]["pf"] += g[f"{side}_score"]
            agg[code]["pa"] += g[f"{opp}_score"]
            if g[f"{side}_score"] > g[f"{opp}_score"]:
                agg[code]["w"] += 1
            elif g[f"{side}_score"] < g[f"{opp}_score"]:
                agg[code]["l"] += 1
            else:
                agg[code]["t"] += 1

    checks, failures = [], []
    for code, off in sorted(official.items()):
        mine = agg[code]
        for field, label in (("w", "wins"), ("l", "losses"), ("t", "ties"),
                             ("pf", "points for"), ("pa", "points against")):
            ok = mine[field] == off[field]
            checks.append({"code": code, "club": C.FULL_NAME.get(code, C.FULL_NAME["ARI"]),
                           "official_code": off["code"], "field": label,
                           "official": off[field], "feed": mine[field], "match": ok})
            if not ok:
                failures.append(f"{off['code']} {label}: official {off[field]} != feed {mine[field]}")

    report = {}
    totals = {"pf": sum(v["pf"] for v in agg.values()), "pa": sum(v["pa"] for v in agg.values()),
              "w": sum(v["w"] for v in agg.values()), "l": sum(v["l"] for v in agg.values()),
              "t": sum(v["t"] for v in agg.values())}
    official_totals = {"pf": sum(o["pf"] for o in official.values()),
                       "pa": sum(o["pa"] for o in official.values()),
                       "w": sum(o["w"] for o in official.values()),
                       "l": sum(o["l"] for o in official.values()),
                       "t": sum(o["t"] for o in official.values())}
    if totals != official_totals:
        failures.append(f"league totals differ: feed {totals} vs official {official_totals}")

    played_rows = [r for r in rows if r["played"]]
    report = {
        "schema_version": 1,
        "built_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "settlement_authority": "official final score, reconciled (see policy P07)",
        "official_standings": {
            "url": C.S["standings"], "observed_at": inputs.standings()[0]["observed_at"],
            "clubs": len(official),
        },
        "community_games": {"url": C.G["schedules"],
                            "sha256": C.manifest()["files"].get("games", {}).get("sha256")},
        "counts": {
            "games_scheduled": len(rows),
            "games_played": len(played_rows),
            "games_unplayed": len(rows) - len(played_rows),
            "ties": sum(1 for r in played_rows if r["winner"] == "TIE"),
            "team_fields_checked": len(checks),
            "team_fields_matching": sum(1 for c in checks if c["match"]),
            "clubs_checked": len(official),
            "weeks_covered": sorted({r["week"] for r in played_rows}),
        },
        "league_totals": {"feed": totals, "official": official_totals, "match": totals == official_totals},
        "reconciliation": checks,
        "failures": failures,
        "passed": not failures,
        "statement": ("Every one of the {n} club x field checks reproduces nfl.com's official 2026 standings. "
                      "That is what makes this feed usable as a settlement source.").format(n=len(checks))
        if not failures else "Reconciliation FAILED; no backtest may settle against this feed.",
    }
    C.write_json("results.json", report)
    return report


def main() -> int:
    report = build()
    c = report["counts"]
    print(f"Results feed: {c['games_played']} played of {c['games_scheduled']} scheduled; "
          f"{c['team_fields_matching']}/{c['team_fields_checked']} club x field checks match official standings.")
    if report["failures"]:
        print("FAILED:")
        for item in report["failures"][:20]:
            print(" -", item)
        return 1
    print("Reconciliation: PASS — official standings totals reproduced exactly "
          f"(PF {report['league_totals']['feed']['pf']}, PA {report['league_totals']['feed']['pa']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
