"""Scoring and uncertainty for the Shadow Board. PREREGISTRATION.md §7 fixes which of these may be used.

Every function is deterministic: the bootstrap and the simulation take a fixed seed (20261115) and a fixed
number of draws, so a page rebuilt from the same data prints the same interval. Proper scoring rules only -
a score a strategy can improve by being vague is not used anywhere in this workspace.
"""
from __future__ import annotations

import math
import random

SEED = 20261115
BOOT_DRAWS = 5000
LUCK_DRAWS = 20000
ALPHA = 0.05
BH_Q = 0.10


# ------------------------------------------------------------------ scoring rules
def brier(p: float, y: float) -> float:
    return (p - y) ** 2


def log_score(p: float, y: float, eps: float = 1e-6) -> float:
    p = min(max(p, eps), 1.0 - eps)
    return -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def stdev(xs) -> float:
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a hit rate: correct coverage near 0 and 1, unlike a normal approximation."""
    if n == 0:
        return (float("nan"), float("nan"))
    ph = hits / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    hw = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return ((c - hw) / d, (c + hw) / d)


# ------------------------------------------------------------------ uncertainty
def cluster_bootstrap(values: list[float], draws: int = BOOT_DRAWS, seed: int = SEED):
    """Resample whole games (clusters), not bets. Returns (point, lo, hi, p_value_of_beating_zero).

    ``values`` are the per-game contributions to the statistic of interest; a positive mean means skill.
    The p-value is the share of resamples at or below zero (one-sided, H0: mean <= 0).
    """
    n = len(values)
    if n < 2:
        return (mean(values), float("nan"), float("nan"), float("nan"))
    rnd = random.Random(seed)
    stats = []
    for _ in range(draws):
        sample = [values[rnd.randrange(n)] for _ in range(n)]
        stats.append(mean(sample))
    stats.sort()
    lo = stats[int(math.floor((ALPHA / 2) * draws))]
    hi = stats[int(math.floor((1 - ALPHA / 2) * draws)) - 1]
    below = sum(1 for s in stats if s <= 0)
    return (mean(values), lo, hi, (below + 1) / (draws + 1))


def cluster_bootstrap_ratio(model_vals: list[float], bench_vals: list[float],
                            draws: int = BOOT_DRAWS, seed: int = SEED) -> dict:
    """Bootstrap a *ratio* statistic - use it when the reported quantity is 1 - model/benchmark.

    Resamples whole games (both vectors share the index), so the interval and the p-value describe exactly the
    number printed on the page. Returns {"point","lo","hi","p","sd","n"}.
    """
    n = len(model_vals)
    if n < 2 or len(bench_vals) != n:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan"), "p": float("nan"),
                "sd": float("nan"), "n": n}
    rnd = random.Random(seed)
    stats = []
    for _ in range(draws):
        idx = [rnd.randrange(n) for _ in range(n)]
        m = sum(model_vals[i] for i in idx) / n
        b = sum(bench_vals[i] for i in idx) / n
        stats.append(1.0 - m / b if b > 0 else float("nan"))
    stats = [x for x in stats if x == x]
    if not stats:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan"), "p": float("nan"),
                "sd": float("nan"), "n": n}
    stats.sort()
    point = 1.0 - mean(model_vals) / mean(bench_vals) if mean(bench_vals) > 0 else float("nan")
    return {"point": point,
            "lo": stats[int(math.floor((ALPHA / 2) * len(stats)))],
            "hi": stats[min(len(stats) - 1, int(math.floor((1 - ALPHA / 2) * len(stats))))],
            "p": (sum(1 for x in stats if x <= 0) + 1) / (len(stats) + 1),
            "sd": stdev(stats), "n": n}


def games_for_positive_bound(point: float, sd: float, n: int) -> float:
    """Games needed before the 2.5 % bound of this statistic clears zero, at the observed dispersion.

    From sd(mean) = sd * sqrt(n/N): the bound is positive once N > n * (1.96 sd / point) squared. An
    approximation for planning, not a promise of significance.
    """
    if not (point > 0) or not (sd > 0) or n < 2:
        return float("inf")
    return math.ceil(n * (1.96 * sd / point) ** 2)


def benjamini_hochberg(pvals: dict, q: float = BH_Q) -> dict:
    """Return {key: pass} after Benjamini-Hochberg control across the declared family."""
    items = sorted(((p, k) for k, p in pvals.items() if p == p))
    m = len(items)
    out = {k: False for k in pvals}
    max_rank = 0
    for rank, (p, key) in enumerate(items, start=1):
        if p <= q * rank / m:
            max_rank = rank
    for rank, (p, key) in enumerate(items, start=1):
        out[key] = rank <= max_rank
    return out


# ------------------------------------------------------------------ association
def pearson(xs, ys) -> float:
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def fisher_ci(r: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Fisher-z interval for a Pearson correlation; undefined, and reported as such, when n is too small."""
    if not (-1 < r < 1) or n < 4:
        return (float("nan"), float("nan"))
    zeta = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    return (math.tanh(zeta - z * se), math.tanh(zeta + z * se))


