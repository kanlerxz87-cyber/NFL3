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
import capture_official as capture
import validation as v

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
