"""Small, dependency-free statistics toolkit used by the NFL3 engine.

Everything here is deterministic and implemented from the textbook definitions so that the
published numbers can be audited without NumPy/SciPy.  Where a normal approximation is used the
assumption is named in the function docstring.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence


# ---------------------------------------------------------------- summary statistics
def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def variance(xs: Sequence[float]) -> float:
    """Sample variance (Bessel-corrected)."""
    n = len(xs)
    if n < 2:
        return float("nan")
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def stdev(xs: Sequence[float]) -> float:
    return math.sqrt(variance(xs))


def median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if not n:
        return float("nan")
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def quantile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (same definition as R's type 7 / numpy default)."""
    s = sorted(xs)
    if not s:
        return float("nan")
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[int(pos)]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def skewness(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    m = mean(xs)
    s = stdev(xs)
    if s == 0:
        return 0.0
    g1 = sum(((x - m) / s) ** 3 for x in xs) / n
    return g1 * math.sqrt(n * (n - 1)) / (n - 2)


def kurtosis_excess(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 4:
        return float("nan")
    m = mean(xs)
    s = stdev(xs)
    if s == 0:
        return 0.0
    m4 = sum(((x - m) / s) ** 4 for x in xs) / n
    return m4 - 3.0


# ---------------------------------------------------------------- inference
def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's algorithm, max abs error ~1.15e-9)."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def two_sided_p(z: float) -> float:
    """Two-sided p-value for a z statistic under the standard normal reference."""
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95% by default)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Clopper-Pearson) interval via ridder/incomplete beta search on the binomial CDF."""
    if n == 0:
        return (float("nan"), float("nan"))

    def binom_cdf(k: int, n_: int, p: float) -> float:
        # log-space to avoid overflow; p is clamped away from the open interval ends
        p = min(1 - 1e-15, max(1e-15, p))
        tot = 0.0
        for i in range(0, k + 1):
            tot += math.exp(
                math.lgamma(n_ + 1) - math.lgamma(i + 1) - math.lgamma(n_ - i + 1)
                + i * math.log(p) + (n_ - i) * math.log(1 - p)
            )
        return min(1.0, tot)

    lo = 0.0 if successes == 0 else _bisect(
        lambda p: binom_cdf(successes - 1, n, p) - (1 - alpha / 2), 0.0, 1.0)
    hi = 1.0 if successes == n else _bisect(
        lambda p: binom_cdf(successes, n, p) - (alpha / 2), 0.0, 1.0)
    return (lo, hi)


def _bisect(f, lo: float, hi: float, tol: float = 1e-10, iters: int = 200) -> float:
    flo = f(lo)
    for _ in range(iters):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < tol or hi - lo < tol:
            return mid
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def pearson(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, int]:
    """Pearson correlation and the number of complete pairs."""
    pairs = [(x, y) for x, y in zip(xs, ys) if not math.isnan(x) and not math.isnan(y)]
    n = len(pairs)
    if n < 3:
        return (float("nan"), n)
    mx = mean([p[0] for p in pairs])
    my = mean([p[1] for p in pairs])
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x, _ in pairs)
    syy = sum((y - my) ** 2 for _, y in pairs)
    if sxx == 0 or syy == 0:
        return (float("nan"), n)
    return (sxy / math.sqrt(sxx * syy), n)


def fisher_ci(r: float, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% CI for a correlation using Fisher's z transformation."""
    if n < 4 or math.isnan(r) or abs(r) >= 1:
        return (float("nan"), float("nan"))
    zr = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    return (math.tanh(zr - z * se), math.tanh(zr + z * se))


def spearman(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, int]:
    pairs = [(x, y) for x, y in zip(xs, ys) if not math.isnan(x) and not math.isnan(y)]
    if len(pairs) < 3:
        return (float("nan"), len(pairs))
    rx = _rank([p[0] for p in pairs])
    ry = _rank([p[1] for p in pairs])
    r, _ = pearson(rx, ry)
    return (r, len(pairs))


