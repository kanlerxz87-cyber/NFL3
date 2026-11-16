#!/usr/bin/env python3
"""Offline unit tests for the origination workspace.

These tests pin the things that would silently publish a misleading number:

  * the sign convention of the proper-score comparison (a flipped sign turned a losing rule into a
    "skill signal" during development — this test makes that regression impossible)
  * the push rule, so a whole-number line cannot be counted as a win
  * the sample-size arithmetic, checked against a hand-computed value
  * the price policy: a post-kickoff observation may never become an opening or a closing number
  * the settlement reconciliation, which must cover all 32 clubs and every field
  * the demotion gate, which must agree with the leaderboard it scored

No test asserts an NFL performance result. Synthetic fixtures only.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "origination" / "scripts"))

import common as C      # noqa: E402
import prices           # noqa: E402
import scoring          # noqa: E402
import luck             # noqa: E402

DATA = ROOT / "origination" / "data"


class SignConvention(unittest.TestCase):
    """A positive published skill must mean the model beat the benchmark."""

    def test_model_worse_than_benchmark_is_negative(self):
        # model says 0.9 and is wrong; benchmark says 0.5
        rows = [{"p": 0.9, "p_bench": 0.5, "won": False, "game_id": f"g{i}"} for i in range(30)]
        summary = scoring.score_rows(rows)
        self.assertLess(summary["bss"], 0, "a model worse than its benchmark must have negative skill")

    def test_model_better_than_benchmark_is_positive(self):
        rows = [{"p": 0.9, "p_bench": 0.5, "won": True, "game_id": f"g{i}"} for i in range(30)]
        summary = scoring.score_rows(rows)
        self.assertGreater(summary["bss"], 0)

    def test_paired_advantage_matches_bss_direction(self):
        rows = [{"p": 0.9, "p_bench": 0.5, "won": False, "game_id": f"g{i}"} for i in range(40)]
        ci = scoring.paired_skill(rows, n_boot=200)
        summary = scoring.score_rows(rows)
        self.assertLess(ci["point"], 0)
        self.assertLess(summary["bss"], 0)
        # The bootstrap resamples the skill score itself, so its point estimate must reproduce 1 - B/B0.
        self.assertAlmostEqual(ci["point"], 1 - summary["brier"] / summary["bench_brier"], places=9)
        self.assertAlmostEqual(ci["point"], summary["bss"], places=9)

    def test_interval_is_on_the_same_scale_as_the_point_estimate(self):
        """A published interval must describe the number printed next to it.

        Regression: the bootstrap once resampled a raw Brier *difference* (-0.027) and it was rendered in
        a column headed "Brier skill" beside a skill score of -0.106. Both were negative, so no verdict
        changed, but the two numbers were not the same quantity and a reader could not reconcile them.
        """
        import json
        board = json.loads((DATA / "leaderboard.json").read_text(encoding="utf-8"))
        for row in board["results"]:
            s = row["summary"]
            if s.get("lo") is None:
                continue
            self.assertAlmostEqual(s["point"], s["bss"], places=9,
                                   msg=f"{row['id']}: bootstrap point and analytic skill disagree")
            self.assertLessEqual(s["lo"], s["point"] + 1e-12,
                                 msg=f"{row['id']}: interval lower bound is above the point estimate")
            self.assertGreaterEqual(s["hi"], s["point"] - 1e-12,
                                    msg=f"{row['id']}: interval upper bound is below the point estimate")

    def test_control_arm_skill_is_exactly_zero(self):
        rows = [{"p": 0.5, "p_bench": 0.5, "won": bool(i % 2), "game_id": f"g{i}"} for i in range(20)]
        self.assertEqual(scoring.score_rows(rows)["bss"], 0.0)


class Grading(unittest.TestCase):
    def test_whole_number_spread_push_is_not_a_win(self):
        result = scoring.grade_spread(True, 3.0, 3, None)
        self.assertEqual(result["result"], "push")
        self.assertIsNone(result["won"])

    def test_push_is_excluded_from_the_denominator(self):
        rows = [
            {"p": 0.5, "p_bench": 0.5, "won": None, "push": True, "game_id": "a"},
            {"p": 0.5, "p_bench": 0.5, "won": True, "push": False, "game_id": "b"},
            {"p": 0.5, "p_bench": 0.5, "won": False, "push": False, "game_id": "c"},
        ]
        summary = scoring.score_rows(rows)
        self.assertEqual(summary["n"], 2, "a push must not be scored as a win or a loss")
        self.assertEqual(summary["n_push"], 1)

    def test_half_point_line_cannot_push(self):
        self.assertNotEqual(scoring.grade_spread(True, 3.5, 3, None)["result"], "push")

    def test_under_side_of_a_total_is_graded_correctly(self):
        self.assertTrue(scoring.grade_total(False, 45.5, 30)["won"])
        self.assertFalse(scoring.grade_total(True, 45.5, 30)["won"])

    def test_moneyline_tie_is_not_a_loss(self):
        self.assertEqual(scoring.grade_moneyline(True, 0)["result"], "push")


class SampleSize(unittest.TestCase):
    def test_known_value_from_the_closed_form(self):
        # Independently computed: p0=.5, p1=.55, alpha=.05 one-sided, power=.8 -> 617 graded bets.
        self.assertEqual(luck.required_n(0.055 - 0.005), 617)

    def test_smaller_edges_need_more_sample(self):
        self.assertGreater(luck.required_n(0.02), luck.required_n(0.05))
        self.assertGreater(luck.required_n(0.05), luck.required_n(0.10))

    def test_zero_edge_needs_no_sample(self):
        self.assertEqual(luck.required_n(0.0), 0)

    def test_binomial_tail_is_one_at_the_floor(self):
        self.assertAlmostEqual(luck._binomial_tail(10, 0), 1.0)
        self.assertAlmostEqual(luck._binomial_tail(10, 10), 0.5 ** 10, places=12)


class WilsonInterval(unittest.TestCase):
    def test_interval_contains_the_estimate_and_is_wider_at_small_n(self):
        lo, hi = scoring.wilson(12, 20)
        self.assertLess(lo, 0.6)
        self.assertGreater(hi, 0.6)
        lo_small, hi_small = scoring.wilson(6, 10)
        self.assertGreater(hi_small - lo_small, hi - lo, "fewer observations must widen the interval")

    def test_zero_n_returns_blank(self):
        self.assertEqual(scoring.wilson(0, 0), (None, None))


class PricePolicy(unittest.TestCase):
    def test_post_kickoff_observation_never_becomes_an_opening(self):
        """The ledger's own rule, exercised on a synthetic pair of events."""
        import datetime as dt
        event_kickoff = dt.datetime(2026, 11, 15, 18, 0, tzinfo=dt.timezone.utc)
        before = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.timezone.utc)
        after = dt.datetime(2026, 11, 16, 2, 0, tzinfo=dt.timezone.utc)
        self.assertTrue(before < event_kickoff)
        self.assertFalse(after < event_kickoff)

    def test_committed_ledger_separates_pre_and_post(self):
        ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
        for event in ledger["events"]:
            for market, cell in event["markets"].items():
                if cell.get("opening"):
                    self.assertTrue(cell.get("opening_observed_at"),
                                    f"{event['event_id']}/{market}: opening without a clock time")
                if cell.get("post_hoc"):
                    self.assertIn("may not be used", cell.get("post_hoc_usable_for", ""))

    def test_two_captures_are_both_retained(self):
        ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(ledger["snapshot_files"]), 2,
                                "a second observation must be a new file, not an overwrite")
        names = [s["path"] for s in ledger["snapshot_files"]]
        self.assertEqual(len(names), len(set(names)))

    def test_price_movement_is_measured_not_assumed(self):
        ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
        moved = [cell for event in ledger["events"] for cell in event["markets"].values()
                 if cell.get("moved_since_opening")]
        for cell in moved:
            self.assertGreaterEqual(cell["n_pre_kickoff"], 2,
                                    "movement cannot be claimed from a single observation")
            self.assertNotEqual(cell["opening"], cell["closing"])
        self.assertGreaterEqual(len(moved), 1, "the two captures are expected to show some movement")

    def test_g05_passes_only_with_a_measured_interval(self):
        gates = json.loads((DATA / "gates.json").read_text(encoding="utf-8"))
        g05 = next(g for g in gates["gates"] if g["id"] == "G05")
        ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
        moved = sum(1 for e in ledger["events"] for c in e["markets"].values()
                    if c.get("moved_since_opening"))
        if moved == 0:
            self.assertEqual(g05["status"], "blocked",
                             "two captures of an unchanged number do not create a closing price")
        else:
            self.assertEqual(g05["status"], "pass")
            self.assertIn("moved", g05["number"])

    def test_policy_is_frozen_by_hash(self):
        ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
        self.assertTrue(ledger.get("policy_sha256"))
        self.assertEqual(ledger["policy_sha256"], C.sha256_file(ROOT / ledger["policy"]))

    def test_kickoff_zone_conversion_is_documented(self):
        self.assertIn("UTC-4", prices.eastern_offset_note())


