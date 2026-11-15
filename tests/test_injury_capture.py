#!/usr/bin/env python3
"""Offline tests for the injury-report archive. Fixtures are SYNTHETIC (invented names, same markup
shape as the verified parser expects). They prove the drift alarms, the delta logic and the archive
behaviour; they are not evidence about any NFL player or the live page."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "injury-capture" / "scripts"))
import common  # noqa: E402
import capture  # noqa: E402

TEAM_HEAD = '<div class="d3-o-section-sub-title"><span>{team}</span></div>'
TABLE_HEAD = (
    '<table class="x"><thead><tr><th scope="col">Player</th><th scope="col">Position</th>'
    '<th scope="col">Injuries</th><th scope="col">Practice Status</th><th scope="col">Game Status</th>'
    "</tr></thead><tbody>"
)


def player_row(name: str, slug: str, pos: str, injury: str, practice: str, game: str) -> str:
    return (f'<tr><td><a href="https://www.nfl.com/players/{slug}/">{name}</a></td><td>{pos}</td>'
            f"<td>{injury}</td><td>{practice}</td><td>{game}</td></tr>")


def page(sections: str, week: int = 10, season: int = 2026) -> bytes:
    html = (f"<!doctype html><html><head><title>Official Latest NFL Injury Report for Players - "
            f"Week {week} of the {season} Season | NFL.com</title></head><body>"
            f'<h2 class="d3-o-section-title">SUNDAY, NOVEMBER 15TH</h2>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">AAA</span>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">BBB</span>{sections}</body></html>')
    return html.encode("utf-8")


GOOD = (
    TEAM_HEAD.format(team="Alpha") + TABLE_HEAD
    + player_row("Test Player One", "test-player-one", "WR", "Knee", "Did Not Participate In Practice", "Out")
    + player_row("Test Player Two", "test-player-two", "CB", "", "Full Participation in Practice", "")
    + "</tbody></table>"
    + TEAM_HEAD.format(team="Bravo")
    + '<p class="nfl-o-no-results__text">No Injuries Reported</p>'
)
URL = "https://www.nfl.com/injuries/"
OBSERVED = "2026-11-15T13:00:00Z"


class StructureTests(unittest.TestCase):
    def test_clean_fixture_has_no_failures(self):
        result = common.inspect_html(page(GOOD), URL, OBSERVED)
        self.assertEqual(result["failures"], [])
        self.assertEqual((result["week"], result["season"]), (10, 2026))
        self.assertEqual(result["injury_rows"], 2)
        self.assertEqual(result["no_injury_sections"], 1)
        self.assertEqual(result["team_sections"], 2)

    def test_missing_column_fails_loudly(self):
        broken = GOOD.replace('<th scope="col">Game Status</th>', "", 1)
        result = common.inspect_html(page(broken), URL, OBSERVED)
        self.assertTrue(any("missing column(s): Game Status" in f for f in result["failures"]))

    def test_unknown_game_label_fails(self):
        changed = GOOD.replace(">Out</td>", ">Probable</td>", 1)
        result = common.inspect_html(page(changed), URL, OBSERVED)
        self.assertTrue(any("unrecognised game status 'Probable'" in f for f in result["failures"]))

    def test_unknown_practice_label_fails(self):
        changed = GOOD.replace("Full Participation in Practice", "Walkthrough", 1)
        result = common.inspect_html(page(changed), URL, OBSERVED)
        self.assertTrue(any("unrecognised practice status" in f for f in result["failures"]))

    def test_team_without_table_or_notice_fails(self):
        dropped = GOOD.replace('<p class="nfl-o-no-results__text">No Injuries Reported</p>', "", 1)
        result = common.inspect_html(page(dropped), URL, OBSERVED)
        self.assertTrue(any(f.startswith("structure: 2 team sections") for f in result["failures"]))

    def test_missing_week_label_fails(self):
        raw = page(GOOD).replace(b"Week 10 of the 2026 Season", b"Pre-season")
        result = common.inspect_html(raw, URL, OBSERVED)
        self.assertTrue(any("no 'Week N of the YYYY Season'" in f for f in result["failures"]))

    def test_blank_practice_status_fails(self):
        changed = GOOD.replace("Full Participation in Practice", "", 1)
        result = common.inspect_html(page(changed), URL, OBSERVED)
        self.assertTrue(any("practice status ''" in f for f in result["failures"]))


class DeltaTests(unittest.TestCase):
    def capture_of(self, html_bytes: bytes, cid: str, when: str) -> dict:
        result = common.inspect_html(html_bytes, URL, when)
        return {"id": cid, "captured_at_utc": when, "rows": result["rows"], "no_results": result["no_results"],
                "week": result["week"], "season": result["season"], "failures": result["failures"]}

    def test_changes_are_field_level(self):
        newer = (
            TEAM_HEAD.format(team="Alpha") + TABLE_HEAD
            + player_row("Test Player One", "test-player-one", "WR", "Knee", "Limited Participation in Practice", "Questionable")
            + player_row("Test Player Three", "test-player-three", "S", "Hip", "Did Not Participate In Practice", "Out")
            + "</tbody></table>"
            + TEAM_HEAD.format(team="Bravo") + TABLE_HEAD
            + player_row("Test Player Four", "test-player-four", "DT", "Back", "Limited Participation in Practice", "")
            + "</tbody></table>"
        )
        old = self.capture_of(page(GOOD), "a", "2026-11-14T00:00:00Z")
        new = self.capture_of(page(newer), "b", "2026-11-15T00:00:00Z")
        kinds = {(c["kind"], c["player"], c["field"]) for c in common.diff_captures(old, new)}
        sections = {(c["kind"], c["team"], c["before"], c["after"]) for c in common.diff_captures(old, new)
                    if c["kind"] == "section"}
        self.assertIn(("section", "Bravo", "No Injuries Reported", "1 row"), sections)
        self.assertIn(("changed", "Test Player One", "Practice status"), kinds)
        self.assertIn(("changed", "Test Player One", "Game status"), kinds)
        self.assertIn(("removed", "Test Player Two", "Listed on report"), kinds)
        self.assertIn(("added", "Test Player Three", "Listed on report"), kinds)
        self.assertNotIn(("changed", "Test Player One", "Injury"), kinds)

    def test_identical_reads_produce_no_delta(self):
        a = self.capture_of(page(GOOD), "a", "2026-11-14T00:00:00Z")
        b = self.capture_of(page(GOOD), "b", "2026-11-15T00:00:00Z")
        self.assertEqual(common.diff_captures(a, b), [])

    def test_conflict_flags(self):
        rows = [{"team": "T", "player": "P", "game_status": "Out", "practice_status": "Full Participation in Practice"}]
        flags = common.conflict_flags(rows * 2)
        self.assertTrue(any("game status Out but practice Full" in f for f in flags))
        self.assertTrue(any("listed 2 times" in f for f in flags))


class ArchiveTests(unittest.TestCase):
    def test_reads_are_recorded_and_raw_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            ok = page(GOOD)
            self.assertEqual(capture.record_read(archive, ok, URL, 200, OBSERVED, OBSERVED, URL), 0)
            self.assertEqual(capture.record_read(archive, ok, URL, 200, OBSERVED, "2026-11-15T19:00:00Z", URL), 0)
            lines = (archive / "index.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 2)  # every read recorded, even when unchanged
            raw_files = list((archive / "raw").glob("*.html.gz"))
            self.assertEqual(len(raw_files), 1)  # identical bytes stored once
            import json
            second = json.loads(lines[1])
            self.assertFalse(second["changed_vs_previous"])
            self.assertEqual(second["status"], "ok")

    def test_drift_is_recorded_and_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            broken = page(GOOD.replace('<th scope="col">Game Status</th>', "", 1))
            self.assertEqual(capture.record_read(archive, broken, URL, 200, OBSERVED, OBSERVED, URL), 3)
            import json
            entry = json.loads((archive / "index.jsonl").read_text().splitlines()[0])
            self.assertEqual(entry["status"], "drift")
            self.assertTrue(entry["failures"])
            self.assertEqual(len(list((archive / "raw").glob("*.html.gz"))), 1)  # evidence kept

    def test_fetch_failure_is_recorded_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            self.assertEqual(capture.record_read(archive, None, URL, None, OBSERVED, OBSERVED, URL,
                                                 error="URLError: timed out"), 4)
            import json
            entry = json.loads((archive / "index.jsonl").read_text().splitlines()[0])
            self.assertEqual(entry["status"], "fetch_failed")
            self.assertFalse((archive / "raw").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
