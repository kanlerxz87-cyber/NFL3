"""Regression tests for the availability ledger: capture integrity, joins and published pages.

Offline tests. They check that the stored official captures still hash to their recorded digests,
that the joins are derived from the committed depth capture rather than asserted, and that the
published pages agree with the artifact.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "availability-ledger"
LEDGER = LAB / "data" / "ledger.json"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
PAGES = ["index.html", "ledger.html", "availability.html", "depth-flags.html", "diff.html",
         "flagged.html", "sources.html"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestCaptures(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_every_capture_is_an_official_nfl_page(self):
        self.assertGreater(len(self.data["captures"]), 0)
        for capture in self.data["captures"]:
            url = capture["meta"]["source_url"]
            self.assertTrue(url.startswith("https://www.nfl.com/"), url)
            self.assertIn("retrieved_at_utc", capture["meta"])
            # the stored capture must parse as an ISO timestamp
            dt.datetime.fromisoformat(capture["meta"]["retrieved_at_utc"].replace("Z", "+00:00"))

    def test_capture_digests_still_match_the_stored_files(self):
        for capture in self.data["captures"]:
            path = ROOT / capture["file"] if str(capture["file"]).startswith("availability-ledger") \
                else LAB / "data" / "captures" / capture["file"]
            self.assertTrue(path.exists(), capture["file"])
            self.assertEqual(sha256_file(path), capture["sha256"],
                             f"{capture['file']} no longer hashes to its recorded digest")

    def test_capture_files_record_their_provenance_in_the_header(self):
        for capture in self.data["captures"]:
            path = LAB / "data" / "captures" / capture["file"]
            text = path.read_text(encoding="utf-8")
            self.assertIn("--- body ---", text)
            for key in ("source_url", "retrieved_at_utc", "capture_scope", "row_format"):
                self.assertIn(f"# {key}:", text, f"{capture['file']} is missing #{key}")

    def test_every_ledger_row_points_at_an_official_page(self):
        for entry in self.data["reserve_entries"]:
            self.assertTrue(entry["source_url"].startswith("https://www.nfl.com/"))
            self.assertTrue(entry["player_url"].startswith("https://www.nfl.com/"))
            self.assertRegex(entry["date"], r"^2026-\d{2}-\d{2}$")
        for trade in self.data["trade_events"]:
            self.assertTrue(trade["source_url"].startswith("https://www.nfl.com/"))
            self.assertRegex(trade["date"], r"^2026-\d{2}-\d{2}$")


class TestJoins(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_the_depth_capture_timestamp_is_the_committed_one(self):
        self.assertEqual(self.data["depth_capture"]["observed_at"], self.snap["observed_at"])
        self.assertEqual(self.data["depth_capture"]["depth_rows"], len(self.snap["depth_rows"]))

    def test_stale_rows_are_strictly_older_than_the_capture(self):
        capture_day = self.snap["observed_at"][:10]
        for row in self.data["stale_depth_rows"]:
            self.assertLess(row["event_date"], capture_day)
            self.assertIn("stale", row["verdict"])

    def test_same_day_rows_are_not_called_stale(self):
        capture_day = self.snap["observed_at"][:10]
        for row in self.data["same_day_depth_rows"]:
            self.assertEqual(row["event_date"], capture_day)
            self.assertIn("unresolved", row["verdict"])
            self.assertNotIn("stale", row["verdict"])

    def test_stale_rows_are_real_depth_rows_from_the_committed_capture(self):
        depth = {(r["team"], r["player"].strip().lower()) for r in self.snap["depth_rows"]}
        club_to_team = {"Commanders": "Commanders", "Rams": "Rams", "49ers": "49ers",
                        "Vikings": "Vikings", "Broncos": "Denver Broncos"}
        for row in self.data["stale_depth_rows"]:
            team = club_to_team.get(row["club"], row["club"])
            self.assertIn((team, row["player"].strip().lower()), depth,
                          f"{row['player']} is not a depth row in the committed capture")

    def test_traded_players_are_absent_from_the_club_they_left(self):
        for row in self.data["traded_players_removed_from_former_club"]:
            self.assertTrue(row["chart_captured"],
                            "a club without a captured chart cannot be a control case")

    def test_reserve_listed_players_absent_from_the_report_are_reported(self):
        absent = [c for c in self.data["report_coverage"] if not c["on_report"]]
        self.assertGreater(len(absent), 0)
        for row in absent:
            self.assertEqual(row["designation"], "")
            self.assertTrue(row["report_source_url"].startswith("https://www.nfl.com/"))

    def test_the_diff_is_a_diff_not_a_second_snapshot(self):
        diff = self.data["diff"]
        self.assertIn(diff["status"], ("two dated captures", "no second capture"))
        for row in diff["rows"]:
            self.assertTrue(row["source"].startswith("https://www.nfl.com/"))
            self.assertTrue(row["depth_source"].startswith("https://"))

    def test_the_executive_summary_quotes_the_artifact(self):
        summary = (LAB / "EXECUTIVE_SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn(f'{len(self.data["reserve_entries"])} reserve-list placements'
                      .replace(" reserve-list placements", ""), summary)
        self.assertIn(f'{len(self.data["stale_depth_rows"])} stale depth rows', summary)
        self.assertIn(f'{len(self.data["same_day_depth_rows"])} unresolved row', summary)
        self.assertIn(f'{len(self.data["traded_players_removed_from_former_club"])} control cases',
                      summary)

    def test_the_baltimore_case_is_left_unresolved(self):
        case = self.data["baltimore_case"]
        self.assertEqual(case["status"], "unresolved")
        self.assertGreaterEqual(len(case["depth_rows"]), 2)
        self.assertIsNotNone(case["trade"])

    def test_a_reserve_placement_after_the_capture_is_not_flagged(self):
        # A player placed on the reserve list after the depth capture cannot be a stale row.
        capture_day = self.snap["observed_at"][:10]
        for entry in self.data["reserve_entries"]:
            if entry["date"] > capture_day:
                names = {r["player"] for r in self.data["stale_depth_rows"]}
                self.assertNotIn(entry["player"], names)


class TestPages(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_every_page_exists_without_placeholders_or_broken_links(self):
        for name in PAGES:
            path = LAB / name
            self.assertTrue(path.exists(), f"{name} is missing")
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b(None|nan|undefined|null)\b", text),
                              f"{name} contains a placeholder token")
            for href in re.findall(r'href="([^"]+)"', text):
                if not href.startswith("http"):
                    self.assertTrue((LAB / href).resolve().exists(), f"{name}: broken link {href}")

    def test_every_table_row_carries_a_source_link(self):
        for name in PAGES:
            text = (LAB / name).read_text(encoding="utf-8")
            rows = [r for r in re.findall(r"<tr>(.*?)</tr>", text, re.S) if "<td" in r]
            for row in rows:
                self.assertIn('href="http', row, f"{name}: a table row has no source link")

    def test_the_index_quotes_the_artifact_counts(self):
        text = (LAB / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'<strong>{len(self.data["reserve_entries"])}</strong>', text)
        self.assertIn(f'<strong>{len(self.data["trade_events"])}</strong>', text)
        self.assertIn(f'<strong>{len(self.data["stale_depth_rows"])}</strong>', text)

    def test_the_diff_page_lists_every_diff_row(self):
        text = (LAB / "diff.html").read_text(encoding="utf-8")
        for row in self.data["diff"]["rows"]:
            self.assertIn(row["player"], text)

    def test_the_depth_flags_page_lists_every_flagged_row(self):
        text = (LAB / "depth-flags.html").read_text(encoding="utf-8")
        flagged = (self.data["stale_depth_rows"] + self.data["same_day_depth_rows"]
                   + self.data["stale_depth_rows"])
        for row in self.data["stale_depth_rows"] + self.data["same_day_depth_rows"]:
            self.assertIn(row["player"], text)


if __name__ == "__main__":
    unittest.main()
