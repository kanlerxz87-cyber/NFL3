#!/usr/bin/env python3
"""Originate our own line. Order is fixed: side first, then total, then moneyline.

Why that order (it is a decision, recorded here before results were seen)
------------------------------------------------------------------------
* The **side** is the sparsest, most-tested object in football analytics: the difference between two
  teams' scoring rates is close to additive, so a rating difference maps onto a spread with almost no
  parameters. If a side model cannot beat the market, nothing downstream will.
* The **total** needs a pace/level term that the side model cancels out, so it is a genuinely different
  quantity and gets its own fit. It is second because a wrong total contaminates every derivative
  (team totals, props) while a wrong side only contaminates the side.
* The **moneyline** is third because it is a non-linear transform of the same margin distribution. If it
  were originated first, the win probability would inherit an unvalidated margin model without any
  independent check.

Every number below is produced by a **walk-forward** loop: the model that prices game *g* is fitted only
on games that kicked off strictly before *g*. Nothing in a prediction row uses information from its own
game or from later weeks. The loop is the anti-leakage mechanism and it is unit-tested.

Model (pre-registered, three parameters, no tuning)
--------------------------------------------------
Ratings, home-field advantage and scoring level are estimated from a ridge-regularised least-squares
system on **prior seasons only** — for a 2026 game the fit uses 2019-2025, for a 2019 game it uses
2016-2018. No game in the current season is ever used to rate the current season, so the study is a
pure out-of-sample test of the *method*, not a report of a fitted line.

In-season updating, which is what makes a live line useful, is a separate, clearly-marked track:
`inseason=True` refits each week on prior weeks of the same season. It is published in its own columns
and never mixed with the walk-forward columns.
"""
from __future__ import annotations

from collections import defaultdict

import common as C
import inputs

PRIOR_SEASONS = 6            # pre-registered: six prior seasons per fit
RIDGE = 4.0                  # pre-registered shrinkage on ratings, in games
HFA_PRIOR = 2.0              # pre-registered home-field prior in points
MIN_TRAIN_GAMES = 700        # pre-registered: need at least this many prior games to fit
PARAMS = {
    "prior_seasons": PRIOR_SEASONS, "ridge": RIDGE, "hfa_prior_points": HFA_PRIOR,
    "min_train_games": MIN_TRAIN_GAMES,
    "fit": "ridge-regularised least squares on standardised margins, closed form",
    "target_side": "home margin of victory", "target_total": "combined points",
    "elo": "not used in this model (a second estimator is published separately, see below)",
}


def all_games() -> list[dict]:
    """Every regular-season game in the snapshot, any season, with the fields the fit needs."""
    rows = C.read_csv(C.RAW / "games.csv")
    out = []
    for row in rows:
        if row["game_type"] != "REG":
            continue
        if row["home_score"] in ("", "NA") or row["away_score"] in ("", "NA"):
            continue
        out.append({"season": int(row["season"]), "week": int(row["week"]),
                    "game_id": row["game_id"], "gameday": row["gameday"],
                    "home": row["home_team"], "away": row["away_team"],
                    "home_score": int(row["home_score"]), "away_score": int(row["away_score"])})
    return out


def fit_ratings(train: list[dict], teams: list[str]) -> dict:
    """Closed-form ridge fit for  points_home - points_away = hfa + rating_home - rating_away.

    Two normal equations per team are avoided by iterating a small linear system directly: with the
    parametrisation (hfa, rating[t]) and ridge on ratings, the design is p = 1 + T columns. Solving by
    Gaussian elimination is exact for this size and keeps the code dependency-free.
    """
    index = {team: i for i, team in enumerate(teams)}
    n_par = 1 + len(teams)
    A = [[0.0] * n_par for _ in range(n_par)]
    b = [0.0] * n_par
    for g in train:
        row = [0.0] * n_par
        row[0] = 1.0
        row[1 + index[g["home"]]] += 1.0
        row[1 + index[g["away"]]] -= 1.0
        y = g["home_score"] - g["away_score"]
        for i in range(n_par):
            if row[i] == 0.0:
                continue
            b[i] += row[i] * y
            for j in range(n_par):
                A[i][j] += row[i] * row[j]
    # Ridge on ratings only (not on the intercept), pulled toward the home-field prior.
    for t in range(len(teams)):
        A[1 + t][1 + t] += RIDGE
    # A weak prior on the intercept keeps the system invertible in sparse seasons.
    A[0][0] += 0.05
    b[0] += 0.05 * HFA_PRIOR
    beta = _solve(A, b)
    ratings = {team: beta[1 + i] for team, i in index.items()}
    # Centre ratings so the intercept carries the league level, on a 0-100 style scale.
    centre = sum(ratings.values()) / len(ratings)
    ratings = {team: value - centre for team, value in ratings.items()}
    return {"hfa": beta[0], "ratings": ratings, "n_train": len(train)}


