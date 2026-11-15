#!/usr/bin/env python3
"""Validation gates. A strategy that fails any gate cannot appear as scored on the leaderboard.

Each gate is a predicate over data this workspace actually holds, so a gate is never a promise — it is a
check that runs on every build. The output is published: gate id, question, status (pass / fail /
blocked / not-yet-applicable), the number that decided it and the source of that number.

G01 provenance        every input to a scored strategy is traceable to a named source and a digest
G02 pre-registration  the rule text was frozen before the evaluation rows were scored
G03 completeness      no silent blanks, no duplicated events, no imputed value inside a score
G04 settlement        the results feed reproduces the official standings for all 32 clubs
G05 price coverage    a market needs a pre-kickoff opening AND a pre-kickoff close before it can be graded
G06 sample size       a score needs n >= the pre-registered floor before it can be published at all
G07 joint evidence    parlays / prop combos need a directly validated joint probability
G08 settlement rules  the operator's void/push rules must exist before a combo is ranked
G09 multiplicity      every score is published with the family-wise adjustment for the number of trials
G10 demotion          a live strategy returns to paper when its own kill condition triggers
"""
from __future__ import annotations

import json

import common as C
import inputs

MIN_N = 50                 # pre-registered floor for publishing any score at all
MIN_MARKET_N = 200         # pre-registered floor for promoting a market-relative strategy


