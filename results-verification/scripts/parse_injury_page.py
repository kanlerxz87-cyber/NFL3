#!/usr/bin/env python3
"""Parse an official NFL.com injury-report page (as rendered to markdown by the page-fetch tool)
into per-player rows: club, player, player_url, position, injuries, practice_status, game_status.

Club attribution: the rendered page emits a bare club-name line immediately before each club table.
Rows are matched on the canonical player URL. Blank cells are preserved as empty strings.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CLUBS = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
    "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Broncos": "DEN", "Colts": "IND",
    "Cowboys": "DAL", "Lions": "DET", "Packers": "GB", "Titans": "TEN", "Texans": "HOU",
    "Chiefs": "KC", "Chargers": "LAC", "Rams": "LA", "Raiders": "LV", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Commanders": "WAS", "Jaguars": "JAX",
    "Seahawks": "SEA", "Buccaneers": "TB",
}

ROW_RE = re.compile(r"^\| \[([^]]+)]\((https://www\.nfl\.com/players/[^)]+)\) \| ([^|]*) \| ([^|]*) \| ([^|]*) \| ([^|]*) \|\s*$")


def parse(text: str) -> dict:
    lines = text.split("\n")
    rows, current_club, no_injury_sections = [], None, []
    week_header = None
    for i, line in enumerate(lines):
        m = re.match(r"^## Injuries - WEEK (\d+)", line)
        if m:
            week_header = int(m.group(1))
        m = re.match(r"^([A-Za-z0-9'&.\- ]+)$", line.strip())
        if m and m.group(1).strip() in CLUBS:
            current_club = m.group(1).strip()
        if line.strip().startswith("| Player | Position | Injuries | Practice Status | Game Status |"):
            # table follows; subsequent club tables will reset current_club via a new bare club line
            pass
        rm = ROW_RE.match(line)
        if rm:
            name, url, pos, inj, prac, game = rm.groups()
            rows.append({
                "club": current_club,
                "club_code": CLUBS.get(current_club) if current_club else None,
                "player": name.strip(),
                "player_url": url.strip(),
                "position": pos.strip(),
                "injuries": inj.strip(),
                "practice_status": prac.strip(),
                "game_status": game.strip(),
                "line": i + 1,
            })
        if re.match(r"^#{2,3} .*(No Injuries Reported|no injuries)", line, re.I):
            no_injury_sections.append(line.strip())
    return {"week": week_header, "rows": rows, "no_injury_sections": no_injury_sections}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 2:
        print("usage: parse_injury_page.py <input.md> <output.json>")
        return 2
    src, dst = Path(args[0]), Path(args[1])
    text = src.read_text(encoding="utf-8")
    parsed = parse(text)
    out = {
        "source_file": str(src),
        "sha256_of_file": sha256(src),
        "week": parsed["week"],
        "row_count": len(parsed["rows"]),
        "no_injury_sections": parsed["no_injury_sections"],
        "rows": parsed["rows"],
    }
    dst.write_text(json.dumps(out, indent=1))
    print(f"parsed {len(parsed['rows'])} rows, week {parsed['week']}, "
          f"{len(parsed['no_injury_sections'])} no-injury sections -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
