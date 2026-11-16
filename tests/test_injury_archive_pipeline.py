#!/usr/bin/env python3
"""End-to-end rehearsal of the injury-archive pipeline with the network stubbed out.

`archive_lib.fetch` is replaced by a function that returns synthetic bytes for the two official
URL patterns. Everything downstream is the real code path: the real capture CLI, the real
content-addressed store, the real parser, the real join, the real page renderer and the real
fail-closed verifier. This proves the workflow that runs in CI can complete, and that its gates
hold, without asserting anything about an NFL player or page.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "injury-archive" / "scripts"))
import archive_lib as lib  # noqa: E402
import capture  # noqa: E402

TEAM_HEAD = '<div class="d3-o-section-sub-title"><span>{team}</span></div>'
TABLE_HEAD = (
    '<table class="x"><thead><tr><th scope="col">Player</th><th scope="col">Position</th>'
    '<th scope="col">Injuries</th><th scope="col">Practice Status</th><th scope="col">Game Status</th>'
    "</tr></thead><tbody>"
)


def row(name, slug, pos, injury, practice, game):
    return (f'<tr><td><a href="https://www.nfl.com/players/{slug}/">{name}</a></td><td>{pos}</td>'
            f"<td>{injury}</td><td>{practice}</td><td>{game}</td></tr>")


def injury_page(season: int, week: int) -> bytes:
    sections = (
        TEAM_HEAD.format(team="Lions") + TABLE_HEAD
        + row("Alpha One", "alpha-one", "S", "Knee", "Did Not Participate In Practice", "Out")
        + row("Beta Two", "beta-two", "WR", "Rib", "Limited Participation in Practice", "Questionable")
        + row("Gamma Three", "gamma-three", "CB", "Hip", "Did Not Participate In Practice", "Out")
        + "</tbody></table>"
        + TEAM_HEAD.format(team="Bears") + TABLE_HEAD
        + row("Delta Four", "delta-four", "QB", "Ankle", "Full Participation in Practice", "Questionable")
        + "</tbody></table>"
    )
    return (f"<!doctype html><html><head><title>Official NFL Injury Report for Players - "
            f"Week {week} of the {season} Season | NFL.com</title></head><body>"
            f'<h2 class="d3-o-section-title">SUNDAY</h2>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">AAA</span>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">BBB</span>{sections}</body></html>'
            ).encode()


def inactives_page(season: int, week: int) -> bytes:
    return (f"<html><body><h1>NFL Week {week} inactives: players ruled out for Sunday's "
            f"{season} NFL season games</h1><h2>EARLY GAMES</h2><h3>LIONS</h3><ul>"
            f"<li>CB Gamma Three</li><li>RB Omega Nine</li></ul><h3>BEARS</h3>"
            f"<ul><li>QB Delta Four</li></ul></body></html>").encode()


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {k: getattr(lib, k) for k in
                      ("ROOT", "DATA", "RAW", "INDEX", "INJURIES_JSON", "INACTIVES_JSON",
                       "DESIGNATIONS_JSON", "COVERAGE_JSON", "CLUBS_JSON")}
        lib.ROOT = self.tmp
        lib.DATA = self.tmp / "injury-archive" / "data"
        lib.RAW = lib.DATA / "raw"
        lib.INDEX = lib.DATA / "index.jsonl"
        lib.INJURIES_JSON = lib.DATA / "injuries.json"
        lib.INACTIVES_JSON = lib.DATA / "inactives.json"
        lib.DESIGNATIONS_JSON = lib.DATA / "designations.json"
        lib.COVERAGE_JSON = lib.DATA / "coverage.json"
        lib.CLUBS_JSON = lib.DATA / "clubs.json"
        lib.DATA.mkdir(parents=True, exist_ok=True)
        lib.CLUBS_JSON.write_text(json.dumps({
            "clubs": [{"club": "Detroit Lions", "nickname": "LIONS"},
                      {"club": "Chicago Bears", "nickname": "BEARS"}]}), encoding="utf-8")
        self.saved_fetch = lib.fetch
        lib.fetch = self.fake_fetch

    def tearDown(self):
        lib.fetch = self.saved_fetch
        for key, value in self.saved.items():
            setattr(lib, key, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def fake_fetch(url, hosts, timeout=45):
        if "/injuries/league/" in url:
            season = int(url.split("/league/")[1].split("/")[0])
            week = int(url.rsplit("REG", 1)[1])
            return injury_page(season, week), url, 200
        if "inactives-players" in url:
            week = int(url.split("nfl-week-")[1].split("-")[0])
            season = int(url.rsplit("-", 2)[1])
            return inactives_page(season, week), url, 200
        raise AssertionError(f"unexpected URL in rehearsal: {url}")

    def test_capture_build_join(self):
        self.assertEqual(capture.capture_injury(2026, 10, quiet=True), 0)
        self.assertEqual(capture.capture_inactives(2026, 10, quiet=True), 0)
        index = lib.read_index()
        self.assertEqual([e["status"] for e in index], ["ok", "ok"])
        for entry in index:
            stored = lib.load_raw(entry["raw_file"])
            self.assertEqual(lib.sha256_bytes(stored), entry["sha256"])

        import build
        data = build.build_artifacts()
        self.assertIn("2026-10", data["injuries"])
        self.assertIn("2026-10", data["inactives"])
        joined = {o["player"]: o["outcome"] for o in data["designations"]["observations"]}
        self.assertEqual(joined["Gamma Three"], "inactive (on the official inactive list)")
        self.assertEqual(joined["Delta Four"], "inactive (on the official inactive list)")
        self.assertEqual(joined["Alpha One"], "active (not on the inactive list)")
        self.assertEqual(joined["Beta Two"], "active (not on the inactive list)")
        # Out: 2 designations, 1 inactive -> 50%; Questionable: 2 designations, 1 inactive -> 50%
        by_label = {r["group"]: r for r in data["designations"]["by_label"]}
        self.assertEqual(by_label["Out"]["n"], 2)
        self.assertEqual(by_label["Out"]["inactive"], 1)
        self.assertAlmostEqual(by_label["Out"]["inactive_rate"], 0.5)
        self.assertLess(by_label["Out"]["inactive_ci_low"], 0.5)
        self.assertGreater(by_label["Out"]["inactive_ci_high"], 0.5)
        totals = data["designations"]["totals"]
        self.assertEqual(totals["designations"],
                         totals["inactive"] + totals["active"] + totals["uncovered"] + totals["ambiguous"])

    def test_unpublished_address_is_recorded_not_invented(self):
        import urllib.error

        def not_found(url, hosts, timeout=45):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        lib.fetch = not_found
        self.assertEqual(capture.capture_inactives(2021, 3, quiet=True), 0)
        entry = lib.read_index()[-1]
        self.assertEqual(entry["status"], "not_published")
        self.assertEqual(entry["http_status"], 404)

    def test_transport_failure_exits_nonzero_and_is_recorded(self):
        def broken(url, hosts, timeout=45):
            raise TimeoutError("read timed out")

        lib.fetch = broken
        self.assertEqual(capture.capture_injury(2026, 10, quiet=True), 4)
        self.assertEqual(lib.read_index()[-1]["status"], "fetch_failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
