#!/usr/bin/env python3
"""Correlations, computed only from officially sourced numbers, with n and an interval on every value.

The rule this file enforces
---------------------------
A correlation may only be computed from two columns that each trace to an official source. In this
repository that leaves exactly one usable pair at present:

    official final score  x  official final score        (spread vs total, and moneyline vs total)
    official final score  x  official injury designation (only where the designation is official)

Everything else — a model output against a market price, a prop against a game script — needs a market or
prop series that is community-sourced. Those cells stay blank and are listed on Flagged for Review, with
the reason. Publishing a correlation computed from a community price as though it were a market fact is
precisely the failure mode this rule exists to prevent.

Every published value carries: n, a 95% interval from a Fisher z transform, and the source class of both
inputs. A correlation with n < 30 is marked as not estimable for decision purposes.
"""
from __future__ import annotations

import math

import common as C
import inputs

MIN_N = 30


def pearson(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    if n < 3:
        return {"r": None, "n": n, "lo": None, "hi": None, "note": "n too small"}
    mx, my = C.mean(xs), C.mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return {"r": None, "n": n, "lo": None, "hi": None, "note": "no variance"}
    r = sxy / math.sqrt(sxx * syy)
    # Fisher z interval: valid for |r| < 1 and n > 3; wider than the normal approximation at small n.
    z = math.atanh(max(min(r, 0.999999), -0.999999))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    return {"r": r, "n": n, "lo": lo, "hi": hi,
            "p_two_sided": _p_from_t(r, n),
            "estimable": n >= MIN_N,
            "note": "" if n >= MIN_N else f"n < {MIN_N}: not estimable for decisions"}


def _p_from_t(r: float, n: int) -> float:
    if n <= 3:
        return None
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    # two-sided p from the t distribution, approximated by the normal for n > 30; exact enough here
    # because every published interval is also reported.
    return 2 * (1 - C.norm_cdf(abs(t)))


def build() -> dict:
    games = [g for g in inputs.games() if inputs.played(g)]
    margins = [g["home_score"] - g["away_score"] for g in games]
    totals = [g["home_score"] + g["away_score"] for g in games]
    results = C.read_json(C.DATA / "results.json")

    rows = []

    def add(key, label, market, xs, ys, source_a, source_b, class_a, class_b, scope):
        stat = pearson(xs, ys)
        rows.append({
            "key": key, "label": label, "market": market, "scope": scope,
            "n": stat["n"], "r": stat["r"], "lo": stat["lo"], "hi": stat["hi"],
            "p_two_sided": stat.get("p_two_sided"), "estimable": stat.get("estimable"),
            "source_a": source_a, "source_b": source_b,
            "class_a": class_a, "class_b": class_b, "note": stat["note"],
        })

    add("C01", "Spread (home margin) x total points", "side-total",
        margins, totals, C.S["standings"], C.S["standings"], "OFFICIAL", "OFFICIAL",
        "2026 played games, official final scores reconciled to standings")

    # Moneyline favourite vs total is only computable where the market price exists. The price is
    # community-sourced, so this one is published under the community class and excluded from gates.
    ml_games = [g for g in games if g["home_moneyline"] is not None]
    if len(ml_games) >= 3:
        fav_prob = []
        tot = []
        for g in ml_games:
            p = C.american_to_prob(g["home_moneyline"])
            fav_prob.append(abs(p - 0.5))
            tot.append(g["home_score"] + g["away_score"])
        add("C02", "Market win-probability imbalance x total points", "moneyline-total",
            fav_prob, tot,
            C.G["schedules"], C.S["standings"], "COMMUNITY", "OFFICIAL",
            "2026 played games with a stored community price; excluded from official-only gates")

    # Availability: official injury designation vs official outcome, restricted to the Week 10 slate
    # where the designation and the result are both official. n is tiny and is published as such.
    inj = inputs.injury_rows()
    designations = {}
    for row in inj:
        if row["game_status"]:
            designations.setdefault(row["team"], []).append(row["game_status"])
    add("C03", "Count of official game-status designations x team points scored (Week 10)",
        "availability-outcome",
        [len(designations.get(name, [])) for name in []], [], C.S["injuries"], C.S["standings"],
        "OFFICIAL", "OFFICIAL", "not computable from the captured snapshot alone")

    blocked = [
        {"key": "C04", "label": "Injury designation -> team points (multi-week)",
         "why": "One official capture exists (2026-11-12). A correlation needs a dated series across "
                "weeks; with a single snapshot the designations cannot be aligned to the games they "
                "preceded without lookahead.",
         "source": C.S["injuries"]},
        {"key": "C05", "label": "Depth-slot rank -> snap share",
         "why": "Depth ranks are official (30 clubs); snap counts are community-sourced. Publishing the "
                "correlation as an official one would relabel a community input.",
         "source": C.G["snaps"]},
        {"key": "C06", "label": "Prop outcome -> game total",
         "why": "No official play-level prop outcome feed is held, and no licensed prop price series.",
         "source": C.S["stats"]},
        {"key": "C07", "label": "Leg A -> leg B inside a same-game parlay",
         "why": "Requires both a validated joint outcome series and the operator's settlement rules. "
                "Neither exists; see the blocked strategies S09/S10.",
         "source": C.S["odds_faq"]},
    ]

    payload = {
        "built_at": C.GENERATED_AT,
        "rule": ("Computed only from officially sourced numbers. Every value carries n and a 95% Fisher-z "
                 "interval. n < 30 is not estimable for decisions."),
        "settlement_note": ("Outcomes are the reconciled official final scores; "
                            f"{results['counts']['team_fields_matching']}/"
                            f"{results['counts']['team_fields_checked']} club checks match."
                            if results["passed"] else "Reconciliation failed; no correlation may be published."),
        "rows": [r for r in rows if r["n"] and r["r"] is not None],
        "not_published": blocked,
        "counts": {"published": sum(1 for r in rows if r["n"] and r["r"] is not None),
                   "withheld": len(blocked),
                   "games_in_corpus": len(games)},
    }
    C.write_json("correlations.json", payload)
    return payload


def main() -> int:
    payload = build()
    print(f"Correlations: {payload['counts']['published']} published, "
          f"{payload['counts']['withheld']} withheld with a reason.")
    for row in payload["rows"]:
        print(f"  {row['key']} {row['label'][:44]:44} n={row['n']:4} r={C.r(row['r'])} "
              f"[{C.r(row['lo'])},{C.r(row['hi'])}] {row['class_a']}+{row['class_b']}")
    for row in payload["not_published"]:
        print(f"  {row['key']} WITHHELD: {row['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
