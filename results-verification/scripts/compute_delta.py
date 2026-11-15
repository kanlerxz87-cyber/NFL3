#!/usr/bin/env python3
"""Compute the per-player delta between two parsed injury-report observations.

Players are matched on the canonical https://www.nfl.com/players/... URL. The delta lists changes
only (the delta, never the level): designation changes, practice-status changes, injury-text
changes, club reassignments, rows added to and removed from the later observation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIELDS = ("position", "injuries", "practice_status", "game_status")


def main() -> int:
    baseline_path, observation_path, out_path = sys.argv[1:4]
    base = json.loads(Path(baseline_path).read_text())
    obs = json.loads(Path(observation_path).read_text())

    base_by_url: dict[str, dict] = {}
    for r in base["rows"]:
        if r["player_url"] in base_by_url:
            print(f"FAIL duplicate player URL in baseline: {r['player_url']}")
            return 1
        base_by_url[r["player_url"]] = r
    obs_by_url: dict[str, dict] = {}
    for r in obs["rows"]:
        if r["player_url"] in obs_by_url:
            print(f"FAIL duplicate player URL in observation: {r['player_url']}")
            return 1
        obs_by_url[r["player_url"]] = r

    changes, added, removed = [], [], []
    for url, o in obs_by_url.items():
        b = base_by_url.get(url)
        if b is None:
            added.append(o)
            continue
        diffs = {}
        for f in FIELDS:
            if b[f] != o[f]:
                diffs[f] = {"baseline": b[f], "observation": o[f]}
        if b["club"] != o["club"]:
            diffs["club"] = {"baseline": b["club"], "observation": o["club"]}
        if diffs:
            entry = {
                "player": o["player"],
                "player_url": url,
                "club": o["club"],
                "position": o["position"],
                "baseline_observed_at": base["observed_at"],
                "observation_observed_at": obs["observed_at"],
                "changes": diffs,
            }
            changes.append(entry)
    for url, b in base_by_url.items():
        if url not in obs_by_url:
            removed.append(b)

    root = Path(__file__).resolve().parents[2]
    base_p, obs_p = Path(baseline_path).resolve(), Path(observation_path).resolve()
    out = {
        "schema_version": 1,
        "generated_by": "results-verification/scripts/compute_delta.py (session arena/16183225-nfl3)",
        "baseline": {
            "file": str(base_p.relative_to(root)),
            "observed_at": base["observed_at"],
            "rows": base["row_count"],
            "clubs": len({r["club"] for r in base["rows"]}),
            "sha256_of_source_page": base["sha256_of_file"],
        },
        "observation": {
            "file": str(obs_p.relative_to(root)),
            "observed_at": obs["observed_at"],
            "rows": obs["row_count"],
            "clubs": len({r["club"] for r in obs["rows"]}),
            "sha256_of_source_page": obs["sha256_of_file"],
        },
        "counts": {
            "players_on_both": len(obs_by_url) - len(added),
            "rows_with_changes": len(changes),
            "rows_added_to_later_observation": len(added),
            "rows_removed_from_later_observation": len(removed),
            "game_status_changes": sum(1 for c in changes if "game_status" in c["changes"]),
            "practice_status_changes": sum(1 for c in changes if "practice_status" in c["changes"]),
            "club_reassignments": sum(1 for c in changes if "club" in c["changes"]),
        },
        "changes": changes,
        "added": [{"player": a["player"], "club": a["club"], "player_url": a["player_url"],
                   "practice_status": a["practice_status"], "game_status": a["game_status"]} for a in added],
        "removed": [{"player": r["player"], "club": r["club"], "player_url": r["player_url"],
                     "practice_status": r["practice_status"], "game_status": r["game_status"]} for r in removed],
    }
    Path(out_path).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["counts"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
