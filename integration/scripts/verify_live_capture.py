#!/usr/bin/env python3
"""Compare the published injury view with a fresh capture of the official page.

Reads a raw capture of https://www.nfl.com/injuries/ (the page rendered to text by
the session's page-fetch tool), parses every injury row out of it, and compares
the result field by field with the rows this repository publishes.

Nothing here infers a value. A difference is reported as a difference; a row that
cannot be matched is reported as unmatched with a reason. The output is the
evidence behind the "Flagged for Review" page, not a correction to it.

Usage:
    python3 integration/scripts/verify_live_capture.py
    python3 integration/scripts/verify_live_capture.py --capture <file> --label "<text>"

The capture directory must contain `manifest.json` describing the capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "integration"
CAPTURE_DIR = INTEGRATION / "data" / "captures" / "2026-11-13-nfl-injuries"
CAPTURE_FILE = CAPTURE_DIR / "nfl-injuries-2026-11-13.md"

sys.path.insert(0, str(ROOT / "ops-center" / "scripts"))
import model  # noqa: E402  (read-only import; reuses the published merge logic)

INJURY_URL = "https://www.nfl.com/injuries/"

CLUBS = [
    "Commanders", "Giants", "Patriots", "Lions", "Chiefs", "Falcons", "Vikings",
    "Packers", "Jaguars", "Titans", "Bills", "Jets", "Dolphins", "Colts",
    "Panthers", "Saints", "Texans", "Browns", "Rams", "Cardinals", "Seahawks",
    "Raiders", "49ers", "Cowboys", "Steelers", "Bengals", "Chargers", "Ravens",
    "Eagles", "Bears", "Dolphins", "Broncos",
]

ROW = "| ["


def parse_capture(text: str) -> dict:
    """Parse the rendered capture into rows keyed by (team, player)."""
    rows: dict[tuple[str, str], dict] = {}
    no_injury: list[str] = []
    team = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("|") and not line.startswith(ROW):
            continue  # table separator or header row
        if line.startswith(ROW):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 5:
                continue
            name_cell = cells[0]
            if "[" not in name_cell or "]" not in name_cell:
                continue
            player = name_cell[name_cell.index("[") + 1:name_cell.index("]")]
            url = name_cell[name_cell.index("](") + 2:name_cell.rindex(")")] if "](" in name_cell else ""
            key = (team, player)
            rows[key] = {
                "team": team,
                "player": player,
                "position": cells[1],
                "injury": cells[2],
                "practice_status": cells[3],
                "game_status": cells[4],
                "player_url": url,
            }
            continue
        if line in CLUBS:
            team = line
            continue
        if line == "No Injuries Reported":
            no_injury.append(team)
            continue
    return {"rows": rows, "no_injury_sections": no_injury}


def published_rows() -> dict[tuple[str, str], dict]:
    """The injury view this repository publishes: capture + later re-observation."""
    snapshot = model.load_snapshot()
    recheck = model.load_recheck()
    merged = model.merge_recheck(snapshot, recheck)
    out: dict[tuple[str, str], dict] = {}
    for row in merged:
        out[(row["team"], row["player"])] = {
            "team": row["team"],
            "player": row["player"],
            "position": row.get("position", ""),
            "injury": row.get("injury", ""),
            "practice_status": row.get("practice_status", ""),
            "game_status": row.get("game_status", ""),
            "player_url": row.get("player_url", ""),
            "origin": row.get("origin", ""),
            "observed_at": row.get("observed_at", ""),
        }
    return out


FIELDS = ("position", "injury", "practice_status", "game_status")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", default=str(CAPTURE_FILE))
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    capture_path = Path(args.capture)
    raw = capture_path.read_bytes()
    text = raw.decode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()

    manifest_path = capture_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    live = parse_capture(text)
    pub = published_rows()

    matched, drift, unmatched_pub, new_live = [], [], [], []
    for key, prow in pub.items():
        lrow = live["rows"].get(key)
        if lrow is None:
            unmatched_pub.append(prow)
            continue
        diffs = {f: {"published": prow.get(f, ""), "live": lrow.get(f, "")}
                 for f in FIELDS if prow.get(f, "") != lrow.get(f, "")}
        if diffs:
            drift.append({"team": prow["team"], "player": prow["player"],
                          "origin": prow.get("origin", ""), "differences": diffs})
        else:
            matched.append({"team": prow["team"], "player": prow["player"]})
    for key, lrow in live["rows"].items():
        if key not in pub:
            new_live.append(lrow)

    published_no_injury = {
        s["team"] for s in json.loads(
            (ROOT / "decision-lab" / "data" / "official_snapshot.json").read_text(encoding="utf-8")
        )["no_injury_sections"]
    }
    live_no_injury = set(live["no_injury_sections"])
    still_no_injury = sorted(published_no_injury & live_no_injury)
    now_reporting = sorted(published_no_injury - live_no_injury)
    new_no_injury = sorted(live_no_injury - published_no_injury)

    report = {
        "schema_version": 1,
        "generated_by": "integration/scripts/verify_live_capture.py (session arena/af49b4f9-nfl3)",
        "capture": {
            "url": manifest.get("url", INJURY_URL),
            "label": args.label or manifest.get("label", ""),
            "file": str(capture_path.relative_to(ROOT)),
            "bytes": len(raw),
            "sha256": digest,
            "observed_at": manifest.get("observed_at", ""),
            "method": manifest.get("method", ""),
        },
        "counts": {
            "published_rows": len(pub),
            "live_rows": len(live["rows"]),
            "matched": len(matched),
            "drifted": len(drift),
            "published_not_on_live_page": len(unmatched_pub),
            "on_live_page_not_published": len(new_live),
            "teams_reporting_no_injuries_published": len(published_no_injury),
            "teams_reporting_no_injuries_live": len(live_no_injury),
        },
        "drift": drift,
        "published_not_on_live_page": unmatched_pub,
        "on_live_page_not_published": new_live,
        "no_injury_sections": {
            "published": sorted(published_no_injury),
            "live": sorted(live_no_injury),
            "still_no_injuries": still_no_injury,
            "now_reporting_players": now_reporting,
            "newly_no_injuries": new_no_injury,
        },
        "boundary": (
            "A difference here is a difference between two observations of a mutable official "
            "page, not an error in either. The published view is not corrected by this script; "
            "the difference is published so a reviewer can decide."
        ),
    }

    out = INTEGRATION / "data" / "verification.json"
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    c = report["counts"]
    print(f"capture {capture_path.name}: {c['live_rows']} live rows, sha256 {digest[:16]}...")
    print(f"published rows: {c['published_rows']}")
    print(f"  identical: {c['matched']}")
    print(f"  drifted:   {c['drifted']}")
    print(f"  published but not on the live page: {c['published_not_on_live_page']}")
    print(f"  on the live page but not published:  {c['on_live_page_not_published']}")
    print(f"  teams now reporting players that published 'No Injuries Reported': {now_reporting}")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
