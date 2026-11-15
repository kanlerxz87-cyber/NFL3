#!/usr/bin/env python3
"""The strategy registry and the leaderboard it feeds.

A strategy here is a *rule*, not a result. Each one has: a frozen definition, the market it prices, the
sample window it is allowed to see, the benchmarks it is scored against, the gates it must pass, and two
"what would change our mind" statements — one that would promote it and one that would kill it. The text
of every rule is hashed, so a change is a new registration rather than a quiet edit.

The leaderboard is a proper-score table, not a win-rate table. See `leaderboard.py` for the rendering.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

import common as C
import scoring

REGISTRY = C.DATA / "strategies.json"
VERSION = "2026-11-15.v1"


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def strategies() -> list[dict]:
    """The registry. Definitions are frozen text; the hash is the registration."""
    rows = [
        {
            "id": "S01", "family": "singles", "market": "side",
            "name": "Model spread vs market spread (no threshold)",
            "rule": ("Bet the side when the originated margin differs from the stored market spread by "
                     "at least Δ points, Δ = 0. Tie games push on whole numbers only."),
            "delta": 0.0,
            "why": "The baseline that must exist before any threshold: if no Δ edge exists at Δ=0, a "
                   "threshold only manufactures noise.",
            "promote": "Paired BSS interval lower bound above 0 on pre-kickoff rows with n ≥ 200.",
            "kill": "Interval straddles 0 after 400 graded legs, or the sign flips between the two "
                    "independent estimators (ridge and Elo).",
        },
        {
            "id": "S02", "family": "singles", "market": "side",
            "name": "Model spread vs market spread (Δ ≥ 1.5)",
            "rule": "Same as S01 but only when |model − market| ≥ 1.5 points.",
            "delta": 1.5,
            "why": "Tests whether selectivity helps or just shrinks n.",
            "promote": "Paired BSS interval lower bound above 0 with n ≥ 200 at Δ=1.5.",
            "kill": "BSS at Δ=1.5 is not better than Δ=0 after the multiplicity adjustment.",
        },
        {
            "id": "S03", "family": "singles", "market": "total",
            "name": "Model total vs market total",
            "rule": "Bet over when the originated total exceeds the stored total by ≥ 1.0 point, under "
                    "by the same margin.",
            "delta": 1.0,
            "why": "The total is a different quantity; it must be tested on its own rather than assumed.",
            "promote": "Paired BSS interval lower bound above 0 with n ≥ 200.",
            "kill": "Total MAE is worse than the market's MAE on the same rows.",
        },
        {
            "id": "S04", "family": "singles", "market": "moneyline",
            "name": "Model win probability vs de-vigged moneyline",
            "rule": "Bet the side whose model probability exceeds the de-vigged market probability by "
                    "≥ 3 percentage points.",
            "delta": 0.03,
            "why": "The moneyline is third because it inherits the margin model; it is a transform test, "
                   "not an independent signal.",
            "promote": "Paired BSS interval lower bound above 0 with n ≥ 200.",
            "kill": "Model probabilities are less calibrated than the de-vigged market on the same rows.",
        },
        {
            "id": "S05", "family": "controls", "market": "side",
            "name": "Control: always take the home side",
            "rule": "Bet home on every pre-kickoff row, ignoring the model.",
            "delta": None,
            "why": "A rigged benchmark. If a model cannot beat 'always home', it carries no side skill.",
            "promote": "Never promoted. It exists to be beaten.",
            "kill": "n/a — control arm.",
        },
        {
            "id": "S06", "family": "controls", "market": "side",
            "name": "Control: always take the favourite",
            "rule": "Bet the side the market prices as favourite, ignoring the model.",
            "delta": None,
            "why": "The classic 'favourites only' control. Long-run losing at a vig, so a model that "
                   "beats it has demonstrated something the crowd already prices.",
            "promote": "Never promoted.",
            "kill": "n/a — control arm.",
        },
        {
            "id": "S07", "family": "controls", "market": "side",
            "name": "Control: always take the underdog",
            "rule": "Bet the side the market prices as underdog.",
            "delta": None,
            "why": "The other side of the favourite control; a market with a strong favourite bias would "
                   "make one of S06/S07 look skilful for the wrong reason.",
            "promote": "Never promoted.",
            "kill": "n/a — control arm.",
        },
        {
            "id": "S08", "family": "controls", "market": "total",
            "name": "Control: always take the over",
            "rule": "Bet over on every pre-kickoff row, ignoring the model.",
            "delta": None,
            "why": "Tests whether a total model is beating a coin, not a trend.",
            "promote": "Never promoted.",
            "kill": "n/a — control arm.",
        },
        {
            "id": "S09", "family": "parlays", "market": "parlay",
            "name": "Two-leg same-week parlay (joint-evidence gate)",
            "rule": ("Combine two legs only when a directly validated joint probability exists. Marginal "
                     "probabilities may not be multiplied: dependence inside a game and across a slate "
                     "makes the product wrong in both directions."),
            "delta": None,
            "why": "Parlays are where most claimed edges live and where they are least verifiable.",
            "promote": "A joint probability validated on held-out data, plus the operator's void and push "
                       "rules, plus a settled sample with push handling.",
            "kill": "No joint estimate exists → the strategy stays BLOCKED, not 'promising'.",
            "gate_status": "blocked",
            "blocked_by": "G07 joint-evidence gate: no validated joint probability is available.",
        },
        {
            "id": "S10", "family": "player-props", "market": "prop-combo",
            "name": "Player-prop combination (joint-evidence gate)",
            "rule": ("Rank a prop combination only when a directly validated joint probability and the "
                     "operator's void/push rules are both available."),
            "delta": None,
            "why": "Props are correlated within a game (pace, game script, weather). Multiplying marginals "
                   "is invalid.",
            "promote": "A validated joint model with held-out calibration and settled grading.",
            "kill": "No prop outcome feed exists → stays BLOCKED.",
            "gate_status": "blocked",
            "blocked_by": "G07 + G08: no validated joint probability and no prop settlement feed.",
        },
    ]
    for row in rows:
        row["registration"] = _h(json.dumps({k: row[k] for k in ("id", "rule", "delta", "market")},
                                            sort_keys=True)) + " · " + VERSION
        row["registered_at"] = C.GENERATED_AT
    return rows


def _rows_for(model_report: dict) -> list[dict]:
    """Prediction rows that can carry a market-relative probability."""
    out = []
    for r in model_report["rows"]:
        if r.get("market_spread") is None:
            continue
        out.append(r)
    return out


def _bench(r: dict) -> float:
    """The market's own probability. This is the benchmark every model must beat."""
    if r.get("market_ml_home_fair") is not None:
        return r["market_ml_home_fair"]
    return 0.5


