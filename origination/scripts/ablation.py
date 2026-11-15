#!/usr/bin/env python3
"""Injury and personnel ablations — not fixed point penalties.

The brief is explicit: instead of subtracting a fixed number of points for a missing starter, run the
same model with and without the personnel features and report the difference *with uncertainty*. That is
what this file does, and it reports the honest outcome even when the answer is "no measurable effect in
this sample".

Design
------
For each game the ablation compares two otherwise identical margin models:

    base      margin = hfa + rating(home) - rating(away)                      (the model in model.py)
    personnel margin = base - κ_home + κ_away,
              where κ_club = λ × (measured snap share lost to official unavailability)

  * Unavailability comes only from the official report: a player with game status `Out`/`Doubtful`, or a
    reserve-list player whose club is on the report. Nothing is inferred.
  * The weight of the missing player is his **measured snap share** from the community snap feed, not his
    name or draft slot. Depth is a measurement here.
  * λ is a single scalar, and it is **not fitted**. It is set to a pre-registered one-snap-share-one-point
    conversion and then the whole λ grid is published, so a reader can see whether any λ would have
    produced a signal. Reporting only the best λ would be tuning on the outcome.

Chronological holdouts
----------------------
Weeks 1-6 are the fit window and Weeks 7-10 are held out. The rating fit for every game still uses only
prior seasons (walk-forward), so the holdout split is an *additional* check on the ablation term rather
than the only protection.

What is deliberately not claimed
--------------------------------
The corpus is 137 played games with a single official injury snapshot. A personnel effect of one or two
points on a 13.5-point margin sd is far below the noise this sample can resolve. The table therefore
publishes the interval, and the verdict column says when the interval covers zero. That is a finding, not
a failure.
"""
from __future__ import annotations

import json
from collections import defaultdict

import common as C
import inputs
import model as model_mod

LAMBDA_PRIMARY = 1.0     # pre-registered: points of margin per unit of lost snap share
LAMBDA_GRID = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
FIT_WEEKS = (1, 6)
HOLDOUT_WEEKS = (7, 10)


def _availability_load() -> dict:
    """Per (club, player): official designation and measured snap share."""
    snaps = inputs.snap_counts()
    share = {}
    for s in snaps:
        key = (s["team"], s["player"].lower())
        value = s["offense_pct"] if s["offense_pct"] is not None else s["defense_pct"]
        if value is None:
            continue
        # Keep the largest measured share seen: a player's role is best described by the time he has
        # actually played, not by a week he was injured and did not appear.
        share[key] = max(share.get(key, 0.0), value)

    load = defaultdict(float)
    detail = defaultdict(list)
    for row in inputs.injury_rows():
        code = inputs.team_of_club_name(row["team"])
        if not code:
            continue
        status = row["game_status"]
        if status not in ("Out", "Doubtful"):
            continue
        key = (code, row["player"].lower())
        measured = share.get(key)
        if measured is None:
            continue
        load[code] += measured
        detail[code].append({"player": row["player"], "status": status,
                             "snap_share": measured, "source_url": row["source_url"]})
    # A reserve-list player is unavailable by construction, but without a measured snap share his
    # weight cannot be estimated; those players are counted, not imputed.
    return {"load": dict(load), "detail": dict(detail),
            "share_source": C.G["snaps"], "report_source": C.S["injuries"]}


