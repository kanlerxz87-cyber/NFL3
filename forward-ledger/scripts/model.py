#!/usr/bin/env python3
"""FL1: the pre-registered singles-only team-strength model, fit on the official results ledger.

Protocol: forward-ledger/PREREGISTRATION.md (its commit hash is the registration). This script contains
no threshold, window or gate that the protocol does not name, and it publishes no price-dependent number:
the market-line and residual columns stay empty because `pricing/PRICE_DATA_POLICY.md` grants no source.

Pure standard library, deterministic, no network. Outputs:
  data/ratings_2026_w10.csv        fitted attack/defence ratings and the fitted constants
  data/fit_diagnostics.json        in-sample and chronological-holdout diagnostics, correlation register
  data/prospects_2026_w11.csv      one row per Week 11 fixture: our line, the market line (blank), the difference (blank)
  data/prospect_records.jsonl      one JSON record per forecast: probability plus the inputs that produced it
  data/leaderboard.json            the divisions, their eligibility state and the controls
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"

# --- constants named in PREREGISTRATION.md section 2; changing one here requires a new registration ---
HFA_START = 2.0            # starting value for the estimated home-field term; the fit replaces it
ITERATIONS = 400           # alternating-least-squares sweeps, fixed so the fit is reproducible
SIGMA_FLOOR = 6.0          # a fitted scoring sd below this is treated as a fit failure, not a value
LINE_ROUND_SIDED = 0.5     # fair spread is published rounded to the half point
LINE_ROUND_TOTAL = 1.0     # fair total is published rounded to the whole point
HOLDOUT_WEEKS = (9, 10)    # chronological holdout for the backtest diagnostics
PRIMARY_ESTIMATOR = "fl1-additive"
SECONDARY_ESTIMATOR = "fl1-sum-of-rates"
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261116


def utc_stamp() -> str:
    """Issue stamp for the prospective records. A registration is only meaningful with a clock time."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_ledger() -> list[dict]:
    path = DATA / "results_ledger.csv"
    if not path.is_file():
        raise SystemExit("forward-ledger/model: run scripts/build_ledger.py first")
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    return [r for r in rows if r["status"] == "final" and r["away_score"] != "" and r["home_score"] != ""]


def fit(games: list[dict]) -> dict:
    """Alternating least squares on an additive attack/defence model with a home-field term.

    points_home = mu + att_home - def_away + hfa
    points_away = mu + att_away - def_home
    No shrinkage, no priors, no rounding: the estimate is the arithmetic mean of the implied values.
    """
    clubs = sorted({g["away"] for g in games} | {g["home"] for g in games})
    mu = statistics.fmean([int(g["away_score"]) for g in games] + [int(g["home_score"]) for g in games])
    att = {c: 0.0 for c in clubs}
    defence = {c: 0.0 for c in clubs}
    hfa = HFA_START
    for _ in range(ITERATIONS):
        scored_home = defaultdict(list)
        allowed_home = defaultdict(list)
        scored_away = defaultdict(list)
        allowed_away = defaultdict(list)
        home_margins = []
        for g in games:
            h, a = g["home"], g["away"]
            ph, pa = int(g["home_score"]), int(g["away_score"])
            scored_home[h].append(ph - mu + defence[a] - hfa)
            allowed_home[h].append(mu + att[a] - pa)   # the home club's defence is measured by what it allows
            scored_away[a].append(pa - mu + defence[h])   # the away club scores without the home-field term
            allowed_away[a].append(mu + att[h] - ph)  # the away club's defence is measured by what it allows
            home_margins.append(ph - pa)
        for club in clubs:
            att_vals = scored_home[club] + scored_away[club]
            def_vals = allowed_home[club] + allowed_away[club]
            att[club] = statistics.fmean(att_vals) if att_vals else att[club]
            defence[club] = statistics.fmean(def_vals) if def_vals else defence[club]
        # identifiability: centre the two rating vectors, keep mu as the fitted league average
        att_mean = statistics.fmean(att.values())
        def_mean = statistics.fmean(defence.values())
        att = {c: v - att_mean for c, v in att.items()}
        defence = {c: v - def_mean for c, v in defence.items()}
        hfa = max(-14.0, min(14.0, statistics.fmean(home_margins) / 2.0))
    scored = defaultdict(list)
    for g in games:
        scored[g["home"]].append(int(g["home_score"]))
        scored[g["away"]].append(int(g["away_score"]))
    return {"mu": mu, "hfa": hfa, "att": att, "def": defence, "iterations": ITERATIONS,
            "score_avg": {c: statistics.fmean(v) for c, v in scored.items()}}


