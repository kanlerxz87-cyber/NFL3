#!/usr/bin/env python3
"""Independent line-by-line verification of the Week 10 2026 NFL injury data.

Three sources are compared field by field:

  A. verification/evidence/live_injuries_2026_w10.tsv
     An independent extraction of the live official report
     (https://www.nfl.com/injuries/) taken through a different rendering path
     (fetch_page markdown) by session arena/e0b5058a-nfl3 at
     2026-11-12T22:34:14Z -- see the evidence header.
  B. decision-lab/data/official_snapshot.json  (committed capture, 06:32:36Z)
  C. dashboard/data/injuries_2026_w10.csv      (committed dashboard extract)

Checks:
  1. B vs C  -- cross-extractor agreement on the same official page.
  2. A vs B  -- live page drift since the committed capture (16h apart).
  3. A vs C  -- live page drift vs the dashboard extract.
  4. internal counts (rows per source, no-injury sections).

Rules:
  * A row is only compared when its key (team, player, position) exists in
    both sides of a pair; anything else is reported as added/removed.
  * Differences are reported, never silently reconciled. Blank stays blank.
  * Every reported item carries the official source URL.

Exit code 0 always (this is a reporting tool); the verify gate for the site is
tests/check_site.py. Run:  python3 verification/verify.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "verification" / "evidence" / "live_injuries_2026_w10.tsv"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
DASH_CSV = ROOT / "dashboard" / "data" / "injuries_2026_w10.csv"
OUT = ROOT / "verification" / "report.json"

SOURCE_LIVE = "https://www.nfl.com/injuries/"
FIELDS = ("injury", "practice_status", "game_status")


def load_evidence(path: Path) -> list[dict]:
    rows: list[dict] = []
    day = matchup = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# DAY:"):
            day = line[len("# DAY:"):].strip()
        elif line.startswith("# MATCHUP:"):
            matchup = line[len("# MATCHUP:"):].strip()
        elif line.startswith("#") or not line.strip():
            continue
        else:
            parts = line.split("\t")
            if len(parts) != 6:
                raise ValueError(f"evidence line must have 6 tab fields: {line!r}")
            team, player, position, injury, practice, game = parts
            rows.append({
                "team": team, "player": player, "position": position,
                "injury": injury, "practice_status": practice, "game_status": game,
                "day": day, "matchup": matchup,
            })
    return rows


def load_snapshot(path: Path) -> tuple[list[dict], list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc["injury_rows"], doc.get("no_injury_sections", [])


def load_dashboard(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def key(row: dict) -> tuple[str, str, str]:
    return (row.get("team", ""), row.get("player", ""), row.get("position", ""))


def compare(a: list[dict], b: list[dict], a_name: str, b_name: str) -> dict:
    a_map: dict[tuple, list[dict]] = {}
    b_map: dict[tuple, list[dict]] = {}
    for row in a:
        a_map.setdefault(key(row), []).append(row)
    for row in b:
        b_map.setdefault(key(row), []).append(row)

    only_a, only_b, field_diffs, dup_a, dup_b = [], [], [], [], []
    for k in sorted(set(a_map) | set(b_map)):
        la, lb = a_map.get(k, []), b_map.get(k, [])
        if len(la) > 1:
            dup_a.append({"key": k, "count": len(la)})
        if len(lb) > 1:
            dup_b.append({"key": k, "count": len(lb)})
        if la and not lb:
            only_a.append({"key": k, "rows": len(la)})
            continue
        if lb and not la:
            only_b.append({"key": k, "rows": len(lb)})
            continue
        ra, rb = la[0], lb[0]
        diffs = {}
        for f in FIELDS:
            va, vb = ra.get(f, ""), rb.get(f, "")
            if va != vb:
                diffs[f] = {a_name: va, b_name: vb}
        if diffs:
            field_diffs.append({"key": k, "diffs": diffs})

    matched = sum(1 for k in set(a_map) & set(b_map))
    return {
        "a": a_name, "b": b_name,
        "a_rows": len(a), "b_rows": len(b),
        "matched_keys": matched,
        "only_in_a": only_a, "only_in_b": only_b,
        "field_diffs": field_diffs,
        "duplicate_keys_a": dup_a, "duplicate_keys_b": dup_b,
        "exact_matches": matched - len(field_diffs),
    }


def main() -> int:
    evidence = load_evidence(EVIDENCE)
    snapshot, no_injury = load_snapshot(SNAPSHOT)
    dashboard = load_dashboard(DASH_CSV)

    dash_rows = [{
        "team": r["team_name"], "player": r["player"], "position": r["position"],
        "injury": r["injury"], "practice_status": r["practice_status"],
        "game_status": r["game_status"],
    } for r in dashboard]

    # Day/matchup context check: A (live) and B (snapshot) share the same format;
    # C (dashboard CSV) uses a different date format and is not compared here.
    snap_ctx = {(r.get("team"), r.get("player"), r.get("position")):
                (r.get("day"), r.get("matchup")) for r in snapshot}
    ctx_diffs = []
    for r in evidence:
        k = (r.get("team"), r.get("player"), r.get("position"))
        if k in snap_ctx:
            live_ctx = (r.get("day"), r.get("matchup"))
            if live_ctx != snap_ctx[k]:
                ctx_diffs.append({"key": k, "A_live": live_ctx, "B_snapshot": snap_ctx[k]})

    results = {
        "generated_by": "verification/verify.py (session arena/e0b5058a-nfl3)",
        "day_matchup_context_diffs_A_vs_B": ctx_diffs,
        "sources": {
            "A_live": {
                "name": "live official report (independent markdown extraction)",
                "url": SOURCE_LIVE,
                "observed_at": "2026-11-12T22:34:14Z",
                "rows": len(evidence),
            },
            "B_snapshot": {
                "name": "decision-lab committed capture",
                "url": SOURCE_LIVE,
                "observed_at": json.loads(SNAPSHOT.read_text())["observed_at"],
                "rows": len(snapshot),
                "no_injury_sections": [
                    {"team": s.get("team"), "text": s.get("text"), "day": s.get("day")}
                    for s in no_injury
                ],
            },
            "C_dashboard": {
                "name": "dashboard committed CSV",
                "url": SOURCE_LIVE,
                "rows": len(dash_rows),
            },
        },
        "pairs": {
            "B_vs_C": compare(snapshot, dash_rows, "B_snapshot", "C_dashboard"),
            "A_vs_B": compare(evidence, snapshot, "A_live", "B_snapshot"),
            "A_vs_C": compare(evidence, dash_rows, "A_live", "C_dashboard"),
        },
        "totals": {
            "evidence_rows": len(evidence),
            "snapshot_rows": len(snapshot),
            "dashboard_rows": len(dash_rows),
            "evidence_no_injury_teams": [
                line.split(":", 1)[1].strip()
                for line in EVIDENCE.read_text().splitlines()
                if line.startswith("# NO_INJURIES:")
            ],
        },
    }

    # Summary counts for the report page
    for name, pair in results["pairs"].items():
        pair["summary"] = (
            f"{pair['exact_matches']}/{pair['matched_keys']} matched keys agree on all fields; "
            f"{len(pair['only_in_a'])} only in {pair['a']}; "
            f"{len(pair['only_in_b'])} only in {pair['b']}; "
            f"{len(pair['field_diffs'])} field-level differences"
        )

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary
    print(f"evidence rows: {len(evidence)}  snapshot rows: {len(snapshot)}  dashboard rows: {len(dash_rows)}")
    for name, pair in results["pairs"].items():
        print(f"\n[{name}] {pair['summary']}")
        for item in pair["only_in_a"]:
            print(f"  only in {pair['a']}: {item['key']}")
        for item in pair["only_in_b"]:
            print(f"  only in {pair['b']}: {item['key']}")
        for item in pair["field_diffs"]:
            print(f"  field diff {item['key']}: {item['diffs']}")
    print(f"\nday/matchup context differences A vs B: {len(ctx_diffs)}")
    for item in ctx_diffs:
        print(f"  context diff {item['key']}: {item['A_live']} != {item['B_snapshot']}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
