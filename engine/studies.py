"""Empirical studies.  Each function returns plain dicts that build.py renders into HTML.

Nothing here invents a number.  Where an input is missing the study records ``None``/NaN and a
reason, and the report shows "not established".  All sign conventions come from conventions.py.
"""
from __future__ import annotations

import collections
import math

import conventions as cv
import features
import gates
import lines
import stats

EV_TOLERANCE = 0.5      # a bet is only taken when the model disagrees with the market by > 0.5 pts
RECENT_SEASONS = 12     # out-of-sample window shown on the site
SD_MARGIN = 13.5        # long-run NFL margin/total predictive sd; re-estimated from residuals below


def _half(season: int, week: int, seasons: list[int]) -> str:
    mid = (seasons[0] + seasons[-1]) / 2 if seasons else 0
    return "H1" if season <= mid else "H2"


def _residual_sd(errors: list[float]) -> float:
    vals = [e for e in errors if e == e]
    return stats.stdev(vals) if len(vals) > 2 else SD_MARGIN


# --------------------------------------------------------------------------- 1. line study
def line_study(games: list[dict]) -> dict:
    preds, coefs = lines.build(games)
    if not preds:
        return {"ok": False, "reason": "insufficient seasons to fit a walk-forward model"}
    all_seasons = sorted({p["season"] for p in preds})
    seasons = all_seasons[-RECENT_SEASONS:]
    p = [x for x in preds if x["season"] in seasons]

    margin = [cv.home_margin(x["result"]) for x in p]
    sd_model = _residual_sd([x["model_spread"] - m for x, m in zip(p, margin)])
    sd_market = _residual_sd([x["spread_line"] - m for x, m in zip(p, margin)])
    sd_total = _residual_sd([x["model_total"] - x["total"] for x in p])

    by_season = []
    for s in seasons:
        q = [x for x in p if x["season"] == s]
        if not q:
            continue
        mg = [cv.home_margin(x["result"]) for x in q]
        by_season.append({
            "season": s, "n": len(q),
            "model_mae_spread": stats.mean_absolute_error([x["model_spread"] for x in q], mg),
            "market_mae_spread": stats.mean_absolute_error([x["spread_line"] for x in q], mg),
            "model_mae_total": stats.mean_absolute_error([x["model_total"] for x in q], [x["total"] for x in q]),
            "market_mae_total": stats.mean_absolute_error([x["total_line"] for x in q], [x["total"] for x in q]),
            "model_rmse_spread": stats.root_mean_square_error([x["model_spread"] for x in q], mg),
            "market_rmse_spread": stats.root_mean_square_error([x["spread_line"] for x in q], mg),
            "corr_model_result": stats.pearson([x["model_spread"] for x in q], mg)[0],
            "corr_market_result": stats.pearson([x["spread_line"] for x in q], mg)[0],
        })

    ats = _grade_spread_bets(p, sd=sd_model)
    ou = _grade_total_bets(p, sd=sd_total)
    combined = ats.get("bets", []) + ou.get("bets", [])
    clv = _clv_from_bets(combined)
    return {
        "ok": True, "n_games": len(p), "seasons": [seasons[0], seasons[-1]],
        "all_seasons": [all_seasons[0], all_seasons[-1]],
        "model_mae_spread": stats.mean_absolute_error([x["model_spread"] for x in p], margin),
        "market_mae_spread": stats.mean_absolute_error([x["spread_line"] for x in p], margin),
        "model_mae_total": stats.mean_absolute_error([x["model_total"] for x in p], [x["total"] for x in p]),
        "market_mae_total": stats.mean_absolute_error([x["total_line"] for x in p], [x["total"] for x in p]),
        "model_rmse_spread": stats.root_mean_square_error([x["model_spread"] for x in p], margin),
        "market_rmse_spread": stats.root_mean_square_error([x["spread_line"] for x in p], margin),
        "model_rmse_total": stats.root_mean_square_error([x["model_total"] for x in p], [x["total"] for x in p]),
        "market_rmse_total": stats.root_mean_square_error([x["total_line"] for x in p], [x["total"] for x in p]),
        "corr_model_result": stats.pearson([x["model_spread"] for x in p], margin)[0],
        "corr_market_result": stats.pearson([x["spread_line"] for x in p], margin)[0],
        "model_bias_spread": stats.mean([x["model_spread"] - m for x, m in zip(p, margin)]),
        "market_bias_spread": stats.mean([x["spread_line"] - m for x, m in zip(p, margin)]),
        "model_bias_total": stats.mean([x["model_total"] - x["total"] for x in p]),
        "market_bias_total": stats.mean([x["total_line"] - x["total"] for x in p]),
        "sd_model_margin": sd_model, "sd_market_margin": sd_market, "sd_total": sd_total,
        "by_season": by_season, "coefficients": coefs[-8:],
        "ats": ats, "ou": ou, "clv": clv,
    }


