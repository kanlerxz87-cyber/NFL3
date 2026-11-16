#!/usr/bin/env python3
"""Aggregate the newest hashed official injury-report capture and diff it with the committed baseline.

Why this exists: several published pages still carry the 2026-11-12 read (254 rows) as though it were
current, while the archive holds a 2026-11-15/16 read with 347 rows. The correction is computed here
from bytes that are already committed and hash-pinned, so it needs no network and no hand transcription.

Privacy boundary: the club-level aggregates are published; row-level names are not republished here,
because the public-analysis / private-data-layer split (requirements register) is still an open owner
decision. The count of blank cells is published so the gap is visible without exposing the rows.

Outputs `data/availability_w10.json` and `data/availability_w10.csv`.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"

spec = importlib.util.spec_from_file_location("injury_capture_common", ROOT / "injury-capture" / "scripts" / "common.py")
if spec is None or spec.loader is None:
    raise SystemExit("forward-ledger/availability_w10: cannot load the verified injury parser")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)

GAME_ORDER = ["Out", "Doubtful", "Questionable", ""]
PRACTICE_ORDER = ["Did Not Participate In Practice", "Limited Participation in Practice", "Full Participation in Practice"]


def club_profile(rows: list[dict], club: str) -> dict:
    mine = [r for r in rows if r["team"] == club]
    game = Counter(r["game_status"] for r in mine)
    practice = Counter(r["practice_status"] for r in mine)
    return {
        "club": club,
        "rows": len(mine),
        "game_out": game.get("Out", 0),
        "game_doubtful": game.get("Doubtful", 0),
        "game_questionable": game.get("Questionable", 0),
        "game_status_blank": game.get("", 0),
        "practice_dnp": practice.get("Did Not Participate In Practice", 0),
        "practice_lp": practice.get("Limited Participation in Practice", 0),
        "practice_fp": practice.get("Full Participation in Practice", 0),
        "injury_named": sum(1 for r in mine if (r.get("injury") or "").strip()),
        "injury_blank": sum(1 for r in mine if not (r.get("injury") or "").strip()),
        "official_player_links": sum(1 for r in mine if str(r.get("player_url", "")).startswith("https://www.nfl.com/players/")),
    }


def main() -> int:
    index = common.read_index()
    ok = [entry for entry in index if entry.get("status") == "ok" and entry.get("raw_file")]
    if not ok:
        raise SystemExit("forward-ledger/availability_w10: the archive holds no successful capture with retained bytes")
    newest = ok[-1]
    capture = common.load_archived_capture(newest)
    if capture["failures"]:
        raise SystemExit(f"forward-ledger/availability_w10: the newest capture fails its own structure check: "
                         f"{capture['failures'][:3]}")
    rows = capture["rows"]
    baseline = common.baseline_capture()
    base_rows = baseline["rows"] if baseline else []

    clubs = sorted({r["team"] for r in rows})
    base_clubs = {r["team"] for r in base_rows}
    profiles = [club_profile(rows, club) for club in clubs]
    base_by_club = {club: len([r for r in base_rows if r["team"] == club]) for club in sorted(base_clubs)}
    for profile in profiles:
        before = base_by_club.get(profile["club"])
        profile["rows_2026_11_12"] = "" if before is None else before
        profile["row_delta"] = "" if before is None else profile["rows"] - before
    missing_clubs = sorted(base_clubs - set(clubs))

    game_counts = Counter(r["game_status"] for r in rows)
    practice_counts = Counter(r["practice_status"] for r in rows)
    base_game_counts = Counter(r["game_status"] for r in base_rows)
    keyed_base = {common.row_key(r): r for r in base_rows}
    keyed_new = {common.row_key(r): r for r in rows}
    added = sorted(set(keyed_new) - set(keyed_base))
    removed = sorted(set(keyed_base) - set(keyed_new))
    designation_changes = [k for k in sorted(set(keyed_base) & set(keyed_new))
                           if keyed_base[k]["game_status"] != keyed_new[k]["game_status"]]
    practice_changes = [k for k in sorted(set(keyed_base) & set(keyed_new))
                        if keyed_base[k]["practice_status"] != keyed_new[k]["practice_status"]]

    summary = {
        "schema": "nfl3-forward-ledger-availability/v1",
        "source_url": newest["source_url"],
        "capture": {
            "captured_at_utc": capture["captured_at_utc"],
            "sha256": capture["sha256"],
            "bytes": newest["bytes"],
            "raw_file": newest["raw_file"],
            "week": capture["week"],
            "season": capture["season"],
            "archive_reads_recorded": len(index),
            "archive_read_note": "index.jsonl holds one line per read including failed ones; "
                                 f"this profile uses the newest read whose status is ok: {newest['captured_at_utc']}",
        },
        "rows": len(rows),
        "clubs_with_a_table": len(clubs),
        "no_injury_sections": len(capture["no_results"]),
        "clubs_listed_as_injury_free": sorted(capture["no_results"]),
        "game_status_counts": {label: game_counts.get(label, 0) for label in GAME_ORDER},
        "practice_status_counts": {label: practice_counts.get(label, 0) for label in PRACTICE_ORDER},
        "rows_with_a_game_designation": sum(v for k, v in game_counts.items() if k),
        "blank_game_status_cells": game_counts.get("", 0),
        "injury_text_blank": sum(1 for r in rows if not (r.get("injury") or "").strip()),
        "player_links_official": sum(1 for r in rows if str(r.get("player_url", "")).startswith("https://www.nfl.com/players/")),
        "conflict_flags": newest.get("conflict_flags", []),
        "delta_vs_2026_11_12_baseline": {
            "baseline_captured_at_utc": (baseline or {}).get("captured_at_utc", ""),
            "baseline_rows": len(base_rows),
            "baseline_game_status_counts": {label: base_game_counts.get(label, 0) for label in GAME_ORDER},
            "baseline_rows_with_designation": sum(v for k, v in base_game_counts.items() if k),
            "rows_added": len(added),
            "rows_removed": len(removed),
            "game_designation_changes": len(designation_changes),
            "practice_status_changes": len(practice_changes),
            "clubs_present_now_but_not_then": sorted(set(clubs) - base_clubs),
            "clubs_present_then_but_not_now": missing_clubs,
            "note": "The baseline's raw bytes were not retained (it is a parsed-only snapshot), so the delta is "
                    "reported as a count of changes, not as a per-row replay of the morning state.",
        },
        "per_club": profiles,
        "privacy_note": "Club-level aggregates only. Row-level player rows stay in the hash-pinned capture under "
                        "captures/nfl-injuries/raw/ and are not republished here until the public-analysis / "
                        "private-data-layer decision is recorded.",
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "availability_w10.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (DATA / "availability_w10.csv").open("w", encoding="utf-8", newline="") as fh:
        fields = [key for key in profiles[0]]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(profiles)
    print(f"availability: {summary['rows']} rows across {summary['clubs_with_a_table']} clubs "
          f"from capture {summary['capture']['sha256'][:12]} at {summary['capture']['captured_at_utc']}")
    print(f"designations: {summary['rows_with_a_game_designation']} rows carry a game status, "
          f"{summary['blank_game_status_cells']} are blank; vs baseline {len(base_rows)} rows "
          f"({summary['delta_vs_2026_11_12_baseline']['baseline_rows_with_designation']} designated)")
    print(f"delta: +{len(added)} rows, -{len(removed)} rows, {len(designation_changes)} designation changes, "
          f"{len(practice_changes)} practice changes; conflict flags {len(summary['conflict_flags'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
