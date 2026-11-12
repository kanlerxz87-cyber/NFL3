"""Self-tests for the engine. Run with:  python3 engine/test_engine.py

These exist because a single sign error silently flips every graded bet. The convention tests use
real rows from the nflverse community schedule so they fail loudly if the formula is ever "fixed"
in the wrong direction again.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conventions as cv
import gates
import stats

FAILURES: list[str] = []


def check(name: str, got, want, tol: float = 1e-9) -> None:
    ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
    if not ok:
        FAILURES.append(f"{name}: got {got!r}, expected {want!r}")
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")


# --------------------------------------------------------------- sign conventions on real games
print("sign conventions (real release rows)")

# 2025_01_DAL_PHI: DAL 20 @ PHI 24 -> result +4. spread_line +8.5 = PHI home favourites by 8.5.
# PHI won by only 4, so the home side did NOT cover and the away side DID.
covered, push = cv.home_covers(4.0, 8.5)
check("DAL@PHI home cover (won by 4 as 8.5 fav)", covered, False)
check("DAL@PHI not a push", push, False)
check("DAL@PHI away cover", cv.away_covers(4.0, 8.5)[0], True)

# 2025_01_KC_LAC: KC 21 @ LAC 27 -> result +6, spread_line -3 = KC road favourites by 3.
# LAC (home) won by 6 and were getting 3, so the home side covered.
check("KC@LAC home cover (won by 6 as 3-pt dog)", cv.home_covers(6.0, -3.0)[0], True)

# 2025_01_ARI_NO: total 33, result -7 -> NO 13, ARI 20. ARI won by 7, and spread_line -6 means the
# AWAY side was favoured by 6. Home margin -7 against a line of -6 -> -1, so the home side did NOT cover.
check("ARI@NO home cover (lost by 7 as 6-pt home dog)", cv.home_covers(-7.0, -6.0)[0], False)
check("ARI@NO away cover (away 6-pt fav won by 7)", cv.away_covers(-7.0, -6.0)[0], True)

# exact push: home wins by exactly the number
check("push detected (won by 3, line 3)", cv.home_covers(3.0, 3.0), (False, True))

# totals
check("over wins (48 vs 47.5)", cv.over_wins(48.0, 47.5), (True, False))
check("under wins (44 vs 47.5)", cv.over_wins(44.0, 47.5), (False, False))
check("total push (47 vs 47)", cv.over_wins(47.0, 47.0), (False, True))

# model edge points the right way
check("model edge home positive when model > market", cv.model_edge_home(4.0, 2.5), 1.5)
check("model edge over positive when model > market", cv.model_edge_over(48.0, 45.0), 3.0)

# --------------------------------------------------------------- statistics against known values
print("\nstatistics (reference values)")
check("norm_ppf(0.975)", stats.norm_ppf(0.975), 1.959963984540054, 1e-6)
check("norm_ppf(0.995)", stats.norm_ppf(0.995), 2.5758293035489004, 1e-6)
check("norm_cdf(1.96)", stats.norm_cdf(1.96), 0.9750021048517795, 1e-9)
check("pearson known", stats.pearson([1, 2, 3, 4], [1, 3, 2, 4])[0], 0.8, 1e-12)
check("mean", stats.mean([1, 2, 3, 4]), 2.5)
check("variance (sample)", stats.variance([2, 4, 4, 4, 5, 5, 7, 9]), 4.571428571428571, 1e-9)
check("median even", stats.median([1, 2, 3, 4]), 2.5)
check("wilson lower below point estimate", stats.wilson_interval(52, 100)[0] < 0.52, True)

# ------------------------------------------------------------------ sportsbook price conversion
print("\nsportsbook prices")
check("american -110 to decimal", stats.american_to_decimal(-110), 1.9090909090909092, 1e-9)
check("american +100 to decimal", stats.american_to_decimal(100), 2.0)
check("american -110 implied", stats.american_to_implied(-110), 0.5238095238095238, 1e-9)
check("american +145 implied", stats.american_to_implied(145), 0.40816326530612246, 1e-9)
check("payout of -110 winner", stats.american_payout(-110), 0.9090909090909091, 1e-9)
check("payout of +145 winner", stats.american_payout(145), 1.45, 1e-12)
check("kelly on 55% at 1.909", stats.kelly_fraction(0.55, 1.909), (0.55 * 1.909 - 1) / (1.909 - 1), 1e-12)

# ------------------------------------------------------------------ selection-adjustment maths
print("\nselection adjustment")
check("expected max of 1 normal", stats.expected_max_of_k_normals(1), 0.0)
check("expected max of 10 > max of 2",
      stats.expected_max_of_k_normals(10) > stats.expected_max_of_k_normals(2), True)
check("expected max of 1000 > 3", stats.expected_max_of_k_normals(1000) > 3.0, True)
check("more trials means a higher bar",
      stats.deflated_threshold(500, 50) > stats.deflated_threshold(500, 5), True)

# ------------------------------------------------------------------ gate logic
print("\ngate behaviour")
lucky = [{"profit": 0.9, "won": 1, "season": 2025, "half": "H1", "clv": 1.0} for _ in range(20)]
check("a 20-bet hot streak fails the sample gate",
      gates.evaluate("lucky", "x", lucky)["gates"]["G1_sample"], False)
many = [{"profit": 0.05, "won": 1, "season": 2020 + (i % 4), "half": "H1" if i % 2 else "H2",
         "clv": 0.4} for i in range(300)]
ev = gates.evaluate("steady", "x", many, pvals_family={"steady": 1e-6},
                    n_attempts=1)
check("a steady 300-bet sample clears G1", ev["gates"]["G1_sample"], True)
check("it also clears G2 profit", ev["gates"]["G2_profit"], True)
neg = [{"profit": -0.05, "won": 0, "season": 2020 + (i % 4), "half": "H1" if i % 2 else "H2",
        "clv": -0.4} for i in range(300)]
check("a losing sample fails G2", gates.evaluate("loser", "x", neg, n_attempts=1)["gates"]["G2_profit"], False)

print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"{len(FAILURES)} FAILURE(S):\n" + "\n".join(FAILURES)))
sys.exit(1 if FAILURES else 0)
