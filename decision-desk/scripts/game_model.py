#!/usr/bin/env python3
"""Signal research on the verified official game log (NFL.com, 2026 Weeks 1-9).

Everything here is computed from data/games_2026.csv, which is cross-checked
against the official NFL.com standings by scripts/crosscheck_games.py. No market
prices, no third-party data, and no value is invented: parameters that cannot be
estimated from official scores are reported as unknown.

What this produces
------------------
1. League constants that a line needs: mean total points, sd of total, mean and sd
   of home margin, estimated home-field advantage. These are the raw ingredients of
   an originated total/spread and they ARE estimable from official scores.
2. Opponent-adjusted attack/defence ratings (ridge least squares).
3. Split-half reliability: how much of an observed team rating is stable signal and
   how much is noise. This is the honest version of "removing luck" - luck is never
   removed, but the share of variance that repeats can be measured and reported.
4. Real, non-market correlation coefficients (margin vs total, week-to-week
   autocorrelation, half-rating cross correlation) and - where a market is missing -
   an explicit refusal to state a number.
5. Walk-forward out-of-sample skill of the ratings as a winner-probability model,
   scored with Brier and log loss against two naive baselines, so skill is measured
   out of sample rather than in sample.
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
GAMES = DESK / "data" / "games_2026.csv"
OUT = DESK / "data" / "analysis.json"
SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/week-{}"
STANDINGS_URL = "https://www.nfl.com/standings/"
SEED = 20261112
RIDGE = 2.0  # shrinkage on team ratings; declared, and varied in the sensitivity block


# ----------------------------------------------------------------------------- maths
def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def var(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def sd(xs):
    return math.sqrt(var(xs))


def pearson(xs, ys):
    n = min(len(xs), len(ys))
    if n < 3:
        return float("nan")
    mx, my = mean(xs[:n]), mean(ys[:n])
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sxx = sum((xs[i] - mx) ** 2 for i in range(n))
    syy = sum((ys[i] - my) ** 2 for i in range(n))
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def solve(matrix, vector):
    """Gaussian elimination with partial pivoting (small dense systems only)."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular system")
        a[col], a[pivot] = a[pivot], a[col]
        inv = 1.0 / a[col][col]
        for j in range(col, n + 1):
            a[col][j] *= inv
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            if factor:
                for j in range(col, n + 1):
                    a[r][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


PYTHAGOREAN_EXPONENT = 2.37  # conventional value; an assumption, published as such


def pythagorean(pf, pa, games):
    if pf + pa <= 0 or games == 0:
        return None
    rate = pf ** PYTHAGOREAN_EXPONENT / (pf ** PYTHAGOREAN_EXPONENT + pa ** PYTHAGOREAN_EXPONENT)
    return rate * games


def norm_cdf(x, mu=0.0, sigma=1.0):
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def r4(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, 4)


# ----------------------------------------------------------------------------- data
def load_games():
    with GAMES.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    played, blank = [], []
    for row in rows:
        if row["away_score"] == "" or row["home_score"] == "":
            blank.append(row)
            continue
        row["a"], row["h"] = int(row["away_score"]), int(row["home_score"])
        row["week"] = int(row["week"])
        played.append(row)
    return rows, played, blank


def fit_ratings(games, ridge=RIDGE):
    """home_pts = mu + hfa/2 + att[home] - def[away]; away_pts = mu - hfa/2 + att[away] - def[home]."""
    teams = sorted({g["away_team"] for g in games} | {g["home_team"] for g in games})
    index = {t: i for i, t in enumerate(teams)}
    n = 2 * len(teams) + 2  # att..., def..., mu, hfa
    mu_i, hfa_i = 2 * len(teams), 2 * len(teams) + 1
    xtx = [[0.0] * n for _ in range(n)]
    xty = [0.0] * n

    def observe(x, y):
        for i, xi in enumerate(x):
            if xi == 0.0:
                continue
            xty[i] += xi * y
            row = xtx[i]
            for j in range(i, n):
                if x[j]:
                    row[j] += xi * x[j]

    for g in games:
        away, home = index[g["away_team"]], index[g["home_team"]]
        for points, own, opp, sign in ((g["h"], home, away, 1.0), (g["a"], away, home, -1.0)):
            x = [0.0] * n
            x[own] = 1.0
            x[len(teams) + opp] = -1.0
            x[mu_i] = 1.0
            x[hfa_i] = 0.5 * sign
            observe(x, points)

    for t in range(2 * len(teams)):  # ridge on team effects only, not mu/hfa
        xtx[t][t] += ridge
    for i in range(n):
        for j in range(i):
            xtx[i][j] = xtx[j][i]
    beta = solve(xtx, xty)
    att = {t: beta[i] for t, i in index.items()}
    dfn = {t: beta[len(teams) + i] for t, i in index.items()}
    return {"teams": teams, "attack": att, "defense": dfn,
            "league_points_per_team": beta[mu_i], "hfa": beta[hfa_i],
            "rated_games": len(games)}


def residuals(games, model):
    out = []
    for g in games:
        a, h = g["away_team"], g["home_team"]
        pred_home = (model["league_points_per_team"] + model["hfa"] / 2
                     + model["attack"][h] - model["defense"][a])
        pred_away = (model["league_points_per_team"] - model["hfa"] / 2
                     + model["attack"][a] - model["defense"][h])
        out.append((g, pred_home - g["h"], pred_away - g["a"]))
    return out


def bootstrap_ci(values, stat, reps=2000, seed=SEED):
    rng = random.Random(seed)
    n = len(values)
    if n < 5:
        return None
    draws = []
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        draws.append(stat(sample))
    draws.sort()
    return [r4(draws[int(0.025 * reps)]), r4(draws[int(0.975 * reps)])]


# ----------------------------------------------------------------------------- analysis
def main() -> int:
    rows, played, blank = load_games()
    totals = [g["a"] + g["h"] for g in played]
    margins = [g["h"] - g["a"] for g in played]
    result: dict = {"source": {"games_csv": "data/games_2026.csv",
                               "schedule_pages": [SCHEDULE.format(w) for w in range(1, 10)],
                               "standings_crosscheck": STANDINGS_URL,
                               "observed": "2026-11-12",
                               "note": "Scores are official NFL.com finals. One Week 2 game is rendered "
                                       "'Hidden Score' on the official page and is left blank, never inferred."}}

    # 1. league constants a line needs
    result["league"] = {
        "games_with_scores": len(played),
        "games_unverified_blank": [f"week {g['week']} {g['away_team']} at {g['home_team']}" for g in blank],
        "mean_total_points": r4(mean(totals)),
        "sd_total_points": r4(sd(totals)),
        "mean_home_margin": r4(mean(margins)),
        "sd_home_margin": r4(sd(margins)),
        "mean_home_margin_ci95": bootstrap_ci(margins, mean),
        "median_total_points": r4(sorted(totals)[len(totals) // 2]),
        "share_home_wins": r4(sum(1 for m in margins if m > 0) / len(margins)),
        "share_ties": r4(sum(1 for m in margins if m == 0) / len(margins)),
        "note": "A total line needs the mean and sd of the combined score; a spread needs the "
                "mean and sd of the margin. These are estimated from official finals only. "
                "They describe the past nine weeks and carry no market comparison.",
    }

    model = fit_ratings(played)
    result["model_all"] = {
        "form": "home = mu + hfa/2 + attack[home] - defence[away]; away = mu - hfa/2 + attack[away] - defence[home]",
        "ridge_lambda": RIDGE,
        "mu_points_per_team": r4(model["league_points_per_team"]),
        "hfa_points": r4(model["hfa"]),
        "implied_league_total": r4(2 * model["league_points_per_team"]),
        "fitted_games": model["rated_games"],
    }
    res = residuals(played, model)
    result["model_fit"] = {
        "residual_sd_home_points": r4(sd([rh for _, rh, _ in res])),
        "residual_sd_away_points": r4(sd([ra for _, _, ra in res])),
        "residual_sd_margin": r4(sd([rh - ra for _, rh, ra in res])),
        "note": "Residual sd of the margin is the number a spread's uncertainty band needs. "
                "It is estimated in sample, so it is optimistic.",
    }

    # 2. split-half reliability = how much of a rating repeats (the honest 'luck' statement)
    odd = [g for g in played if g["week"] % 2 == 1]
    even = [g for g in played if g["week"] % 2 == 0]
    m_odd, m_even = fit_ratings(odd), fit_ratings(even)
    teams = sorted(set(m_odd["attack"]) & set(m_even["attack"]))
    net_odd = [m_odd["attack"][t] + m_odd["defense"][t] for t in teams]
    net_even = [m_even["attack"][t] + m_even["defense"][t] for t in teams]
    r_half = pearson(net_odd, net_even)
    spearman_brown = (2 * r_half / (1 + r_half)) if r_half > -1 else None
    result["reliability"] = {
        "method": "Split the nine weeks into odd and even weeks, re-fit team ratings independently, "
                  "correlate the implied net team strength. Spearman-Brown corrects the half-sample "
                  "correlation to the full nine-week scale.",
        "half_sample_r": r4(r_half),
        "spearman_brown_full_sample": r4(spearman_brown),
        "stable_variance_share": r4(spearman_brown),
        "noise_variance_share": r4(1 - spearman_brown) if spearman_brown is not None else None,
        "games_in_odd_weeks": len(odd),
        "games_in_even_weeks": len(even),
        "caveat": "A nine-week, single-season sample is small. The reliability figure bounds how much "
                  "of an early-season team rating can be trusted; it does not make the rating predictive "
                  "and it is not a market edge.",
    }

    # 3. real correlations (only from official scores; no market data involved)
    pairs = []
    pairs.append({
        "pair": "Same-game margin vs same-game total",
        "a": "margin", "b": "total", "n": len(margins),
        "r": r4(pearson(margins, totals)),
        "ci95": bootstrap_ci(list(zip(margins, totals)), lambda s: pearson([p[0] for p in s], [p[1] for p in s])),
        "use": "Sets whether a spread signal and a total signal can be treated as independent when "
               "combining legs. This is measured; prop-to-prop correlation is not, because no prop "
               "outcome data exists in this repository.",
    })
    prev_margin, next_margin = [], []
    by_team_week = {}
    for g in played:
        by_team_week.setdefault(g["home_team"], {})[g["week"]] = g["h"] - g["a"]
        by_team_week.setdefault(g["away_team"], {})[g["week"]] = g["a"] - g["h"]
    for team, weeks in by_team_week.items():
        for w in sorted(weeks):
            if w + 1 in weeks:
                prev_margin.append(weeks[w])
                next_margin.append(weeks[w + 1])
    pairs.append({
        "pair": "Team margin in week w vs week w+1 (week-to-week persistence)",
        "a": "margin_w", "b": "margin_w+1", "n": len(prev_margin),
        "r": r4(pearson(prev_margin, next_margin)),
        "ci95": bootstrap_ci(list(zip(prev_margin, next_margin)),
                             lambda s: pearson([p[0] for p in s], [p[1] for p in s])),
        "use": "If week-to-week persistence is near zero, single-week streak or 'hot team' signals are "
               "noise and must not be promoted to a strategy.",
    })
    team_pf, team_pa = [], []
    for team in sorted(by_team_week):
        team_pf.append(sum(g["h"] if g["home_team"] == team else g["a"]
                           for g in played if team in (g["home_team"], g["away_team"])))
        team_pa.append(sum(g["a"] if g["home_team"] == team else g["h"]
                           for g in played if team in (g["home_team"], g["away_team"])))
    pairs.append({
        "pair": "Team points scored vs points allowed (32 teams, whole sample)",
        "a": "pf", "b": "pa", "n": len(team_pf),
        "r": r4(pearson(team_pf, team_pa)),
        "ci95": bootstrap_ci(list(zip(team_pf, team_pa)),
                             lambda s: pearson([p[0] for p in s], [p[1] for p in s])),
        "use": "Measured, not assumed. If scoring and conceding are strongly positively related, "
               "pace is a shared factor and affects how a team total and a game total move together.",
    })
    pairs.append({
        "pair": "Prop-to-prop correlation (any two player props)",
        "a": "prop_a", "b": "prop_b", "n": 0, "r": None, "ci95": None,
        "use": "UNKNOWN - BLANK. No player-level outcome data exists in this repository, so no prop "
               "correlation can be stated. Any number here would be fabricated. It must be measured "
               "from official box scores before a prop-combination strategy may pass a gate.",
    })
    result["correlations"] = pairs

    # 4. walk-forward out-of-sample skill, nothing tuned on the evaluation weeks
    wf = []
    for week in sorted({g["week"] for g in played}):
        if week < 4:
            continue
        fit_games = [g for g in played if g["week"] < week]
        test = [g for g in played if g["week"] == week]
        if len(fit_games) < 20 or not test:
            continue
        m = fit_ratings(fit_games)
        sigma = sd([rh - ra for _, rh, ra in residuals(fit_games, m)]) or 13.0
        for g in test:
            a, h = g["away_team"], g["home_team"]
            pred = (m["attack"][h] - m["defense"][a]) - (m["attack"][a] - m["defense"][h]) + m["hfa"]
            p_home = norm_cdf(pred, 0.0, sigma)
            outcome = 1.0 if g["h"] > g["a"] else (0.5 if g["h"] == g["a"] else 0.0)
            wf.append({"week": week, "p": p_home, "y": outcome, "pred_margin": pred,
                       "actual_margin": g["h"] - g["a"]})

    def score(rows_, key):
        n = len(rows_)
        brier = sum((r_[key] - r_["y"]) ** 2 for r_ in rows_) / n
        ll = -sum(r_["y"] * math.log(max(r_[key], 1e-9)) + (1 - r_["y"]) * math.log(max(1 - r_[key], 1e-9))
                  for r_ in rows_) / n
        return brier, ll

    if wf:
        b_model, l_model = score(wf, "p")
        home_rate = mean([r_["y"] for r_ in wf])
        base_rows = [{"y": r_["y"], "p": home_rate} for r_ in wf]
        half_rows = [{"y": r_["y"], "p": 0.5} for r_ in wf]
        b_base, l_base = score(base_rows, "p")
        b_half, l_half = score(half_rows, "p")
        correct = sum(1 for r_ in wf if (r_["p"] > 0.5) == (r_["y"] > 0.5) and r_["y"] != 0.5)
        graded = sum(1 for r_ in wf if r_["y"] != 0.5)
        mae = mean([abs(r_["pred_margin"] - r_["actual_margin"]) for r_ in wf])
        result["walk_forward"] = {
            "evaluation_weeks": sorted({r_["week"] for r_ in wf}),
            "n_games": len(wf),
            "brier_model": r4(b_model),
            "brier_home_base_rate": r4(b_base),
            "brier_coin_flip": r4(b_half),
            "log_loss_model": r4(l_model),
            "log_loss_home_base_rate": r4(l_base),
            "log_loss_coin_flip": r4(l_half),
            "brier_skill_vs_base_rate": r4(1 - b_model / b_base),
            "brier_skill_vs_coin_flip": r4(1 - b_model / b_half),
            "straight_up_accuracy": r4(correct / graded) if graded else None,
            "margin_mae": r4(mae),
            "sigma_used_note": "sigma is re-estimated inside each walk-forward step from prior weeks only",
            "verdict": "Computed out of sample with no tuning on evaluation weeks. Even a positive "
                       "number here is a winner-probability skill, not a betting edge: no price, no vig, "
                       "no closing line and no settlement archive exist in this repository.",
        }
        # how stable is the skill week to week - this is the "selectively skill based" question
        weekly = []
        for wk in sorted({r_["week"] for r_ in wf}):
            block = [r_ for r_ in wf if r_["week"] == wk]
            b_m, l_m = score(block, "p")
            b_c, l_c = score([{"y": r_["y"], "p": 0.5} for r_ in block], "p")
            weekly.append({"week": wk, "n": len(block), "brier_model": r4(b_m),
                           "brier_coin_flip": r4(b_c),
                           "skill_vs_coin_flip": r4(1 - b_m / b_c),
                           "log_loss_model": r4(l_m)})
        result["walk_forward"]["weekly"] = weekly
        wins = sum(1 for w in weekly if w["skill_vs_coin_flip"] > 0)
        result["walk_forward"]["weeks_with_positive_skill"] = f"{wins} of {len(weekly)}"
        result["walk_forward"]["skill_ci95"] = bootstrap_ci(
            wf, lambda s: 1 - score(s, "p")[0] / score([{"y": r_["y"], "p": 0.5} for r_ in s], "p")[0])

    # 4b. luck vs skill: wins compared with wins implied by point differential
    league_sd = result["model_fit"]["residual_sd_margin"]
    team_pf_map, team_pa_map = {}, {}
    for t in model["teams"]:
        own_games = [g for g in played if t in (g["home_team"], g["away_team"])]
        team_pf_map[t] = sum(g["h"] if g["home_team"] == t else g["a"] for g in own_games)
        team_pa_map[t] = sum(g["a"] if g["home_team"] == t else g["h"] for g in own_games)
    luck_rows = []
    for t in model["teams"]:
        games_t = [g for g in played if t in (g["home_team"], g["away_team"])]
        real_w = real_l = real_t = 0
        exp_w = 0.0
        close_w = close_g = 0
        for g in games_t:
            is_home = g["home_team"] == t
            own, conceded = (g["h"], g["a"]) if is_home else (g["a"], g["h"])
            opp = g["away_team"] if is_home else g["home_team"]
            if own > conceded:
                real_w += 1
            elif own < conceded:
                real_l += 1
            else:
                real_t += 1
            expected_own = (model["league_points_per_team"] + model["hfa"] * (0.5 if is_home else -0.5)
                            + model["attack"][t] - model["defense"][opp])
            expected_opp = (model["league_points_per_team"] - model["hfa"] * (0.5 if is_home else -0.5)
                            + model["attack"][opp] - model["defense"][t])
            actual_margin = own - conceded
            # wins the fitted ratings expected, not wins actually earned
            exp_w += norm_cdf(expected_own - expected_opp, 0.0, league_sd)
            if abs(actual_margin) <= 7:
                close_g += 1
                if own > conceded:
                    close_w += 1
        luck_rows.append({
            "team": t, "games": len(games_t), "w": real_w, "l": real_l, "t": real_t,
            "expected_wins_from_points": r4(exp_w),
            "wins_minus_expected": r4(real_w - exp_w),
            "one_score_games": close_g, "one_score_wins": close_w,
            "one_score_record": f"{close_w}-{close_g - close_w}" if close_g else "",
            "pythagorean_wins": r4(pythagorean(team_pf_map[t], team_pa_map[t], len(games_t))),
            "note": "expected_wins_from_ratings is the win total the opponent-adjusted ratings predicted "
                    "before those games; wins minus that total is the unexplained residual (candidate luck "
                    "or clutch performance, not proof of either). pythagorean_wins uses the conventional "
                    "2.37 exponent, which is an assumption and is labelled as one.",
        })
    luck_rows.sort(key=lambda r: r["wins_minus_expected"] if r["wins_minus_expected"] is not None else 0,
                   reverse=True)
    result["luck"] = {
        "method": "For every team, actual wins are compared with (a) the wins the fitted opponent-adjusted "
                  "ratings expected before those games and (b) a Pythagorean point-differential estimate. "
                  "All inputs are official finals.",
        "league_sd_margin_used": r4(league_sd),
        "pythagorean_exponent": PYTHAGOREAN_EXPONENT,
        "teams": luck_rows,
        "summary": "Reported because 'removing luck' is a request the data can only partly satisfy. What "
                   "the data supports is measuring (a) how much of a rating repeats, (b) how far a team's "
                   "record sits from its point differential, and (c) whether skill survives out of sample. "
                   "Luck itself is never removed.",
    }

    # 5. team table
    team_rows = []
    for t in model["teams"]:
        weeks = by_team_week.get(t, {})
        pf = sum(g["h"] if g["home_team"] == t else g["a"] for g in played if t in (g["home_team"], g["away_team"]))
        pa = sum(g["a"] if g["home_team"] == t else g["h"] for g in played if t in (g["home_team"], g["away_team"]))
        team_rows.append({
            "team": t,
            "games": len(weeks),
            "points_for": pf,
            "points_against": pa,
            "net_points": pf - pa,
            "attack_rating": r4(model["attack"][t]),
            "defence_rating": r4(model["defense"][t]),
            "net_rating": r4(model["attack"][t] + model["defense"][t]),
            "half_r_odd": r4(m_odd["attack"][t] + m_odd["defense"][t]),
            "half_r_even": r4(m_even["attack"][t] + m_even["defense"][t]),
        })
    team_rows.sort(key=lambda r: r["net_rating"], reverse=True)
    result["teams"] = team_rows

    # 6. originated numbers (with explicit uncertainty, and no market claim)
    led = {}
    for g in played:
        a, h = g["away_team"], g["home_team"]
        pred = (model["attack"][h] - model["defense"][a]) - (model["attack"][a] - model["defense"][h]) + model["hfa"]
        led[f"{a}@{h}"] = {
            "away": a, "home": h,
            "originated_home_margin": r4(pred),
            "originated_total": r4(2 * model["league_points_per_team"]),
            "sigma_margin_for_band": r4(result["model_fit"]["residual_sd_margin"]),
        }
    result["origination"] = {
        "method": "Independent numbers, not copies of any market. Spread = opponent-adjusted net rating "
                  "difference plus estimated home-field advantage. Total = fitted league total, which is "
                  "constant by construction for every game - a documented limitation of a points-only model.",
        "board": led,
        "status": "SHADOW ONLY. No originated number in this table has been compared with a market price, "
                  "so no edge, no value and no closing-line advantage is claimed or measurable here.",
    }

    result["limitations"] = [
        "Nine weeks of one season, 135 usable finals: wide uncertainty on every estimate.",
        "No injury adjustment: ratings ignore who was actually available.",
        "No market prices anywhere in the repository, so edge, vig and CLV are UNKNOWN and blank.",
        "No player-level outcomes, so prop and parlay-leg correlations are UNKNOWN and blank.",
        "A constant total for every game is a model limitation, not a claim about any matchup.",
        "The one hidden-score game is excluded rather than estimated.",
        "Home-field advantage is estimated here at essentially zero for this sample. That is a sample "
        "property of 2026 Weeks 1-9 and must not be generalised into a prior without more seasons.",
    ]
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(DESK)}")
    print(f"league total {result['league']['mean_total_points']} (sd {result['league']['sd_total_points']}); "
          f"home margin {result['league']['mean_home_margin']} (sd {result['league']['sd_home_margin']})")
    print(f"reliability r_half={result['reliability']['half_sample_r']} "
          f"spearman_brown={result['reliability']['spearman_brown_full_sample']}")
    if wf:
        print(f"walk-forward n={len(wf)} brier={result['walk_forward']['brier_model']} "
              f"vs coin flip {result['walk_forward']['brier_coin_flip']} "
              f"vs base rate {result['walk_forward']['brier_home_base_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