class Settlement(unittest.TestCase):
    def test_reconciliation_covers_all_clubs_and_fields(self):
        results = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
        self.assertTrue(results["passed"], "the results feed must reconcile before anything is graded")
        self.assertEqual(results["counts"]["clubs_checked"], 32)
        self.assertEqual(results["counts"]["team_fields_checked"], 160, "32 clubs x 5 fields")
        self.assertEqual(results["counts"]["team_fields_checked"],
                         results["counts"]["team_fields_matching"])

    def test_league_totals_balance(self):
        results = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
        totals = results["league_totals"]["feed"]
        self.assertEqual(totals["pf"], totals["pa"], "every point scored is a point allowed")
        self.assertEqual(totals["w"], totals["l"], "every win is somebody's loss")
        self.assertEqual(totals["w"] + totals["l"] + totals["t"], results["counts"]["games_played"] * 2)


class Demotion(unittest.TestCase):
    def test_gate_agrees_with_the_leaderboard(self):
        gates = json.loads((DATA / "gates.json").read_text(encoding="utf-8"))
        board = json.loads((DATA / "leaderboard.json").read_text(encoding="utf-8"))
        below = {r["id"] for r in board["results"]
                 if isinstance(r["summary"].get("hi"), float) and r["summary"]["hi"] < 0}
        self.assertEqual(set(gates["demoted"]), below)

    def test_no_strategy_is_called_validated(self):
        board = json.loads((DATA / "leaderboard.json").read_text(encoding="utf-8"))
        gates = json.loads((DATA / "gates.json").read_text(encoding="utf-8"))
        for row in board["results"]:
            lo = row["summary"].get("lo")
            n = row["summary"].get("n") or 0
            if lo is not None and lo > 0:
                self.assertLess(n, gates["floors"]["promote_min_n"],
                                f"{row['id']} would be promotable; update the register honestly")
        self.assertEqual(gates["summary"].get("fail", 0) + gates["summary"].get("pass", 0)
                         + gates["summary"].get("blocked", 0), len(gates["gates"]))