def _normal_cover(mean_margin: float, line: float, sd: float) -> float:
    """Probability the home side covers `line`, from a normal margin model with the measured sd."""
    return C.norm_cdf((mean_margin - line) / sd)


def _normal_over(mean_total: float, line: float, sd: float) -> float:
    return C.norm_cdf((mean_total - line) / sd)


def evaluate_strategy(strategy: dict, rows: list[dict]) -> dict:
    """Score one frozen rule on the shared corpus.

    Probability semantics are stated per market, because a proper score is meaningless otherwise:
      side      p = P(chosen side covers),            p_bench = 0.5 (a line is a coin by construction)
      total     p = P(chosen side of the total hits), p_bench = 0.5
      moneyline p = originated P(home wins),          p_bench = de-vigged market P(home wins)
      controls  p = 0.5,                              p_bench = 0.5  -> BSS is exactly 0 by design,
                                                                      which is the point of a control.
    """
    graded: list[dict] = []
    for r in rows:
        market = strategy["market"]
        is_control = strategy["family"] == "controls"
        sd_m = r.get("sd_margin")
        sd_t = r.get("sd_total")
        if market == "side":
            if r.get("market_spread") is None or not sd_m:
                continue
            if strategy["id"] == "S05":
                pick_home, p = True, 0.5
            elif strategy["id"] == "S06":
                pick_home, p = (r["market_spread"] < 0), 0.5
            elif strategy["id"] == "S07":
                pick_home, p = (r["market_spread"] > 0), 0.5
            else:
                gap = r["model_margin"] - r["market_spread"]
                if abs(gap) < (strategy["delta"] or 0.0):
                    continue
                pick_home = gap > 0
                p = _normal_cover(r["model_margin"], r["market_spread"], sd_m)
                if not pick_home:
                    p = 1.0 - p
            g = scoring.grade_spread(pick_home, r["market_spread"], r["actual_margin"], None)
            graded.append({**r, "p": p, "p_bench": 0.5, "pick_home": pick_home, **g})
        elif market == "total":
            if r.get("market_total") is None or not sd_t:
                continue
            if is_control:
                over, p = True, 0.5
            else:
                gap = r["model_total"] - r["market_total"]
                if abs(gap) < (strategy["delta"] or 0.0):
                    continue
                over = gap > 0
                p = _normal_over(r["model_total"], r["market_total"], sd_t)
                if not over:
                    p = 1.0 - p
            g = scoring.grade_total(over, r["market_total"], r["actual_total"])
            graded.append({**r, "p": p, "p_bench": 0.5, "over": over, **g})
        elif market == "moneyline":
            bench = _bench(r)
            p_home = r.get("p_home")
            if bench is None or (not is_control and p_home is None):
                continue
            if is_control:
                pick_home, p = (r.get("market_ml_home") or 100) < 0, 0.5
                p_bench = 0.5
            else:
                gap = p_home - bench
                if abs(gap) < (strategy["delta"] or 0.0):
                    continue
                pick_home = gap > 0
                p = p_home if pick_home else 1.0 - p_home
                p_bench = bench if pick_home else 1.0 - bench
            g = scoring.grade_moneyline(pick_home, r["actual_margin"])
            graded.append({**r, "p": p, "p_bench": p_bench, "pick_home": pick_home, **g})
    summary = scoring.score_rows(graded)
    if graded:
        summary.update(scoring.paired_skill(graded))
        summary["wilson"] = scoring.wilson(sum(1 for x in graded if x.get("won")),
                                          sum(1 for x in graded if x.get("won") is not None))
    return {"strategy": strategy, "rows": graded, "summary": summary}


