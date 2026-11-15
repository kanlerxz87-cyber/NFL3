#!/usr/bin/env python3
"""Evaluation: proper scores, uncertainty, controls, and the honesty labels attached to every number.

Three rules that shape the whole file
------------------------------------
1. **A proper score needs an outcome and a probability that was fixed before the outcome.** Rows whose
   only price came after kickoff are not skipped silently: they are kept out of every market-relative
   score, labelled `post_hoc`, and shown in the excluded counts.
2. **A leaderboard is only meaningful against benchmarks.** Every strategy is scored on the same rows
   against the same benchmarks, so the Brier Skill Score is relative to a real alternative.
3. **No number stands alone.** Every score carries n, an uncertainty interval, and the multiplicity
   adjustment for the number of strategies scored against this corpus.

The score is the Brier Skill Score (BSS). Positive means the strategy beat its benchmark on the same
rows; a value whose interval includes zero is not evidence of skill.
"""
from __future__ import annotations

import json
from collections import defaultdict

import common as C

DATA = C.DATA


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- grading
def grade_spread(pick_home: bool, line: float | None, margin_home: int, price: int | None) -> dict:
    """Grade a spread bet. A push is excluded from win/loss, not scored as a win."""
    if line is None:
        return {"result": "no-price", "push": False, "won": None}
    edge = margin_home - line if pick_home else line - margin_home
    if abs(edge) < 1e-9:
        return {"result": "push", "push": True, "won": None}
    return {"result": "win" if edge > 0 else "loss", "push": False, "won": edge > 0}


def grade_total(over: bool, line: float | None, total: int) -> dict:
    if line is None:
        return {"result": "no-price", "push": False, "won": None}
    edge = (total - line) if over else (line - total)
    if abs(edge) < 1e-9:
        return {"result": "push", "push": True, "won": None}
    return {"result": "win" if edge > 0 else "loss", "push": False, "won": edge > 0}


def grade_moneyline(pick_home: bool, margin_home: int) -> dict:
    if margin_home == 0:
        return {"result": "push", "push": True, "won": None}   # no push in the market; reported only
    won = (margin_home > 0) == pick_home
    return {"result": "win" if won else "loss", "push": False, "won": won}


# ----------------------------------------------------------------------------- scores
def score_rows(rows: list[dict]) -> dict:
    """Score a list of settled predictions. `rows` need p, won, event_id and week."""
    graded = [r for r in rows if r.get("won") is not None]
    if not graded:
        return {"n": 0}
    brier = C.mean([C.brier(r["p"], int(r["won"])) for r in graded])
    bench = C.mean([C.brier(r["p_bench"], int(r["won"])) for r in graded])
    logloss = C.mean([C.log_loss(r["p"], int(r["won"])) for r in graded])
    bench_ll = C.mean([C.log_loss(r["p_bench"], int(r["won"])) for r in graded])
    return {
        "n": len(graded), "n_push": sum(1 for r in rows if r.get("push")),
        "brier": brier, "bench_brier": bench, "bss": C.brier_skill(brier, bench),
        "logloss": logloss, "bench_logloss": bench_ll,
        "logloss_skill": C.brier_skill(logloss, bench_ll),
        "accuracy": C.mean([1.0 if r["won"] else 0.0 for r in graded]),
        "bench_accuracy": C.mean([1.0 if r["p_bench"] >= 0.5 else 0.0 for r in graded]),
        "calibration_gap": C.mean([r["p"] - (1.0 if r["won"] else 0.0) for r in graded]),
    }


def paired_skill(rows: list[dict], n_boot: int = 2000) -> dict:
    """Paired game-cluster bootstrap of the Brier **advantage**: benchmark error minus model error.

    Sign convention, fixed here and asserted in tests: a POSITIVE value means the model's Brier error
    is smaller than the benchmark's, i.e. the model is better. Using (model - benchmark) instead would
    publish a negative result as a positive one; the unit tests pin the direction.
    """
    graded = [r for r in rows if r.get("won") is not None]
    if len(graded) < 5:
        return {"point": None, "lo": None, "hi": None, "n_clusters": 0}
    benchmark = [C.brier(r["p_bench"], int(r["won"])) for r in graded]
    model = [C.brier(r["p"], int(r["won"])) for r in graded]
    groups = [r.get("event_id") or r.get("game_id") for r in graded]
    return C.cluster_bootstrap_ci(benchmark, model, groups, n_boot=n_boot)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a rate; used for every win-rate column so a small n cannot look sure."""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def multiplicity_note(n_trials: int, alpha: float = 0.05) -> dict:
    """Bonferroni bound. With m strategies tested on the same corpus, the family-wise level is split."""
    return {"trials": n_trials, "alpha": alpha, "alpha_per_test": alpha / max(n_trials, 1)}