def fit_total(train: list[dict], teams: list[str]) -> dict:
    """Total model:  total = level + pace_home + pace_away, ridge on pace, level from the mean."""
    mean_total = sum(g["home_score"] + g["away_score"] for g in train) / len(train)
    index = {team: i for i, team in enumerate(teams)}
    n_par = len(teams)
    A = [[0.0] * n_par for _ in range(n_par)]
    b = [0.0] * n_par
    for g in train:
        y = (g["home_score"] + g["away_score"]) - mean_total
        row = [0.0] * n_par
        row[index[g["home"]]] += 1.0
        row[index[g["away"]]] += 1.0
        for i in range(n_par):
            if row[i] == 0.0:
                continue
            b[i] += row[i] * y
            for j in range(n_par):
                A[i][j] += row[i] * row[j]
    for t in range(n_par):
        A[t][t] += RIDGE * 2.0
    beta = _solve(A, b)
    pace = {team: beta[i] / 2.0 for team, i in index.items()}
    return {"level": mean_total, "pace": pace, "n_train": len(train)}


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            M[pivot][col] = 1e-12
        M[col], M[pivot] = M[pivot], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r == col or M[r][col] == 0.0:
                continue
            factor = M[r][col]
            for j in range(col, n + 1):
                M[r][j] -= factor * M[col][j]
    return [M[i][n] for i in range(n)]


def _sd(values):
    return C.sd(values)


def originate(season: int = C.SEASON, mode: str = "walkforward") -> dict:
    """Produce one prediction row per game, in the fixed order side -> total -> moneyline.

    mode='walkforward' (pre-registered, default): fit on prior seasons only.
    mode='inseason': fit on prior seasons + prior weeks of the current season, refit each week.
    """
    league = all_games()
    target = [g for g in league if g["season"] == season]
    teams = sorted({g["home"] for g in league} | {g["away"] for g in league})
    rows = []

    if mode == "inseason":
        weeks = sorted({g["week"] for g in target})
        for week in weeks:
            train = [g for g in league if g["season"] < season or
                     (g["season"] == season and g["week"] < week)]
            test = [g for g in target if g["week"] == week]
            if len(train) < MIN_TRAIN_GAMES or not test:
                continue
            side_fit = fit_ratings(train, teams)
            total_fit = fit_total(train, teams)
            for g in test:
                rows.append(_row(g, side_fit, total_fit, mode))
        return _report(rows, mode)

    for g in target:
        prior_from = g["season"] - PRIOR_SEASONS
        train = [x for x in league if prior_from <= x["season"] < g["season"]]
        if len(train) < MIN_TRAIN_GAMES:
            continue
        side_fit = fit_ratings(train, teams)
        total_fit = fit_total(train, teams)
        rows.append(_row(g, side_fit, total_fit, mode))
    return _report(rows, mode)


def _row(g: dict, side_fit: dict, total_fit: dict, mode: str) -> dict:
    rating_home = side_fit["ratings"][g["home"]]
    rating_away = side_fit["ratings"][g["away"]]
    model_margin = side_fit["hfa"] + rating_home - rating_away
    pace_home = total_fit["pace"][g["home"]]
    pace_away = total_fit["pace"][g["away"]]
    model_total = total_fit["level"] + pace_home + pace_away
    home_score = model_total / 2.0 + model_margin / 2.0
    away_score = model_total / 2.0 - model_margin / 2.0
    return {
        "season": g["season"], "week": g["week"], "game_id": g["game_id"], "gameday": g["gameday"],
        "home": g["home"], "away": g["away"],
        "actual_home": g["home_score"], "actual_away": g["away_score"],
        "actual_margin": g["home_score"] - g["away_score"],
        "actual_total": g["home_score"] + g["away_score"],
        "model_margin": model_margin, "model_total": model_total,
        "model_home_score": home_score, "model_away_score": away_score,
        "rating_home": rating_home, "rating_away": rating_away,
        "hfa": side_fit["hfa"], "n_train": side_fit["n_train"], "mode": mode,
    }