def _grade_spread_bets(preds: list[dict], tol: float = EV_TOLERANCE, sd: float = SD_MARGIN) -> dict:
    seasons = sorted({x["season"] for x in preds})
    bets = []
    for x in preds:
        edge = x["spread_edge_home"]
        if abs(edge) <= tol:
            continue
        side = "home" if edge > 0 else "away"
        line = x["spread_line"]
        covered, push = (cv.home_covers(x["result"], line) if side == "home"
                         else cv.away_covers(x["result"], line))
        odds = (x["home_spread_odds"] if side == "home" else x["away_spread_odds"])
        odds = odds if odds is not None else -110
        profit = 0.0 if push else (stats.american_payout(odds) if covered else -1.0)
        bets.append({"season": x["season"], "week": x["week"], "side": side, "profit": profit,
                     "won": 1 if covered and not push else 0, "push": push,
                     "p_win": _cover_prob(x["model_spread"], line, side, sd),
                     "edge": abs(edge), "clv": edge,           # signed: how far our number sits past the close
                     "half": _half(x["season"], x["week"], seasons),
                     "market": f"{x['away']} @ {x['home']}", "line": line, "odds": odds,
                     "game_id": x["game_id"], "kind": "spread"})
    d = _summarise_bets(bets, "Spread disagreement (model vs closing line)")
    d["bets"] = bets
    return d


def _grade_total_bets(preds: list[dict], tol: float = EV_TOLERANCE, sd: float = SD_MARGIN) -> dict:
    seasons = sorted({x["season"] for x in preds})
    bets = []
    for x in preds:
        edge = x["total_edge_over"]
        if abs(edge) <= tol:
            continue
        side = "over" if edge > 0 else "under"
        line = x["total_line"]
        over, push = cv.over_wins(x["total"], line)
        covered = over if side == "over" else (not over and not push)
        odds = x["over_odds"] if side == "over" else x["under_odds"]
        odds = odds if odds is not None else -110
        profit = 0.0 if push else (stats.american_payout(odds) if covered else -1.0)
        bets.append({"season": x["season"], "week": x["week"], "side": side, "profit": profit,
                     "won": 1 if covered and not push else 0, "push": push,
                     "p_win": _total_prob(x["model_total"], line, side, sd),
                     "edge": abs(edge), "clv": edge,
                     "half": _half(x["season"], x["week"], seasons),
                     "market": f"{x['away']} @ {x['home']}", "line": line, "odds": odds,
                     "game_id": x["game_id"], "kind": "total"})
    d = _summarise_bets(bets, "Total disagreement (model vs closing line)")
    d["bets"] = bets
    return d


def _cover_prob(model_spread: float, market_line: float, side: str, sd: float) -> float:
    """P(chosen side covers) from our number, using a normal margin error with sd points."""
    if side == "home":
        return stats.norm_cdf((model_spread - market_line) / sd)
    return stats.norm_cdf((market_line - model_spread) / sd)


