"""Proper-scoring, de-vigging and cluster-bootstrap helpers for the skill lab.

Everything here is dependency-free and deterministic so that a reviewer can re-run the
published numbers from the committed data with no external library.

Definitions implemented here are the ones frozen in ``docs/SKILL_LAB_PRE_REGISTRATION.md``
(registration SL-PRE-01, amended by SL-PRE-01a before any result was computed).
"""
from __future__ import annotations

import math
import random
from typing import Callable, Iterable, Sequence

# ------------------------------------------------------------------ normal distribution


def norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Standard normal quantile (Acklam's rational approximation, |error| < 1.15e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError("norm_ppf requires 0 < p < 1")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ------------------------------------------------------------------ prices and de-vigging


def american_to_decimal(odds: float | None) -> float | None:
    """American odds -> decimal payout per unit staked.  None when the price is missing."""
    if odds is None:
        return None
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o == 0 or o != o:
        return None
    return round(1 + 100 / o, 6) if o < 0 else round(1 + o / 100, 6)


def american_to_prob(odds: float | None) -> float | None:
    """Raw implied probability from American odds (before removing the margin)."""
    if odds is None:
        return None
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o == 0 or o != o:
        return None
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def devig_proportional(p1: float, p2: float) -> tuple[float, float]:
    """Primary de-vig method (registered): scale both implied probabilities to sum to one."""
    total = p1 + p2
    if total <= 0:
        return (float("nan"), float("nan"))
    return (p1 / total, p2 / total)


def devig_shin(p1: float, p2: float) -> tuple[float, float]:
    """Secondary de-vig method (registered): Shin's insider-trading model.

    Solves for the fraction of insider money ``z`` such that the Shin probabilities sum to one.
    Returns ``(nan, nan)`` when no solution exists, so a caller never silently falls back.
    """
    total = p1 + p2
    if total <= 0 or p1 <= 0 or p2 <= 0:
        return (float("nan"), float("nan"))

    def probs(z: float) -> tuple[float, float]:
        denom = 2.0 * (1.0 - z)
        if denom <= 0:
            return (float("nan"), float("nan"))
        out = []
        for pi in (p1, p2):
            rad = z * z + 4.0 * (1.0 - z) * pi * pi / total
            if rad < 0:
                return (float("nan"), float("nan"))
            out.append((math.sqrt(rad) - z) / denom)
        return (out[0], out[1])

    lo, hi = 0.0, 0.999
    for _ in range(200):
        mid = (lo + hi) / 2.0
        a, b = probs(mid)
        if a != a or b != b:
            return (float("nan"), float("nan"))
        if a + b > 1.0:
            lo = mid
        else:
            hi = mid
    a, b = probs((lo + hi) / 2.0)
    if a != a or b != b or abs((a + b) - 1.0) > 1e-6:
        return (float("nan"), float("nan"))
    return (a, b)


# ------------------------------------------------------------------ proper scores


def brier(p: float, y: float) -> float:
    """Brier score (mean squared error of a binary probability). Lower is better."""
    return (p - y) ** 2


def log_loss(p: float, y: float, clip: float = 1e-4) -> float:
    """Negative log likelihood with a fixed clip so a never-zero probability stays finite."""
    q = min(max(p, clip), 1.0 - clip)
    return -(y * math.log(q) + (1.0 - y) * math.log(1.0 - q))


def skill(model_score: float, reference_score: float) -> float:
    """Relative skill: 1 - model/reference.  Positive means the model scored better."""
    if reference_score <= 0 or reference_score != reference_score:
        return float("nan")
    return 1.0 - model_score / reference_score


def mean(xs: Sequence[float]) -> float:
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else float("nan")


def calibration_error(pairs: Sequence[tuple[float, float]], bins: int = 5) -> tuple[float, list[dict]]:
    """Expected calibration error over equal-width probability bins.

    ``pairs`` are (probability, outcome) observations.  Returns (ECE, per-bin detail).
    """
    if not pairs:
        return (float("nan"), [])
    detail: list[dict] = []
    ece = 0.0
    n = len(pairs)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if (lo <= p < hi or (b == bins - 1 and p == 1.0))]
        if not sel:
            detail.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": 0, "mean_predicted": None,
                           "observed_rate": None, "gap": None})
            continue
        mp = mean([p for p, _ in sel])
        obs = mean([y for _, y in sel])
        gap = abs(mp - obs)
        ece += (len(sel) / n) * gap
        detail.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": len(sel), "mean_predicted": mp,
                       "observed_rate": obs, "gap": gap})
    return (ece, detail)


# ------------------------------------------------------------------ cluster bootstrap


def cluster_bootstrap(per_game: Sequence[tuple[str, Sequence[float]]], stat: Callable[[list[float]], float],
                      n_boot: int = 10000, seed: int = 20260101, alpha: float = 0.05
                      ) -> dict:
    """Resample **games** with replacement; keep every value attached to a drawn game.

    ``per_game`` is a list of ``(game_id, values)``.  ``stat`` receives the flattened values of
    the resampled games and returns the statistic of interest.

    Returns the point estimate, the percentile interval, the one-sided bootstrap p-value for
    "statistic <= 0" and the number of resamples.
    """
    if not per_game:
        return {"point": float("nan"), "ci95": [None, None], "lower95": None,
                "p_one_sided": None, "n_boot": 0, "n_games": 0}
    rnd = random.Random(seed)
    n_games = len(per_game)
    point = stat([v for _, vals in per_game for v in vals])
    draws: list[float] = []
    for _ in range(n_boot):
        vals: list[float] = []
        for _ in range(n_games):
            vals.extend(per_game[rnd.randrange(n_games)][1])
        draws.append(stat(vals))
    draws.sort()
    lo_idx = int(math.floor((alpha / 2) * (len(draws) - 1)))
    hi_idx = int(math.ceil((1 - alpha / 2) * (len(draws) - 1)))
    lo = draws[lo_idx]
    hi = draws[hi_idx]
    non_pos = sum(1 for d in draws if d <= 0.0)
    p_one = non_pos / len(draws)
    return {"point": point, "ci95": [lo, hi], "lower95": lo, "upper95": hi,
            "p_one_sided": p_one, "n_boot": n_boot, "n_games": n_games}


def benjamini_hochberg(pvalues: dict[str, float], q: float = 0.05) -> dict[str, dict]:
    """Benjamini-Hochberg step-up control.  Returns per-key p, adjusted q-value and pass flag."""
    items = [(k, v) for k, v in pvalues.items() if v == v]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, dict] = {}
    prev = 1.0
    for i in range(m - 1, -1, -1):
        key, p = items[i]
        adj = min(prev, p * m / (i + 1))
        prev = adj
        out[key] = {"p": p, "q": adj, "pass": adj <= q, "rank": i + 1}
    for key in pvalues:
        if key not in out:
            out[key] = {"p": None, "q": None, "pass": False, "rank": None}
    return out


def percentile(values: Sequence[float], q: float) -> float:
    vals = sorted(v for v in values if v == v)
    if not vals:
        return float("nan")
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return vals[int(pos)]
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)
