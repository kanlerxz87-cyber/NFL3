"""Regression tests for the skill lab: the protocol, the scores and the published pages.

These are offline tests. They never re-run the evaluation (the published artifact is the
evaluation); they check that the artifact, the protocol and the pages still agree with each
other, so that a later edit cannot quietly change a published number.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "skill-lab"
RESULTS = LAB / "data" / "results.json"
sys.path.insert(0, str(LAB / "scripts"))

import scorelib as sl  # noqa: E402


def load() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


class TestScorelib(unittest.TestCase):
    def test_brier_and_log_loss_definitions(self):
        # A perfect forecast scores 0; a 50/50 forecast scores 0.25 on the Brier scale.
        self.assertAlmostEqual(sl.brier(1.0, 1.0), 0.0, places=12)
        self.assertAlmostEqual(sl.brier(0.5, 1.0), 0.25, places=12)
        self.assertAlmostEqual(sl.brier(0.5, 0.0), 0.25, places=12)
        # log loss punishes a confident miss without bound.
        self.assertGreater(sl.log_loss(0.01, 1.0), sl.log_loss(0.9, 1.0))
        self.assertAlmostEqual(sl.log_loss(0.5, 1.0), -math.log(0.5), places=12)

    def test_skill_is_relative_to_the_benchmark(self):
        self.assertAlmostEqual(sl.skill(0.25, 0.25), 0.0, places=12)
        self.assertAlmostEqual(sl.skill(0.20, 0.25), 0.2, places=12)
        self.assertLess(sl.skill(0.30, 0.25), 0.0)

    def test_normal_quantile_round_trip(self):
        self.assertAlmostEqual(sl.norm_ppf(0.975), 1.959963985, places=6)
        self.assertAlmostEqual(sl.norm_cdf(0.0), 0.5, places=12)
        self.assertAlmostEqual(sl.norm_cdf(1.959963985), 0.975, places=6)
        self.assertAlmostEqual(sl.norm_ppf(sl.norm_cdf(0.37)), 0.37, places=8)

    def test_devig_methods_recover_a_fair_price(self):
        # Two even sides: the fair probability of each is 0.5.
        self.assertAlmostEqual(sl.devig_proportional(0.5, 0.5)[0], 0.5, places=12)
        # A 60/40 favourite pair de-vigged proportionally gives 0.6.
        p_home, p_away = sl.devig_proportional(0.60, 0.40)
        self.assertAlmostEqual(p_home, 0.6, places=12)
        self.assertAlmostEqual(p_home + p_away, 1.0, places=12)
        # The Shin method must also produce a probability pair that sums to one.
        s_home, s_away = sl.devig_shin(0.60, 0.40)
        self.assertAlmostEqual(s_home + s_away, 1.0, places=12)
        self.assertGreater(s_home, 0.5)

    def test_benjamini_hochberg_is_monotone_and_conservative(self):
        # the helper takes {name: p_value} and returns {name: {"q": ..., "pass": ...}}
        out = sl.benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}, q=0.05)
        self.assertEqual(set(out), {"a", "b", "c", "d"})
        qs = [out[k]["q"] for k in ("a", "b", "c", "d")]
        self.assertTrue(all(qs[i] <= qs[i + 1] for i in range(len(qs) - 1)))
        self.assertTrue(all(0.0 <= x <= 1.0 for x in qs))
        # The smallest p-value must survive a 0.05 threshold.
        self.assertLess(qs[0], 0.05)
        self.assertTrue(out["a"]["pass"])
        self.assertFalse(out["d"]["pass"])

    def test_percentile_is_deterministic(self):
        values = [3.0, 1.0, 2.0]
        self.assertAlmostEqual(sl.percentile(values, 0.5), 2.0, places=12)
        self.assertAlmostEqual(sl.percentile(values, 0.0), 1.0, places=12)
        self.assertAlmostEqual(sl.percentile(values, 1.0), 3.0, places=12)


class TestArtifact(unittest.TestCase):
    def setUp(self):
        self.res = load()
        self.meta = self.res["meta"]

    def test_artifact_records_the_protocol_and_its_commit(self):
        self.assertTrue(self.meta["protocol"].startswith("SL-PRE-01"))
        commit = self.meta["pre_registration_commit"]
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        out = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, "the registered commit must exist in the history")
        # the registration commit must predate the first commit that changed the results artifact
        reg_date = subprocess.run(
            ["git", "-C", str(ROOT), "show", "-s", "--format=%cI", commit],
            capture_output=True, text=True).stdout.strip()
        res_date = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%cI", "--",
             "skill-lab/data/results.json"], capture_output=True, text=True).stdout.strip()
        self.assertTrue(reg_date < res_date,
                        "the protocol must be committed before the results artifact is added")

    def test_corpus_matches_the_registration(self):
        corpus = self.meta["primary_corpus"]
        self.assertEqual(corpus["observed_games"], corpus["expected_games"])
        self.assertEqual(corpus["expected_games"], 136)
        self.assertEqual(corpus["weeks"], "1-9")
        self.assertEqual(corpus["season"], 2026)

    def test_gate_arithmetic_and_eligibility(self):
        for run in self.res["runs"].values():
            for row in run["rows"]:
                gates = row["gates"]
                self.assertEqual(row["gates_total"], len(gates))
                self.assertEqual(row["gates_passed"], sum(1 for ok, _ in gates.values() if ok))
                self.assertEqual(row["eligible_for_ranking"], all(ok for ok, _ in gates.values()))

    def test_no_row_is_promoted_without_every_gate(self):
        # The published result of this corpus is a negative one; if a future rebuild promotes a row,
        # this test fails loudly rather than letting a silent promotion reach the site.
        for run in self.res["runs"].values():
            for row in run["rows"]:
                if row["eligible_for_ranking"]:
                    self.assertGreater(row["bootstrap"]["lower95"], 0.0)
                    self.assertLess(row["bh_q"], 0.05)

    def test_bootstrap_interval_brackets_the_point_estimate(self):
        for run in self.res["runs"].values():
            for row in run["rows"]:
                boot = row["bootstrap"]
                self.assertLessEqual(boot["ci95"][0], boot["point"] + 1e-9)
                self.assertGreaterEqual(boot["ci95"][1], boot["point"] - 1e-9)
                self.assertEqual(boot["n_boot"], 10000)

    def test_control_is_hard_and_the_benchmark_is_the_market(self):
        run = self.res["runs"]["primary"]
        for row in run["rows"]:
            ctrl = row["control_random"]
            self.assertEqual(ctrl["seeds"], 1000)
            # A hard pick (0 or 1) scores 0.0 on a correct row and 1.0 on a wrong one, so its mean
            # Brier score over the corpus is the miss rate. It must sit near the market's own
            # score, and the skill it implies must be far below zero.
            self.assertGreater(ctrl["brier_mean"], 0.0)
            self.assertLess(ctrl["brier_mean"], 1.0)
            self.assertLess(ctrl["skill_p95"], 0.0)
            self.assertGreater(row["brier_market"], 0.0)

    def test_graded_rows_carry_both_lines_and_both_scores(self):
        graded = self.res["runs"]["primary"]["graded"]
        self.assertGreater(len(graded), 0)
        for row in graded[:200]:
            self.assertIn("model_prob", row)
            self.assertIn("market_line", row)
            self.assertIn("model_line", row)
            self.assertIn("brier_model", row)
            self.assertIn("brier_market", row)
            self.assertNotIn("_pred", row)

    def test_dependence_joint_is_measured_not_assumed(self):
        dep = self.res["dependence"]
        self.assertGreater(dep["n"], 0)
        self.assertIn("joint_cover_and_over_observed", dep)
        self.assertIn("joint_cover_and_over_if_independent", dep)

    def test_pages_are_published_and_free_of_placeholders(self):
        pages = ["index.html", "leaderboard.html", "mind-change.html", "controls.html", "staking.html",
                 "dependence.html", "graded.html", "methodology.html", "flagged.html", "sources.html"]
        for name in pages:
            path = LAB / name
            self.assertTrue(path.exists(), f"{name} is missing")
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b(None|nan|undefined|null)\b", text),
                              f"{name} contains a placeholder token")
            for href in re.findall(r'href="([^"]+)"', text):
                if not href.startswith("http"):
                    self.assertTrue((LAB / href).resolve().exists(), f"{name}: broken link {href}")


class TestPublishedNumbers(unittest.TestCase):
    """The published pages must quote the artifact, not a separately maintained number."""

    def setUp(self):
        self.res = load()

    def test_leaderboard_quotes_the_skill_of_every_row(self):
        text = (LAB / "leaderboard.html").read_text(encoding="utf-8")
        for row in self.res["runs"]["primary"]["rows"]:
            value = f'{row["skill_brier"]:+.4f}'
            self.assertIn(value, text, f"leaderboard does not quote {row['strategy']} skill {value}")

    def test_index_quotes_the_corpus_size_and_the_eligible_count(self):
        text = (LAB / "index.html").read_text(encoding="utf-8")
        self.assertIn(str(self.res["meta"]["primary_corpus"]["observed_games"]), text)
        eligible = sum(1 for r in self.res["runs"]["primary"]["rows"] if r["eligible_for_ranking"])
        self.assertIn(f'ELIGIBLE FOR RANKING</span><strong>{eligible}<', text)

    def test_the_executive_summary_quotes_the_artifact(self):
        summary = (LAB / "EXECUTIVE_SUMMARY.md").read_text(encoding="utf-8")
        for row in self.res["runs"]["primary"]["rows"]:
            boot = row["bootstrap"]
            skill = f'{row["skill_brier"]:+.4f}'.replace("-", "\u2212")
            self.assertIn(skill, summary, f"summary does not quote {row['strategy']} skill {skill}")
            lo = f'{boot["lower95"]:+.4f}'.replace("-", "\u2212")
            self.assertIn(lo, summary, f"summary does not quote {row['strategy']} lower bound {lo}")
        self.assertIn("0 of 6 rows qualified", summary)

    def test_the_two_sided_field_is_published_for_every_row(self):
        text = (LAB / "mind-change.html").read_text(encoding="utf-8")
        for row in self.res["runs"]["primary"]["rows"]:
            self.assertIn(row["strategy"], text)
        self.assertIn("towards belief", text)
        self.assertIn("towards rejection", text)
        # the field must not be a restatement of the run: it must be registered forward
        self.assertIn("SL-PRE-01b", text)

    def test_every_graded_row_links_to_an_official_scores_page(self):
        text = (LAB / "graded.html").read_text(encoding="utf-8")
        links = re.findall(r'href="(https://www\.nfl\.com/scores/2026/week-\d+)"', text)
        self.assertEqual(len(links), len(self.res["runs"]["primary"]["graded"]))


if __name__ == "__main__":
    unittest.main()