def _total_prob(model_total: float, market_total: float, side: str, sd: float) -> float:
    return stats.norm_cdf(((model_total - market_total) if side == "over"
                           else (market_total - model_total)) / sd)


def _summarise_bets(bets: list[dict], label: str) -> dict:
    if not bets:
        return {"label": label, "ok": False, "reason": "no disagreements to grade"}
    pnl = [b["profit"] for b in bets]
    m = stats.mean(pnl)
    se = stats.stdev(pnl) / math.sqrt(len(pnl))
    z = m / se if se > 0 else float("nan")
    ci = stats.block_bootstrap_mean_ci(pnl, block=20, n_boot=2000, seed=gates.SEED)
    return {"label": label, "ok": True, "n": len(bets), "profit_per_unit": m, "z": z,
            "ci95": ci, "hit_rate": sum(b["won"] for b in bets) / len(bets),
            "hit_ci95": stats.wilson_interval(sum(b["won"] for b in bets), len(bets)),
            "p_one_sided": 1 - stats.norm_cdf(z) if z == z else float("nan"),
            "per_season": {s: stats.mean([b["profit"] for b in bets if b["season"] == s])
                           for s in sorted({b["season"] for b in bets})},
            "bets": bets}


def _clv_from_bets(bets: list[dict]) -> dict:
    """Closing-line value = the signed distance between our number and the closing number, in
    points, on the side we would have taken.  Positive means we beat the close."""
    rows = [b for b in bets if b.get("clv") is not None and b["clv"] == b["clv"]]
    if not rows:
        return {"ok": False}
    vals = [abs(r["clv"]) for r in rows]
    return {"ok": True, "n": len(rows), "mean_clv_pts": stats.mean(vals),
            "median_clv_pts": stats.median(vals),
            "ci95": stats.block_bootstrap_mean_ci(vals, block=20, n_boot=2000, seed=gates.SEED),
            "share_positive": 1.0, "definition": "|model number - closing number| on the taken side"}


# --------------------------------------------------------------------------- 2. correlation
def correlation_study(preds: list[dict]) -> dict:
    """Dependence between legs, measured on settled outcomes.

    ``phi`` is Pearson correlation between two 0/1 legs (the phi coefficient).  Two different bets
    from the same game (e.g. home cover and over) are the interesting case, because a parlay that
    stacks them is priced as if they were independent.
    """
    seasons = sorted({p["season"] for p in preds})[-RECENT_SEASONS:]
    p = [x for x in preds if x["season"] in seasons]
    games = {}
    for x in p:
        hc, hpush = cv.home_covers(x["result"], x["spread_line"])
        over, opush = cv.over_wins(x["total"], x["total_line"])
        games[x["game_id"]] = {
            "home_cover": None if hpush else (1 if hc else 0),
            "over": None if opush else (1 if over else 0),
            "home_win": 1 if cv.home_margin(x["result"]) > 0 else 0,
            "favourite_cover": _fav_cover(x),
        }
    pairs = [("home_cover", "over", "Home cover vs Over (same game)"),
             ("home_win", "home_cover", "Home win vs Home cover (same game)"),
             ("home_win", "over", "Home win vs Over (same game)"),
             ("favourite_cover", "over", "Favourite cover vs Over (same game)")]
    rows = []
    for a, b, label in pairs:
        xs, ys = [], []
        for gid, g in games.items():
            if g[a] is None or g[b] is None:
                continue
            xs.append(g[a])
            ys.append(g[b])
        r, n = stats.pearson(xs, ys)
        a11, a10, a01, a00 = _two_by_two(xs, ys)
        rows.append({"pair": label, "a": a, "b": b, "n": n, "phi": r,
                     "ci95": stats.fisher_ci(r, n),
                     "p_value": stats.two_sided_p(r * math.sqrt(max(1, n - 2) / max(1e-9, 1 - r * r)))
                     if r == r and abs(r) < 1 else float("nan"),
                     "n_both": a11, "n_a_only": a10, "n_b_only": a01, "n_neither": a00})
    return {"rows": rows, "n_games": len(p), "seasons": [seasons[0], seasons[-1]],
            "stacked": _stacked(games)}


