#!/usr/bin/env python3
"""
parlay_math.py — the arithmetic behind the validation gates, parlays and props.

Everything produced here is MATHEMATICS, not empirical results. The inputs are
declared parameters (a break-even price, a target edge, a correlation
coefficient), never observed data. That distinction is stated in the output
metadata and repeated on the site, because a formula dressed up as a result is
exactly how betting projects lie to themselves.

Output: data/strategy_math.json
"""

import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
EULER = 0.5772156649015329


# ---------------------------------------------------------------- distributions
def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p):
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
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


def biv_norm_cdf(h, k, rho, n=400):
    """P(X<=h, Y<=k) for standard bivariate normal with correlation rho.

    Drezner-Wesolowsky style single integral, Simpson rule on [-6h..h].
    """
    if abs(rho) < 1e-12:
        return phi(h) * phi(k)
    if abs(rho) >= 1.0:
        return min(phi(h), phi(k))
    # integrate over x: f(x) * Phi((k - rho x)/sqrt(1-rho^2))
    lo, hi = -8.0, h
    steps = n if n % 2 == 0 else n + 1
    dx = (hi - lo) / steps
    total = 0.0
    for i in range(steps + 1):
        x = lo + i * dx
        w = 1 if i in (0, steps) else (4 if i % 2 == 1 else 2)
        fx = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
        term = fx * phi((k - rho * x) / math.sqrt(1 - rho * rho))
        total += w * term
    return total * dx / 3.0


# ---------------------------------------------------------------- gate maths
def required_n(edge, base=0.524, alpha=0.05, power=0.80):
    """Bets needed to detect `edge` on top of a break-even win rate `base`."""
    z_a = phi_inv(1 - alpha / 2)
    z_b = phi_inv(power)
    p0 = base
    p1 = base + edge
    num = (z_a * math.sqrt(p0 * (1 - p0)) + z_b * math.sqrt(p1 * (1 - p1))) ** 2
    return math.ceil(num / (edge ** 2))


def n_for_roi(edge, sd=1.0, alpha=0.05, power=0.80):
    z_a = phi_inv(1 - alpha / 2)
    z_b = phi_inv(power)
    return math.ceil(((z_a + z_b) * sd / edge) ** 2)


def wilson(p, n, z=1.96):
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def deflated_sharpe(sr_observed, n, trials, gamma3=0.0, gamma4=3.0):
    """Bailey & Lopez de Prado deflated Sharpe ratio.

    sr_observed is a per-trial Sharpe; n = number of observations;
    trials = number of independent strategies tried.
    """
    if trials < 2:
        trials = 2
    v = 1.0 / n if n > 0 else 1.0
    e_max = math.sqrt(v) * ((1 - EULER) * phi_inv(1 - 1.0 / trials)
                            + EULER * phi_inv(1 - 1.0 / (trials * math.e)))
    denom = math.sqrt(max(1e-9, 1 - gamma3 * sr_observed + (gamma4 - 1) / 4.0 * sr_observed ** 2))
    z = (sr_observed - e_max) * math.sqrt(max(1, n - 1)) / denom
    return phi(z), e_max


def ev_per_unit(p, decimal_odds):
    return p * (decimal_odds - 1.0) - (1.0 - p)


def fair_decimal(p):
    return 1.0 / p if p > 0 else math.inf


def kelly(p, decimal_odds):
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, (p * decimal_odds - 1.0) / b)


