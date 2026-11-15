#!/usr/bin/env python3
"""Build the skill lab: walk-forward forecasts, proper scores, controls and uncertainty.

Protocol: ``docs/SKILL_LAB_PRE_REGISTRATION.md`` (SL-PRE-01) as amended by
``docs/SKILL_LAB_PRE_REGISTRATION_AMENDMENT.md`` (SL-PRE-01a).  The registration is frozen;
this script only computes what the registration describes and publishes what it produces.

Nothing here is betting advice, a sportsbook, or an approved wagering system.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import html
import json
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "engine"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(HERE))

import features          # noqa: E402  (engine)
import lines             # noqa: E402  (engine)
import loader            # noqa: E402  (engine)
import stats as engstats  # noqa: E402  (engine)
import scorelib as sl    # noqa: E402  (this workspace)

LAB = ROOT / "skill-lab"
DATA = LAB / "data"
OUT_JSON = DATA / "results.json"

PROTOCOL_ID = "SL-PRE-01 (+ SL-PRE-01a)"
N_BOOT = 10000
BOOT_SEED = 20260101
RANDOM_SEEDS = 1000
BH_Q = 0.05
PRIMARY_SEASON = 2026
PRIMARY_MAX_WEEK = 9
MIN_GAMES_GATE = 100
ECE_LIMIT = 0.05

# The six registered strategy rows.  One family per run.
STRATEGIES = [
    ("spread_full", "Margin model (Elo + form + rest) vs closing spread", "spread", "full"),
    ("spread_elo", "Simple team strength (Elo only) vs closing spread", "spread", "elo"),
    ("total_ls", "Total model, least-squares estimator vs closing total", "total", "full"),
    ("total_shrink", "Total model, shrinkage estimator vs closing total", "total", "shrink"),
    ("ml_full", "Margin model (Elo + form + rest) vs closing moneyline", "moneyline", "full"),
    ("ml_elo", "Simple team strength (Elo only) vs closing moneyline", "moneyline", "elo"),
]

MARKET_LABEL = {"spread": "Spread", "total": "Total", "moneyline": "Moneyline"}


# --------------------------------------------------------------------------- helpers
def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:  # pragma: no cover - diagnostics only
        return ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nfl_scores_url(season: int, week: int) -> str:
    return f"https://www.nfl.com/scores/{season}/week-{week}"


# --------------------------------------------------------------------------- the model
def fit_elo_only(train: list[dict]) -> list[float]:
    """Simple team-strength model: home margin regressed on the pre-game Elo difference only."""
    X, y = [], []
    for g in train:
        elo_diff = (g.get("home_elo_pre", 1505.0) - g.get("away_elo_pre", 1505.0)) / 100.0
        X.append([elo_diff])
        y.append(g["result"])
    return lines.ols(X, y)


def predict_elo_only(beta: list[float], g: dict) -> float:
    elo_diff = (g.get("home_elo_pre", 1505.0) - g.get("away_elo_pre", 1505.0)) / 100.0
    return beta[0] + beta[1] * elo_diff


def residual_sd(train: list[dict], predict, target: str) -> float:
    res = []
    for g in train:
        try:
            pred = predict(g)
        except Exception:
            continue
        if pred is None or pred != pred:
            continue
        y = g["result"] if target == "result" else g["total"]
        if y is None or y != y:
            continue
        res.append(y - pred)
    return engstats.stdev(res) if len(res) > 2 else float("nan")


def shrink_total(g: dict, league_total: float) -> float:
    """Registered second total estimator: league mean plus one third of the form gap."""
    vals = [g.get("home_form_pts"), g.get("away_form_pts"),
            g.get("home_form_opp_pts"), g.get("away_form_opp_pts")]
    if any(v is None or v != v for v in vals):
        return league_total
    m = sum(vals) / 4.0
    return league_total + (m - league_total) / 3.0


def walk_forward(games: list[dict]) -> tuple[list[dict], list[dict]]:
    """Walk-forward predictions for every eligible season (no lookahead)."""
    features.elo_ratings(games)
    features.rolling_team_form(games)
    by_season: dict[int, list[dict]] = collections.defaultdict(list)
    for g in games:
        by_season[g["season"]].append(g)
    seasons = sorted(s for s in by_season if len(by_season[s]) >= 100)
    preds: list[dict] = []
    audit: list[dict] = []
    for season in seasons:
        train = [g for s in seasons if s < season for g in by_season[s]]
        if len({g["season"] for g in train}) < 4:
            continue
        league_total = engstats.mean([g["total"] for g in train if g["total"] is not None])
        beta_s = lines.fit_spread(train)
        beta_t = lines.fit_total(train, league_total)
        beta_e = fit_elo_only(train)
        sigma_s = residual_sd(train, lambda g: lines.predict_spread(beta_s, g), "result")
        sigma_t = residual_sd(train, lambda g: lines.predict_total(beta_t, g, league_total), "total")
        sigma_e = residual_sd(train, lambda g: predict_elo_only(beta_e, g), "result")
        base_rates = {
            "home_win": engstats.mean([1.0 if g["result"] > 0 else 0.0 for g in train]),
            "home_cover": engstats.mean([1.0 if g["result"] > g["spread_line"] else 0.0
                                         for g in train if g["spread_line"] is not None]),
            "over": engstats.mean([1.0 if g["total"] > g["total_line"] else 0.0
                                   for g in train if g["total_line"] is not None]),
        }
        audit.append({
            "season": season, "n_train_games": len(train),
            "n_train_seasons": len({g["season"] for g in train}),
            "league_total_train": round(league_total, 3),
            "beta_spread": [round(b, 5) for b in beta_s],
            "beta_total": [round(b, 5) for b in beta_t],
            "beta_elo_only": [round(b, 5) for b in beta_e],
            "sigma_spread_train": round(sigma_s, 4),
            "sigma_total_train": round(sigma_t, 4),
            "sigma_elo_only_train": round(sigma_e, 4),
            "base_rates_train": {k: round(v, 5) for k, v in base_rates.items()},
        })
        for g in by_season[season]:
            ps = lines.predict_spread(beta_s, g)
            pe = predict_elo_only(beta_e, g)
            pt = lines.predict_total(beta_t, g, league_total)
            psh = shrink_total(g, league_total)
            if any(v is None or v != v for v in (ps, pe, pt, psh, sigma_s, sigma_t, sigma_e)):
                continue
            preds.append({
                "game_id": g["game_id"], "season": g["season"], "week": g["week"],
                "gameday": g["gameday"], "away": g["away"], "home": g["home"],
                "away_score": g["away_score"], "home_score": g["home_score"],
                "result": g["result"], "total": g["total"],
                "spread_line": g["spread_line"], "total_line": g["total_line"],
                "away_ml": g["away_ml"], "home_ml": g["home_ml"],
                "away_spread_odds": g["away_spread_odds"], "home_spread_odds": g["home_spread_odds"],
                "over_odds": g["over_odds"], "under_odds": g["under_odds"],
                "model_spread": ps, "model_spread_elo": pe,
                "model_total": pt, "model_total_shrink": psh,
                "sigma_spread": sigma_s, "sigma_total": sigma_t, "sigma_elo": sigma_e,
                "base_home_win": base_rates["home_win"],
                "base_home_cover": base_rates["home_cover"],
                "base_over": base_rates["over"],
            })
    return preds, audit


# --------------------------------------------------------------------------- grading
def market_prices(p: dict, market: str) -> dict:
    """Raw implied probabilities and the de-vigged benchmark probability for the graded event."""
    if market == "spread":
        home_p = sl.american_to_prob(p["home_spread_odds"])
        away_p = sl.american_to_prob(p["away_spread_odds"])
        if home_p is None or away_p is None:
            return {}
        prop, _ = sl.devig_proportional(home_p, away_p)
        shin, _ = sl.devig_shin(home_p, away_p)
        return {"event_prob_raw": home_p, "other_prob_raw": away_p,
                "benchmark_prob": prop, "benchmark_prob_shin": shin}
    if market == "total":
        over_p = sl.american_to_prob(p["over_odds"])
        under_p = sl.american_to_prob(p["under_odds"])
        if over_p is None or under_p is None:
            return {}
        prop, _ = sl.devig_proportional(over_p, under_p)
        shin, _ = sl.devig_shin(over_p, under_p)
        return {"event_prob_raw": over_p, "other_prob_raw": under_p,
                "benchmark_prob": prop, "benchmark_prob_shin": shin}
    home_p = sl.american_to_prob(p["home_ml"])
    away_p = sl.american_to_prob(p["away_ml"])
    if home_p is None or away_p is None:
        return {}
    prop, _ = sl.devig_proportional(home_p, away_p)
    shin, _ = sl.devig_shin(home_p, away_p)
    return {"event_prob_raw": home_p, "other_prob_raw": away_p,
            "benchmark_prob": prop, "benchmark_prob_shin": shin}


def grade(p: dict, market: str) -> dict | None:
    """Grade one game for one market.  Returns None when the market cannot be graded."""
    prices = market_prices(p, market)
    if not prices:
        return None
    if market == "spread":
        line = p["spread_line"]
        if line is None or p["result"] is None:
            return None
        if p["result"] == line:
            return None  # push: excluded by the registered exclusion rule
        y = 1.0 if p["result"] > line else 0.0
        model_line = None
        return {"market": market, "market_line": line, "event": "Home covers",
                "outcome": y, "model_prob": None, "benchmark_prob": prices["benchmark_prob"],
                "benchmark_prob_shin": prices["benchmark_prob_shin"], "prices": prices}
    if market == "total":
        line = p["total_line"]
        if line is None or p["total"] is None:
            return None
        if p["total"] == line:
            return None
        y = 1.0 if p["total"] > line else 0.0
        return {"market": market, "market_line": line, "event": "Over",
                "outcome": y, "model_prob": None, "benchmark_prob": prices["benchmark_prob"],
                "benchmark_prob_shin": prices["benchmark_prob_shin"], "prices": prices}
    if p["home_score"] is None or p["away_score"] is None:
        return None
    if p["home_score"] == p["away_score"]:
        return None
    y = 1.0 if p["home_score"] > p["away_score"] else 0.0
    return {"market": market, "market_line": None, "event": "Home wins",
            "outcome": y, "model_prob": None, "benchmark_prob": prices["benchmark_prob"],
            "benchmark_prob_shin": prices["benchmark_prob_shin"], "prices": prices}


def model_probability(p: dict, market: str, variant: str) -> tuple[float | None, float | None]:
    """Return (model probability for the graded event, model line for the market)."""
    if market == "spread":
        sigma = p["sigma_spread"] if variant == "full" else p["sigma_elo"]
        model = p["model_spread"] if variant == "full" else p["model_spread_elo"]
        if sigma is None or sigma <= 0 or sigma != sigma:
            return (None, None)
        return (sl.norm_cdf((model - p["spread_line"]) / sigma), model)
    if market == "total":
        sigma = p["sigma_total"]
        model = p["model_total"] if variant == "full" else p["model_total_shrink"]
        if sigma is None or sigma <= 0 or sigma != sigma:
            return (None, None)
        return (sl.norm_cdf((model - p["total_line"]) / sigma), model)
    sigma = p["sigma_spread"] if variant == "full" else p["sigma_elo"]
    model = p["model_spread"] if variant == "full" else p["model_spread_elo"]
    if sigma is None or sigma <= 0 or sigma != sigma:
        return (None, None)
    return (sl.norm_cdf(model / sigma), model)


def base_rate_probability(p: dict, market: str) -> float | None:
    if market == "spread":
        return p.get("base_home_cover")
    if market == "total":
        return p.get("base_over")
    return p.get("base_home_win")


def stake_for(p: dict, market: str, take_event: bool) -> dict | None:
    """Flat-stake ledger entry for one side of one market."""
    if market == "spread":
        odds = p["home_spread_odds"] if take_event else p["away_spread_odds"]
        line = p["spread_line"]
        if odds is None or line is None or p["result"] is None:
            return None
        if p["result"] == line:
            return None
        won = (p["result"] > line) if take_event else (p["result"] < line)
        dec = sl.american_to_decimal(odds)
        return {"odds": odds, "decimal": dec, "won": won,
                "profit": (dec - 1.0) if won else -1.0, "push": False}
    if market == "total":
        odds = p["over_odds"] if take_event else p["under_odds"]
        line = p["total_line"]
        if odds is None or line is None or p["total"] is None:
            return None
        if p["total"] == line:
            return None
        won = (p["total"] > line) if take_event else (p["total"] < line)
        dec = sl.american_to_decimal(odds)
        return {"odds": odds, "decimal": dec, "won": won,
                "profit": (dec - 1.0) if won else -1.0, "push": False}
    odds = p["home_ml"] if take_event else p["away_ml"]
    if odds is None or p["home_score"] is None or p["away_score"] is None:
        return None
    if p["home_score"] == p["away_score"]:
        return None
    won = (p["home_score"] > p["away_score"]) if take_event else (p["away_score"] > p["home_score"])
    dec = sl.american_to_decimal(odds)
    return {"odds": odds, "decimal": dec, "won": won,
            "profit": (dec - 1.0) if won else -1.0, "push": False}


def favourite_stake(p: dict, market: str) -> dict | None:
    """Control C3: always take the shorter price (the market favourite)."""
    if market == "spread":
        a, b = sl.american_to_prob(p["home_spread_odds"]), sl.american_to_prob(p["away_spread_odds"])
    elif market == "total":
        a, b = sl.american_to_prob(p["over_odds"]), sl.american_to_prob(p["under_odds"])
    else:
        a, b = sl.american_to_prob(p["home_ml"]), sl.american_to_prob(p["away_ml"])
    if a is None or b is None:
        return None
    return stake_for(p, market, take_event=(a >= b))


# --------------------------------------------------------------------------- statistics
def bootstrap_skill(obs: list[tuple[str, float, float]], n_boot: int = N_BOOT,
                    seed: int = BOOT_SEED, alpha: float = 0.05) -> dict:
    """Cluster bootstrap of the Brier skill, resampling games (not forecasts).

    Per-game aggregates are pre-computed so each resample is O(games) arithmetic rather than a
    list rebuild; the statistic is identical to recomputing the means on the resampled games.
    """
    games: dict[str, list[tuple[float, float]]] = collections.defaultdict(list)
    for gid, bm, br in obs:
        games[gid].append((bm, br))
    keys = list(games)
    if not keys:
        return {"point": float("nan"), "ci95": [None, None], "lower95": None,
                "p_one_sided": None, "n_boot": 0, "n_games": 0}
    agg = [(sum(t[0] for t in games[k]), sum(t[1] for t in games[k]), len(games[k])) for k in keys]
    model_by_game = [a[0] for a in agg]
    ref_by_game = [a[1] for a in agg]
    n_by_game = [a[2] for a in agg]
    get_model = model_by_game.__getitem__
    get_ref = ref_by_game.__getitem__
    get_n = n_by_game.__getitem__

    def stat(idx: list[int]) -> float:
        sn = sum(map(get_n, idx))
        sr = sum(map(get_ref, idx))
        if sn <= 0 or sr <= 0:
            return float("nan")
        return 1.0 - (sum(map(get_model, idx)) / sn) / (sr / sn)

    point = stat(list(range(len(keys))))
    rnd = random.Random(seed)
    n_keys = len(keys)
    draws = []
    for _ in range(n_boot):
        draws.append(stat(rnd.choices(range(n_keys), k=n_keys)))
    draws.sort()
    lo = draws[int(math.floor((alpha / 2) * (len(draws) - 1)))]
    hi = draws[int(math.ceil((1 - alpha / 2) * (len(draws) - 1)))]
    p_one = sum(1 for d in draws if d <= 0.0) / len(draws)
    return {"point": point, "ci95": [lo, hi], "lower95": lo, "upper95": hi,
            "p_one_sided": p_one, "n_boot": n_boot, "n_games": len(keys)}


def bootstrap_mean(obs: list[tuple[str, float]], n_boot: int = N_BOOT,
                   seed: int = BOOT_SEED, alpha: float = 0.05) -> dict:
    games: dict[str, list[float]] = collections.defaultdict(list)
    for gid, v in obs:
        games[gid].append(v)
    keys = list(games)
    if not keys:
        return {"point": float("nan"), "ci95": [None, None], "lower95": None,
                "p_one_sided": None, "n_boot": 0, "n_games": 0}
    agg = [(sum(games[k]), len(games[k])) for k in keys]
    sum_by_game = [a[0] for a in agg]
    n_by_game = [a[1] for a in agg]
    get_sum = sum_by_game.__getitem__
    get_n = n_by_game.__getitem__

    def stat(idx: list[int]) -> float:
        n = sum(map(get_n, idx))
        return (sum(map(get_sum, idx)) / n) if n else float("nan")

    point = stat(list(range(len(keys))))
    rnd = random.Random(seed)
    n_keys = len(keys)
    draws = []
    for _ in range(n_boot):
        draws.append(stat(rnd.choices(range(n_keys), k=n_keys)))
    draws.sort()
    lo = draws[int(math.floor((alpha / 2) * (len(draws) - 1)))]
    hi = draws[int(math.ceil((1 - alpha / 2) * (len(draws) - 1)))]
    p_one = sum(1 for d in draws if d <= 0.0) / len(draws)
    return {"point": point, "ci95": [lo, hi], "lower95": lo, "upper95": hi,
            "p_one_sided": p_one, "n_boot": n_boot, "n_games": len(keys)}


def random_control(graded: list[dict], seeds: int = RANDOM_SEEDS, base_seed: int = BOOT_SEED) -> dict:
    """Control C2: random hard side pick, 1,000 seeds.  Returns the skill distribution."""
    if not graded:
        return {}
    bs_market = sl.mean([g["brier_market"] for g in graded])
    # Pre-compute the per-row outcomes of a hard pick so the seed loop is pure arithmetic.
    table = []
    for g in graded:
        y = g["outcome"]
        se, so = g["stake_event"], g["stake_other"]
        table.append((
            sl.brier(1.0, y), sl.brier(0.0, y),
            sl.log_loss(1.0, y), sl.log_loss(0.0, y),
            se["profit"] if se else None, so["profit"] if so else None,
        ))
    skills, returns, briers = [], [], []
    for s in range(seeds):
        rnd = random.Random(base_seed + s)
        bs_sum = ll_sum = 0.0
        ret_sum = 0.0
        ret_n = 0
        for b_ev, b_ot, l_ev, l_ot, p_ev, p_ot in table:
            if rnd.random() < 0.5:
                bs_sum += b_ev
                ll_sum += l_ev
                if p_ev is not None:
                    ret_sum += p_ev
                    ret_n += 1
            else:
                bs_sum += b_ot
                ll_sum += l_ot
                if p_ot is not None:
                    ret_sum += p_ot
                    ret_n += 1
        brier_mean = bs_sum / len(table)
        skills.append(sl.skill(brier_mean, bs_market))
        briers.append(brier_mean)
        returns.append(ret_sum / ret_n if ret_n else float("nan"))
    return {"seeds": seeds, "brier_mean": sl.mean(briers),
            "skill_p50": sl.percentile(skills, 0.5), "skill_p95": sl.percentile(skills, 0.95),
            "skill_max": max(skills), "return_p50": sl.percentile(returns, 0.5),
            "return_p95": sl.percentile(returns, 0.95), "return_max": max(returns),
            "market_brier": bs_market}


# --------------------------------------------------------------------------- run assembly
def build_run(preds: list[dict], label: str, season_filter=None, keep_graded: bool = False) -> dict:
    """Grade, score and test every registered strategy row for one run."""
    graded_by_strategy: dict[str, list[dict]] = {sid: [] for sid, *_ in STRATEGIES}
    exclusions: collections.Counter = collections.Counter()
    excluded_examples: list[dict] = []

    def exclude(reason: str, p: dict, market: str) -> None:
        exclusions[reason] += 1
        if len(excluded_examples) < 40:
            excluded_examples.append({"reason": reason, "game_id": p["game_id"], "market": market})

    for p in preds:
        if season_filter and not season_filter(p):
            continue
        for sid, _name, market, variant in STRATEGIES:
            g = grade(p, market)
            if g is None:
                exclude("no gradeable market price or line for this market", p, market)
                continue
            mp, model_line = model_probability(p, market, variant)
            if mp is None:
                exclude("model probability unavailable (missing residual scale)", p, market)
                continue
            y = g["outcome"]
            g.update({
                "strategy": sid, "game_id": p["game_id"], "season": p["season"], "week": p["week"],
                "gameday": p["gameday"], "away": p["away"], "home": p["home"],
                "model_prob": mp, "model_line": model_line, "market_line": g["market_line"],
                "line_gap": (model_line - g["market_line"])
                if (model_line is not None and g["market_line"] is not None) else None,
                "brier_model": sl.brier(mp, y), "brier_market": sl.brier(g["benchmark_prob"], y),
                "logloss_model": sl.log_loss(mp, y), "logloss_market": sl.log_loss(g["benchmark_prob"], y),
                "stake_event": stake_for(p, market, True),
                "stake_other": stake_for(p, market, False),
                "stake_favourite": favourite_stake(p, market),
                "_pred": p,
            })
            graded_by_strategy[sid].append(g)

    rows: list[dict] = []
    for sid, name, market, variant in STRATEGIES:
        graded = graded_by_strategy[sid]
        if not graded:
            rows.append({"strategy": sid, "name": name, "market": market, "variant": variant,
                         "n_games": 0, "status": "no gradeable forecasts"})
            continue
        bs_model = sl.mean([g["brier_model"] for g in graded])
        bs_market = sl.mean([g["brier_market"] for g in graded])
        ll_model = sl.mean([g["logloss_model"] for g in graded])
        ll_market = sl.mean([g["logloss_market"] for g in graded])
        skill_brier = sl.skill(bs_model, bs_market)
        skill_ll = sl.skill(ll_model, ll_market)
        boot = bootstrap_skill([(g["game_id"], g["brier_model"], g["brier_market"]) for g in graded])
        boot_ll = bootstrap_mean([(g["game_id"], g["logloss_model"] - g["logloss_market"])
                                  for g in graded])

        # control C4: training-window base rate applied to every graded event
        base_p = base_rate_probability(graded[0]["_pred"], market)
        base_obs = [(base_p, g["outcome"]) for g in graded] if base_p is not None else []
        bs_base = sl.mean([sl.brier(p, y) for p, y in base_obs]) if base_obs else float("nan")
        skill_base = sl.skill(bs_base, bs_market) if base_obs else float("nan")

        # control C2: random hard pick
        ctrl = random_control(graded)

        # calibration (G6)
        ece, bins = sl.calibration_error([(g["model_prob"], g["outcome"]) for g in graded])

        # staking view (retrospective, community prices)
        stakes, ret = [], []
        for g in graded:
            stake = g["stake_event"] if g["model_prob"] > 0.5 else g["stake_other"]
            if stake:
                stakes.append(stake)
                ret.append(stake["profit"])
        fav = [g["stake_favourite"] for g in graded]
        fav = [f for f in fav if f]
        model_return = sl.mean(ret) if ret else float("nan")
        fav_return = sl.mean([f["profit"] for f in fav]) if fav else float("nan")
        fav_hit = sl.mean([1.0 if f["won"] else 0.0 for f in fav]) if fav else float("nan")
        # stressed price: 10% worse payout, same picks
        stressed = [0.9 * (s["decimal"] - 1.0) if s["won"] else -1.0 for s in stakes if s["decimal"]]
        stressed_return = sl.mean(stressed) if stressed else float("nan")
        fav_stressed = [0.9 * (f["decimal"] - 1.0) if f["won"] else -1.0 for f in fav if f["decimal"]]
        fav_stressed_return = sl.mean(fav_stressed) if fav_stressed else float("nan")
        return_boot = bootstrap_mean([(g["game_id"], (g["stake_event"] if g["model_prob"] > 0.5
                                                      else g["stake_other"])["profit"])
                                      for g in graded
                                      if (g["stake_event"] if g["model_prob"] > 0.5
                                          else g["stake_other"]) is not None])

        rows.append({
            "strategy": sid, "name": name, "market": market, "variant": variant,
            "n_games": len(graded),
            "n_forecasts": len(graded),
            "brier_model": bs_model, "brier_market": bs_market, "skill_brier": skill_brier,
            "logloss_model": ll_model, "logloss_market": ll_market, "skill_logloss": skill_ll,
            "bootstrap": boot, "bootstrap_logloss_diff": boot_ll,
            "control_random": ctrl, "control_base_rate_prob": base_p,
            "control_base_rate_brier": bs_base, "control_base_rate_skill": skill_base,
            "calibration_ece": ece, "calibration_bins": bins,
            "staking": {"n_bets": len(stakes), "return_per_unit": model_return,
                        "hit_rate": sl.mean([1.0 if s["won"] else 0.0 for s in stakes]) if stakes else None,
                        "return_ci95": return_boot.get("ci95"),
                        "favourites_only_return": fav_return, "favourites_only_hit_rate": fav_hit,
                        "return_at_minus_10pct_price": stressed_return,
                        "favourites_only_return_at_minus_10pct_price": fav_stressed_return},
        })

    # multiplicity across the family
    pvals = {r["strategy"]: r["bootstrap"]["p_one_sided"] for r in rows if "bootstrap" in r}
    bh = sl.benjamini_hochberg(pvals, BH_Q)
    for r in rows:
        if "bootstrap" not in r:
            continue
        b = bh.get(r["strategy"], {})
        r["bh_p"] = b.get("p")
        r["bh_q"] = b.get("q")
        r["bh_pass"] = b.get("pass")
        gates = {
            "G1 sample": (r["n_games"] >= MIN_GAMES_GATE, f"{r['n_games']} graded games (need >= {MIN_GAMES_GATE})"),
            "G2 skill": (r["skill_brier"] > 0, f"Brier skill {r['skill_brier']:+.4f}"),
            "G3 uncertainty": (r["bootstrap"]["lower95"] is not None and r["bootstrap"]["lower95"] > 0,
                               f"cluster lower bound {r['bootstrap']['lower95']:+.4f}" if r["bootstrap"]["lower95"] is not None else "no interval"),
            "G4 multiplicity": (bool(r["bh_pass"]),
                                f"BH q={r['bh_q']:.4f} at q={BH_Q}" if r["bh_q"] is not None else "no p-value"),
            "G5 control": (r["skill_brier"] > r["control_random"]["skill_p95"]
                           and (r["control_base_rate_skill"] != r["control_base_rate_skill"]
                                or r["skill_brier"] > r["control_base_rate_skill"]),
                           f"random 95th pct {r['control_random']['skill_p95']:+.4f}; base-rate {r['control_base_rate_skill']:+.4f}"),
            "G6 calibration": (r["calibration_ece"] == r["calibration_ece"] and r["calibration_ece"] <= ECE_LIMIT,
                               f"ECE {r['calibration_ece']:.4f} (limit {ECE_LIMIT})"),
            "G7 price realism": (True, "signal gates do not use a price; staking return at -10% price is published separately"),
        }
        r["gates"] = gates
        r["gates_passed"] = sum(1 for ok, _ in gates.values() if ok)
        r["gates_total"] = len(gates)
        r["eligible_for_ranking"] = all(ok for ok, _ in gates.values())
        r["status"] = "eligible for ranking" if r["eligible_for_ranking"] else "not eligible"
    trials = len(pvals)
    for r in rows:
        r["family_trials"] = trials

    all_graded = sum(graded_by_strategy.values(), [])
    public = []
    if keep_graded:
        for g in all_graded:
            public.append({k: v for k, v in g.items()
                           if k not in ("_pred", "stake_event", "stake_other", "stake_favourite",
                                        "prices", "model_line", "market_line")} |
                          {"model_line": g["model_line"], "market_line": g["market_line"],
                           "line_gap": g["line_gap"],
                           "event": g["event"],
                           "event_prob_raw": g["prices"]["event_prob_raw"],
                           "other_prob_raw": g["prices"]["other_prob_raw"]})
    return {
        "label": label,
        "rows": rows,
        "graded": public,
        "exclusions": dict(exclusions),
        "excluded_examples": excluded_examples,
        "n_games_in_corpus": len({g["game_id"] for g in all_graded}),
    }


def dependence_analysis(preds: list[dict], season_filter=None) -> dict:
    """Within-game dependence: observed joint probabilities against the independence product."""
    per_game: dict[str, dict] = {}
    for p in preds:
        if season_filter and not season_filter(p):
            continue
        if p["spread_line"] is None or p["total_line"] is None:
            continue
        if p["result"] is None or p["total"] is None:
            continue
        if p["result"] == p["spread_line"] or p["total"] == p["total_line"]:
            continue
        cover = 1.0 if p["result"] > p["spread_line"] else 0.0
        over = 1.0 if p["total"] > p["total_line"] else 0.0
        home_win = 1.0 if p["result"] > 0 else 0.0
        per_game[p["game_id"]] = {"cover": cover, "over": over, "home_win": home_win,
                                  "home": p["home"], "away": p["away"], "week": p["week"]}
    games = list(per_game.values())
    n = len(games)
    if not n:
        return {"n": 0}
    p_cover = sl.mean([g["cover"] for g in games])
    p_over = sl.mean([g["over"] for g in games])
    p_win = sl.mean([g["home_win"] for g in games])
    joint_cover_over = sl.mean([g["cover"] * g["over"] for g in games])
    joint_all = sl.mean([g["cover"] * g["over"] * g["home_win"] for g in games])
    prod_cover_over = p_cover * p_over
    prod_all = p_cover * p_over * p_win

    def phi(a: list[float], b: list[float]) -> float:
        """Phi coefficient (Matthews' correlation for binary variables).

        phi = (n11 - n1*n2/n) / sqrt(n1(n-n1) * n2(n-n2)) / n, written here in the
        equivalent multiplied-through form: (n*n11 - n1*n2) / sqrt(n1(n-n1)*n2(n-n2)).
        """
        n_ = len(a)
        n11 = sum(x * y for x, y in zip(a, b))
        n1 = sum(a)
        n2 = sum(b)
        num = n_ * n11 - n1 * n2
        den = math.sqrt((n1 * (n_ - n1)) * (n2 * (n_ - n2)))
        return num / den if den else float("nan")

    cover_v = [g["cover"] for g in games]
    over_v = [g["over"] for g in games]
    win_v = [g["home_win"] for g in games]
    return {
        "n": n,
        "p_home_cover": p_cover, "p_over": p_over, "p_home_win": p_win,
        "joint_cover_and_over_observed": joint_cover_over,
        "joint_cover_and_over_if_independent": prod_cover_over,
        "joint_all_three_observed": joint_all,
        "joint_all_three_if_independent": prod_all,
        "phi_cover_over": phi(cover_v, over_v),
        "phi_cover_win": phi(cover_v, win_v),
        "phi_over_win": phi(over_v, win_v),
        "note": ("Marginal probabilities for the legs of a same-game parlay cannot be multiplied: "
                 "the observed joint probability differs from the independence product."),
    }


def main() -> int:
    games = features.reg_games()
    preds, audit = walk_forward(games)
    primary = [p for p in preds if p["season"] == PRIMARY_SEASON and p["week"] <= PRIMARY_MAX_WEEK]
    supporting = [p for p in preds if not (p["season"] == PRIMARY_SEASON and p["week"] <= PRIMARY_MAX_WEEK)]
    run_primary = build_run(primary, f"{PRIMARY_SEASON} regular season, weeks 1-{PRIMARY_MAX_WEEK}",
                           keep_graded=True)
    run_supporting = build_run(supporting, "Supporting panel: every earlier regular season (walk-forward)")
    dependence = dependence_analysis(primary)

    manifest = loader.manifest()
    games_asset = manifest.get("files", {}).get("games", {})
    reg_commit = git("rev-list", "--all", "--", "docs/SKILL_LAB_PRE_REGISTRATION.md")
    meta = {
        "protocol": PROTOCOL_ID,
        "protocol_path": "docs/SKILL_LAB_PRE_REGISTRATION.md",
        "amendment_path": "docs/SKILL_LAB_PRE_REGISTRATION_AMENDMENT.md",
        "pre_registration_commit": reg_commit,
        "code_commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "primary_corpus": {"season": PRIMARY_SEASON, "weeks": f"1-{PRIMARY_MAX_WEEK}",
                           "expected_games": 136,
                           "observed_games": len({p["game_id"] for p in primary})},
        "supporting_corpus": {"seasons": sorted({p["season"] for p in supporting}),
                              "observed_games": len({p["game_id"] for p in supporting})},
        "data": {"games_csv": games_asset.get("asset_url"),
                 "games_sha256": games_asset.get("sha256"),
                 "release_updated_utc": games_asset.get("release_asset_updated_utc"),
                 "authority": "community-maintained release (nflverse); NOT an official NFL price archive"},
        "official_sources": {
            "scores": "https://www.nfl.com/scores/",
            "standings": "https://www.nfl.com/standings/league",
            "odds_terms": "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL",
            "rulebook": "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/",
        },
        "settings": {"n_boot": N_BOOT, "boot_seed": BOOT_SEED, "random_control_seeds": RANDOM_SEEDS,
                     "bh_q": BH_Q, "min_games_gate": MIN_GAMES_GATE, "ece_limit": ECE_LIMIT},
        "season_audit": audit,
    }

    out = {"meta": meta, "runs": {"primary": run_primary, "supporting": run_supporting},
           "dependence": dependence}
    DATA.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=1, sort_keys=False), encoding="utf-8")
    print(f"skill-lab: primary corpus {meta['primary_corpus']['observed_games']} games, "
          f"supporting {meta['supporting_corpus']['observed_games']} games")
    for r in run_primary["rows"]:
        if "bootstrap" not in r:
            print(f"  {r['strategy']}: no gradeable forecasts")
            continue
        print(f"  {r['strategy']}: n={r['n_games']} skill={r['skill_brier']:+.4f} "
              f"lower={r['bootstrap']['lower95']:+.4f} q={r['bh_q']:.4f} "
              f"gates={r['gates_passed']}/{r['gates_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