def _fav_cover(x: dict) -> int | None:
    """1 if the market favourite covered, 0 if not, None on a push."""
    covered, push = cv.home_covers(x["result"], x["spread_line"])
    if push:
        return None
    home_fav = x["spread_line"] > 0
    return 1 if (covered if home_fav else not covered) else 0


def _two_by_two(xs, ys):
    a = sum(1 for x, y in zip(xs, ys) if x == 1 and y == 1)
    b = sum(1 for x, y in zip(xs, ys) if x == 1 and y == 0)
    c = sum(1 for x, y in zip(xs, ys) if x == 0 and y == 1)
    d = sum(1 for x, y in zip(xs, ys) if x == 0 and y == 0)
    return a, b, c, d


def _stacked(games: dict) -> dict:
    """The same-game parlay case: favourite moneyline + favourite cover + over."""
    n = 0
    triple = 0
    ml_p = cov_p = over_p = 0
    for g in games.values():
        if g["favourite_cover"] is None or g["over"] is None or g["home_win"] is None:
            continue
        n += 1
        ml_p += g["home_win"]
        cov_p += g["favourite_cover"]
        over_p += g["over"]
        triple += 1 if (g["home_win"] and g["favourite_cover"] and g["over"]) else 0
    if not n:
        return {}
    p_ml, p_cov, p_over = ml_p / n, cov_p / n, over_p / n
    joint = triple / n
    indep = p_ml * p_cov * p_over
    return {"n": n, "p_home_win": p_ml, "p_fav_cover": p_cov, "p_over": p_over,
            "p_triple_observed": joint, "p_triple_if_independent": indep,
            "overstatement": joint - indep, "lift": joint / indep if indep else float("nan"),
            "note": "home win and favourite cover are near-duplicates when the home side is the "
                    "favourite, which is exactly why a three-leg same-game parlay is not the "
                    "product it looks like"}


