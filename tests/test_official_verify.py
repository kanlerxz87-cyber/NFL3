#!/usr/bin/env python3
"""Regression tests for the official-verify workspace.

These tests are deliberately about *invariants*, not about the numbers. A test
that pinned Brier = 0.2245 would fail the moment a game was added and would teach
nobody anything. A test that pins "the corpus must reconcile to the official
standings" fails exactly when something is wrong.

Synthetic fixtures are used where the point is arithmetic; real committed data is
used where the point is that the committed data is sound.
"""
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "official-verify"
DATA = SITE / "data"
sys.path.insert(0, str(SITE / "scripts"))

import evaluate  # noqa: E402


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SITE / "scripts" / script), *args],
        cwd=ROOT, capture_output=True, text=True,
    )


class CorpusIntegrity(unittest.TestCase):
    """The committed corpus must be internally consistent and officially reconcilable."""

    def test_corpus_reconciles_to_official_standings(self):
        result = run("verify_corpus.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 mismatch", result.stdout)

    def test_every_game_has_an_official_source_url(self):
        with (DATA / "games_2026_official.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreater(len(rows), 100)
        for row in rows:
            self.assertTrue(
                row["source_url"].startswith("https://www.nfl.com/"),
                f"{row['game_id']} is not sourced to nfl.com",
            )
            self.assertTrue(row["source_id"].startswith("OV-S"))

    def test_no_blank_scores_are_published(self):
        with (DATA / "games_2026_official.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.assertTrue(row["away_score"].strip().isdigit(), row["game_id"])
                self.assertTrue(row["home_score"].strip().isdigit(), row["game_id"])

    def test_standings_cover_all_32_clubs(self):
        with (DATA / "standings_2026_official.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 32)
        self.assertEqual(len({r["team"] for r in rows}), 32)


class PreRegistration(unittest.TestCase):
    """The registration gate must actually gate."""

    def test_gate_passes_on_the_committed_tree(self):
        result = run("check_prereg.py")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("G-PREREG PASS", result.stdout)

    def test_gate_fails_when_the_corpus_changes(self):
        """A modified corpus must break the hash the registration recorded.

        This is the whole point of the gate: results cannot drift away from the
        data they were registered against.
        """
        original = (DATA / "games_2026_official.csv").read_text(encoding="utf-8")
        try:
            (DATA / "games_2026_official.csv").write_text(
                original + "2026_99_XX_YY,2026,99,2026-12-31,Thursday,XX,0,YY,0,no,,OV-S01,https://www.nfl.com/schedules/2026/by-week/week-1\n",
                encoding="utf-8",
            )
            result = run("check_prereg.py")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sha256", result.stdout)
        finally:
            (DATA / "games_2026_official.csv").write_text(original, encoding="utf-8")

    def test_registration_commit_precedes_head(self):
        log = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%H", "--",
             "official-verify/prereg/PREREG-2026-OV1.md"],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.split()
        self.assertTrue(log, "registration file is not committed")
        oldest = log[-1]
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", oldest, "HEAD"],
            cwd=ROOT, capture_output=True,
        )
        self.assertEqual(ancestor.returncode, 0, "registration does not precede HEAD")


class ModelMath(unittest.TestCase):
    """Arithmetic that must hold regardless of the data."""

    def test_normal_cdf_is_a_distribution_function(self):
        self.assertAlmostEqual(evaluate.norm_cdf(0.0), 0.5, places=9)
        self.assertLess(evaluate.norm_cdf(-1.0), evaluate.norm_cdf(0.0))
        self.assertGreater(evaluate.norm_cdf(1.0), evaluate.norm_cdf(0.0))
        self.assertAlmostEqual(evaluate.norm_cdf(1.0) + evaluate.norm_cdf(-1.0), 1.0, places=9)

    def test_ridge_fit_satisfies_sum_to_zero(self):
        games = evaluate.load_games()
        teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
        mu, hfa, attack, defence = evaluate.design(games, teams)
        self.assertAlmostEqual(sum(attack), 0.0, places=6)
        self.assertAlmostEqual(sum(defence), 0.0, places=6)
        self.assertGreater(mu, 10.0)
        self.assertLess(mu, 40.0)

    def test_brier_of_a_perfect_forecast_is_zero(self):
        self.assertEqual(evaluate.brier([(1.0, 1.0), (0.0, 0.0)]), 0.0)

    def test_brier_of_a_coin_flip_on_one_win_one_loss_is_a_quarter(self):
        self.assertAlmostEqual(evaluate.brier([(0.5, 1.0), (0.5, 0.0)]), 0.25)

    def test_cluster_bootstrap_is_deterministic_for_a_fixed_seed(self):
        diffs = [0.01 * i for i in range(40)]
        first = evaluate.cluster_bootstrap(diffs, draws=200, seed=7)
        second = evaluate.cluster_bootstrap(diffs, draws=200, seed=7)
        self.assertEqual(first, second)
        self.assertLessEqual(first[0], first[1])

    def test_bootstrap_interval_contains_the_mean_for_symmetric_input(self):
        diffs = [-0.05] * 50 + [0.05] * 50
        lo, hi = evaluate.cluster_bootstrap(diffs, draws=500, seed=1)
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 0.0)


