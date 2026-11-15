#!/usr/bin/env python3
"""Walk-forward evaluation of the pre-registered model (PREREG-2026-OV1).

Implements *exactly* what the registration froze and nothing else:

  * ridge regression with lambda 2.0 on a sum-to-zero constraint;
  * fit on games with week < evaluation week only;
  * fixed sigma = 13.5 for margin and total;
  * evaluation window Weeks 4-10, warm-up Weeks 1-3;
  * three controls: coin flip, home base rate (fitting games only), favourites only;
  * Brier score primary, log loss secondary, cluster bootstrap over games
    (2,000 draws, seed 20261115) for a 95 % interval;
  * skill always stated relative to a benchmark, never as a raw rate.

The script writes `official-verify/data/evaluation.json`. It refuses to run if
the pre-registration gate fails, so a result can never exist without a
registration that precedes it.
"""
from __future__ import annotations

import csv
import json
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "official-verify" / "data"
GAMES = DATA / "games_2026_official.csv"
OUT = DATA / "evaluation.json"

LAMBDA = 2.0
SIGMA = 13.5
SIGMA_TOTAL = 13.5
WARMUP_WEEKS = (1, 2, 3)
EVAL_WEEKS = (4, 5, 6, 7, 8, 9, 10)
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261115


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def load_games():
    with GAMES.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    games = []
    for r in rows:
        if not r["home_score"].strip() or not r["away_score"].strip():
            continue
        games.append(
            {
                "week": int(r["week"]),
                "home": r["home_team"],
                "away": r["away_team"],
                "hs": int(r["home_score"]),
                "as": int(r["away_score"]),
                "game_id": r["game_id"],
                "source_url": r["source_url"],
            }
        )
    return games


def design(games, teams):
    """Ridge fit on the sum-to-zero parameterisation, closed form, no library."""
    index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    # parameters: mu, hfa, attack[0..n-1] (last one implied), defence[0..n-1] (last implied)
    k = 2 + 2 * (n_teams - 1)

    def params_to_vectors(theta):
        mu, hfa = theta[0], theta[1]
        attack = theta[2 : 2 + n_teams - 1]
        defence = theta[2 + n_teams - 1 :]
        attack = list(attack) + [-sum(attack)]
        defence = list(defence) + [-sum(defence)]
        return mu, hfa, attack, defence

    rows, ys = [], []
    for g in games:
        h, a = index[g["home"]], index[g["away"]]
        for sign, team, opponent, target in (
            (+1, h, a, g["hs"]),
            (-1, a, h, g["as"]),
        ):
            row = [0.0] * k
            row[0] = 1.0                     # mu
            row[1] = sign * 0.5              # hfa/2 with sign
            if team != n_teams - 1:
                row[2 + team] = 1.0          # own attack
            if opponent != n_teams - 1:
                row[2 + n_teams - 1 + opponent] = -1.0  # opponent defence
            rows.append(row)
            ys.append(float(target))

    # normal equations with ridge on every parameter except mu
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, y in zip(rows, ys):
        for i in range(k):
            if row[i] == 0.0:
                continue
            xty[i] += row[i] * y
            for j in range(k):
                if row[j] != 0.0:
                    xtx[i][j] += row[i] * row[j]
    for i in range(k):
        if i != 0:
            xtx[i][i] += LAMBDA
    # Gaussian elimination
    a_mat = [row[:] + [xty[i]] for i, row in enumerate(xtx)]
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(a_mat[r][col]))
        if abs(a_mat[pivot][col]) < 1e-12:
            raise SystemExit("singular system: not enough fitting games")
        a_mat[col], a_mat[pivot] = a_mat[pivot], a_mat[col]
        pv = a_mat[col][col]
        for j in range(col, k + 1):
            a_mat[col][j] /= pv
        for r in range(k):
            if r != col and a_mat[r][col] != 0.0:
                factor = a_mat[r][col]
                for j in range(col, k + 1):
                    a_mat[r][j] -= factor * a_mat[col][j]
    theta = [a_mat[i][k] for i in range(k)]
    return params_to_vectors(theta)


def brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def logloss(pairs):
    total = 0.0
    for p, y in pairs:
        p = min(max(p, 1e-12), 1 - 1e-12)
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(pairs)