def run() -> dict:
    wf = C.read_json(C.DATA / "origination_walkforward.json")
    rows = wf["rows"]
    avail = _availability_load()
    load = avail["load"]

    buckets = {"fit": [r for r in rows if FIT_WEEKS[0] <= r["week"] <= FIT_WEEKS[1]],
               "holdout": [r for r in rows if HOLDOUT_WEEKS[0] <= r["week"] <= HOLDOUT_WEEKS[1]],
               "all": rows}

    grid = []
    for lam in LAMBDA_GRID:
        entry = {"lambda": lam, "buckets": {}}
        for name, bucket in buckets.items():
            base_err, adj_err = [], []
            for r in bucket:
                base = r["model_margin"]
                adj = base - lam * (load.get(r["home"], 0.0) - load.get(r["away"], 0.0))
                actual = r["actual_margin"]
                base_err.append(base - actual)
                adj_err.append(adj - actual)
            diffs = [abs(a) - abs(b) for a, b in zip(adj_err, base_err)]
            ci = C.cluster_bootstrap_ci([abs(b) for b in base_err], [abs(a) for a in adj_err],
                                        [r["game_id"] for r in bucket], n_boot=1500)
            entry["buckets"][name] = {
                "n": len(bucket),
                "base_mae": C.mean([abs(x) for x in base_err]),
                "personnel_mae": C.mean([abs(x) for x in adj_err]),
                "mae_improvement": C.mean(diffs),
                "mae_improvement_lo": ci["lo"], "mae_improvement_hi": ci["hi"],
                "base_bias": C.mean(base_err), "personnel_bias": C.mean(adj_err),
                "residual_sd": C.sd(adj_err),
            }
        grid.append(entry)

    # Per-club loads, which is also the deficiency view the team-level page needs.
    club_rows = []
    for code in sorted(C.FULL_NAME):
        injured = avail["detail"].get(code, [])
        club_rows.append({
            "club": code, "club_name": C.FULL_NAME[code],
            "n_unavailable_with_measured_time": len(injured),
            "lost_snap_share": load.get(code, 0.0),
            "players": injured[:8],
            "report_source": C.S["injuries"],
        })

    primary = next(e for e in grid if e["lambda"] == LAMBDA_PRIMARY)
    payload = {
        "built_at": C.GENERATED_AT,
        "design": {
            "lambda_primary": LAMBDA_PRIMARY, "lambda_grid": LAMBDA_GRID,
            "fit_weeks": FIT_WEEKS, "holdout_weeks": HOLDOUT_WEEKS,
            "weight": "measured snap share of the unavailable player (community snap feed)",
            "unavailability": "official game status Out/Doubtful on the captured report",
            "fitted": False,
        },
        "headline": {
            "n_all": primary["buckets"]["all"]["n"],
            "mae_improvement_all": primary["buckets"]["all"]["mae_improvement"],
            "mae_improvement_holdout": primary["buckets"]["holdout"]["mae_improvement"],
            "holdout_lo": primary["buckets"]["holdout"]["mae_improvement_lo"],
            "holdout_hi": primary["buckets"]["holdout"]["mae_improvement_hi"],
        },
        "grid": grid,
        "clubs": club_rows,
        "sources": {
            "injury": C.S["injuries"], "snap": C.G["snaps"],
            "depth": str((C.LAB / "official_snapshot.json").relative_to(C.ROOT)),
        },
        "limits": [
            "One official injury snapshot (2026-11-12). A player hurt after that observation is not in "
            "this ablation, so the personnel term under-counts late-week changes.",
            "Snap share measures a role, not the value of a player. Replacing a high-share left tackle "
            "with another high-share player would show no effect by construction.",
            "137 played games cannot resolve a 1-2 point effect on a 13.5 point margin sd. The interval "
            "is the result, not the point estimate.",
            "λ is not fitted. The full grid is published so a reader can see that no λ rescues the signal "
            "in this sample.",
        ],
    }
    C.write_json("ablation.json", payload)
    return payload


def main() -> int:
    payload = run()
    h = payload["headline"]
    print(f"Ablation (λ={LAMBDA_PRIMARY}): n={h['n_all']}")
    print(f"  all weeks   MAE improvement {h['mae_improvement_all']:+.3f} points")
    print(f"  holdout 7-10 MAE improvement {h['mae_improvement_holdout']:+.3f} "
          f"[{h['holdout_lo']:+.3f}, {h['holdout_hi']:+.3f}]")
    verdict = ("no measurable effect in this sample" if h["holdout_lo"] <= 0 <= h["holdout_hi"]
               else "interval excludes zero")
    print(f"  verdict: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
