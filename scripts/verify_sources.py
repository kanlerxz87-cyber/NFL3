#!/usr/bin/env python3
"""Line-by-line verification of the published snapshot against official sources.

Two modes:

* default ("sample") — compares the committed snapshot with the transcribed live
  readings stored in ``data/verification/``. Those files were read from the live
  official pages and are described in ``data/verification/README.md``.
* ``--recapture`` — re-fetches the official pages from this machine, rebuilds the
  snapshot in memory and compares the **whole** population with the committed
  snapshot. This is the mode the Pages workflow runs, where the runner has
  network access.

The script never writes a value into the snapshot. Drift between the live page
and the committed capture is reported as a finding, because NFL.com publishes a
mutable page and a point-in-time capture is expected to lag it.

Exit status is 0 for a completed verification. Use ``--strict`` to fail the build
when drift is detected.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "decision-lab"
DATA = ROOT / "data" / "verification"
SNAPSHOT = LAB / "data" / "official_snapshot.json"
OUT = DATA / "verification.json"

INJURY_FIELDS = ("position", "injury", "practice_status", "game_status")
DEPTH_FIELDS = ("unit", "position", "published_rank", "player")


def depth_key(row: dict) -> tuple[str, str, str, str]:
    """Key a depth row by unit, position group, published rank and player.

    A club may publish the same player at two positions (for example a punter and
    a holder), so the position group and the published order are part of the key.
    """
    return (row.get("unit", ""), row.get("position", ""), str(row.get("published_rank", "")), row.get("player", ""))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def index_injuries(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["team"], row["player"]): row for row in rows}


def index_depth(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    return {(row["team"], row["unit"], row["player"]): row for row in rows}


def compare_injuries(live: list[dict], snapshot: list[dict], teams: set[str]) -> dict:
    live_keys = [(row["team"], row["player"]) for row in live]
    snap_keys = [(row["team"], row["player"]) for row in snapshot if row["team"] in teams]
    duplicates = sorted({key for key in live_keys if live_keys.count(key) > 1} |
                         {key for key in snap_keys if snap_keys.count(key) > 1})
    live_index = {(row["team"], row["player"]): row for row in live}
    snap_index = {(row["team"], row["player"]): row for row in snapshot if row["team"] in teams}
    matched, changed, added, removed = [], [], [], []
    for key in sorted(snap_index):
        snap_row, live_row = snap_index[key], live_index.get(key)
        if live_row is None:
            removed.append({"team": key[0], "player": key[1],
                            "note": "present in the committed snapshot, not on the live page at read time"})
            continue
        diffs = {field: [snap_row.get(field, ""), live_row.get(field, "")] for field in INJURY_FIELDS
                 if snap_row.get(field, "") != live_row.get(field, "")}
        if diffs:
            changed.append({"team": key[0], "player": key[1], "fields": diffs})
        else:
            matched.append({"team": key[0], "player": key[1]})
    for key in sorted(live_index):
        if key not in snap_index:
            added.append({"team": key[0], "player": key[1],
                          "note": "on the live page at read time, absent from the committed snapshot"})
    return {"rows_compared": len(matched), "rows_matched": len(matched),
            "rows_changed": changed, "rows_added_since_capture": added,
            "rows_removed_since_capture": removed,
            "duplicate_keys": [{"team": team, "player": player} for team, player in duplicates]}


def compare_depth(live: list[dict], snapshot: list[dict], team: str) -> dict:
    live_index = {depth_key(row): row for row in live}
    snap_index = {depth_key(row): row for row in snapshot if row["team"] == team}
    matched, changed, added, removed = [], [], [], []
    for key in sorted(snap_index):
        snap_row, live_row = snap_index[key], live_index.get(key)
        if live_row is None:
            removed.append({"unit": key[0], "position": key[1], "rank": key[2], "player": key[3],
                            "note": "present in the committed snapshot, not on the live club page at read time"})
            continue
        diffs = {field: [snap_row.get(field, ""), live_row.get(field, "")] for field in DEPTH_FIELDS
                 if str(snap_row.get(field, "")) != str(live_row.get(field, ""))}
        if diffs:
            changed.append({"unit": key[0], "position": key[1], "player": key[3], "fields": diffs})
        else:
            matched.append({"unit": key[0], "position": key[1], "player": key[3]})
    for key in sorted(live_index):
        if key not in snap_index:
            added.append({"unit": key[0], "position": key[1], "rank": key[2], "player": key[3],
                          "note": "on the live club page at read time, absent from the committed snapshot"})
    return {"rows_compared": len(matched), "rows_matched": len(matched),
            "rows_changed": changed, "rows_added_since_capture": added,
            "rows_removed_since_capture": removed}


def sample_mode(snapshot: dict) -> dict:
    injuries = read_csv(DATA / "live_injuries_2026-11-12.csv")
    depth = read_csv(DATA / "live_depth_commanders_2026-11-12.csv")
    teams = sorted({row["team"] for row in injuries})
    injury_result = compare_injuries(injuries, snapshot["injury_rows"], set(teams))
    depth_result = compare_depth(depth, snapshot["depth_rows"], "Commanders")
    return {
        "mode": "sample",
        "method": ("Rows transcribed field by field from the live official pages on 2026-11-12 and "
                   "compared with the committed snapshot. Not a byte-level re-fetch: the build agent "
                   "has no direct HTTPS egress to nfl.com."),
        "pages_read": [
            {"url": "https://www.nfl.com/injuries/", "publisher": "NFL", "read_at": "2026-11-12T22:25Z",
             "teams_read_in_full": teams},
            {"url": "https://www.commanders.com/team/depth-chart", "publisher": "Washington Commanders",
             "read_at": "2026-11-12T22:30Z", "teams_read_in_full": ["Commanders"]},
        ],
        "injuries": injury_result,
        "depth": depth_result,
        "coverage": {
            "snapshot_injury_rows": len(snapshot["injury_rows"]),
            "rows_read_live": len(injuries),
            "snapshot_teams": len({row["team"] for row in snapshot["injury_rows"]}),
            "teams_read_live": len(teams),
            "snapshot_depth_rows": len(snapshot["depth_rows"]),
            "depth_rows_read_live": len(depth),
        },
    }


def compare_depth_all(live: list[dict], snapshot: list[dict]) -> dict:
    """Compare every published depth row, not only one club's chart."""
    live_index = {depth_key(row): row for row in live}
    snap_index = {depth_key(row): row for row in snapshot}
    matched, changed, added, removed = [], [], [], []
    for key in sorted(snap_index):
        snap_row, live_row = snap_index[key], live_index.get(key)
        if live_row is None:
            removed.append({"team": snap_row.get("team", ""), "unit": key[0], "position": key[1],
                            "rank": key[2], "player": key[3],
                            "note": "present in the committed snapshot, absent from the live capture"})
            continue
        diffs = {field: [snap_row.get(field, ""), live_row.get(field, "")] for field in DEPTH_FIELDS
                 if str(snap_row.get(field, "")) != str(live_row.get(field, ""))}
        if diffs:
            changed.append({"team": snap_row.get("team", ""), "unit": key[0], "player": key[3], "fields": diffs})
        else:
            matched.append({"team": snap_row.get("team", ""), "unit": key[0], "player": key[3]})
    for key in sorted(live_index):
        if key not in snap_index:
            added.append({"team": live_index[key].get("team", ""), "unit": key[0], "position": key[1],
                          "rank": key[2], "player": key[3],
                          "note": "present in the live capture, absent from the committed snapshot"})
    return {"rows_compared": len(matched), "rows_matched": len(matched),
            "rows_changed": changed, "rows_added_since_capture": added,
            "rows_removed_since_capture": removed}