def predict(model: dict, away: str, home: str) -> dict:
    mu, hfa = model["mu"], model["hfa"]
    att, defence = model["att"], model["def"]
    exp_home = mu + att[home] - defence[away] + hfa
    exp_away = mu + att[away] - defence[home]
    return {
        "exp_home": exp_home, "exp_away": exp_away,
        "exp_margin_home": exp_home - exp_away,
        "exp_total": exp_home + exp_away,
        # secondary totals estimator named in PREREGISTRATION.md §3: the two clubs' own scoring averages summed
        "exp_total_secondary": model["score_avg"][home] + model["score_avg"][away],
    }


def normal_cdf(x: float, mu: float = 0.0, sd: float = 1.0) -> float:
    if sd <= 0:
        raise ValueError("a non-positive sd is a fit failure, not a number")
    return 0.5 * (1.0 + math.erf((x - mu) / (sd * math.sqrt(2.0))))


def residuals(model: dict, games: list[dict]) -> dict:
    margin_res, total_res, margin_hat, total_hat, actual_margin, actual_total = [], [], [], [], [], []
    for g in games:
        p = predict(model, g["away"], g["home"])
        am = int(g["home_score"]) - int(g["away_score"])
        at = int(g["home_score"]) + int(g["away_score"])
        margin_res.append(am - p["exp_margin_home"])
        total_res.append(at - p["exp_total"])
        margin_hat.append(p["exp_margin_home"])
        total_hat.append(p["exp_total"])
        actual_margin.append(am)
        actual_total.append(at)
    def sd(values):
        return statistics.pstdev(values) if len(values) > 1 else 0.0
    out = {
        "n": len(games),
        "sigma_margin": sd(margin_res),
        "sigma_total": sd(total_res),
        "var_margin_actual": statistics.pvariance(actual_margin),
        "var_margin_predicted": statistics.pvariance(margin_hat),
        "margin_r2": pearson(margin_hat, actual_margin) ** 2,
        "total_r2": pearson(total_hat, actual_total) ** 2,
        "mean_abs_margin_error": statistics.fmean(abs(v) for v in margin_res),
        "mean_abs_total_error": statistics.fmean(abs(v) for v in total_res),
    }
    if out["sigma_margin"] < SIGMA_FLOOR or out["sigma_total"] < SIGMA_FLOOR:
        raise SystemExit(f"forward-ledger/model: fitted sd below the floor declared in the protocol: {out}")
    return out


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3 or n != len(ys):
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else float("nan")