def run() -> dict:
    wf = json.loads((C.DATA / "origination_walkforward.json").read_text())
    rows = _rows_for(wf)
    for r in rows:
        r["sd_margin"] = wf["residual"]["margin_sd"]
        r["sd_total"] = wf["residual"]["total_sd"]
    strategies_ = strategies()
    results = [evaluate_strategy(s, rows) for s in strategies_ if s.get("gate_status") != "blocked"]
    m = scoring.multiplicity_note(len(strategies_))
    C.write_json("strategies.json", {"version": VERSION, "strategies": strategies_,
                                     "multiplicity": m, "built_at": C.GENERATED_AT})
    C.write_json("leaderboard.json", {
        "built_at": C.GENERATED_AT, "multiplicity": m,
        "benchmark": ("de-vigged market moneyline where available; 0.5 otherwise"),
        "note": ("Every score below is computed on the same pre-kickoff evaluation corpus. A number whose "
                 "interval includes zero is not evidence of skill."),
        "results": [{"id": r["strategy"]["id"], "name": r["strategy"]["name"],
                     "family": r["strategy"]["family"], "market": r["strategy"]["market"],
                     "summary": r["summary"], "rows": r["rows"]} for r in results],
        "blocked": [s for s in strategies_ if s.get("gate_status") == "blocked"],
    })
    for r in results:
        s = r["summary"]
        print(f"{r['strategy']['id']} {r['strategy']['name'][:44]:44} n={s.get('n',0):4} "
              f"bss={C.r(s.get('bss'))} acc={C.r(s.get('accuracy'))}")
    return {r["strategy"]["id"]: r for r in results}


if __name__ == "__main__":
    run()
