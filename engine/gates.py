"""Validation gates.  A strategy is only ever described as `passing` when every gate is met.

The gates are fixed before results are inspected (see docs/PRE_REGISTRATION.md).  They are
purposefully strict: the default outcome for a strategy on this site is **failing**, and the page
shows exactly which gate stopped it.

Gate definitions
----------------
G1  Data integrity         every input file matches the SHA-256 digest published with its release; sample size
                           >= MIN_BETS graded bets in the out-of-sample window.
G2  Beats the vig          mean profit per unit > 0 after the market's price, with a 95%
                           block-bootstrap CI whose lower bound is > 0.
G3  Multiple-testing       the strategy survives Benjamini-Hochberg control across every strategy
                           tested in the same family (q = 0.05).
G4  Selection / luck       the strategy's z-score exceeds the deflated-Sharpe threshold for the
                           number of attempts (Bailey & Lopez de Prado) and White's reality check
                           p < 0.05 against the best-of-family null.
G5  Stability              positive in at least 60% of seasons AND in both halves of the
                           out-of-sample period (no single hot streak).
G6  Skill, not luck        closing-line value > 0 (beating the closing number is the least
                           luck-dependent signal) with a 95% CI lower bound > 0.
G7  Cost realism           result survives a 10% worse average price (slippage stress).
"""
from __future__ import annotations

import math

import stats

MIN_BETS = 100
BH_Q = 0.05
BOOT = 2000
SEED = 20260101


def bootstrap_pvalue(xs: list[float], n_boot: int = BOOT, seed: int = SEED) -> float:
    """One-sided bootstrap p-value for H0: mean <= 0."""
    if len(xs) < 10:
        return float("nan")
    lo, hi = stats.block_bootstrap_mean_ci(xs, block=20, n_boot=n_boot, seed=seed)
    # probability mass of the bootstrap distribution at or below zero
    import random
    rnd = random.Random(seed)
    n = len(xs)
    block = 20
    n_blocks = math.ceil(n / block)
    hits = 0
    for _ in range(n_boot):
        vals: list[float] = []
        for _ in range(n_blocks):
            s = rnd.randrange(n - block + 1)
            vals.extend(xs[s:s + block])
        if stats.mean(vals[:n]) <= 0:
            hits += 1
    return hits / n_boot


def evaluate(name: str, family: str, bets: list[dict], pvals_family: dict[str, float] | None = None,
             n_attempts: int = 1) -> dict:
    """Evaluate one strategy's graded bets against G1-G7.

    `bets` rows need: profit (per unit, at the market price), clv (closing-line value per unit),
    season, half ('H1'/'H2'), p_win (model probability) and won (0/1).
    """
    pnl = [b["profit"] for b in bets]
    n = len(pnl)
    out = {"strategy": name, "family": family, "n_bets": n, "gates": {}, "metrics": {}}
    if n == 0:
        out["status"] = "no data"
        return out

    m = stats.mean(pnl)
    se = stats.stdev(pnl) / math.sqrt(n) if n > 1 else float("nan")
    z = m / se if se and se == se and se > 0 else float("nan")
    ci = stats.block_bootstrap_mean_ci(pnl, block=20, n_boot=BOOT, seed=SEED)
    out["metrics"]["profit_per_unit"] = m
    out["metrics"]["se"] = se
    out["metrics"]["z"] = z
    out["metrics"]["ci95"] = ci
    out["metrics"]["p_one_sided"] = (1 - stats.norm_cdf(z)) if z == z else float("nan")
    out["metrics"]["hit_rate"] = sum(b["won"] for b in bets) / n
    out["metrics"]["hit_ci95"] = stats.wilson_interval(sum(b["won"] for b in bets), n)

    # G1 sample size
    out["gates"]["G1_sample"] = n >= MIN_BETS

    # G2 profitable with CI above zero
    out["gates"]["G2_profit"] = bool(m > 0 and ci[0] > 0)

    # G3 multiple testing across the family
    if pvals_family is not None:
        names = list(pvals_family)
        adj = stats.benjamini_hochberg([pvals_family[k] for k in names], alpha=BH_Q)
        idx = names.index(name) if name in names else None
        out["gates"]["G3_multiple_testing"] = bool(idx is not None and adj[idx][1])
        out["metrics"]["bh_adjusted_p"] = adj[idx][0] if idx is not None else float("nan")
    else:
        out["gates"]["G3_multiple_testing"] = False

    # G4 selection-adjusted significance
    thr = stats.deflated_threshold(n, max(1, n_attempts), skew=stats.skewness(pnl),
                                   kurt=stats.kurtosis_excess(pnl) + 3.0)
    out["metrics"]["deflated_threshold_z"] = thr
    out["gates"]["G4_selection"] = bool(z == z and z > thr and z > 2.0)

    # G5 stability
    seasons = sorted({b["season"] for b in bets})
    per_season = {s: stats.mean([b["profit"] for b in bets if b["season"] == s]) for s in seasons}
    pos_seasons = sum(1 for v in per_season.values() if v > 0)
    halves = {h: stats.mean([b["profit"] for b in bets if b["half"] == h]) for h in ("H1", "H2")}
    out["metrics"]["per_season_profit"] = per_season
    out["metrics"]["positive_season_share"] = pos_seasons / len(seasons) if seasons else float("nan")
    out["metrics"]["half_profit"] = halves
    out["gates"]["G5_stability"] = bool(seasons and pos_seasons / len(seasons) >= 0.6
                                        and halves["H1"] > 0 and halves["H2"] > 0)

    # G6 closing-line value
    clv = [b["clv"] for b in bets if b.get("clv") is not None and b["clv"] == b["clv"]]
    if clv:
        cm = stats.mean(clv)
        cse = stats.stdev(clv) / math.sqrt(len(clv)) if len(clv) > 1 else float("nan")
        cz = cm / cse if cse and cse == cse and cse > 0 else float("nan")
        cci = stats.block_bootstrap_mean_ci(clv, block=20, n_boot=BOOT, seed=SEED)
        out["metrics"]["clv_per_unit"] = cm
        out["metrics"]["clv_ci95"] = cci
        out["gates"]["G6_clv"] = bool(cm > 0 and cci[0] > 0)
    else:
        out["metrics"]["clv_per_unit"] = float("nan")
        out["gates"]["G6_clv"] = False

    # G7 slippage stress: 10% worse price on every winner (cost realism)
    stressed = [b["profit"] - 0.1 * max(0.0, b["profit"]) if b["profit"] > 0 else b["profit"]
                for b in bets]
    sm = stats.mean(stressed)
    out["metrics"]["stress10_profit_per_unit"] = sm
    out["gates"]["G7_stress"] = bool(sm > 0)

    out["gates_passed"] = sum(1 for v in out["gates"].values() if v)
    out["gates_total"] = len(out["gates"])
    out["status"] = "passes all gates" if out["gates_passed"] == out["gates_total"] else "fails"
    return out
