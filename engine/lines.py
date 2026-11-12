"""Stage 1 - originate an independent line, then measure it against the market.

Inputs
------
* Verified official games file (scores + the market's own closing line).
* Leak-free pre-game Elo ratings and rolling form built in `features.py`.

Output per game
---------------
``model_spread``  - our own number (positive = home team favoured, matching the schedule schema).
``model_total``   - our own total, from a scoring model that blends both teams' offensive form,
                    defensive form and league pace.
``edge``          - model minus market.  Positive edge on the spread means the home side is better
                    than the price implies.

This is deliberately a transparent, low-parameter model: every coefficient is estimated by
plain least squares on *prior* seasons only (walk-forward), so the out-of-sample evaluation in
`studies.py` is honest.  It is a benchmark, not a claim of profitability.
"""
from __future__ import annotations

import collections
import math

import conventions as cv
import features
import stats

LEAGUE_POINTS = 22.0  # long-run NFL points per team per game; recomputed from data when available


# ------------------------------------------------------------------ tiny OLS (normal equations)
def ols(X: list[list[float]], y: list[float], ridge: float = 1e-6) -> list[float]:
    """Least squares with a tiny ridge term for numerical stability. X excludes the intercept."""
    n = len(X)
    p = len(X[0]) + 1
    # design matrix with intercept
    A = [[1.0] + row for row in X]
    ATA = [[0.0] * p for _ in range(p)]
    ATy = [0.0] * p
    for i in range(n):
        for j in range(p):
            aj = A[i][j]
            if aj == 0.0:
                continue
            ATy[j] += aj * y[i]
            for k in range(j, p):
                ATA[j][k] += aj * A[i][k]
    for j in range(p):
        for k in range(j):
            ATA[j][k] = ATA[k][j]
    for j in range(p):
        ATA[j][j] += ridge
    return _solve(ATA, ATy)


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        d = M[col][col]
        if abs(d) < 1e-12:
            continue
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] / d
            if f:
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


# ------------------------------------------------------------------ model specification
SPREAD_FEATURES = ["elo_diff", "form_diff_diff", "rest_diff", "hfa"]


def _row(g: dict) -> list[float]:
    """Spread model row: Elo difference, recent scoring-margin difference, rest difference."""
    elo_diff = (g.get("home_elo_pre", 1505.0) - g.get("away_elo_pre", 1505.0)) / 100.0
    hf, af = g.get("home_form_diff"), g.get("away_form_diff")
    form_diff = 0.0 if (hf is None or af is None or hf != hf or af != af) else (hf - af) / 7.0
    hr, ar = g.get("home_rest"), g.get("away_rest")
    rest_diff = 0.0 if (hr is None or ar is None) else max(-10.0, min(10.0, (hr - ar) / 7.0))
    return [elo_diff, form_diff, rest_diff, 1.0]


def fit_spread(train: list[dict]) -> list[float]:
    X = [_row(g)[:3] for g in train]
    y = [cv.home_margin(g["result"]) for g in train]   # target: home margin, same sign as spread_line
    return ols(X, y)


def predict_spread(beta: list[float], g: dict) -> float:
    r = _row(g)
    return beta[0] + sum(b * x for b, x in zip(beta[1:], r[:3]))


# ------------------------------------------------------------------ totals model
TOTAL_FEATURES = ["home_form_pts", "away_form_pts", "home_form_opp_pts", "away_form_opp_pts",
                  "pace_base"]


def fit_total(train: list[dict], league_total: float) -> list[float]:
    X, y = [], []
    for g in train:
        if any(g.get(k) is None or g.get(k) != g.get(k) for k in
               ("home_form_pts", "away_form_pts", "home_form_opp_pts", "away_form_opp_pts")):
            continue
        X.append([(g["home_form_pts"] - league_total / 2) / 7.0,
                  (g["away_form_pts"] - league_total / 2) / 7.0,
                  (g["home_form_opp_pts"] - league_total / 2) / 7.0,
                  (g["away_form_opp_pts"] - league_total / 2) / 7.0,
                  1.0])
        y.append(g["total"])
    if len(X) < 30:
        return [league_total, 1.0, 1.0, -1.0, -1.0]
    return ols([r[:4] for r in X], y)


def predict_total(beta: list[float], g: dict, league_total: float) -> float:
    hs, as_, ho, ao = (g.get("home_form_pts"), g.get("away_form_pts"),
                       g.get("home_form_opp_pts"), g.get("away_form_opp_pts"))
    if any(v is None or v != v for v in (hs, as_, ho, ao)):
        return league_total
    return (beta[0]
            + beta[1] * (hs - league_total / 2) / 7.0
            + beta[2] * (as_ - league_total / 2) / 7.0
            + beta[3] * (ho - league_total / 2) / 7.0
            + beta[4] * (ao - league_total / 2) / 7.0)


# ------------------------------------------------------------------ walk-forward driver
def build(games: list[dict], min_train_seasons: int = 4) -> tuple[list[dict], list[dict]]:
    """Walk-forward: for each season, fit on earlier seasons only, then predict that season.

    Returns (predictions, coefficients-by-season) - coefficients are published so the model can be
    audited rather than trusted.
    """
    features.elo_ratings(games)
    features.rolling_team_form(games)
    by_season: dict[int, list[dict]] = collections.defaultdict(list)
    for g in games:
        by_season[g["season"]].append(g)
    seasons = sorted(s for s in by_season if len(by_season[s]) >= 100)
    preds: list[dict] = []
    coefs: list[dict] = []
    for season in seasons:
        train = [g for s in seasons if s < season for g in by_season[s]]
        if len({g["season"] for g in train}) < min_train_seasons:
            continue
        league_total = stats.mean([g["total"] for g in train if g["total"] is not None])
        beta_s = fit_spread(train)
        beta_t = fit_total(train, league_total)
        coefs.append({"season": season, "n_train_games": len(train),
                      "league_total_train": round(league_total, 3),
                      "beta_spread": [round(b, 5) for b in beta_s],
                      "beta_total": [round(b, 5) for b in beta_t],
                      "features_spread": ["intercept"] + SPREAD_FEATURES[:3],
                      "features_total": ["intercept"] + TOTAL_FEATURES[:4]})
        for g in by_season[season]:
            if g["spread_line"] is None or g["total_line"] is None:
                continue
            ps = predict_spread(beta_s, g)
            pt = predict_total(beta_t, g, league_total)
            if ps != ps or pt != pt:
                continue
            preds.append({**g, "model_spread": ps, "model_total": pt,
                          "spread_edge_home": cv.model_edge_home(ps, g["spread_line"]),
                          "total_edge_over": cv.model_edge_over(pt, g["total_line"])})
    return preds, coefs