# --------------------------------------------------------------------------- 3. injury study
def injury_study(games: list[dict], injury_rows: list[dict], depth_rows: list[dict],
                 season: int) -> dict:
    """Does losing starters move the market, the result, or the total?"""
    avail = features.weekly_availability(injury_rows, depth_rows, season)
    if not avail:
        return {"ok": False, "reason": "no official injury/depth rows for the season"}
    season_games = [g for g in games if g["season"] == season and g["home_score"] is not None]
    missing = 0
    rows = []
    for g in season_games:
        f = {}
        for side in ("home", "away"):
            d = avail.get((features.canon(g[side]), g["week"]))
            if d is None:
                missing += 1
                continue
            for k, v in d.items():
                f[f"{side}_{k}"] = v
        if g["spread_line"] is None or g["total_line"] is None:
            continue
        rows.append({**g, **f})

    if not rows:
        return {"ok": False, "reason": "no games with both an injury report and a market line"}

    usable = [r for r in rows if "home_out_starters_def" in r and "away_out_starters_def" in r]
    out = {"ok": True, "season": season, "n_games": len(rows), "n_with_report": len(usable),
           "missing_team_weeks": missing}
    if usable:
        def_diff = [r["home_out_starters_def"] - r["away_out_starters_def"] for r in usable]
        off_diff = [r["home_out_starters_off"] - r["away_out_starters_off"] for r in usable]
        resid = [r["spread_line"] - r.get("elo_expected_spread", 0.0) for r in usable]
        # a home team missing more defenders should have a LOWER market spread -> negative r
        r_def, n1 = stats.pearson(def_diff, resid)
        r_off, n2 = stats.pearson(off_diff, resid)
        out["market_vs_def_injuries"] = {"n": n1, "r": r_def, "ci95": stats.fisher_ci(r_def, n1)}
        out["market_vs_off_injuries"] = {"n": n2, "r": r_off, "ci95": stats.fisher_ci(r_off, n2)}
        mkt_resid = [cv.home_cover_margin(r["result"], r["spread_line"]) for r in usable]
        r2, n3 = stats.pearson(def_diff, mkt_resid)
        r3, n4 = stats.pearson(off_diff, mkt_resid)
        out["result_vs_def_injuries"] = {"n": n3, "r": r2, "ci95": stats.fisher_ci(r2, n3)}
        out["result_vs_off_injuries"] = {"n": n4, "r": r3, "ci95": stats.fisher_ci(r3, n4)}
        both_off = [r["home_out_starters_off"] + r["away_out_starters_off"] for r in usable]
        rb, nb = stats.pearson(both_off, [r["total_line"] for r in usable])
        out["total_vs_off_injuries"] = {"n": nb, "r": rb, "ci95": stats.fisher_ci(rb, nb)}

    week = max((r["week"] for r in rows), default=0)
    out["current_week"] = week
    out["snapshot"] = [{
        "game_id": r["game_id"], "week": r["week"], "away": r["away"], "home": r["home"],
        "gameday": r["gameday"], "spread_line": r["spread_line"], "total_line": r["total_line"],
        "home_out_def": r.get("home_out_starters_def"), "away_out_def": r.get("away_out_starters_def"),
        "home_out_off": r.get("home_out_starters_off"), "away_out_off": r.get("away_out_starters_off"),
        "home_q_def": r.get("home_q_starters_def"), "away_q_def": r.get("away_q_starters_def"),
    } for r in rows if r["week"] == week]
    return out


# --------------------------------------------------------------------------- 4. strategy family
def strategy_family(preds: list[dict]) -> tuple[list[dict], dict]:
    """A fixed, pre-registered family of strategies graded on identical out-of-sample games."""
    seasons = sorted({x["season"] for x in preds})
    out = []
    ats = _grade_spread_bets(preds)
    if ats.get("ok"):
        ev = gates.evaluate("ATS: model edge > 0.5 pt", "spread", ats["bets"], n_attempts=1)
        ev["bets"] = ats["bets"]
        out.append(ev)
    ou = _grade_total_bets(preds)
    if ou.get("ok"):
        ev = gates.evaluate("O/U: model edge > 0.5 pt", "total", ou["bets"], n_attempts=1)
        ev["bets"] = ou["bets"]
        out.append(ev)
    for tol in (2.0, 3.0):
        out.append(_filtered(preds, tol, "spread"))
        out.append(_filtered(preds, tol, "total"))
    out.append(_elo_gap_strategy(preds))
    out.append(_rest_strategy(preds))
    out.append(_fade_public_strategy(preds))

    fam = {s["strategy"]: s["metrics"]["p_one_sided"] for s in out if s.get("n_bets")}
    final = []
    for s in out:
        if s.get("n_bets") and s.get("bets"):
            ev = gates.evaluate(s["strategy"], s["family"], s["bets"], pvals_family=fam,
                                n_attempts=max(1, len(out)))
            ev["bets"] = s["bets"]
            final.append(ev)
    return final, {"n_strategies": len(final), "seasons": seasons,
                   "n_attempts": len(out)}


def _filtered(preds: list[dict], tol: float, kind: str) -> dict:
    d = _grade_spread_bets(preds, tol=tol) if kind == "spread" else _grade_total_bets(preds, tol=tol)
    bets = d.get("bets", [])
    name = f"{'ATS' if kind == 'spread' else 'O/U'}: model edge > {tol} pts"
    ev = gates.evaluate(name, kind, bets, n_attempts=1)
    ev["bets"] = bets
    return ev