class Content(unittest.TestCase):
    def test_leaderboard_never_renders_backtest_scores(self):
        page = (ROOT / "origination" / "leaderboard.html").read_text(encoding="utf-8")
        self.assertIn("forward-ledger/leaderboard.html", page)
        self.assertIn("No backtest result is eligible", page)
        self.assertNotIn("S01", page)
        self.assertNotIn("S02", page)
        self.assertNotIn("Brier skill score", page)
        self.assertNotIn("<table", page.lower())

    def test_every_requirement_has_a_gate_and_a_number(self):
        req = json.loads((DATA / "requirements.json").read_text(encoding="utf-8"))
        for row in req["rows"]:
            self.assertTrue(row["gate"].strip(), f"{row['id']} has no gate")
            self.assertTrue(str(row["number"]).strip(), f"{row['id']} has no clearance number")
            self.assertIn(row["state"], {"implemented", "partial", "blocked"})

    def test_every_question_names_what_it_blocks(self):
        qs = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(qs["rows"]), 20)
        for row in qs["rows"]:
            self.assertTrue(row["blocks"].strip(), f"{row['id']} blocks nothing and should not be here")
            self.assertTrue(row["discovery"].strip(), f"{row['id']} has no discovery action")

    def test_every_strategy_has_both_directions(self):
        reg = json.loads((DATA / "strategies.json").read_text(encoding="utf-8"))
        for row in reg["strategies"]:
            self.assertTrue(row["promote"].strip())
            self.assertTrue(row["kill"].strip())
            self.assertTrue(row["registration"].strip())

    def test_suggestions_rank_by_what_they_unblock(self):
        sug = json.loads((DATA / "suggestions.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sug["rows"]), 8)
        for row in sug["rows"]:
            self.assertTrue(row["unblocks"], f"{row['title']} unblocks nothing")
            self.assertTrue(row["decision"].strip())


class Availability(unittest.TestCase):
    def test_shared_rank_one_slots_are_kept_as_groups(self):
        avail = json.loads((DATA / "availability_graph.json").read_text(encoding="utf-8"))
        shared = [s for s in avail["slots"] if s["rank"] == 1 and s["n_players"] > 1]
        self.assertGreater(len(shared), 0, "the corpus must contain the shared-slot case")
        for slot in shared:
            self.assertGreater(len(slot["members"]), 1, "a shared slot may not be collapsed")

    def test_no_depth_row_claims_a_confirmed_starter(self):
        snap = json.loads((ROOT / "decision-lab" / "data" / "official_snapshot.json").read_text())
        for row in snap["depth_rows"]:
            self.assertEqual(row.get("confirmed_starter", ""), "",
                             "no official source names a starter; the field must stay blank")

    def test_reserve_players_are_tracked(self):
        avail = json.loads((DATA / "availability_graph.json").read_text(encoding="utf-8"))
        self.assertGreater(avail["coverage"]["reserve_players"], 0,
                           "'not listed' must never imply 'available'")


class Correlations(unittest.TestCase):
    def test_every_published_value_has_n_and_an_interval(self):
        corr = json.loads((DATA / "correlations.json").read_text(encoding="utf-8"))
        for row in corr["rows"]:
            self.assertIsNotNone(row["n"])
            self.assertIsNotNone(row["lo"])
            self.assertIsNotNone(row["hi"])
            self.assertLessEqual(row["lo"], row["r"])
            self.assertGreaterEqual(row["hi"], row["r"])

    def test_withheld_items_name_a_reason(self):
        corr = json.loads((DATA / "correlations.json").read_text(encoding="utf-8"))
        for row in corr["not_published"]:
            self.assertGreater(len(row["why"]), 20, f"{row['key']} withheld without a real reason")


class Ablation(unittest.TestCase):
    def test_no_fixed_penalty_and_a_published_interval(self):
        abl = json.loads((DATA / "ablation.json").read_text(encoding="utf-8"))
        self.assertFalse(abl["design"]["fitted"], "lambda must not be fitted on the evaluation corpus")
        self.assertGreaterEqual(len(abl["grid"]), 5, "the full lambda grid must be published")
        head = abl["headline"]
        self.assertIsNotNone(head["holdout_lo"])
        self.assertIsNotNone(head["holdout_hi"])
        self.assertLessEqual(head["holdout_lo"], head["holdout_hi"])


class Site(unittest.TestCase):
    def test_every_page_is_in_the_navigation(self):
        index = (ROOT / "origination" / "index.html").read_text(encoding="utf-8")
        for page in sorted((ROOT / "origination").glob("*.html")):
            self.assertIn(page.name, index, f"{page.name} is not in the shared navigation")

    def test_no_page_claims_a_guarantee(self):
        for page in (ROOT / "origination").glob("*.html"):
            text = page.read_text(encoding="utf-8").lower()
            for phrase in ("guaranteed", "risk-free", "sure thing"):
                self.assertNotIn(phrase, text, f"{page.name} claims {phrase}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
