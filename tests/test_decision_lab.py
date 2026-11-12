#!/usr/bin/env python3
"""Offline tests for the decision lab. Synthetic records are not NFL evidence."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "decision-lab" / "scripts"))
import availability as av
import capture_official as capture
import validation as v
import verify_live as vl

INJURY_FIXTURE = '''
<h2 class="d3-o-section-title">THURSDAY, NOVEMBER 12TH</h2>
<span class="nfl-c-matchup-strip__team-abbreviation">WAS</span>
<span class="nfl-c-matchup-strip__team-abbreviation">NYG</span>
<div class="d3-o-section-sub-title"><span>Commanders</span></div>
<table><thead><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr></thead>
<tbody><tr><td><a href="/players/lucas-patrick/">Lucas Patrick</a></td><td>C</td><td>Concussion</td><td>Did Not Participate In Practice</td><td>Out</td></tr>
<tr><td><a href="/players/jayden-daniels/">Jayden Daniels</a></td><td>QB</td><td></td><td>Full Participation in Practice</td><td></td></tr></tbody></table>
<div class="d3-o-section-sub-title"><span>Seahawks</span></div>
<p class="nfl-o-no-results__text">No Injuries Reported</p>
'''
DEPTH_FIXTURE = '''
<table summary="Offense"><caption>Offense</caption><thead><tr><th>Position</th><th>First</th><th>Second</th><th>Third</th></tr></thead>
<tbody><tr><td>QB</td><td><a href="/team/players-roster/a/">Starter A</a></td><td><a href="/team/players-roster/b/">Backup B</a></td><td></td></tr></tbody></table>
'''
COLTS_FIXTURE = json.dumps({"articleBody": "OFFENSE\n\nQB: Daniel Jones, Anthony Richardson Sr., Riley Leonard\n\nDEFENSE\n\nDE: Laiatu Latu, Caden Curry"})


def synthetic_records(n=300, seed=7, community=False, future=False, combo=False):
    import random
    rng = random.Random(seed)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    digest = hashlib.sha256(b"synthetic-test-fixture").hexdigest()
    for i in range(n):
        kickoff = base + timedelta(days=i)
        forecast = kickoff - timedelta(hours=2)
        p = 0.62
        outcome = 1 if rng.random() < 0.68 else 0
        row = {
            "strategy_id": "synthetic", "game_id": f"game-{i}", "season": 2025 + i % 2, "fold": i % 3,
            "division": "Same-game parlays" if combo else "Singles", "market": "test", "side": "test",
            "available_at": (forecast - timedelta(hours=1)).isoformat(), "forecast_at": forecast.isoformat(),
            "logged_at": (forecast + timedelta(minutes=1)).isoformat(), "quote_at": (forecast - timedelta(minutes=5)).isoformat(),
            "kickoff": (kickoff + timedelta(hours=2) if future else kickoff).isoformat(),
            "probability": p, "baseline_probability": 0.5, "outcome": outcome,
            "american_odds": -110, "settlement": "win" if outcome else "loss", "settlement_verified": True,
            "source_url": "https://github.com/nflverse/nflverse-data" if community else "https://www.nfl.com/injuries/",
            "source_sha256": digest, "source_verified": True, "official_outcome_verified": True,
            "config_hash": "test-config", "prospective": True,
        }
        if combo:
            row.update(joint_probability=0.42, independence_probability=0.30, joint_outcome=1 if rng.random() < 0.5 else 0)
        rows.append(row)
    return rows


def policy(**overrides):
    cfg = {"config_hash": "test-config", "preregistered_at": "2025-01-01T00:00:00+00:00", "trial_count": 1,
           "shadow_verified": True, "shadow_version_hash": "test-config", "shadow_game_count": 150,
           "reward_policy_approved": True, "funding_verified": True, "bootstrap_replicates": 500,
           "min_games": 256, "min_seasons": 2, "min_folds": 3, "min_shadow_games": 128}
    cfg.update(overrides)
    return cfg


class CaptureTests(unittest.TestCase):
    def test_injury_blank_preserved(self):
        rows, empty = capture.parse_injuries(INJURY_FIXTURE, "https://www.nfl.com/injuries/", "2026-11-12T00:00:00+00:00", "0"*64)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["game_status"], "Out")
        self.assertEqual(rows[1]["injury"], "")
        self.assertEqual(rows[1]["game_status"], "")
        self.assertEqual(rows[1]["replacement_player"], "")
        self.assertEqual(empty[0]["team"], "Seahawks")

    def test_depth_rank_not_confirmation(self):
        rows = capture.parse_depth_tables(DEPTH_FIXTURE, "Commanders", "https://www.commanders.com/team/depth-chart", "2026-11-12T00:00:00+00:00", "0"*64)
        self.assertEqual([r["published_rank"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["confirmed_starter"], "")
        self.assertEqual(rows[1]["expected_snaps"], "")

    def test_colts_unofficial_authority(self):
        raw = f'<script type="application/ld+json">{COLTS_FIXTURE}</script>'
        rows = capture.parse_colts_article(raw, "https://www.colts.com/news/x", "2026-11-12T00:00:00+00:00", "0"*64)
        self.assertEqual(len(rows), 5)
        self.assertIn("UNOFFICIAL", rows[0]["authority"])
        self.assertEqual(rows[2]["published_rank"], 3)

    def test_snapshot_hashes(self):
        snapshot = capture.build_snapshot({"nfl-injuries": (INJURY_FIXTURE.encode(), "https://www.nfl.com/injuries/")}, "2026-11-12T00:00:00+00:00")
        self.assertEqual(snapshot["manifest"][0]["sha256"], hashlib.sha256(INJURY_FIXTURE.encode()).hexdigest())
        self.assertFalse(snapshot["coverage"]["licensed_market_history"])

    def test_club_directory_does_not_cross_anchors(self):
        raw = ('<a title="View Chicago Bears Profile" href="/teams/chicago-bears/">View Profile</a>'
               '<a title="View Chicago Bears Website" href="https://www.chicagobears.com/">View Full Site</a>'
               '<a title="View Houston Texans Profile" href="/teams/houston-texans">View Profile</a>'
               '<a title="View Houston Texans Website" href="https://www.houstontexans.com/">View Full Site</a>')
        clubs = capture.club_directory(raw)
        self.assertEqual(clubs, [("Chicago Bears", "https://www.chicagobears.com/"), ("Houston Texans", "https://www.houstontexans.com/")])


class ValidationTests(unittest.TestCase):
    def test_odds_and_vig(self):
        self.assertAlmostEqual(v.implied_probability(-110), 0.5238095238095238)
        self.assertAlmostEqual(sum(v.remove_vig([v.implied_probability(-110), v.implied_probability(-110)])), 1.0)
        with self.assertRaises(ValueError):
            v.american_to_decimal(-50)

    def test_brier_and_correlation(self):
        self.assertAlmostEqual(v.brier(0.8, 1), 0.040000000000000036)
        self.assertAlmostEqual(v.pearson([1, 2, 3, 4], [1, 3, 2, 4]), 0.8)
        self.assertIsNone(v.pearson([1, 1], [0, 1]))

    def test_multiplicity_increases_bar(self):
        self.assertGreater(v.bonferroni_z(50), v.bonferroni_z(1))

    def test_lucky_small_sample_fails(self):
        result = v.assess(synthetic_records(20), policy())
        self.assertFalse(result["eligible"])
        self.assertFalse(result["gates"]["G06"]["pass"])

    def test_community_source_fails_official_gate(self):
        result = v.assess(synthetic_records(300, community=True), policy())
        self.assertFalse(result["gates"]["G01"]["pass"])
        self.assertFalse(result["eligible"])

    def test_future_leak_fails(self):
        rows = synthetic_records(300)
        rows[0]["available_at"] = rows[0]["kickoff"]
        result = v.assess(rows, policy())
        self.assertFalse(result["gates"]["G02"]["pass"])

    def test_strong_synthetic_can_pass_research_gates(self):
        result = v.assess(synthetic_records(400), policy())
        self.assertTrue(result["gates"]["G06"]["pass"], result["gates"]["G06"])
        self.assertTrue(result["eligible"], result["gates"])
        self.assertIsNone(result["metrics"]["roi"])

    def test_combo_requires_joint_evidence(self):
        rows = synthetic_records(400, combo=True)
        for r in rows:
            r.pop("joint_probability")
        result = v.assess(rows, policy())
        self.assertFalse(result["gates"]["G07"]["pass"])

    def test_rewards_withheld_without_funding(self):
        result = v.assess(synthetic_records(400), policy(funding_verified=False))
        self.assertFalse(result["gates"]["G10"]["pass"])
        self.assertFalse(result["eligible"])


class AvailabilityTests(unittest.TestCase):
    """Synthetic fixtures only: these assert join logic, not NFL facts."""

    def snapshot(self):
        return {
            "observed_at": "2026-01-01T00:00:00+00:00",
            "injury_rows": [
                {"day": "D", "matchup": "AAA @ BBB", "team": "AAA", "player": "Starter One", "position": "WR",
                 "injury": "", "practice_status": "Did Not Participate In Practice", "game_status": "", "player_url": "",
                 "source_url": "https://www.nfl.com/injuries/", "observed_at": "", "source_sha256": "",
                 "confirmed_active": "", "replacement_player": "", "replacement_rank": "", "expected_snaps": ""},
                {"day": "D", "matchup": "AAA @ BBB", "team": "AAA", "player": "Backup Two", "position": "WR",
                 "injury": "", "practice_status": "Limited Participation in Practice", "game_status": "Questionable",
                 "player_url": "", "source_url": "https://www.nfl.com/injuries/", "observed_at": "", "source_sha256": "",
                 "confirmed_active": "", "replacement_player": "", "replacement_rank": "", "expected_snaps": ""},
                {"day": "D", "matchup": "AAA @ BBB", "team": "AAA", "player": "Number Prefixed", "position": "CB",
                 "injury": "", "practice_status": "Full Participation in Practice", "game_status": "", "player_url": "",
                 "source_url": "https://www.nfl.com/injuries/", "observed_at": "", "source_sha256": "",
                 "confirmed_active": "", "replacement_player": "", "replacement_rank": "", "expected_snaps": ""},
                {"day": "D", "matchup": "AAA @ BBB", "team": "BBB", "player": "Unparsed Club", "position": "RB",
                 "injury": "", "practice_status": "Full Participation in Practice", "game_status": "", "player_url": "",
                 "source_url": "https://www.nfl.com/injuries/", "observed_at": "", "source_sha256": "",
                 "confirmed_active": "", "replacement_player": "", "replacement_rank": "", "expected_snaps": ""},
            ],
            "no_injury_sections": [
                {"team": "BBB", "matchup": "AAA @ BBB", "day": "D", "text": "No Injuries Reported",
                 "source_url": "https://www.nfl.com/injuries/", "observed_at": "", "source_sha256": ""},
            ],
            "depth_rows": [
                {"team": "AAA", "unit": "Offense", "position": "WR", "player": "Starter One", "published_rank": 1,
                 "rank_basis": "published column order", "authority": "club depth chart", "player_url": "",
                 "source_url": "https://www.aaa.com/team/depth-chart", "observed_at": "", "source_sha256": "",
                 "confirmed_starter": "", "replacement_assignment": "", "expected_snaps": ""},
                {"team": "AAA", "unit": "Offense", "position": "WR", "player": "Starter One B", "published_rank": 1,
                 "rank_basis": "published column order", "authority": "club depth chart", "player_url": "",
                 "source_url": "https://www.aaa.com/team/depth-chart", "observed_at": "", "source_sha256": "",
                 "confirmed_starter": "", "replacement_assignment": "", "expected_snaps": ""},
                {"team": "AAA", "unit": "Offense", "position": "WR", "player": "Backup Two", "published_rank": 2,
                 "rank_basis": "published column order", "authority": "club depth chart", "player_url": "",
                 "source_url": "https://www.aaa.com/team/depth-chart", "observed_at": "", "source_sha256": "",
                 "confirmed_starter": "", "replacement_assignment": "", "expected_snaps": ""},
            ],
            "depth_directory_successes": [{"team": "AAA", "url": "https://www.aaa.com/", "sha256": "", "observed_at": "", "rows": 3}],
            "depth_directory_failures": [{"team": "BBB", "directory_url": "https://www.bbb.com/", "reason": "no table",
                                          "source_url": "https://www.nfl.com/teams/", "observed_at": ""}],
        }

    def test_join_keeps_unmatched_rows_with_reason(self):
        doc = av.analyse(self.snapshot())
        self.assertEqual(doc["coverage"]["matched_rows"], 2)          # Starter One, Backup Two
        self.assertEqual(doc["coverage"]["unmatched_rows"], 2)        # Number Prefixed, Unparsed Club
        reasons = {u["player"]: u["reason"] for u in doc["unmatched"]}
        self.assertIn("no captured machine-readable", reasons["Unparsed Club"])
        self.assertIn("name not present", reasons["Number Prefixed"])

    def test_replacement_lead_uses_next_published_player(self):
        doc = av.analyse(self.snapshot())
        lead = next(r for r in doc["replacement_leads"] if r["player"] == "Starter One")
        self.assertEqual(lead["next_player"], "Backup Two")
        self.assertEqual(lead["next_rank"], 2)
        self.assertEqual(lead["next_status"], "Limited Participation in Practice | Questionable")

    def test_replacement_never_infers_a_name(self):
        doc = av.analyse(self.snapshot())
        for lead in doc["replacement_leads"]:
            self.assertIn(lead["next_player"], {r["player"] for r in self.snapshot()["depth_rows"]})

    def test_inferred_fields_stay_blank(self):
        doc = av.analyse(self.snapshot())
        self.assertFalse(any("replacement_player" in k for k in doc["coverage"]))

    def test_duplicate_rank_one_slots_are_detected(self):
        doc = av.analyse(self.snapshot())
        slot = next(s for s in doc["depth_slots"] if s["slot"] == "WR:WR")
        self.assertEqual(slot["top3_listed"], 2)

    def test_position_family_is_explicit_and_unmapped_is_visible(self):
        self.assertEqual(av.family("RUSH"), "UNMAPPED")
        self.assertEqual(av.family("SAM"), "LB")
        self.assertEqual(av.family("LT"), "OL")


class VerificationTests(unittest.TestCase):
    """Synthetic comparison tests: no network, no NFL claims."""

    base = {"team": "AAA", "player": "One", "day": "D", "matchup": "AAA @ BBB", "position": "WR",
            "injury": "Knee", "practice_status": "Limited Participation in Practice", "game_status": "Questionable"}

    def test_identical_records_match(self):
        result = vl.compare_records([self.base], [dict(self.base)], vl.INJURY_FIELDS)
        self.assertEqual((result["matched"], result["mismatched"]), (1, 0))

    def test_field_change_is_reported_not_corrected(self):
        live = dict(self.base, game_status="Out")
        result = vl.compare_records([self.base], [live], vl.INJURY_FIELDS)
        self.assertEqual(result["mismatched"], 1)
        self.assertEqual(result["details"][0]["field"], "game_status")
        self.assertEqual(result["details"][0]["published"], "Questionable")
        self.assertEqual(result["details"][0]["live"], "Out")

    def test_blank_is_not_equal_to_a_value(self):
        live = dict(self.base, game_status="")
        result = vl.compare_records([self.base], [live], vl.INJURY_FIELDS)
        self.assertEqual(result["mismatched"], 1)

    def test_missing_and_extra_rows_are_counted(self):
        result = vl.compare_records([self.base], [], vl.INJURY_FIELDS)
        self.assertEqual(result["missing_live"], 1)
        other = dict(self.base, player="Two")
        result = vl.compare_records([self.base], [other], vl.INJURY_FIELDS)
        self.assertEqual(result["missing_live"], 1)
        self.assertEqual(result["extra_live"], 1)

    def test_no_injury_sections_compare_as_sets(self):
        pub = [{"team": "AAA"}]
        live = [{"team": "BBB"}]
        result = vl.compare_no_injury(pub, live)
        self.assertEqual(result["mismatched"], 2)

    def test_depth_comparison_detects_rank_change(self):
        row = {"unit": "Offense", "position": "WR", "player": "One", "published_rank": 1}
        result = vl.compare_depth([row], [dict(row, published_rank=2)])
        self.assertEqual(result["mismatched"], 2)

    def test_offline_run_never_claims_live_verification(self):
        snapshot = json.loads((ROOT / "decision-lab/data/official_snapshot.json").read_text())
        catalog = json.loads((ROOT / "decision-lab/data/catalog.json").read_text())
        doc = vl.run_offline(snapshot, catalog)
        self.assertEqual(doc["mode"], "offline-structural")
        self.assertIn(doc["status"], {"structural-only", "drift"})
        for fam in doc["families"]:
            self.assertNotEqual(fam["status"], "verified")


class CatalogTests(unittest.TestCase):
    def test_catalog_sources_and_blanks(self):
        catalog = json.loads((ROOT / "decision-lab/data/catalog.json").read_text())
        sources = {s["id"]: s for s in catalog["sources"]}
        for section in ("requirements", "questions", "suggestions", "strategies", "gates", "flags"):
            for row in catalog[section]:
                self.assertIn(row["source"], sources, row.get("id"))
                self.assertTrue(v.official_source(sources[row["source"]]["url"]))
        for q in catalog["questions"]:
            if q["blocking"] and q["id"] not in {"Q16", "Q20"}:
                self.assertEqual(q["answer"], "", q["id"])
        for s in catalog["strategies"]:
            self.assertEqual(s["status"], "Not run")
        for s in catalog["suggestions"]:
            for field in ("success_metric", "tradeoff", "depends"):
                self.assertTrue(s.get(field), s["id"])
        self.assertEqual({p["id"] for p in catalog["paths"]}, {"A", "B", "C"})
        for path in catalog["paths"]:
            for field in ("prerequisites", "cost", "benefit", "risk"):
                self.assertTrue(path.get(field), path["id"])
        ids = [f["id"] for f in catalog["flags"]]
        self.assertEqual(len(ids), len(set(ids)))
        for flag in catalog["flags"]:
            self.assertTrue(flag["action"], flag["id"])

    def test_availability_artifacts_are_reproducible(self):
        snapshot = json.loads((ROOT / "decision-lab/data/official_snapshot.json").read_text())
        committed = json.loads((ROOT / "decision-lab/data/availability.json").read_text())
        fresh = av.analyse(snapshot)
        for key in ("coverage", "replacement_leads", "depth_slots", "unmatched"):
            self.assertEqual(json.dumps(committed[key], sort_keys=True), json.dumps(fresh[key], sort_keys=True), key)

    def test_verification_artifact_covers_structural_families(self):
        doc = json.loads((ROOT / "decision-lab/data/verification.json").read_text())
        ids = {f["id"] for f in doc["families"]}
        self.assertTrue({"F7", "F8"} <= ids)
        for fam in doc["families"]:
            self.assertIn("source_url", fam)
            if fam["rows_checked"]:
                self.assertLessEqual(fam["matched"], fam["rows_checked"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