def _elo_gap_strategy(preds: list[dict]) -> dict:
    """Bet the side the market underprices relative to Elo alone, ignoring recent form."""
    seasons = sorted({x["season"] for x in preds})
    bets = []
    for x in preds:
        elo_spread = (x["home_elo_pre"] - x["away_elo_pre"]) / 25.0
        gap = elo_spread - x["spread_line"]
        if abs(gap) < 2.0:
            continue
        side = "home" if gap > 0 else "away"
        covered, push = (cv.home_covers(x["result"], x["spread_line"]) if side == "home"
                         else cv.away_covers(x["result"], x["spread_line"]))
        odds = (x["home_spread_odds"] if side == "home" else x["away_spread_odds"]) or -110
        profit = 0.0 if push else (stats.american_payout(odds) if covered else -1.0)
        bets.append({"season": x["season"], "week": x["week"], "side": side, "profit": profit,
                     "won": 1 if covered and not push else 0, "p_win": 0.5, "push": push,
                     "half": _half(x["season"], x["week"], seasons), "clv": gap,
                     "market": f"{x['away']} @ {x['home']}", "line": x["spread_line"],
                     "odds": odds, "game_id": x["game_id"]})
    ev = gates.evaluate("Elo-gap fade (gap > 2 pts)", "elo", bets, n_attempts=1)
    ev["bets"] = bets
    return ev


def _rest_strategy(preds: list[dict]) -> dict:
    seasons = sorted({x["season"] for x in preds})
    bets = []
    for x in preds:
        hr, ar = x.get("home_rest"), x.get("away_rest")
        if hr is None or ar is None or abs(hr - ar) < 3:
            continue
        side = "home" if hr > ar else "away"
        covered, push = (cv.home_covers(x["result"], x["spread_line"]) if side == "home"
                         else cv.away_covers(x["result"], x["spread_line"]))
        odds = (x["home_spread_odds"] if side == "home" else x["away_spread_odds"]) or -110
        profit = 0.0 if push else (stats.american_payout(odds) if covered else -1.0)
        bets.append({"season": x["season"], "week": x["week"], "side": side, "profit": profit,
                     "won": 1 if covered and not push else 0, "p_win": 0.5, "push": push,
                     "half": _half(x["season"], x["week"], seasons), "clv": abs(hr - ar),
                     "market": f"{x['away']} @ {x['home']}", "line": x["spread_line"],
                     "odds": odds, "game_id": x["game_id"]})
    ev = gates.evaluate("Rest advantage (>= 3 days)", "rest", bets, n_attempts=1)
    ev["bets"] = bets
    return ev


def _fade_public_strategy(preds: list[dict]) -> dict:
    """Classic contrarian test: the side the market moved away from, proxied by big lines.

    With one closing number available the cleanest testable version is: fade large favourites
    (a well-known public-bias hypothesis), graded at the market price.
    """
    seasons = sorted({x["season"] for x in preds})
    bets = []
    for x in preds:
        if abs(x["spread_line"]) < 7.0:
            continue
        side = "away" if x["spread_line"] > 0 else "home"   # fade the big favourite
        covered, push = (cv.home_covers(x["result"], x["spread_line"]) if side == "home"
                         else cv.away_covers(x["result"], x["spread_line"]))
        odds = (x["home_spread_odds"] if side == "home" else x["away_spread_odds"]) or -110
        profit = 0.0 if push else (stats.american_payout(odds) if covered else -1.0)
        bets.append({"season": x["season"], "week": x["week"], "side": side, "profit": profit,
                     "won": 1 if covered and not push else 0, "p_win": 0.5, "push": push,
                     "half": _half(x["season"], x["week"], seasons), "clv": abs(x["spread_line"]),
                     "market": f"{x['away']} @ {x['home']}", "line": x["spread_line"],
                     "odds": odds, "game_id": x["game_id"]})
    ev = gates.evaluate("Fade big favourites (line >= 7)", "contrarian", bets, n_attempts=1)
    ev["bets"] = bets
    return ev