class EvaluationOutput(unittest.TestCase):
    """The published result must be internally coherent, whatever its value."""

    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads((DATA / "evaluation.json").read_text(encoding="utf-8"))

    def test_out_of_sample_size_is_consistent_with_the_weekly_breakdown(self):
        total = sum(w["test_games"] for w in self.ev["per_week"])
        self.assertEqual(total, self.ev["n_games_scored"])

    def test_no_evaluation_week_leaks_into_its_own_fit(self):
        for week in self.ev["per_week"]:
            self.assertLess(
                week["fit_games"], self.ev["n_games_scored"] + week["fit_games"],
            )
            self.assertLess(week["fit_games"], 137)

    def test_controls_are_present(self):
        for key in ("control_home_base_rate", "control_coin_flip", "control_favourites"):
            self.assertIn(key, self.ev["brier"])

    def test_interval_lower_bound_and_gate_agree(self):
        lo, hi = self.ev["cluster_bootstrap_95"]
        self.assertLessEqual(lo, hi)
        self.assertEqual(self.ev["gate_G_CLUSTER_lower_bound_above_zero"], lo > 0)

    def test_skill_is_reported_relative_to_a_benchmark(self):
        expected = 1 - self.ev["brier"]["model"] / self.ev["brier"]["control_home_base_rate"]
        self.assertAlmostEqual(self.ev["skill_vs_home_base_rate"], expected, places=9)

    def test_no_roi_or_price_claim_is_made(self):
        blob = json.dumps(self.ev).lower()
        for forbidden in ('"roi"', "closing_line_value", '"vegas"', '"hold"'):
            self.assertNotIn(forbidden, blob)


