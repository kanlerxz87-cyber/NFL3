#!/usr/bin/env python3
"""Offline regression tests for the independent NFL3 source audit."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import audit_sources as audit


class SourceAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT / "decision-lab/data/official_snapshot.json").read_text(encoding="utf-8"))
        cls.catalog = json.loads((ROOT / "decision-lab/data/catalog.json").read_text(encoding="utf-8"))

    def test_fixed_host_policy_requires_secure_exact_publisher(self):
        self.assertTrue(audit.approved_nfl_or_club_url("https://www.nfl.com/teams/"))
        self.assertTrue(audit.approved_nfl_or_club_url("https://www.colts.com/team/depth-chart"))
        self.assertFalse(audit.approved_nfl_or_club_url("http://www.colts.com/team/depth-chart"))
        self.assertFalse(audit.approved_nfl_or_club_url("https://www.colts.com.attacker.invalid/team/depth-chart"))
        self.assertFalse(audit.approved_nfl_or_club_url("https://attacker.invalid/team/depth-chart"))
        self.assertFalse(audit.approved_nfl_or_club_url("https://user@www.colts.com/team/depth-chart"))
        self.assertFalse(audit.approved_nfl_or_club_url("https://www.colts.com:8443/team/depth-chart"))

    def test_github_host_is_not_an_nfl_or_club_authority(self):
        self.assertFalse(audit.approved_nfl_or_club_url("https://github.com/nflverse/nflverse-data"))
        self.assertFalse(audit.approved_authority_url("https://github.com/unrelated-owner/unverified-data"))
        self.assertTrue(audit.approved_authority_url("https://docs.github.com/en/pages"))

    def test_current_snapshot_matches_fixed_team_host_and_digest_registry(self):
        result = audit.check_snapshot(self.snapshot)
        self.assertEqual(result["fixed_host_check_errors"], [])
        self.assertGreater(result["injury_rows"], 0)
        self.assertGreater(result["depth_rows"], 0)
        self.assertEqual(result["depth_failures"], len(result["coverage_warnings"]))
        self.assertGreater(result["depth_successes"], 0)

    def test_snapshot_cannot_self_authorize_host_in_independent_check(self):
        altered = copy.deepcopy(self.snapshot)
        altered["depth_rows"][0]["source_url"] = "https://untrusted.invalid/depth-chart"
        result = audit.check_snapshot(altered)
        self.assertTrue(any("source host" in error and "untrusted.invalid" in error
                            for error in result["fixed_host_check_errors"]))

    def test_http_depth_source_is_rejected(self):
        altered = copy.deepcopy(self.snapshot)
        altered["depth_rows"][0]["source_url"] = "http://www.commanders.com/team/depth-chart"
        result = audit.check_snapshot(altered)
        self.assertTrue(any("source host None" in error for error in result["fixed_host_check_errors"]))

    def test_existing_gate_self_authorization_gap_is_reproduced(self):
        result = audit.reproduce_existing_allowlist_gaps()
        self.assertTrue(result["snapshot_declared_host_added_to_allowlist"])
        self.assertTrue(result["directory_host_from_synthetic_html_is_adopted"])
        self.assertTrue(result["http_url_host_passes_host_only_membership_check"])
        self.assertTrue(result["arbitrary_github_repository_not_classified_community"])
        self.assertTrue(result["static_allowlist_rejects_snapshot_declared_host"])
        self.assertTrue(result["static_allowlist_rejects_http"])

    def test_every_catalog_source_uses_an_approved_primary_host(self):
        sources = self.catalog["sources"]
        self.assertTrue(sources)
        report_catalog_sources = [
            item for item in audit.collect_report()["sources"] if item["catalogued"]
        ]
        self.assertEqual([item["id"] for item in sources],
                         [item["id"] for item in report_catalog_sources])
        for item in sources:
            with self.subTest(source=item["id"], url=item["url"]):
                self.assertTrue(audit.approved_authority_url(item["url"]))

    def test_repo_row_scan_counts_pages_and_rows_consistently(self):
        result = audit.scan_html_rows()
        self.assertGreater(result["html_pages"], 0)
        self.assertGreater(result["table_rows"], 0)
        self.assertEqual(result["html_pages"], len(result["rows_by_page"]))
        self.assertEqual(result["table_rows"], sum(result["rows_by_page"].values()))
        self.assertLessEqual(result["rows_missing_approved_primary_link"], result["table_rows"])
        self.assertLessEqual(result["rows_community_only"], result["table_rows"])

    def test_report_reproduces_current_snapshot_and_source_gaps(self):
        report = audit.collect_report()
        self.assertEqual(report["strategies_validated"], 0)
        self.assertEqual(report["strategies_total"], len(self.catalog.get("strategies", [])))
        self.assertFalse(report["catalog_source_errors"])
        self.assertEqual(report["snapshot"]["fixed_host_check_errors"], [])
        finding_ids = {finding["id"] for finding in report["findings"]}
        self.assertTrue({"SRC-01", "SRC-02", "SRC-03"}.issubset(finding_ids))
        comparisons = report["audit_count_comparison"]
        stale_audit = (
            comparisons["saved_html_pages"] != comparisons["independent_html_pages"]
            or comparisons["saved_table_rows"] != comparisons["independent_table_rows"]
            or comparisons["saved_index_rows"] != comparisons["independent_index_rows"]
        )
        self.assertEqual("SRC-04" in finding_ids, stale_audit)
        self.assertEqual("SRC-05" in finding_ids,
                         report["table_citations"]["rows_missing_approved_primary_link"] > 0)
        self.assertEqual("SRC-06" in finding_ids,
                         bool(report["snapshot"]["coverage_warnings"]))
        self.assertEqual("SRC-07" in finding_ids, bool(report["catalog_source_errors"]))
        self.assertEqual("SRC-08" in finding_ids,
                         bool(report["snapshot"]["fixed_host_check_errors"]))

    def test_published_audit_tables_have_primary_source_links(self):
        page = ROOT / "verification/index.html"
        self.assertTrue(page.exists(), "run `python3 verification/audit_sources.py --write` first")
        parser = audit.TableCitationAudit()
        parser.feed(page.read_text(encoding="utf-8"))
        self.assertEqual(len(parser.rows), len(audit.TEAM_HOSTS) + len(audit.collect_report()["sources"]))
        for index, links in enumerate(parser.rows, 1):
            with self.subTest(table_row=index, links=links):
                self.assertTrue(any(audit.approved_authority_url(link) for link in links))


if __name__ == "__main__":
    unittest.main(verbosity=2)
