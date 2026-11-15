"""Shared parsing, drift checks and delta logic for the official NFL injury-report archive.

Authority boundary: this module reads bytes captured from https://www.nfl.com/injuries/ and reports
what the page publishes. It does not infer health, participation, replacement assignments or snaps.
Blank source cells stay blank. Any structural surprise is returned as a failure, never repaired.

The HTML parser is the one already verified against this page by decision-lab/scripts/capture_official.py;
it is imported rather than copied so both paths read the page identically.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "captures" / "nfl-injuries"
RAW_DIR = ARCHIVE / "raw"
INDEX = ARCHIVE / "index.jsonl"
BASELINE_SOURCE = ROOT / "decision-lab" / "data" / "official_snapshot.json"
SOURCE_URL = "https://www.nfl.com/injuries/"
ALLOWED_HOSTS = {"www.nfl.com"}
UA = "NFL3-InjuryCapture/1.0 (+https://github.com/kanlerxz87-cyber/NFL3)"

# Pinned vocabularies. An unseen label is a drift alarm, not a value to be guessed or mapped.
PRACTICE_VOCAB = {
    "Did Not Participate In Practice",
    "Limited Participation in Practice",
    "Full Participation in Practice",
}
GAME_VOCAB = {"", "Out", "Doubtful", "Questionable"}
REQUIRED_HEADERS = {"Player", "Position", "Injuries", "Practice Status", "Game Status"}
TITLE_WEEK = re.compile(r"Week\s+(\d+)\s+of\s+the\s+(\d{4})\s+Season", re.I)
TH_PLAYER = re.compile(r"<th[^>]*>\s*Player\s*</th>", re.I)
TH_CELL = re.compile(r"<th[^>]*>(.*?)</th>", re.I | re.S)


def _load_verified_parser():
    path = ROOT / "decision-lab" / "scripts" / "capture_official.py"
    spec = importlib.util.spec_from_file_location("capture_official", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CO = _load_verified_parser()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inspect_html(raw: bytes, final_url: str, observed_at: str) -> dict:
    """Parse one capture and return rows plus every structural failure found.

    `failures` being non-empty means the capture must not be published as a valid read.
    """
    digest = sha256_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    failures: list[str] = []

    title = TITLE_WEEK.search(text)
    week = season = None
    if title:
        week, season = int(title.group(1)), int(title.group(2))
    else:
        failures.append("title: no 'Week N of the YYYY Season' label found")

    day_sections = team_sections = no_results = injury_tables = 0
    header_problems: list[str] = []
    table_data_rows = 0
    for match in CO.TOKEN.finditer(text):
        if match.group("day") is not None:
            day_sections += 1
        elif match.group("team") is not None:
            team_sections += 1
        elif match.group("no_results") is not None:
            if CO.clean(match.group("no_results")):
                no_results += 1
        elif match.group("table") is not None:
            table_html = match.group("table")
            if not TH_PLAYER.search(table_html):
                continue  # not an injury table; the verified parser ignores it too
            injury_tables += 1
            headers = {CO.clean(cell) for cell in TH_CELL.findall(table_html)}
            missing = sorted(REQUIRED_HEADERS - headers)
            if missing:
                header_problems.append(f"injury table {injury_tables} is missing column(s): {', '.join(missing)}")
            for row_match in CO.ROW.finditer(table_html):
                cells = CO.CELL.findall(row_match.group(1))
                if cells and cells[0][0] == "d":
                    table_data_rows += 1
    failures.extend(header_problems)
    if day_sections < 1:
        failures.append("structure: no day headings found")
    if team_sections != injury_tables + no_results:
        failures.append(
            f"structure: {team_sections} team sections but {injury_tables} injury tables + "
            f"{no_results} no-injury notices"
        )

    rows, empty = CO.parse_injuries(text, final_url, observed_at, digest)
    if table_data_rows != len(rows):
        failures.append(f"rows: {table_data_rows} data rows in injury tables but {len(rows)} parsed")
    if not rows and not empty:
        failures.append("rows: no injury evidence parsed")

    for row in rows:
        key = f"{row['team']} / {row['player'] or '(no name)'}"
        for field in ("team", "player", "position", "day"):
            if not row.get(field):
                failures.append(f"row {key}: required field '{field}' is blank")
        if row["practice_status"] not in PRACTICE_VOCAB:
            failures.append(f"row {key}: unrecognised practice status {row['practice_status']!r}")
        if row["game_status"] not in GAME_VOCAB:
            failures.append(f"row {key}: unrecognised game status {row['game_status']!r}")
        if not row["player_url"].startswith("https://www.nfl.com/players/"):
            failures.append(f"row {key}: player link is not an official nfl.com player page")

    return {
        "sha256": digest,
        "bytes": len(raw),
        "week": week,
        "season": season,
        "day_sections": day_sections,
        "team_sections": team_sections,
        "injury_tables": injury_tables,
        "no_injury_sections": len(empty),
        "injury_rows": len(rows),
        "rows": rows,
        "no_results": empty,
        "failures": failures,
    }


def conflict_flags(rows: list[dict]) -> list[str]:
    """Internal-consistency flags. They are reported, never corrected."""
    flags: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["team"], row["player"])
        seen[key] = seen.get(key, 0) + 1
        if row["game_status"] == "Out" and row["practice_status"] == "Full Participation in Practice":
            flags.append(f"{row['team']} / {row['player']}: game status Out but practice Full Participation")
    for (team, player), count in seen.items():
        if count > 1:
            flags.append(f"{team} / {player}: listed {count} times in one report")
    return flags


def read_index() -> list[dict]:
    if not INDEX.exists():
        return []
    return [json.loads(line) for line in INDEX.read_text(encoding="utf-8").splitlines() if line.strip()]


def baseline_capture() -> dict | None:
    """The 2026-11-12 parsed snapshot. Its raw bytes were not retained, so it is labelled as parsed-only."""
    if not BASELINE_SOURCE.exists():
        return None
    data = json.loads(BASELINE_SOURCE.read_text(encoding="utf-8"))
    rows = data.get("injury_rows", [])
    digests = sorted({row.get("source_sha256", "") for row in rows})
    return {
        "id": "baseline",
        "captured_at_utc": data["observed_at"],
        "sha256": digests[0] if len(digests) == 1 else "",
        "week": 10,
        "season": 2026,
        "rows": rows,
        "no_results": data.get("no_injury_sections", []),
        "parsed_only": True,
        "raw_file": "",
    }


def load_archived_capture(entry: dict) -> dict:
    """Re-parse a stored raw capture with the current verified parser."""
    import gzip

    raw = gzip.decompress((ROOT / entry["raw_file"]).read_bytes())
    parsed = inspect_html(raw, entry["final_url"], entry["captured_at_utc"])
    return {
        "id": entry["sha256"][:12],
        "captured_at_utc": entry["captured_at_utc"],
        "sha256": entry["sha256"],
        "week": parsed["week"],
        "season": parsed["season"],
        "rows": parsed["rows"],
        "no_results": parsed["no_results"],
        "parsed_only": False,
        "raw_file": entry["raw_file"],
        "failures": parsed["failures"],
    }


def row_key(row: dict) -> tuple[str, str]:
    return (row["team"], row["player"])


def describe_section(capture: dict, team: str, none_teams: set, rowed_teams: set) -> str:
    if team in none_teams:
        return "No Injuries Reported"
    if team in rowed_teams:
        count = sum(1 for r in capture["rows"] if r["team"] == team)
        return f"{count} row" + ("" if count == 1 else "s")
    return "not in report"


def diff_captures(old: dict, new: dict) -> list[dict]:
    """Field-level changes between two reads. Only differences are returned."""
    changes: list[dict] = []
    base = {"from_utc": old["captured_at_utc"], "to_utc": new["captured_at_utc"],
            "from_id": old["id"], "to_id": new["id"]}
    old_rows = {row_key(r): r for r in old["rows"]}
    new_rows = {row_key(r): r for r in new["rows"]}
    for key in sorted(set(old_rows) | set(new_rows)):
        before, after = old_rows.get(key), new_rows.get(key)
        team, player = key
        if before and after:
            for field, label in (("injury", "Injury"), ("practice_status", "Practice status"),
                                 ("game_status", "Game status")):
                if before[field] != after[field]:
                    changes.append({**base, "kind": "changed", "team": team, "player": player,
                                    "position": after["position"], "field": label,
                                    "before": before[field], "after": after[field],
                                    "player_url": after["player_url"]})
        elif after:
            changes.append({**base, "kind": "added", "team": team, "player": player,
                            "position": after["position"], "field": "Listed on report",
                            "before": "", "after": f"{after['injury'] or 'no injury listed'} · "
                                                   f"{after['practice_status']} · {after['game_status'] or 'no game status'}",
                            "player_url": after["player_url"]})
        else:
            changes.append({**base, "kind": "removed", "team": team, "player": player,
                            "position": before["position"], "field": "Listed on report",
                            "before": f"{before['injury'] or 'no injury listed'} · {before['practice_status']}",
                            "after": "", "player_url": before["player_url"]})
    old_none = {n["team"] for n in old["no_results"]}
    new_none = {n["team"] for n in new["no_results"]}
    old_teams = {r["team"] for r in old["rows"]}
    new_teams = {r["team"] for r in new["rows"]}
    for team in sorted(old_none | old_teams | new_none | new_teams):
        was = describe_section(old, team, old_none, old_teams)
        now = describe_section(new, team, new_none, new_teams)
        if was != now:
            changes.append({**base, "kind": "section", "team": team, "player": "(report section)",
                            "position": "", "field": "Report section", "before": was, "after": now,
                            "player_url": SOURCE_URL})
    return changes