def phi(a: list[int], b: list[int]) -> float:
    """Correlation between two same-game binary events - the quantity a parlay needs before anyone multiplies."""
    n = len(a)
    if n < 3:
        return float("nan")
    p10 = sum(1 for x, y in zip(a, b) if x and not y)
    p01 = sum(1 for x, y in zip(a, b) if y and not x)
    p11 = sum(1 for x, y in zip(a, b) if x and y)
    p00 = n - p10 - p01 - p11
    num = p11 * p00 - p10 * p01
    den = math.sqrt((p11 + p10) * (p01 + p00) * (p11 + p01) * (p10 + p00))
    return float("nan") if den <= 0 else num / den


# ------------------------------------------------------------------ luck
def simulate_record(p_homes: list[float], outcomes: list[float], draws: int = LUCK_DRAWS, seed: int = SEED) -> dict:
    """How much of an observed record is the model and how much is the coin flip.

    Draws the same number of games from the model's own probabilities and compares the resulting
    hit counts and Brier scores with the observed ones. Reported as percentiles, not as a verdict.
    """
    n = len(p_homes)
    if n == 0:
        return {}
    rnd = random.Random(seed)
    hit_draws, brier_draws = [], []
    for _ in range(draws):
        hits = 0
        bs = 0.0
        for p in p_homes:
            y = 1.0 if rnd.random() < p else 0.0
            hits += 1 if (y >= 0.5) == (p >= 0.5) else 0
            bs += (p - y) ** 2
        hit_draws.append(hits)
        brier_draws.append(bs / n)
    hit_draws.sort(); brier_draws.sort()
    obs_hits = sum(1 for p, y in zip(p_homes, outcomes) if (y >= 0.5) == (p >= 0.5))
    obs_brier = mean([(p - y) ** 2 for p, y in zip(p_homes, outcomes)])
    pct_hits = sum(1 for h in hit_draws if h <= obs_hits) / draws
    pct_brier = sum(1 for b in brier_draws if b >= obs_brier) / draws
    return {
        "n": n,
        "observed_hits": obs_hits,
        "expected_hits_mean": mean(hit_draws),
        "expected_hits_sd": stdev(hit_draws),
        "hits_percentile": pct_hits,
        "observed_brier": obs_brier,
        "simulated_brier_mean": mean(brier_draws),
        "simulated_brier_p025": brier_draws[int(math.floor(0.025 * draws))],
        "simulated_brier_p975": brier_draws[int(math.floor(0.975 * draws)) - 1],
        "brier_percentile": pct_brier,
        "draws": draws,
    }


def required_n(effect: float, sd: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Games needed for a one-sided test of mean skill > 0 at the observed dispersion (normal approximation)."""
    if not (effect > 0) or not (sd > 0):
        return float("inf")
    za, zb = 1.645, 0.842            # one-sided 95 % and 80 % power
    return math.ceil((za + zb) ** 2 * sd * sd / (effect * effect))


def calibration(pairs, bins: int = 5) -> list[dict]:
    """Bin forecast probabilities and compare with the observed rate. Small n per bin is printed, not hidden."""
    buckets = [[] for _ in range(bins)]
    for p, y in pairs:
        buckets[min(bins - 1, int(p * bins))].append((p, y))
    out = []
    for i, b in enumerate(buckets):
        lo, hi = i / bins, (i + 1) / bins
        out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(b),
                    "mean_p": mean([p for p, _ in b]) if b else float("nan"),
                    "observed": mean([y for _, y in b]) if b else float("nan")})
    return out