def cluster_bootstrap(diffs, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """95% interval on the mean of per-game paired score differences."""
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(draws):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    lo = means[int(0.025 * draws)]
    hi = means[int(0.975 * draws) - 1]
    return lo, hi


def main() -> int:
    gate = subprocess.run(
        [sys.executable, str(ROOT / "official-verify/scripts/check_prereg.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    if gate.returncode:
        print("Refusing to evaluate: the pre-registration gate failed.")
        print(gate.stdout[-2000:])
        return 1

    games = load_games()
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})

    per_week = []
    all_model, all_base, all_flip, all_fav = [], [], [], []
    totals_rows = []

    for week in EVAL_WEEKS:
        fit = [g for g in games if g["week"] < week]
        test = [g for g in games if g["week"] == week]
        if not fit or not test:
            continue
        mu, hfa, attack, defence = design(fit, teams)
        idx = {t: i for i, t in enumerate(teams)}

        home_wins = sum(1 for g in fit if g["hs"] > g["as"])
        decided = sum(1 for g in fit if g["hs"] != g["as"])
        base = home_wins / decided

        # favourites control: better win share among fitting games
        wins = {t: 0 for t in teams}
        played = {t: 0 for t in teams}
        for g in fit:
            played[g["home"]] += 1
            played[g["away"]] += 1
            if g["hs"] > g["as"]:
                wins[g["home"]] += 1
            elif g["as"] > g["hs"]:
                wins[g["away"]] += 1
        rate = {t: (wins[t] / played[t] if played[t] else 0.5) for t in teams}

        m_pairs, b_pairs, f_pairs, v_pairs = [], [], [], []
        for g in test:
            h, a = idx[g["home"]], idx[g["away"]]
            exp_home = mu + hfa / 2 + attack[h] - defence[a]
            exp_away = mu - hfa / 2 + attack[a] - defence[h]
            margin = exp_home - exp_away
            p_home = norm_cdf(margin / SIGMA)
            y = 1.0 if g["hs"] > g["as"] else (0.5 if g["hs"] == g["as"] else 0.0)
            m_pairs.append((p_home, y))
            b_pairs.append((base, y))
            f_pairs.append((0.5, y))
            fav_home = rate[g["home"]] >= rate[g["away"]]
            v_pairs.append((1.0 if fav_home else 0.0, y))
            totals_rows.append(
                {
                    "game_id": g["game_id"],
                    "week": g["week"],
                    "week_label": f"Week {g['week']}",
                    "matchup": f"{g['away']} @ {g['home']}",
                    "model_total": round(exp_home + exp_away, 2),
                    "actual_total": g["hs"] + g["as"],
                    "model_margin_home": round(margin, 2),
                    "actual_margin_home": g["hs"] - g["as"],
                    "model_p_home": round(p_home, 4),
                    "home_won": y,
                    "source_url": g["source_url"],
                }
            )
        all_model += m_pairs
        all_base += b_pairs
        all_flip += f_pairs
        all_fav += v_pairs
        per_week.append(
            {
                "week": week,
                "week_label": f"Week {week}",
                "fit_games": len(fit),
                "test_games": len(test),
                "brier_model": brier(m_pairs),
                "brier_base": brier(b_pairs),
                "brier_flip": brier(f_pairs),
                "brier_fav": brier(v_pairs),
                "base_home_rate": base,
                "mu": round(mu, 3),
                "hfa": round(hfa, 3),
            }
        )

    # --- primary result: model vs home base rate -------------------------
    diffs = [b - m for (m, _), (b, _) in zip(all_model, all_base)]
    mean_diff = sum(diffs) / len(diffs)
    lo, hi = cluster_bootstrap(diffs)
    b_model, b_base = brier(all_model), brier(all_base)
    b_flip, b_fav = brier(all_flip), brier(all_fav)
    skill_base = 1 - b_model / b_base
    skill_flip = 1 - b_model / b_flip
    skill_fav = 1 - b_model / b_fav

    result = {
        "registration": "official-verify/prereg/PREREG-2026-OV1.md",
        "corpus": "official-verify/data/games_2026_official.csv",
        "n_games_scored": len(all_model),
        "n_games_fit_final": per_week[-1]["fit_games"] if per_week else 0,
        "warmup_weeks": list(WARMUP_WEEKS),
        "evaluation_weeks": list(EVAL_WEEKS),
        "sigma": SIGMA,
        "sigma_total": SIGMA_TOTAL,
        "ridge_lambda": LAMBDA,
        "brier": {
            "model": b_model,
            "control_home_base_rate": b_base,
            "control_coin_flip": b_flip,
            "control_favourites": b_fav,
        },
        "log_loss": {
            "model": logloss(all_model),
            "control_home_base_rate": logloss(all_base),
            "control_coin_flip": logloss(all_flip),
            "control_favourites": logloss(all_fav),
        },
        "skill_vs_home_base_rate": skill_base,
        "skill_vs_coin_flip": skill_flip,
        "skill_vs_favourites": skill_fav,
        "mean_paired_improvement_vs_base": mean_diff,
        "cluster_bootstrap_95": [lo, hi],
        "bootstrap": {
            "draws": BOOTSTRAP_DRAWS,
            "seed": BOOTSTRAP_SEED,
            "unit": "game",
        },
        "gate_G_CLUSTER_lower_bound_above_zero": lo > 0,
        "accuracy": {
            "model_straight_up": sum(
                1 for p, y in all_model if (p > 0.5 and y == 1.0) or (p < 0.5 and y == 0.0)
            ) / len(all_model),
        },
        "per_week": per_week,
        "totals": totals_rows,
        "verdict_note": (
            "Skill is benchmark-relative Brier skill on out-of-sample Weeks 4-10. "
            "It is not return on investment: the corpus holds no prices, so no ROI, "
            "closing-line value or vig claim is made or implied."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Scored {result['n_games_scored']} out-of-sample games (Weeks 4-10).")
    print(f"Brier model {b_model:.4f} | home base rate {b_base:.4f} | coin flip {b_flip:.4f} | favourites {b_fav:.4f}")
    print(f"Brier skill vs base rate {skill_base:+.4f} (95% CI on paired improvement "
          f"{lo:+.4f} to {hi:+.4f})")
    print(f"G-CLUSTER lower bound above zero: {result['gate_G_CLUSTER_lower_bound_above_zero']}")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