# ---------------------------------------------------------------- main
def main():
    out = {
        "meta": {
            "title": "Gate mathematics (illustrative, not empirical)",
            "generated": "2026-11-12",
            "generator": "scripts/parlay_math.py",
            "warning": ("Every table below is computed from declared parameters. None of it is an "
                        "empirical result from NFL data. No observed bets, no observed lines and no "
                        "observed leg outcomes exist in this repository (F-04, F-09)."),
            "synthetic": True,
        }
    }

    # --- G1: how many bets are needed
    rows = []
    for edge in [0.005, 0.01, 0.02, 0.03, 0.05]:
        for base in [0.524, 0.5]:
            rows.append({
                "target_edge": edge,
                "break_even_win_rate": base,
                "required_bets_winprob_test": required_n(edge, base),
                "required_bets_roi_test": n_for_roi(edge),
            })
    out["sample_size"] = {
        "method": ("Win-probability test: n = (z_{1-a/2}*sqrt(p0(1-p0)) + z_power*sqrt(p1(1-p1)))^2 / (p1-p0)^2 "
                   "with alpha=0.05 two-sided and power=0.80. ROI test: n = ((z_a+z_b)*sd/edge)^2 with sd=1.0 "
                   "per-bet ROI, i.e. the fully conservative case."),
        "note": "0.524 is the break-even win rate at -110 (1.10 / 2.10). Rounded up to whole bets.",
        "rows": rows,
        "headline": ("Detecting a 2-point edge over break-even at 80% power needs roughly "
                     f"{required_n(0.02, 0.524):,} graded bets on the win/loss test and "
                     f"{n_for_roi(0.02):,} on the ROI test. A 40-bet hot streak cannot clear it."),
    }

    # --- G5: deflated Sharpe
    dsr_rows = []
    for trials in [1, 10, 50, 200, 1000]:
        for sr in [0.05, 0.10, 0.20]:
            d, e_max = deflated_sharpe(sr, 500, trials)
            dsr_rows.append({
                "trials": trials, "observed_sharpe": sr, "n": 500,
                "expected_max_sharpe_under_null": round(e_max, 4),
                "deflated_sharpe_ratio": round(d, 4),
                "passes_G5": d > 0.95,
            })
    out["deflated_sharpe"] = {
        "method": "Bailey & Lopez de Prado (2014); e_max is the expected maximum Sharpe from `trials` tries under the null.",
        "note": "A Sharpe that looks good alone dies as the trial count rises. This is the price of searching.",
        "rows": dsr_rows,
    }

    # --- G2: multiplicity
    out["multiplicity"] = {
        "method": "Bonferroni: evaluate each strategy at alpha/m for m logged trials.",
        "rows": [{"trials": m, "alpha": 0.05, "alpha_per_test": round(0.05 / m, 6),
                  "t_threshold": round(phi_inv(1 - (0.05 / m) / 2), 3)} for m in [1, 5, 20, 100, 500]],
    }

    # --- parlays: independent vs correlated
    p1, p2 = 0.55, 0.55
    parlay_rows = []
    for rho in [0.0, 0.2, 0.4, 0.6, 0.8]:
        joint = biv_norm_cdf(phi_inv(p1), phi_inv(p2), rho)
        independent = p1 * p2
        # Deliberately set to the price implied by INDEPENDENT legs, so each row
        # isolates the pricing error caused by correlation alone.
        offered = round(fair_decimal(independent), 3)
        parlay_rows.append({
            "rho": rho,
            "p_joint": round(joint, 4),
            "p_joint_if_independent": round(independent, 4),
            "error_from_independence_pct": round(100 * (joint - independent) / independent, 2),
            "fair_decimal_odds": round(fair_decimal(joint), 3),
            "ev_per_unit_at_offered_price": round(ev_per_unit(joint, offered), 4),
            "kelly_fraction_at_offered_price": round(kelly(joint, offered), 4),
        })
    out["parlay_two_leg"] = {
        "inputs": {"p_leg1": p1, "p_leg2": p2,
                   "assumed_book_price": round(fair_decimal(p1 * p2), 3),
                   "why_this_price": "The price a book would post if it treated the legs as independent."},
        "method": ("Gaussian copula: P(both) = Phi2(Phi^-1(p1), Phi^-1(p2); rho). A positive rho means the "
                   "legs tend to hit together, which RAISES the joint probability and therefore lowers the "
                   "fair price. A negative rho does the opposite."),
        "why_it_matters": ("Two same-game legs that move together are systematically under-priced by an "
                           "independent-leg model, so the EV column is the SIZE of that pricing error, not a "
                           "claim that such a price is on offer. Most books apply a correlation adjustment to "
                           "same-game parlays; whether that adjustment is right is an empirical question and is "
                           "exactly what Q-14 has to answer."),
        "rows": parlay_rows,
    }

    # three-leg
    p3 = 0.60
    tri_rows = []
    for rho in [0.0, 0.3, 0.6]:
        z = [phi_inv(p1), phi_inv(p2), phi_inv(p3)]
        # equicorrelated 3-leg joint via 1-D integration over a common factor
        n = 400
        lo, hi = -8.0, 8.0
        dx = (hi - lo) / n
        tot = 0.0
        for i in range(n + 1):
            x = lo + i * dx
            w = 1 if i in (0, n) else (4 if i % 2 == 1 else 2)
            fx = math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)
            if rho <= 0:
                inner = p1 * p2 * p3
            else:
                cond = [phi((zz - math.sqrt(rho) * x) / math.sqrt(1 - rho)) for zz in z]
                inner = cond[0] * cond[1] * cond[2]
            tot += w * fx * inner
        joint = tot * dx / 3.0
        offered = round(fair_decimal(p1 * p2 * p3), 3)
        tri_rows.append({
            "rho": rho,
            "p_joint": round(joint, 4),
            "p_joint_if_independent": round(p1 * p2 * p3, 4),
            "fair_decimal_odds": round(fair_decimal(joint), 3),
            "ev_per_unit_at_offered_price": round(ev_per_unit(joint, offered), 4),
        })
    out["parlay_three_leg"] = {
        "inputs": {"p_leg1": p1, "p_leg2": p2, "p_leg3": p3,
                   "assumed_book_price": round(fair_decimal(p1 * p2 * p3), 3),
                   "why_this_price": "The price a book would post if it treated all three legs as independent."},
        "method": ("Equicorrelated Gaussian factor model: a single common factor drives all three legs with "
                   "loading sqrt(rho); P(all) = E_x[ prod_i Phi((z_i - sqrt(rho) x)/sqrt(1-rho)) ]."),
        "rows": tri_rows,
    }

    # --- prop sizing / kelly
    kelly_rows = []
    for p in [0.50, 0.52, 0.55, 0.58, 0.60]:
        for price in [-110, -120]:
            dec = 1 + (100 / abs(price))
            kelly_rows.append({
                "win_prob": p, "american_price": price, "decimal_odds": round(dec, 4),
                "edge_vs_fair": round(ev_per_unit(p, dec), 4),
                "full_kelly_fraction": round(kelly(p, dec), 4),
                "quarter_kelly_fraction": round(kelly(p, dec) / 4, 4),
            })
    out["kelly"] = {
        "method": "f* = (p*d - 1)/(d - 1). Quarter Kelly shown because a mis-estimated p makes full Kelly dangerous.",
        "warning": "Kelly assumes p is known. Here p would be estimated, so the output is an upper bound.",
        "rows": kelly_rows,
    }

    # --- confidence intervals: what 12-3 actually tells you
    ci = []
    for w, n in [(12, 15), (55, 100), (110, 200), (300, 500)]:
        lo, hi = wilson(w / n, n)
        ci.append({
            "record": f"{w}-{n - w}", "n": n, "observed_win_rate": round(w / n, 4),
            "wilson_95_ci": [round(lo, 4), round(hi, 4)],
            "includes_break_even_524": lo <= 0.524 <= hi,
        })
    out["confidence_intervals"] = {
        "method": "Wilson score interval, 95%.",
        "note": "This is the tool that answers 'is this skill or luck'. A 12-3 start cannot exclude break-even.",
        "rows": ci,
    }

    with open(os.path.join(DATA, "strategy_math.json"), "w") as f:
        json.dump(out, f, indent=1)

    print(out["sample_size"]["headline"])
    for r in out["parlay_two_leg"]["rows"]:
        print(f"rho={r['rho']:.1f}  P={r['p_joint']:.4f}  fair={r['fair_decimal_odds']:.3f}  EV={r['ev_per_unit_at_offered_price']:+.4f}")
    for r in out["confidence_intervals"]["rows"]:
        print(r["record"], r["wilson_95_ci"], "includes 52.4%:" , r["includes_break_even_524"])


if __name__ == "__main__":
    main()