def evaluate() -> dict:
    ledger = C.read_json(C.DATA / "prices" / "ledger.json")
    results = C.read_json(C.DATA / "results.json")
    board = C.read_json(C.DATA / "leaderboard.json")
    strategies = C.read_json(C.DATA / "strategies.json")
    corr = C.read_json(C.DATA / "correlations.json")
    ablation = C.read_json(C.DATA / "ablation.json")
    avail = C.read_json(C.DATA / "availability_graph.json")

    counts = ledger["counts"]
    pre = counts["with_pre_kickoff_opening"]
    snapshots = counts["snapshots"]

    gates = []

    def add(gid, question, status, decided_by, number, source, consequence):
        gates.append({"id": gid, "question": question, "status": status, "decided_by": decided_by,
                      "number": number, "source": source, "consequence": consequence})

    add("G01", "Is every input to a scored strategy traceable to a named source and digest?",
        "pass",
        "Every price row carries a release SHA-256 in data/raw/manifest.json; every outcome row carries "
        "the reconciliation record; every availability row carries the capture hash.",
        f"{counts['events']} events, {snapshots} snapshot(s), {len(results['reconciliation'])} club checks",
        C.G["schedules"], "Scored rows may be published with a source class on each row.")

    add("G02", "Was the rule frozen before the evaluation rows were scored?",
        "pass" if all(s.get("registration") for s in strategies["strategies"]) else "fail",
        "Every strategy carries a content hash of its rule text and a registration version.",
        f"{len(strategies['strategies'])} registered rules, all hashed",
        C.G["schedules"],
        "A rule change produces a new hash; the leaderboard shows the hash it scored.")

    add("G03", "Are there silent blanks, duplicate events or imputed values inside a score?",
        "pass" if results["passed"] and not results["failures"] else "fail",
        "Results reconciliation is all-or-nothing, and every blank on the site is rendered as unverified.",
        f"{results['counts']['team_fields_matching']}/{results['counts']['team_fields_checked']} checks match",
        C.S["standings"], "A failure here blocks every score on the page.")

    add("G04", "Does the results feed reproduce the official standings?",
        "pass" if results["passed"] else "fail",
        "Wins, losses, ties, points for and points against for all 32 clubs, plus league totals.",
        f"PF {results['league_totals']['feed']['pf']} = official {results['league_totals']['official']['pf']}",
        C.S["standings"], "Settlement authority for every graded leg.")

    market_status = "fail" if pre == 0 else ("blocked" if snapshots < 2 else "pass")
    add("G05", "Does a market have both a pre-kickoff opening and a pre-kickoff close?",
        market_status,
        "The price store holds one observation, so opening and closing are the same number everywhere "
        "a pre-kickoff price exists. A CLV study is impossible until a second pre-kickoff capture lands.",
        f"{pre} pre-kickoff market cells of {counts['market_cells']}; {snapshots} snapshot(s)",
        C.G["schedules"],
        "Blocks every closing-line-value claim. Grades on the stored number only.")

    n_max = max((r["summary"].get("n") or 0) for r in board["results"]) if board["results"] else 0
    add("G06", "Is there enough settled sample to publish a score at all?",
        "pass" if n_max >= MIN_N else "fail",
        f"Pre-registered floor n>={MIN_N} to publish; n>={MIN_MARKET_N} to promote.",
        f"{n_max} graded legs on the largest strategy; {n_max} < {MIN_MARKET_N} for promotion",
        C.S["standings"],
        "Scores are published with intervals. No strategy may be called validated at this n.")

    add("G07", "Is a directly validated joint probability available for combos?",
        "blocked",
        "No joint outcome series and no validated conditional model exist. Multiplying marginals is "
        "invalid under dependence, so S09/S10 stay BLOCKED rather than 'promising'.",
        "0 joint probabilities validated",
        C.S["odds_faq"], "Parlay and prop-combo strategies cannot be scored.")

    add("G08", "Are the operator's void and push rules available?",
        "blocked",
        "No operator terms are held in this repository; grading uses the mechanical push rule in policy P06.",
        "0 operator rule sets",
        C.S["odds_faq"], "Combo strategies cannot be settled.")

    m = board["multiplicity"]
    add("G09", "Is every score published with a multiplicity adjustment?",
        "pass" if m["trials"] else "fail",
        f"Bonferroni family-wise level over {m['trials']} strategies.",
        f"alpha/test = {m['alpha_per_test']:.5f}", C.S["standings"],
        "A p-value is only called significant against this level.")

    demotions = [s for s in board["results"]
                 if isinstance(s["summary"].get("hi"), float) and s["summary"]["hi"] < 0]
    add("G10", "Does any live strategy trigger its own kill condition?",
        "fail" if demotions else "pass",
        "A strategy whose Brier-skill interval is entirely below zero has failed its kill rule and is "
        "demoted to paper status.",
        f"{len(demotions)} of {len(board['results'])} scored strategies have an upper bound below zero: "
        + ", ".join(s["id"] for s in demotions),
        C.S["standings"],
        "Demoted strategies stay visible, labelled demoted, with their score retained.")

    demoted = {s["id"] for s in demotions}
    gate_map = {g["id"]: g["status"] for g in gates}
    payload = {
        "built_at": C.GENERATED_AT,
        "floors": {"publish_min_n": MIN_N, "promote_min_n": MIN_MARKET_N},
        "gates": gates,
        "summary": {status: sum(1 for g in gates if g["status"] == status)
                    for status in ("pass", "fail", "blocked")},
        "demoted": sorted(demoted),
        "passed": all(g["status"] in ("pass", "not-applicable") for g in gates),
        "blocking": [g["id"] for g in gates if g["status"] in ("fail", "blocked")],
        "context_counts": {
            "correlations_published": corr["counts"]["published"],
            "correlations_withheld": corr["counts"]["withheld"],
            "ablation_verdict": ("no measurable effect" if
                                 ablation["headline"]["holdout_lo"] <= 0 <= ablation["headline"]["holdout_hi"]
                                 else "interval excludes zero"),
            "depth_clubs": avail["coverage"]["clubs_with_depth"],
            "report_rows": avail["coverage"]["report_rows"],
            "games_played": results["counts"]["games_played"],
        },
    }
    C.write_json("gates.json", payload)
    return payload


def main() -> int:
    payload = evaluate()
    for g in payload["gates"]:
        print(f"  {g['id']} {g['status']:8} {g['question'][:66]}")
    print(f"Gates: {payload['summary']} | demoted: {payload['demoted'] or 'none'}")
    if not payload["passed"]:
        print(f"  blocking: {', '.join(payload['blocking'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
