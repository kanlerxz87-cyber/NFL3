#!/usr/bin/env python3
"""The removal-of-luck panel.

A win rate is a sample statistic with an enormous standard error at NFL season sizes. This module
decomposes what a leaderboard can and cannot see, and separates three different things that are
routinely confused:

    signal        the rule was right more often than chance on the same rows, by a proper score
    staking       the money that happened to be on the winning side
    luck          the part of the realised result that a coin-flip model with the same exposure
                  would have produced with reasonable probability

Everything is computed from the same reconciled results feed and printed with its sample size. Nothing
here asserts that a strategy is profitable; it asserts what the evidence *can* distinguish.
"""
from __future__ import annotations

import math

import common as C
import scoring


def required_n(true_edge: float, p0: float = 0.5, alpha: float = 0.05, power: float = 0.80) -> int:
    """Graded bets needed for a one-sided win/loss test to detect `true_edge` above p0.

    Standard normal approximation:
        n = ( z_alpha * sqrt(p0(1-p0)) + z_power * sqrt(p1(1-p1)) )^2 / (p1 - p0)^2
    with p1 = p0 + true_edge. This is the number that makes 'a hot streak' obviously insufficient.
    """
    if true_edge <= 0:
        return 0
    p1 = p0 + true_edge
    z_a = {0.05: 1.6449, 0.01: 2.3263}.get(alpha, 1.6449)
    z_b = {0.80: 0.8416, 0.90: 1.2816}.get(power, 0.8416)
    return math.ceil(((z_a * math.sqrt(p0 * (1 - p0)) + z_b * math.sqrt(p1 * (1 - p1))) ** 2)
                     / (true_edge ** 2))


def luck_panel(leaderboard: dict, results: dict) -> dict:
    played = results["counts"]["games_played"]
    panel = {
        "built_at": C.GENERATED_AT,
        "corpus": {
            "games_played": played,
            "weeks": results["counts"]["weeks_covered"],
            "reconciliation": (f"{results['counts']['team_fields_matching']}/"
                               f"{results['counts']['team_fields_checked']} club x field checks match "
                               f"official standings"),
            "settlement": results["settlement_authority"],
            "source_url": results["official_standings"]["url"],
        },
        "sample_size_table": [],
        "separations": [],
        "fluke_probability": [],
        "panel_statement": (
            "Sample size first, score second, money never. With 137 played games in the corpus, a "
            "11-9 record and a 19-1 record are both ordinary outcomes for a coin. Only a proper score "
            "with an interval can tell them apart — and at this n, even that cannot resolve an edge "
            "smaller than the intervals below."
        ),
    }
    for edge in (0.02, 0.05, 0.10):
        panel["sample_size_table"].append({
            "edge": edge, "win_probability": 0.5 + edge,
            "n_required_80pct": required_n(edge),
            "n_required_90pct": required_n(edge, power=0.90),
            "n_available_now": played,
            "still_needed": max(0, required_n(edge) - played),
        })

    for res in leaderboard["results"]:
        s = res["summary"]
        if not s.get("n"):
            continue
        n = s["n"]
        wins = round(s["accuracy"] * n)
        lo, hi = s.get("wilson", (None, None))
        panel["separations"].append({
            "id": res["id"], "name": res["name"], "family": res["family"], "n": n, "wins": wins,
            "win_rate": s["accuracy"], "wilson_lo": lo, "wilson_hi": hi,
            "bss": s.get("bss"), "bss_lo": s.get("lo"), "bss_hi": s.get("hi"),
            "calibration_gap": s.get("calibration_gap"),
            "verdict": _verdict(s),
        })
        # How often would a fair coin, flipped n times, produce at least this many wins?
        panel["fluke_probability"].append({
            "id": res["id"], "n": n, "wins": wins,
            "p_at_least_this_many_by_chance": _binomial_tail(n, wins),
            "note": "two-sided-agnostic one-tailed tail probability under p=0.5",
        })
    return panel


def _verdict(summary: dict) -> str:
    lo, hi = summary.get("lo"), summary.get("hi")
    bss = summary.get("bss")
    if bss is None or lo is None:
        return "insufficient rows"
    if lo > 0:
        return "skill signal: interval above zero"
    if hi < 0:
        return "worse than benchmark: interval below zero"
    return "no distinguishable signal: interval includes zero"


def _binomial_tail(n: int, k: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5), computed exactly in log space."""
    if n <= 0:
        return 1.0
    total = 0.0
    log_half = n * math.log(0.5)
    for i in range(k, n + 1):
        log_c = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        total += math.exp(log_c + log_half)
    return min(1.0, total)


def main() -> int:
    leaderboard = C.read_json(C.DATA / "leaderboard.json")
    results = C.read_json(C.DATA / "results.json")
    panel = luck_panel(leaderboard, results)
    C.write_json("luck.json", panel)
    print(f"Luck panel: {panel['corpus']['games_played']} played games; "
          f"{len(panel['separations'])} strategies separated.")
    for row in panel["sample_size_table"]:
        print(f"  edge {row['edge']:.0%}: n={row['n_required_80pct']} needed at 80% power "
              f"({row['still_needed']} more than today)")
    for row in panel["separations"]:
        print(f"  {row['id']} n={row['n']:4} winrate={row['win_rate']:.3f} "
              f"[{row['wilson_lo']:.3f},{row['wilson_hi']:.3f}] bss={C.r(row['bss'])} → {row['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