def boot_ci(values: list[float], draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> list[float]:
    """Deterministic percentile interval for a mean of independent observations (game-cluster resample)."""
    import random
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    return [round(means[int(0.025 * draws)], 4), round(means[int(0.975 * draws)], 4)]


def correlation_register(games: list[dict], model: dict) -> dict:
    """Correlations are computed only from scores published on the official pages, and every value carries n."""
    margins = [int(g["home_score"]) - int(g["away_score"]) for g in games]
    totals = [int(g["home_score"]) + int(g["away_score"]) for g in games]
    wins = [1.0 if m > 0 else 0.0 for m in margins]
    r_mt = pearson(margins, totals)
    # joint vs product for the two events a same-game parlay would most often combine
    mean_total = statistics.fmean(totals)
    joint = sum(1 for m, t in zip(margins, totals) if m > 0 and t > mean_total) / len(games)
    prod = statistics.fmean(wins) * (sum(1 for t in totals if t > mean_total) / len(totals))
    by_week = defaultdict(list)
    for g, m in zip(games, margins):
        by_week[int(g["week"])].append(m)
    same_week_pairs = []
    for week, values in sorted(by_week.items()):
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                same_week_pairs.append((values[i], values[j]))
    r_pairs = pearson([p[0] for p in same_week_pairs], [p[1] for p in same_week_pairs])
    club_stats = defaultdict(lambda: {"gp": 0, "w": 0, "pf": 0, "pa": 0})
    for g in games:
        for club, other, is_home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
            s = club_stats[club]
            s["gp"] += 1
            mine, theirs = (int(g["home_score"]), int(g["away_score"])) if is_home else (int(g["away_score"]), int(g["home_score"]))
            s["pf"] += mine
            s["pa"] += theirs
            if mine > theirs:
                s["w"] += 1
    win_pct = [s["w"] / s["gp"] for s in club_stats.values()]
    diff_per_game = [(s["pf"] - s["pa"]) / s["gp"] for s in club_stats.values()]
    return {
        "n_games": len(games),
        "n_clubs": len(club_stats),
        "margin_vs_total": {"pearson_r": round(r_mt, 4), "n": len(games),
                            "reading": "the dependence a same-game side-and-total parlay assumes away"},
        "joint_over_product_same_game": {
            "joint_p_home_win_and_over_league_mean_total": round(joint, 4),
            "independent_product": round(prod, 4),
            "ratio": round(joint / prod, 4) if prod else None,
            "n": len(games),
        },
        "same_week_cross_game_margin": {"pearson_r": round(r_pairs, 4), "n_pairs": len(same_week_pairs),
                                        "reading": "the dependence a multi-game parlay assumes away"},
        "club_win_pct_vs_point_differential": {"pearson_r": round(pearson(win_pct, diff_per_game), 4),
                                               "n": len(club_stats),
                                               "reading": "how much of a record is the margin it came from"},
        "margin_mean_bootstrap_ci": boot_ci(margins),
        "ties_observed": sum(1 for m in margins if m == 0),
        "caveat": "Pearson r on eight-plus seasons of nothing: this register uses 2026 Weeks 1-10 only. "
                  "It is not a correlation of model errors against the market, which no licensed price row in "
                  "this repository would allow yet.",
    }


def leaderboard_divisions() -> list[dict]:
    """Divisions and their eligibility state. Nothing here is a performance number and nothing may become one
    from a backtest: the eligibility column is a gate outcome, not a result."""
    divisions = [
        "Singles · side", "Singles · total", "Singles · moneyline",
        "Game parlay (two legs, two games)", "Same-game parlay (two legs, one game)", "Player-prop combo",
    ]
    out = []
    for name in divisions:
        out.append({
            "division": name,
            "registered_rows": 1 if name.startswith("Singles") else 0,
            "eligible_for_ranking": 0,
            "why_not": ("no prospective graded fixture yet: the first registered window opens with the "
                        "2026-11-19 20:15 ET kickoff")
            if name.startswith("Singles") else
            ("no row may be registered in this division until a directly validated joint probability and the "
             "operator's void/push rules both exist (joint-evidence gate)"),
            "grading_basis": "benchmark-relative Brier skill with a game-cluster lower bound and Benjamini-Hochberg control"
            if name.startswith("Singles") else "not gradeable",
            "signal_column": "blank until the first graded fixture",
            "staking_column": "blank by price-data policy (no licensed two-sided source)",
        })
    return out


def main() -> int:
    games = load_ledger()
    if len(games) < 140:
        raise SystemExit(f"forward-ledger/model: expected 149 graded games, found {len(games)}")
    model = fit(games)
    diagnostics_fit = residuals(model, games)

    # chronological holdout: fit on Weeks 1-8, evaluate on Weeks 9-10 (fixed by PREREGISTRATION.md §4)
    train = [g for g in games if int(g["week"]) not in HOLDOUT_WEEKS]
    holdout = [g for g in games if int(g["week"]) in HOLDOUT_WEEKS]
    holdout_model = fit(train)
    holdout_diag = residuals(holdout_model, holdout)
    holdout_margins_hat = [predict(holdout_model, g["away"], g["home"])["exp_margin_home"] for g in holdout]
    holdout_margins_act = [int(g["home_score"]) - int(g["away_score"]) for g in holdout]
    holdout_p_home = [normal_cdf(v, 0.0, holdout_diag["sigma_margin"]) for v in holdout_margins_hat]
    holdout_outcome = [1.0 if m > 0 else 0.0 for m in holdout_margins_act]
    brier_model = statistics.fmean((p - y) ** 2 for p, y in zip(holdout_p_home, holdout_outcome))
    base_rate = statistics.fmean(holdout_outcome)
    brier_base = statistics.fmean((base_rate - y) ** 2 for y in holdout_outcome)
    brier_half = statistics.fmean((0.5 - y) ** 2 for y in holdout_outcome)

    ratings_rows = []
    for club in sorted(model["att"]):
        s = [g for g in games if club in (g["away"], g["home"])]
        pf = statistics.fmean([(int(g["home_score"]) if g["home"] == club else int(g["away_score"])) for g in s])
        pa = statistics.fmean([(int(g["away_score"]) if g["home"] == club else int(g["home_score"])) for g in s])
        wins = sum(1 for g in s if (int(g["home_score"]) > int(g["away_score"])) == (g["home"] == club))
        ratings_rows.append({
            "club": club, "games": len(s), "wins": wins, "losses": len(s) - wins,
            "points_for_per_game": round(pf, 3), "points_against_per_game": round(pa, 3),
            "attack": round(model["att"][club], 4), "defence": round(model["def"][club], 4),
            "net_rating": round(model["att"][club] - model["def"][club], 4),
            "source": "computed from data/results_ledger.csv (official NFL.com score pages)",
        })

    fixtures = list(csv.DictReader((DATA / "fixtures_2026_w11.csv").open(encoding="utf-8", newline="")))
    if len(fixtures) != 13:
        raise SystemExit(f"forward-ledger/model: expected 13 Week 11 fixtures, found {len(fixtures)}")
    config_hash = hashlib.sha256(json.dumps(
        {"mu": model["mu"], "hfa": model["hfa"], "att": model["att"], "def": model["def"],
         "sigma_margin": diagnostics_fit["sigma_margin"], "sigma_total": diagnostics_fit["sigma_total"]},
        sort_keys=True).encode()).hexdigest()[:16]
    issued = utc_stamp()
    prospect_rows, records = [], []
    for fx in fixtures:
        away, home = fx["away"], fx["home"]
        p = predict(model, away, home)
        sd_m = diagnostics_fit["sigma_margin"]
        sd_t = diagnostics_fit["sigma_total"]
        margin = p["exp_margin_home"]
        # a negative line means the home club is the favourite, the convention every operator prints
        fair_spread = -round(margin / LINE_ROUND_SIDED) * LINE_ROUND_SIDED
        fair_total = round(p["exp_total"] / LINE_ROUND_TOTAL) * LINE_ROUND_TOTAL
        p_home_win = normal_cdf(margin, 0.0, sd_m)
        p_home_cover = normal_cdf(margin + fair_spread, 0.0, sd_m)   # against our own line, never a market line
        p_over = normal_cdf(0.0, fair_total - p["exp_total"], sd_t)   # P(total > our line)
        push = (normal_cdf(0.5, fair_total - p["exp_total"], sd_t)
                - normal_cdf(-0.5, fair_total - p["exp_total"], sd_t))
        events = {"side": "home covers our originated side line",
                  "total": "game total lands over our originated total",
                  "moneyline": "home club wins the game"}
        for market, projected, our_line, prob in (
            ("side", round(margin, 3), fair_spread, p_home_cover),
            ("total", round(p["exp_total"], 3), fair_total, p_over),
            ("moneyline", round(margin, 3), "", p_home_win),
        ):
            prospect_rows.append({
                "week": 11, "slot": fx["slot"], "kickoff_et": f"{fx['date_et']}T{fx['kickoff_et']}",
                "away": away, "home": home, "market": market,
                "our_line": "" if market == "moneyline" else our_line,
                "projected_value": projected,
                "event": events[market],
                "probability": round(prob, 4),
                "fair_line": our_line if market != "moneyline" else "",
                "market_line": "", "difference": "",
                "push_or_tie_probability": round(push, 4) if market == "total" else "",
                "model_version": "fl1.0.0", "config_hash": config_hash,
                "issued_at_utc": issued,
                "secondary_total_estimator": round(p["exp_total_secondary"], 3) if market == "total" else "",
                "estimator_gap": round(p["exp_total"] - p["exp_total_secondary"], 3) if market == "total" else "",
                "source_url": fx["game_centre_url"],
                "price_policy_note": "market_line and difference stay empty: pricing/PRICE_DATA_POLICY.md grants no source",
            })
            records.append({
                "forecast_id": f"FL1-W11-{fx['slot']}-{away}-{home}-{market}",
                "issued_at_utc": issued, "as_of_data": "2026 week 10 (through 2026-11-16 read)",
                "season": 2026, "week": 11, "slot": fx["slot"], "away": away, "home": home,
                "market": market, "division": f"Singles · {market}",
                "strategy": "FL1", "model_version": "fl1.0.0", "config_hash": config_hash,
                "registration": "forward-ledger/PREREGISTRATION.md §1-§6 (frozen)",
                "event": events[market], "probability": round(prob, 6),
                "our_line": "" if market == "moneyline" else our_line,
                "market_line": "", "residual": "",
                "inputs": {
                    "mu": round(model["mu"], 4), "hfa": round(model["hfa"], 4),
                    "att_home": round(model["att"][home], 4), "def_home": round(model["def"][home], 4),
                    "att_away": round(model["att"][away], 4), "def_away": round(model["def"][away], 4),
                    "sigma_margin": round(sd_m, 4), "sigma_total": round(sd_t, 4),
                    "exp_home_points": round(p["exp_home"], 4), "exp_away_points": round(p["exp_away"], 4),
                    "exp_total_secondary": round(p["exp_total_secondary"], 4),
                    "games_fit": len(games), "ledger_sha256": hashlib.sha256((DATA / "results_ledger.csv").read_bytes()).hexdigest()[:16],
                },
                "supersedes": "", "selected": False,
                "source_urls": [fx["game_centre_url"], "https://www.nfl.com/schedules/2026/by-week/week-11"],
            })

    DATA.mkdir(exist_ok=True)
    with (DATA / "ratings_2026_w10.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ratings_rows[0].keys()))
        writer.writeheader(); writer.writerows(ratings_rows)
    with (DATA / "prospects_2026_w11.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(prospect_rows[0].keys()))
        writer.writeheader(); writer.writerows(prospect_rows)
    with (DATA / "prospect_records.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    diagnostics = {
        "schema": "nfl3-forward-ledger-fit/v1",
        "protocol": "forward-ledger/PREREGISTRATION.md",
        "fitted_on": {"graded_games": len(games), "weeks": sorted({int(g['week']) for g in games}),
                      "source": "data/results_ledger.csv (official score pages, 2026-11-15 and 2026-11-16 reads)"},
        "constants": {"mu": round(model["mu"], 4), "hfa": round(model["hfa"], 4),
                      "iterations": ITERATIONS, "line_round_sided": LINE_ROUND_SIDED,
                      "line_round_total": LINE_ROUND_TOTAL, "sigma_floor": SIGMA_FLOOR,
                      "config_hash": config_hash},
        "in_sample": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in diagnostics_fit.items()},
        "chronological_holdout": {
            "train_weeks": sorted({int(g["week"]) for g in train}), "eval_weeks": list(HOLDOUT_WEEKS),
            "n_train": len(train), "n_eval": len(holdout),
            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in holdout_diag.items()},
            "brier_home_win_model": round(brier_model, 5),
            "brier_home_win_base_rate": round(brier_base, 5),
            "brier_home_win_coin": round(brier_half, 5),
            "brier_skill_vs_base_rate": round(1 - brier_model / brier_base, 4) if brier_base else None,
            "brier_skill_vs_coin": round(1 - brier_model / brier_half, 4),
            "base_rate_home_win": round(base_rate, 4),
            "margin_r2_holdout": round(pearson(holdout_margins_hat, holdout_margins_act) ** 2, 4),
            "luck_split": {
                "variance_of_actual_margin": round(statistics.pvariance(holdout_margins_act), 4),
                "variance_of_expectation": round(statistics.pvariance(holdout_margins_hat), 4),
                "share_of_variance_inside_the_expectation":
                    round(statistics.pvariance(holdout_margins_hat) / statistics.pvariance(holdout_margins_act), 4)
                    if statistics.pvariance(holdout_margins_act) else None,
                "reading": "this is the removal-of-luck number the panel publishes: the share of game-margin "
                           "variance an expectation can address, everything else is luck by construction",
            },
        },
        "correlation_register": correlation_register(games, model),
        "backtest_only_values_for_the_firewall_check": [
            round(brier_model, 5), round(brier_base, 5), round(brier_half, 5),
            round(1 - brier_model / brier_base, 4) if brier_base else None,
            round(model["mu"], 4), round(model["hfa"], 4),
        ],
        "leaderboard_divisions": leaderboard_divisions(),
        "issue_stamp_utc": issued,
        "price_firewall": "no ROI, CLV or residual is computed anywhere in this workspace; the columns exist and are empty",
    }
    (DATA / "fit_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    (DATA / "leaderboard.json").write_text(json.dumps({
        "schema": "nfl3-forward-ledger-leaderboard/v1",
        "graded_fixtures_in_window": 0,
        "window_opens_utc": "2026-11-19T20:15-05:00",
        "divisions": diagnostics["leaderboard_divisions"],
        "controls": [
            {"control": "coin flip", "definition": "0.5 on the home side, always", "registered": True},
            {"control": "base rate", "definition": f"the fitted home-win rate on the evaluation window", "registered": True},
            {"control": "favourites only", "definition": "back the side our own line prefers, at our own line", "registered": True,
             "note": "not gradeable without a price row; the row exists so the run will include it the day a licensed source does"},
            {"control": "random side", "definition": "uniform coin on side selection with a recorded seed", "registered": True},
        ],
        "reward": {"funded": False, "note": "no reward pool is defined by any owner decision; the field stays blank"},
    }, indent=2) + "\n", encoding="utf-8")

    print(f"model fl1.0.0 config {config_hash}: mu={model['mu']:.3f} hfa={model['hfa']:.3f} "
          f"sigma_margin={diagnostics_fit['sigma_margin']:.3f} sigma_total={diagnostics_fit['sigma_total']:.3f}")
    print(f"in-sample margin R2 {diagnostics_fit['margin_r2']:.4f} over {diagnostics_fit['n']} games; "
          f"holdout weeks {HOLDOUT_WEEKS}: R2 {diagnostics['chronological_holdout']['margin_r2_holdout']:.4f}, "
          f"Brier skill vs base rate {diagnostics['chronological_holdout']['brier_skill_vs_base_rate']}")
    print(f"prospective: {len(records)} forecast records issued {issued} across {len(fixtures)} fixtures, "
          f"market and residual columns empty by policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