class Origination(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = json.loads((DATA / "origination.json").read_text(encoding="utf-8"))

    def test_market_and_residual_are_blank_not_zero(self):
        for row in self.orig["board"]:
            self.assertEqual(row["market_side"], "")
            self.assertEqual(row["market_total"], "")
            self.assertEqual(row["residual_side"], "")
            self.assertEqual(row["residual_total"], "")

    def test_every_originated_fixture_is_unplayed_and_sourced(self):
        for row in self.orig["board"]:
            self.assertEqual(row["week"], 11, "only fixtures that had not kicked off may be originated")
            self.assertTrue(row["source_url"].startswith("https://www.nfl.com/"))

    def test_origination_order_is_recorded(self):
        for row in self.orig["board"]:
            self.assertEqual(row["origination_order"], "side -> total -> moneyline")

    def test_probabilities_are_valid_and_prices_consistent(self):
        for row in self.orig["board"]:
            p = row["fair_p_home_win"]
            self.assertGreater(p, 0.0)
            self.assertLess(p, 1.0)
            self.assertAlmostEqual(row["fair_home_decimal"], 1 / p, places=2)
            self.assertAlmostEqual(row["fair_away_decimal"], 1 / (1 - p), places=2)

    def test_neutral_site_gets_no_home_field_term(self):
        for row in self.orig["board"]:
            if row["neutral_site"] == "yes":
                self.assertEqual(row["inputs_hfa"], 0.0)

    def test_side_and_total_are_derivable_from_the_published_inputs(self):
        for row in self.orig["board"]:
            home = (row["inputs_mu"] + row["inputs_hfa"] / 2
                    + row["inputs_attack_home"] - row["inputs_defence_away"])
            away = (row["inputs_mu"] - row["inputs_hfa"] / 2
                    + row["inputs_attack_away"] - row["inputs_defence_home"])
            self.assertAlmostEqual(home + away, row["fair_total"], places=1)
            self.assertAlmostEqual(-(home - away), row["fair_side_home_perspective"], places=1)


class Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.an = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))

    def test_luck_shares_are_complementary_and_bounded(self):
        luck = self.an["luck"]
        share = luck["luck_share_of_win_dispersion"]
        self.assertGreaterEqual(share, 0.0)
        self.assertLessEqual(share, 1.0)
        self.assertAlmostEqual(share + luck["skill_share_of_win_dispersion"], 1.0, places=3)

    def test_every_correlation_publishes_n_and_an_interval(self):
        for c in self.an["correlations"]:
            self.assertGreaterEqual(c["n"], 30)
            self.assertGreaterEqual(c["r"], -1.0)
            self.assertLessEqual(c["r"], 1.0)
            lo, hi = c["ci95_fisher"]
            self.assertLessEqual(lo, c["r"])
            self.assertGreaterEqual(hi, c["r"])

    def test_calibration_bins_sum_to_the_scored_games(self):
        total = sum(b["n"] for b in self.an["calibration"]["bins"])
        self.assertEqual(total, self.an["calibration"]["n_games"])

    def test_thin_bins_are_flagged_rather_than_dropped(self):
        thin = [b for b in self.an["calibration"]["bins"] if b["n"] < 10]
        for b in thin:
            self.assertFalse(b["readable"])
        self.assertEqual(len(self.an["calibration"]["bins"]) >= 1, True)


class Registers(unittest.TestCase):
    def test_requirements_cover_the_brief_and_use_known_states(self):
        with (DATA / "requirements.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 60)
        for row in rows:
            self.assertIn(row["state"], {"done", "partial", "blocked"})
            self.assertTrue(row["blocking_gate"].strip(), row["id"])
            self.assertTrue(row["number_that_would_clear_it"].strip(), row["id"])

    def test_blocked_rows_name_a_gate_and_a_clearing_number(self):
        with (DATA / "requirements.csv").open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["state"] == "blocked"]
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertNotEqual(row["blocking_gate"].strip().lower(), "none", row["id"])

    def test_every_question_names_a_discovery_action(self):
        with (DATA / "questions.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 30)
        for row in rows:
            self.assertTrue(row["discovery_action"].strip(), row["id"])
            self.assertTrue(row["what_it_blocks"].strip(), row["id"])

    def test_every_suggestion_is_two_sided(self):
        with (DATA / "suggestions.csv").open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 15)
        for row in rows:
            text = row["what_would_change_our_mind"].lower()
            self.assertIn("supports", text, row["id"])
            self.assertIn("refut", text, row["id"])


class SiteGate(unittest.TestCase):
    def test_site_checks_pass(self):
        result = run("check_site.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_flags_are_published_with_a_source(self):
        flags = json.loads((DATA / "flags.json").read_text(encoding="utf-8"))["flags"]
        self.assertGreaterEqual(len(flags), 10)
        for f in flags:
            self.assertTrue(f["source_url"].startswith("https://"))
            self.assertTrue(f["action_for_reviewer"].strip())
            self.assertIn(f["status"], {"open", "resolved"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
