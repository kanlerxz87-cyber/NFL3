#!/usr/bin/env python3
"""Luck removal, calibration and correlations, all from official numbers only.

Outputs `official-verify/data/analysis.json`. Every number carries its `n`.

Design notes (why each choice is defensible):

* Luck is not a vibe. A win total is a coin-flip-ish accumulation of
  Bernoulli outcomes, so it has a variance floor even for a perfectly known
  team. We compute the variance of observed wins across the 32 clubs and the
  variance the model's own probabilities imply (sum of p(1-p) per club, averaged
  across clubs). The ratio is the share of club-win dispersion that is luck.
  That is a decomposition with a stated sample size, not a claim.

* Calibration is measured on the same out-of-sample games: predicted home-win
  probability bucketed, with the observed home-win share and n in each bucket.
  A bucket with n < 10 is published but marked as too small to read.

* Correlations are computed only between officially sourced quantities
  (standings points for/against and the official game log). Each value carries
  n, a Fisher-z 95 % interval, and the honest caveat that 32 clubs is a small n
  for a correlation and that these are single-season, in-sample relationships.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "official-verify" / "data"
GAMES = DATA / "games_2026_official.csv"
STANDINGS = DATA / "standings_2026_official.csv"
EVAL = DATA / "evaluation.json"
OUT = DATA / "analysis.json"

MIN_BIN = 10


def load_games():
    with GAMES.open(newline="", encoding="utf-8") as fh:
        return [
            {
                "week": int(r["week"]),
                "home": r["home_team"],
                "away": r["away_team"],
                "hs": int(r["home_score"]),
                "as": int(r["away_score"]),
            }
            for r in csv.DictReader(fh)
            if r["home_score"].strip() and r["away_score"].strip()
        ]


def load_standings():
    with STANDINGS.open(newline="", encoding="utf-8") as fh:
        return [
            {
                "team": r["team"],
                "wins": int(r["wins"]),
                "losses": int(r["losses"]),
                "ties": int(r["ties"]),
                "pf": int(r["points_for"]),
                "pa": int(r["points_against"]),
                "source_url": r["source_url"],
            }
            for r in csv.DictReader(fh)
        ]


def mean(xs):
    return sum(xs) / len(xs)


def variance(xs):
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def pearson(xs, ys):
    n = len(xs)
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r, n, z=1.959964):
    if n <= 3 or abs(r) >= 1:
        return [None, None]
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    lo, hi = math.tanh(zr - z * se), math.tanh(zr + z * se)
    return [round(lo, 4), round(hi, 4)]


def correlation_entry(name, a_label, b_label, xs, ys, use, n_note=""):
    r = pearson(xs, ys)
    return {
        "pair": name,
        "a": a_label,
        "b": b_label,
        "n": len(xs),
        "r": round(r, 4),
        "ci95_fisher": fisher_ci(r, len(xs)),
        "use": use,
        "note": n_note,
    }


def main() -> int:
    games = load_games()
    standings = load_standings()
    ev = json.loads(EVAL.read_text(encoding="utf-8"))

    # ---------------- per-club luck decomposition -------------------------
    p_by_game = {row["game_id"]: row for row in ev["totals"]}
    club = {
        s["team"]: {
            "team": s["team"],
            "games": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "expected_wins": 0.0,
            "p_var": 0.0,
            "model_games": 0,
        }
        for s in standings
    }
    for g in games:
        for team, opp, score, opp_score in (
            (g["home"], g["away"], g["hs"], g["as"]),
            (g["away"], g["home"], g["as"], g["hs"]),
        ):
            c = club[team]
            c["games"] += 1
            if score > opp_score:
                c["wins"] += 1
            elif score < opp_score:
                c["losses"] += 1
            else:
                c["ties"] += 1
    # model-implied expected wins, from out-of-sample predictions only
    by_id = {}
    for g in games:
        gid = f"2026_{g['week']:02d}_{g['away']}_{g['home']}"
        by_id[gid] = g
    for gid, row in p_by_game.items():
        g = by_id.get(gid)
        if g is None:
            continue
        p = row["model_p_home"]
        club[g["home"]]["expected_wins"] += p
        club[g["away"]]["expected_wins"] += 1 - p
        club[g["home"]]["p_var"] += p * (1 - p)
        club[g["away"]]["p_var"] += p * (1 - p)
        club[g["home"]]["model_games"] += 1
        club[g["away"]]["model_games"] += 1

    club_rows = []
    for team in sorted(club):
        c = club[team]
        observed = c["wins"] + 0.5 * c["ties"]
        luck = observed - c["expected_wins"] if c["model_games"] else None
        club_rows.append(
            {
                "team": c["team"],
                "games": c["games"],
                "wins": c["wins"],
                "losses": c["losses"],
                "ties": c["ties"],
                "observed_win_equivalent": observed,
                "model_expected_wins": round(c["expected_wins"], 3),
                "luck_delta": round(luck, 3) if luck is not None else None,
                "model_games_scored": c["model_games"],
                "expected_bernoulli_variance": round(c["p_var"], 4),
            }
        )

    scored = [r for r in club_rows if r["model_games_scored"]]
    observed_var = variance([r["observed_win_equivalent"] for r in scored])
    luck_var = mean([r["expected_bernoulli_variance"] for r in scored])
    luck_share = luck_var / observed_var if observed_var else None

    # ---------------- calibration on out-of-sample games ------------------
    bins = [
        (0.0, 0.4), (0.4, 0.45), (0.45, 0.5), (0.5, 0.55),
        (0.55, 0.6), (0.6, 1.01),
    ]
    cal = []
    for lo, hi in bins:
        members = [
            row for row in ev["totals"] if lo <= row["model_p_home"] < hi
        ]
        if not members:
            continue
        wins = sum(row["home_won"] for row in members)
        cal.append(
            {
                "bin": f"{lo:.2f}-{min(hi, 1.0):.2f}",
                "n": len(members),
                "mean_predicted": round(mean([row["model_p_home"] for row in members]), 4),
                "observed_home_win_share": round(wins / len(members), 4),
                "readable": len(members) >= MIN_BIN,
                "source_url": "official-verify corpus (nfl.com weekly schedule pages)",
            }
        )

    # ---------------- correlations from official numbers ------------------
    corr = []
    pf = [s["pf"] for s in standings]
    pa = [s["pa"] for s in standings]
    net = [s["pf"] - s["pa"] for s in standings]
    wins = [s["wins"] + 0.5 * s["ties"] for s in standings]
    corr.append(
        correlation_entry(
            "points_for vs wins", "official points for", "official wins (ties=0.5)",
            pf, wins, "floor check: scoring and winning are related but not identical",
            "Single season, in-sample. n=32 clubs is small for a correlation.",
        )
    )
    corr.append(
        correlation_entry(
            "net_points vs wins", "official net points", "official wins (ties=0.5)",
            net, wins, "the classic 'points explain wins' relationship",
            "Single season, in-sample. Wins are partly luck, which caps this r.",
        )
    )
    ex = [r["model_expected_wins"] for r in scored]
    ob = [r["observed_win_equivalent"] for r in scored]
    corr.append(
        correlation_entry(
            "model expected wins vs observed wins",
            "model expected wins (out-of-sample)", "observed wins (ties=0.5)",
            ex, ob, "how much of the club win table the model already accounts for",
            "Out-of-sample predictions only; clubs with no scored game are excluded.",
        )
    )
    pf_pg = [s["pf"] / (s["wins"] + s["losses"] + s["ties"]) for s in standings]
    pa_pg = [s["pa"] / (s["wins"] + s["losses"] + s["ties"]) for s in standings]
    corr.append(
        correlation_entry(
            "points scored vs points allowed per game",
            "points for per game", "points against per game",
            pf_pg, pa_pg, "tests the assumption that good offence and good defence are independent",
            "A positive r would mean good offences tend to face bad defences; the sign is reported as found.",
        )
    )

    result = {
        "generated_from": {
            "corpus": "official-verify/data/games_2026_official.csv",
            "standings": "official-verify/data/standings_2026_official.csv",
            "evaluation": "official-verify/data/evaluation.json",
        },
        "luck": {
            "method": (
                "Observed win equivalents (ties counted 0.5) across the 32 official clubs are "
                "compared with the wins the pre-registered model expected out of sample, and "
                "with the Bernoulli variance the model's own probabilities imply. The ratio of "
                "implied Bernoulli variance to observed variance of club win totals is the share "
                "of club-win dispersion that is luck rather than signal."
            ),
            "n_clubs": len(scored),
            "observed_variance_of_wins": round(observed_var, 4),
            "mean_implied_bernoulli_variance": round(luck_var, 4),
            "luck_share_of_win_dispersion": round(luck_share, 4) if luck_share else None,
            "skill_share_of_win_dispersion": round(1 - luck_share, 4) if luck_share else None,
            "clubs": club_rows,
            "caveat": (
                "This is not 'true skill'. It says how much of the spread in club win totals a "
                "coin-flip process could have produced. With one season and 32 clubs the "
                "estimate itself is uncertain, and it is conditional on the registered model."
            ),
        },
        "calibration": {
            "n_games": ev["n_games_scored"],
            "min_readable_bin": MIN_BIN,
            "bins": cal,
            "note": "Buckets with n below the readable threshold are published but marked unreadable.",
        },
        "correlations": corr,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Luck share of club-win dispersion: {luck_share:.3f} (n={len(scored)} clubs)")
    print(f"Calibration bins: {len(cal)}, scored games: {ev['n_games_scored']}")
    for c in corr:
        print(f"  r({c['pair']}) = {c['r']:+.3f}  n={c['n']}  CI {c['ci95_fisher']}")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
