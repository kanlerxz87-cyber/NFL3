#!/usr/bin/env python3
"""Derive availability and replacement-depth evidence from the official snapshot.

Authority boundary
------------------
Every value produced here is either (a) copied from the captured official NFL
injury report, (b) copied from a captured club-published depth page, or (c) an
explicit count/join of those two. Nothing is inferred:

* A published depth rank is NOT a confirmed starter, snap share or assignment.
* A blank injury ``game_status`` is NOT evidence that a player is active.
* "Next published player" means the next player listed by the club in the same
  unit and position family. It is a research lead, not a confirmed replacement.
* Rows that cannot be joined by exact club + player name are counted as
  unmatched and never guessed.

Output: ``decision-lab/data/availability.json``
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SNAPSHOT = DATA / "official_snapshot.json"

# Position -> family mapping. Documented explicitly so an unmapped label is
# visible instead of silently forced into a family.
FAMILY_BY_POSITION = {
    # offense skill
    "QB": "QB", "RB": "RB", "HB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    # offensive line
    "T": "OL", "OT": "OL", "LT": "OL", "LOT": "OL", "RT": "OL", "ROT": "OL",
    "G": "OL", "OG": "OL", "LG": "OL", "RG": "OL", "C": "OL", "OL": "OL",
    # defensive line / edge
    "DE": "DL", "EDGE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "IDL": "DL",
    "LDE": "DL", "RDE": "DL", "LDT": "DL", "RDT": "DL", "N": "DL",
    # linebackers
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB", "WLB": "LB", "SLB": "LB",
    "SAM": "LB", "WILL": "LB", "MIKE": "LB", "LILB": "LB", "RILB": "LB",
    "LOLB": "LB", "ROLB": "LB",
    # secondary
    "CB": "DB", "LCB": "DB", "RCB": "DB", "NCB": "DB", "NB": "DB", "DB": "DB",
    "S": "S", "FS": "S", "SS": "S",
    # specialists
    "K": "ST", "PK": "ST", "P": "ST", "H": "ST", "LS": "ST",
    "KR": "ST", "KOR": "ST", "PR": "ST", "KO": "ST",
}
# Families where a rank-1 absence is a same-family replacement question.
PLAYING_FAMILIES = {"QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "S"}


def family(position: str) -> str:
    return FAMILY_BY_POSITION.get((position or "").strip().upper(), "UNMAPPED")


def load(path: Path = SNAPSHOT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyse(snapshot: dict) -> dict:
    injuries = snapshot["injury_rows"]
    depth = snapshot["depth_rows"]
    no_injury = snapshot.get("no_injury_sections", [])

    # ---- index depth rows by club + exact player name -------------------
    depth_by_player: dict[tuple[str, str], list[dict]] = defaultdict(list)
    depth_by_club: dict[str, list[dict]] = defaultdict(list)
    for row in depth:
        depth_by_player[(row["team"], row["player"])].append(row)
        depth_by_club[row["team"]].append(row)

    clubs_with_depth = sorted(depth_by_club)
    clubs_on_report = sorted({r["team"] for r in injuries} | {r["team"] for r in no_injury})
    matchup_teams = sorted({r["team"] for r in injuries})
    all_matchups = sorted({r["matchup"] for r in injuries} | {r["matchup"] for r in no_injury})
    represented = {r["team"] for r in injuries} | {r["team"] for r in no_injury}
    no_injury_only = sorted({r["team"] for r in no_injury} - {r["team"] for r in injuries})

    # ---- join injury rows to their club depth evidence ------------------
    matched, unmatched = [], []
    for row in injuries:
        candidates = depth_by_player.get((row["team"], row["player"]))
        if not candidates:
            unmatched.append(row)
            continue
        best = sorted(candidates, key=lambda c: (c["published_rank"], c["unit"]))
        entry = dict(row)
        entry["depth_positions"] = "; ".join(f'{c["unit"]} {c["position"]} #{c["published_rank"]}' for c in best)
        entry["best_rank"] = best[0]["published_rank"]
        entry["best_unit"] = best[0]["unit"]
        entry["best_position"] = best[0]["position"]
        entry["depth_source_url"] = best[0]["source_url"]
        entry["depth_authority"] = best[0]["authority"]
        matched.append(entry)

    # ---- replacement leads: next published player in the same family ----
    replacement_leads = []
    for row in matched:
        if not row["best_rank"] == 1:
            continue  # only published rank-1 players create a depth question
        fam = family(row["best_position"])
        if fam not in PLAYING_FAMILIES:
            continue
        pool = [
            c for c in depth_by_club[row["team"]]
            if c["unit"] == row["best_unit"] and family(c["position"]) == fam
            and c["player"] != row["player"] and c["published_rank"] > 1
        ]
        if not pool:
            replacement_leads.append({
                "team": row["team"], "player": row["player"], "position": row["position"],
                "injury": row["injury"], "practice_status": row["practice_status"],
                "game_status": row["game_status"], "published_slot": row["depth_positions"],
                "next_player": "", "next_position": "", "next_rank": "",
                "next_status": "", "note": "No deeper published player in this unit/position family",
                "report_url": row["source_url"], "depth_url": row["depth_source_url"],
            })
            continue
        pool.sort(key=lambda c: (c["published_rank"], c["player"]))
        best = pool[0]
        next_report = next(
            (r for r in injuries if r["team"] == row["team"] and r["player"] == best["player"]), None
        )
        replacement_leads.append({
            "team": row["team"], "player": row["player"], "position": row["position"],
            "injury": row["injury"], "practice_status": row["practice_status"],
            "game_status": row["game_status"], "published_slot": row["depth_positions"],
            "next_player": best["player"], "next_position": best["position"],
            "next_rank": best["published_rank"],
            "next_status": (
                " | ".join(x for x in [next_report["practice_status"], next_report["game_status"]] if x)
                if next_report else ""
            ),
            "note": "" if next_report else "Next published player is not listed on this week's report",
            "report_url": row["source_url"], "depth_url": row["depth_source_url"],
        })

    # ---- club depth-slot table: which published slots are on the report --
    report_index = {(r["team"], r["player"]): r for r in injuries}
    slots = []
    by_slot: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in depth:
        fam = family(row["position"])
        if fam not in PLAYING_FAMILIES:
            continue
        by_slot[(row["team"], row["unit"], f'{row["position"]}:{fam}')].append(row)
    for (team, unit, slot), rows in sorted(by_slot.items()):
        rows.sort(key=lambda c: c["published_rank"])
        listed = []
        for r in rows[:4]:
            rep = report_index.get((team, r["player"]))
            if rep:
                listed.append({
                    "player": r["player"], "rank": r["published_rank"],
                    "injury": rep["injury"], "practice_status": rep["practice_status"],
                    "game_status": rep["game_status"],
                })
        if not listed:
            continue
        slots.append({
            "team": team, "unit": unit, "slot": slot,
            "listed_on_report": listed,
            "top3_listed": sum(1 for x in listed if x["rank"] <= 3),
            "depth_url": rows[0]["source_url"],
            "report_url": injuries[0]["source_url"],
        })
    slots.sort(key=lambda s: (-s["top3_listed"], s["team"], s["unit"], s["slot"]))

    # ---- report-level counts -------------------------------------------
    game_status_counts = Counter(r["game_status"] or "blank" for r in injuries)
    practice_counts = Counter(r["practice_status"] or "blank" for r in injuries)
    unmatched_by_club = Counter(r["team"] for r in unmatched)
    clubs_without_depth = sorted(set(clubs_on_report) - set(clubs_with_depth))

    return {
        "schema": "nfl3-availability/v1",
        # Deliberately no run timestamp: this artifact is byte-reproducible from the
        # snapshot so CI can assert `git diff --exit-code` and a reviewer can diff it.
        "snapshot_observed_at": snapshot.get("observed_at", ""),
        "method": {
            "join_key": "exact (club, player name) match between the NFL report and the club depth page",
            "rank_semantics": "published column order on the club page; not a confirmed starter, snap share or assignment",
            "position_families": "explicit mapping in decision-lab/scripts/availability.py; unmapped labels are reported, not guessed",
            "replacement_rule": "for a published rank-1 player in a playing family, list the next published player of the same club, unit and position family",
            "blank_rule": "blank report cells and blank replacement/depth fields stay blank",
        },
        "coverage": {
            "injury_rows": len(injuries),
            "clubs_on_report": len(clubs_on_report),
            "clubs_with_depth": len(clubs_with_depth),
            "clubs_on_report_without_depth": clubs_without_depth,
            "matchups": len(all_matchups),
            "clubs_represented": len(represented),
            "every_matchup_club_accounted_for": len(represented) == 2 * len(all_matchups),
            "matchup_teams": len(matchup_teams),
            "clubs_no_injury_only": no_injury_only,
            "matched_rows": len(matched),
            "unmatched_rows": len(unmatched),
            "unmatched_by_club": dict(sorted(unmatched_by_club.items())),
            "replacement_leads": len(replacement_leads),
            "rank1_listed_on_report": sum(1 for r in matched if r["best_rank"] == 1),
            "depth_slots_with_report_listing": len(slots),
            "unmapped_positions": sorted(
                p for p in ({r["position"] for r in injuries} | {r["position"] for r in depth})
                if family(p) == "UNMAPPED"
            ),
        },
        "report_status_counts": {
            "game_status": dict(sorted(game_status_counts.items())),
            "practice_status": dict(sorted(practice_counts.items())),
        },
        "matchups": all_matchups,
        "no_injury_sections": [
            {"team": r["team"], "matchup": r["matchup"], "text": r["text"], "source_url": r["source_url"]}
            for r in no_injury
        ],
        "replacement_leads": replacement_leads,
        "depth_slots": slots,
        "unmatched": [
            {
                "team": r["team"], "player": r["player"], "position": r["position"],
                "injury": r["injury"], "practice_status": r["practice_status"],
                "game_status": r["game_status"], "matchup": r["matchup"],
                "reason": (
                    "club has no captured machine-readable depth page"
                    if r["team"] not in depth_by_club
                    else "name not present on the captured club depth page"
                ),
                "report_url": r["source_url"],
                "depth_url": depth_by_club[r["team"]][0]["source_url"] if r["team"] in depth_by_club else "",
            }
            for r in sorted(unmatched, key=lambda x: (x["team"], x["player"]))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DATA / "availability.json")
    args = parser.parse_args()
    doc = analyse(load(args.snapshot))
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    c = doc["coverage"]
    print(
        f"availability: {c['injury_rows']} report rows, {c['matched_rows']} joined to club depth, "
        f"{c['unmatched_rows']} unmatched, {c['replacement_leads']} replacement leads, "
        f"{len(doc['depth_slots'])} depth slots with report listings -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