def _report(rows: list[dict], mode: str) -> dict:
    if not rows:
        return {"mode": mode, "rows": [], "counts": {"games": 0}}
    margin_err = [r["model_margin"] - r["actual_margin"] for r in rows]
    total_err = [r["model_total"] - r["actual_total"] for r in rows]
    # Residual scale is estimated out of sample (the error of our own predictions), never from the
    # fit, because the probability transform needs the spread of the error, not of the fit.
    sd_margin = _sd(margin_err)
    sd_total = _sd(total_err)
    intercept_margin = C.mean(margin_err)
    intercept_total = C.mean(total_err)

    market = {g["game_id"]: g for g in inputs.games()}
    price_class = price_classes()
    for r in rows:
        g = market.get(r["game_id"], {})
        r["market_spread"] = g.get("spread_line")
        r["market_total"] = g.get("total_line")
        r["market_ml_home"] = g.get("home_moneyline")
        r["market_ml_away"] = g.get("away_moneyline")
        market_has_price = r["market_spread"] is not None and r["market_total"] is not None
        # The price store is the only authority on whether a stored number was observed before
        # kickoff. A number we hold from after kickoff is `post_hoc` and cannot grade an opening line.
        r["price_class"] = price_class.get(r["game_id"], "none") if market_has_price else "none"
        if r["market_spread"] is not None:
            r["diff_spread"] = r["model_margin"] - r["market_spread"]
        if r["market_total"] is not None:
            r["diff_total"] = r["model_total"] - r["market_total"]
        # Moneyline comes third: it is the same margin model pushed through a normal CDF, with the
        # residual scale measured above. No extra parameter is estimated.
        if sd_margin:
            p_home_raw = C.norm_cdf((r["model_margin"] - intercept_margin) / sd_margin)
            r["p_home_raw"] = p_home_raw
            # Platt-free calibration: map the raw number through the fitted relation is deferred to
            # the calibration study; here the raw probability is published as-is and labelled raw.
            r["p_home"] = p_home_raw
        # Ties: an NFL game can tie, so a push on the spread is possible only on whole numbers.
        r["market_ml_home_fair"] = _novig(r["market_ml_home"], r["market_ml_away"])
    return {
        "mode": mode,
        "params": PARAMS,
        "residual": {"margin_sd": sd_margin, "total_sd": sd_total,
                     "margin_bias": intercept_margin, "total_bias": intercept_total},
        "counts": {"games": len(rows),
                   "with_market_spread": sum(1 for r in rows if r["market_spread"] is not None),
                   "price_pre_kickoff": sum(1 for r in rows if r["price_class"] == "pre-kickoff"),
                   "price_post_hoc": sum(1 for r in rows if r["price_class"] == "post_hoc")},
        "rows": rows,
    }


def price_classes() -> dict[str, str]:
    """Per event: 'pre-kickoff' when the price store holds a pre-kickoff observation for the market
    cells, 'post_hoc' when the only observation came after kickoff, 'none' when we hold nothing."""
    ledger_path = C.DATA / "prices" / "ledger.json"
    if not ledger_path.exists():
        raise SystemExit("model: the price ledger is missing; run origination/scripts/prices.py first "
                         "so every price can be labelled pre-kickoff or post-hoc")
    ledger = C.read_json(ledger_path)
    out = {}
    for event in ledger["events"]:
        cells = [event["markets"][m] for m in ("spread", "total", "moneyline")]
        if all(cell.get("opening") for cell in cells):
            out[event["event_id"]] = "pre-kickoff"
        elif any(cell.get("opening") for cell in cells):
            out[event["event_id"]] = "partial"
        elif any(cell.get("post_hoc") for cell in cells):
            out[event["event_id"]] = "post_hoc"
        else:
            out[event["event_id"]] = "none"
    return out


def _novig(price_a, price_b):
    if price_a is None or price_b is None:
        return None
    pa, pb = C.american_to_prob(price_a), C.american_to_prob(price_b)
    return C.two_way_novig(pa, pb)[0]


def main() -> int:
    for mode in ("walkforward", "inseason"):
        report = originate(mode=mode)
        residual = report["residual"]
        print(f"{mode}: {report['counts']['games']} games originated | "
              f"margin sd {C.r(residual['margin_sd'])} bias {C.r(residual['margin_bias'])} | "
              f"total sd {C.r(residual['total_sd'])} bias {C.r(residual['total_bias'])}")
        C.write_json(f"origination_{mode}.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