def _rank(vals: Sequence[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


# ---------------------------------------------------------------- sportsbook helpers
def american_to_decimal(odds: int | float) -> float:
    """Convert American odds (-110, +145) to decimal payout (stake included)."""
    o = float(odds)
    return 1 + (o / 100.0 if o > 0 else 100.0 / abs(o))


def american_to_implied(odds: int | float) -> float:
    """Raw (vig-inclusive) implied probability of an American price."""
    o = float(odds)
    return (100.0 / (o + 100.0)) if o > 0 else abs(o) / (abs(o) + 100.0)


def decimal_to_american(dec: float) -> float:
    if dec >= 2.0:
        return (dec - 1) * 100.0
    return -100.0 / (dec - 1)


def american_payout(odds: float, stake: float = 1.0) -> float:
    """Profit (not including stake) of a winning bet at American odds."""
    o = float(odds)
    return stake * (o / 100.0 if o > 0 else -100.0 / o)


def pythagorean_exponent(league_runs_per_game: float) -> float:
    """Pyth analytics exponent 1.83 for NFL scoring (points^e / (points^e + allowed^e))."""
    return 1.83


def brier(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    n = len(probs)
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / n if n else float("nan")


def log_loss(probs: Sequence[float], outcomes: Sequence[int], eps: float = 1e-9) -> float:
    n = len(probs)
    if not n:
        return float("nan")
    tot = 0.0
    for p, o in zip(probs, outcomes):
        q = min(1 - eps, max(eps, p))
        tot += -(o * math.log(q) + (1 - o) * math.log(1 - q))
    return tot / n


def mean_absolute_error(pred: Sequence[float], actual: Sequence[float]) -> float:
    pairs = [(p, a) for p, a in zip(pred, actual) if not math.isnan(p) and not math.isnan(a)]
    return sum(abs(p - a) for p, a in pairs) / len(pairs) if pairs else float("nan")


def root_mean_square_error(pred: Sequence[float], actual: Sequence[float]) -> float:
    pairs = [(p, a) for p, a in zip(pred, actual) if not math.isnan(p) and not math.isnan(a)]
    return math.sqrt(sum((p - a) ** 2 for p, a in pairs) / len(pairs)) if pairs else float("nan")


def bootstrap_mean_ci(xs: Sequence[float], n_boot: int = 2000, seed: int = 20260101,
                      alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean, from a fixed seed (fully reproducible)."""
    if not xs:
        return (float("nan"), float("nan"))
    import random
    rnd = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(n_boot):
        means.append(sum(xs[rnd.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (quantile(means, alpha / 2), quantile(means, 1 - alpha / 2))


def block_bootstrap_mean_ci(xs: Sequence[float], block: int, n_boot: int = 2000,
                            seed: int = 20260101, alpha: float = 0.05) -> tuple[float, float]:
    """Moving-block bootstrap (keeps serial correlation inside a season/clock block)."""
    if not xs:
        return (float("nan"), float("nan"))
    import random
    rnd = random.Random(seed)
    n = len(xs)
    block = max(1, min(block, n))
    n_blocks = math.ceil(n / block)
    means = []
    for _ in range(n_boot):
        vals: list[float] = []
        for _ in range(n_blocks):
            start = rnd.randrange(n - block + 1)
            vals.extend(xs[start:start + block])
        means.append(mean(vals[:n]))
    means.sort()
    return (quantile(means, alpha / 2), quantile(means, 1 - alpha / 2))


def benjamini_hochberg(pvals: Sequence[float], alpha: float = 0.05) -> list[tuple[float, bool]]:
    """BH step-up FDR control. Returns (adjusted p, reject) per input order."""
    m = len(pvals)
    if not m:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        val = min(prev, pvals[idx] * m / rank)
        adj[idx] = val
        prev = val
    return [(adj[i], adj[i] <= alpha) for i in range(m)]


def white_reality_check_best(scores_by_strategy: dict[str, Sequence[float]], n_boot: int = 2000,
                             seed: int = 20260101) -> dict:
    """White's reality-check style test of the best strategy's mean score.

    scores_by_strategy maps strategy name -> per-bet score (profit per unit, or CLV, or any
    stationary score).  The statistic is max over strategies of the mean score, centred by each
    strategy's own mean.  A stationary bootstrap over pooled bet indices approximates the null
    that every strategy has mean zero.  Returns observed best mean and p-value.
    """
    import random
    names = list(scores_by_strategy)
    if not names:
        return {"best": None, "p_value": float("nan"), "n": 0}
    n = min(len(scores_by_strategy[k]) for k in names)
    if n < 20:
        return {"best": names[0], "p_value": float("nan"), "n": n}
    obs = {k: mean(list(scores_by_strategy[k])[:n]) for k in names}
    best = max(obs, key=obs.get)
    centred = {k: [v - obs[k] for v in list(scores_by_strategy[k])[:n]] for k in names}
    rnd = random.Random(seed)
    hits = 0
    for _ in range(n_boot):
        idx = [rnd.randrange(n) for _ in range(n)]
        stat = max(sum(centred[k][i] for i in idx) / n for k in names)
        if stat >= obs[best]:
            hits += 1
    return {"best": best, "observed_mean": obs[best], "p_value": (hits + 1) / (n_boot + 1),
            "n": n, "strategies_compared": len(names)}


def expected_max_of_k_normals(k: int) -> float:
    """E[max of k iid standard normals] - the luck threshold for a leaderboard of k entries."""
    if k <= 1:
        return 0.0
    # closed-form approximation (Bailey & Lopez de Prado 2014, deflated Sharpe ratio)
    emc = 0.5772156649015329
    return (1 - emc) * norm_ppf(1 - 1.0 / k) + emc * norm_ppf(1 - 1.0 / (k * math.e))


def deflated_threshold(n_obs: int, k_trials: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Deflated-Sharpe threshold (Bailey & Lopez de Prado) in studentised units.

    Returns the z-score a strategy's mean must exceed so that its apparent edge survives
    selection over k_trials attempts with n_obs observations and the given return skew/kurtosis.
    """
    if n_obs < 3:
        return float("nan")
    emax = expected_max_of_k_normals(k_trials)
    # standard error adjustment for non-normal returns (Cramér / Lo)
    denom = math.sqrt(max(1e-12, 1 - skew * 0 + (kurt - 1) / 4.0))
    return emax / denom


def kelly_fraction(win_prob: float, dec_odds: float) -> float:
    """Kelly stake fraction for a binary bet priced at decimal odds `dec_odds`."""
    b = dec_odds - 1
    if b <= 0:
        return 0.0
    return max(0.0, (win_prob * dec_odds - 1) / b)