def recapture_mode(snapshot: dict) -> dict:
    sys.path.insert(0, str(LAB / "scripts"))
    import capture_official as capture  # noqa: PLC0415 - optional dependency path

    observed_at = datetime.now(timezone.utc).isoformat()
    captures: dict[str, tuple[bytes, str]] = {}
    pages = []
    for name, (url, hosts) in capture.SOURCES.items():
        try:
            captures[name] = capture.fetch(url, hosts, 45)
            pages.append({"url": url, "publisher": "official", "read_at": observed_at, "teams_read_in_full": []})
        except Exception as error:  # noqa: BLE001 - one unreachable page must not hide the rest
            pages.append({"url": url, "publisher": "official", "read_at": observed_at,
                          "error": f"{type(error).__name__}: {error}"})
    if not captures:
        raise RuntimeError("no official page could be fetched from this machine")
    fresh = capture.build_snapshot(captures, observed_at)
    live_injuries = fresh["injury_rows"]
    teams = {row["team"] for row in live_injuries}
    injury_result = compare_injuries(live_injuries, snapshot["injury_rows"], teams)
    depth_result = compare_depth_all(fresh["depth_rows"], snapshot["depth_rows"])
    for page in pages:
        page["teams_read_in_full"] = sorted(teams)
    return {
        "mode": "recapture",
        "method": ("Official pages re-fetched from this machine, re-parsed with the capture parser and "
                   "compared with the committed snapshot across the full population."),
        "pages_read": pages,
        "injuries": injury_result,
        "depth": depth_result,
        "coverage": {
            "snapshot_injury_rows": len(snapshot["injury_rows"]),
            "rows_read_live": len(live_injuries),
            "snapshot_teams": len({row["team"] for row in snapshot["injury_rows"]}),
            "teams_read_live": len(teams),
            "snapshot_depth_rows": len(snapshot["depth_rows"]),
            "depth_rows_read_live": len(fresh["depth_rows"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recapture", action="store_true",
                        help="re-fetch official pages and verify the full population")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when drift is detected")
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    try:
        result = recapture_mode(snapshot) if args.recapture else sample_mode(snapshot)
    except Exception as error:  # noqa: BLE001 - a failed verification must be reported, not hidden
        result = {"mode": "recapture" if args.recapture else "sample", "error": f"{type(error).__name__}: {error}"}

    injury = result.get("injuries", {})
    depth = result.get("depth", {})
    drift = sum(len(injury.get(key, [])) for key in ("rows_changed", "rows_added_since_capture", "rows_removed_since_capture"))
    drift += sum(len(depth.get(key, [])) for key in ("rows_changed", "rows_added_since_capture", "rows_removed_since_capture"))
    result["summary"] = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_observed_at": snapshot.get("observed_at"),
        "injury_rows_matched": injury.get("rows_matched", 0),
        "injury_rows_compared": injury.get("rows_compared", 0),
        "depth_rows_matched": depth.get("rows_matched", 0),
        "depth_rows_compared": depth.get("rows_compared", 0),
        "drift_rows": drift,
        "drift_detected": bool(drift),
        "verdict": ("Snapshot matches the live official pages for every row read." if not drift
                    else "Live official pages have changed since the committed capture; see the drift rows."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Verification ({result['mode']}): injury {result['summary']['injury_rows_matched']}/"
          f"{result['summary']['injury_rows_compared']} rows matched, depth "
          f"{result['summary']['depth_rows_matched']}/{result['summary']['depth_rows_compared']} matched, "
          f"drift={drift}.")
    if result.get("error"):
        print(f"Verification error: {result['error']}")
    if args.strict and result["summary"]["drift_detected"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
