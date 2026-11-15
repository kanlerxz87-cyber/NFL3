#!/usr/bin/env python3
"""A second, independent estimator: leak-free Elo.

Why a second estimator exists
-----------------------------
The registry's kill rule for the side strategies says a signal must survive *both* estimators. A single
model can look skilful because of one structural choice (here: a ridge fit on season-level scoring
rates). A second model built on a different principle — exponentially-updated Elo with a home-field
term — is a cheap independent check. Agreement is weak evidence; disagreement is a reason not to believe
either.

Leak-free rule
--------------
Every game's rating is taken from the state *before* that game was played. The update is applied after
the prediction is recorded. Ratings persist across seasons with a regression toward the mean applied at
each season boundary, which is the standard published treatment; the size of that regression is fixed
here in advance (one third) rather than fitted.

Parameters are pre-registered below and are not tuned on the evaluation corpus.
"""
from __future__ import annotations

import math

import common as C
import inputs

K = 20.0            # pre-registered Elo K
HFA_ELO = 48.0      # pre-registered home-field advantage in Elo points (~2 points of margin)
REGRESS = 1.0 / 3.0  # pre-registered regression to the mean at a season boundary
START = 1500.0
ELO_PER_POINT = 25.0  # 400 / 16: the conventional mapping from Elo to a point spread

PARAMS = {"k": K, "hfa_elo": HFA_ELO, "season_regression": REGRESS,
          "start_rating": START, "elo_points_per_margin_point": ELO_PER_POINT}


def run(season: int = C.SEASON) -> dict:
    games = [g for g in inputs.games() if inputs.played(g)]
    # The Elo seed needs history, so the loop runs over every played season in the snapshot.
    history = [g for g in C.read_csv(C.RAW / "games.csv")
               if g["game_type"] == "REG" and g["home_score"] not in ("", "NA")
               and g["away_score"] not in ("", "NA")]
    history.sort(key=lambda g: (g["gameday"] or "", g["game_id"]))

    ratings: dict[str, float] = {}
    last_season = None
    rows = []
    for g in history:
        season_now = int(g["season"])
        home, away = g["home_team"], g["away_team"]
        home_score, away_score = int(g["home_score"]), int(g["away_score"])
        if last_season is not None and season_now != last_season:
            for team in ratings:
                ratings[team] = START + (1 - REGRESS) * (ratings[team] - START)
        last_season = season_now
        rh = ratings.get(home, START)
        ra = ratings.get(away, START)
        expected = 1.0 / (1.0 + 10 ** (-(rh + HFA_ELO - ra) / 400.0))
        if season_now == season:
            margin_elo = (rh + HFA_ELO - ra)
            rows.append({
                "season": season_now, "week": int(g["week"]), "game_id": g["game_id"],
                "gameday": g["gameday"], "home": home, "away": away,
                "elo_home": rh, "elo_away": ra, "elo_diff": rh - ra,
                "p_home": expected,
                "model_margin": margin_elo / ELO_PER_POINT,
                "actual_margin": home_score - away_score,
                "actual_total": home_score + away_score,
            })
        # update after recording the prediction
        actual = 1.0 if home_score > away_score else 0.0 if home_score < away_score else 0.5
        mult = 1.0 + 0.5 * (abs(home_score - away_score) >= 14)
        delta = K * mult * (actual - expected)
        ratings[home] = rh + delta
        ratings[away] = ra - delta

    margin_err = [r["model_margin"] - r["actual_margin"] for r in rows]
    return {
        "mode": "elo",
        "params": PARAMS,
        "note": ("Elo is published as a second estimator so a claimed signal can be checked against a "
                 "different model family. It does not use injured-list information and is therefore a "
                 "clean baseline for the availability ablations."),
        "residual": {"margin_sd": C.sd(margin_err), "margin_bias": C.mean(margin_err),
                     "n": len(rows)},
        "counts": {"games": len(rows)},
        "rows": rows,
    }


def main() -> int:
    report = run()
    C.write_json("origination_elo.json", report)
    print(f"Elo: {report['counts']['games']} games, margin sd {C.r(report['residual']['margin_sd'])}, "
          f"bias {C.r(report['residual']['margin_bias'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
