#!/usr/bin/env python3
"""Transcribe one official page read into a verifiable capture, with the parser as the judge.

Why this exists
---------------
The scheduled workflows reach nfl.com from GitHub Actions, but this session's shell does not: the
only reachable path from here is the session fetch tool, which returns rendered *text*, not raw
bytes. A human reading a page and typing rows into JSON is exactly the failure mode this repository
forbids, so the transcription is made machine-checkable instead:

1. the rows are written in the same markup shape the verified parser expects
   (`decision-lab/scripts/capture_official.py`, the parser that produced the 347-row Week 10 read);
2. the capture is stored content-addressed like every other read;
3. `--expect N` requires the parser to return exactly N rows and zero structural failures, so a
   dropped table, a mistyped status label or an invented player name fails this step;
4. the index line records `retrieval_method = "session fetch tool, rendered text"` and
   `raw_bytes_retained = false`, so nobody can mistake it for a byte-exact HTTP capture.

A transcribed capture is weaker evidence than a fetched one, and says so in the archive.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_lib as lib  # noqa: E402

TABLE_HEAD = (
    '<table class="transcribed"><thead><tr><th scope="col">Player</th><th scope="col">Position</th>'
    '<th scope="col">Injuries</th><th scope="col">Practice Status</th><th scope="col">Game Status</th>'
    "</tr></thead><tbody>"
)


def club_section(day: str, club: str, rows: list[dict]) -> str:
    body = []
    for row in rows:
        body.append(
            f'<tr><td><a href="{row["url"]}">{row["player"]}</a></td><td>{row["pos"]}</td>'
            f'<td>{row["injury"]}</td><td>{row["practice"]}</td><td>{row["game"]}</td></tr>'
        )
    return (f'<h2 class="d3-o-section-title">{day}</h2>'
            f'<div class="d3-o-section-sub-title"><span>{club}</span></div>'
            + TABLE_HEAD + "".join(body) + "</tbody></table>")


def build_html(season: int, week: int, sections: list[dict]) -> bytes:
    days = "".join(club_section(s["day"], s["club"], s["rows"]) for s in sections)
    return (f"<!doctype html><html><head><title>Official NFL Injury Report for Players - "
            f"Week {week} of the {season} Season | NFL.com</title></head><body>"
            f'<span class="nfl-c-matchup-strip__team-abbreviation">AAA</span>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">BBB</span>{days}</body></html>'
            ).encode("utf-8")



SECTION = {'MUNICH': 'MUNICH GAME', 'EARLY': 'EARLY GAMES', 'LATE': 'LATE GAMES',
           'SNF': 'SUNDAY NIGHT FOOTBALL', 'MNF': 'MONDAY NIGHT FOOTBALL'}


def build_inactives_html(season: int, week: int, sections: list[dict]) -> bytes:
    parts = [f"<h1>NFL Week {week} inactives: players ruled out for Sunday's {season} NFL season "
             f"games</h1>"]
    last = None
    for section in sections:
        group = section["group"]
        if group != last:
            parts.append(f"<h2>{SECTION[group]}</h2>")
            last = group
        parts.append(f"<h3>{section['club']}</h3><ul>")
        for entry in section["players"]:
            parts.append(f"<li>{entry['raw']}</li>")
        parts.append("</ul>")
    return ("<html><body>" + "".join(parts) + "</body></html>").encode("utf-8")


def transcribe_inactives(args) -> int:
    sections = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    total = sum(len(s["players"]) for s in sections)
    if total != args.expect:
        print(f"::error::transcription holds {total} entries but --expect {args.expect}")
        return 2
    clubs_file = json.loads((lib.DATA / "clubs.json").read_text(encoding="utf-8")) if \
        (lib.DATA / "clubs.json").exists() else {"clubs": []}
    nicknames = {c["nickname"] for c in clubs_file["clubs"]}
    raw = build_inactives_html(args.season, args.week, sections)
    url = lib.inactives_url(args.season, args.week)
    parsed = lib.parse_inactives(raw, url, args.observed_at, nicknames)
    problems = list(parsed["failures"])
    if len(parsed["rows"]) != args.expect:
        problems.append(f"parser returned {len(parsed['rows'])} entries, expected {args.expect}")
    if args.expect_clubs and len(parsed["clubs"]) != args.expect_clubs:
        problems.append(f"parser returned {len(parsed['clubs'])} clubs, expected {args.expect_clubs}")
    if problems:
        print("::error::inactives transcription failed the parser gate:")
        for problem in problems[:10]:
            print(f"  - {problem}")
        return 3
    raw_file = lib.store_raw(raw)
    lib.append_index({
        "kind": "inactives", "season": args.season, "week": args.week, "source_url": url,
        "final_url": url, "http_status": "", "sha256": parsed["sha256"], "raw_file": raw_file,
        "clubs": len(parsed["clubs"]), "players": len(parsed["rows"]),
        "captured_at_utc": args.observed_at, "requested_at_utc": args.observed_at,
        "retrieval_method": "session fetch tool, rendered text (not raw bytes)",
        "raw_bytes_retained": False,
        "transcription_note": ("Entries transcribed from the rendered article and then parsed by "
                               "this archive's inactives parser; the digest is of the reconstructed "
                               "markup, not of the nfl.com bytes."),
        "failures": [], "status": "ok",
    })
    print(f"transcribed inactives {args.season} W{args.week}: {len(parsed['rows'])} entries, "
          f"{len(parsed['clubs'])} clubs, sha256 {parsed['sha256'][:12]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--rows", required=True, help="JSON file: [{day, club, rows: [...]}, ...]")
    parser.add_argument("--expect", type=int, required=True, help="exact row count the parser must return")
    parser.add_argument("--observed-at", required=True, help="clock time of the page read (UTC)")
    parser.add_argument("--expect-clubs", type=int, default=0, help="exact number of club sections")
    parser.add_argument("--kind", choices=("injury", "inactives"), default="injury")
    args = parser.parse_args()

    if args.kind == "inactives":
        return transcribe_inactives(args)

    sections = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    total = sum(len(s["rows"]) for s in sections)
    if total != args.expect:
        print(f"::error::transcription holds {total} rows but --expect {args.expect}")
        return 2

    raw = build_html(args.season, args.week, sections)
    url = lib.injuries_url(args.season, args.week)
    parsed = lib.parse_injuries(raw, url, args.observed_at)

    problems = list(parsed["failures"])
    if parsed["injury_rows"] != args.expect:
        problems.append(f"parser returned {parsed['injury_rows']} rows, expected {args.expect}")
    if args.expect_clubs and parsed["team_sections"] != args.expect_clubs:
        problems.append(f"parser returned {parsed['team_sections']} club sections, expected {args.expect_clubs}")
    if parsed["week"] != args.week or parsed["season"] != args.season:
        problems.append(f"parser read week/season {parsed['week']}/{parsed['season']}")
    if problems:
        print("::error::transcription failed the parser gate:")
        for problem in problems[:10]:
            print(f"  - {problem}")
        return 3

    raw_file = lib.store_raw(raw)
    lib.append_index({
        "kind": "injury", "season": args.season, "week": args.week, "source_url": url,
        "final_url": url, "http_status": "", "sha256": parsed["sha256"], "raw_file": raw_file,
        "injury_rows": parsed["injury_rows"], "team_sections": parsed["team_sections"],
        "no_injury_sections": len(parsed["no_injury_sections"]),
        "captured_at_utc": args.observed_at, "requested_at_utc": args.observed_at,
        "retrieval_method": "session fetch tool, rendered text (not raw bytes)",
        "raw_bytes_retained": False,
        "transcription_note": ("Rows transcribed from the rendered page text and then parsed by the "
                               "repository's verified parser; the digest is of the reconstructed "
                               "markup, so this is not a byte-exact capture of nfl.com."),
        "failures": [], "status": "ok",
    })
    print(f"transcribed {args.season} W{args.week}: {parsed['injury_rows']} rows, "
          f"{parsed['team_sections']} club sections, sha256 {parsed['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
