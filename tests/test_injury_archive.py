#!/usr/bin/env python3
"""Offline tests for the injury-archive library. Every fixture is SYNTHETIC.

The fixtures use invented club names and invented players, in the same markup shape the verified
parser expects. They prove the drift alarms, the join rules, the interval arithmetic and the
fail-closed behaviour. They are not evidence about any NFL player, club or page.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "injury-archive" / "scripts"))
import archive_lib as lib  # noqa: E402

TEAM_HEAD = '<div class="d3-o-section-sub-title"><span>{team}</span></div>'
TABLE_HEAD = (
    '<table class="x"><thead><tr><th scope="col">Player</th><th scope="col">Position</th>'
    '<th scope="col">Injuries</th><th scope="col">Practice Status</th><th scope="col">Game Status</th>'
    "</tr></thead><tbody>"
)


def player_row(name: str, slug: str, pos: str, injury: str, practice: str, game: str) -> str:
    return (f'<tr><td><a href="https://www.nfl.com/players/{slug}/">{name}</a></td><td>{pos}</td>'
            f"<td>{injury}</td><td>{practice}</td><td>{game}</td></tr>")


def injury_page(sections: str, week: int = 10, season: int = 2026) -> bytes:
    return (f"<!doctype html><html><head><title>Official NFL Injury Report for Players - "
            f"Week {week} of the {season} Season | NFL.com</title></head><body>"
            f'<h2 class="d3-o-section-title">SUNDAY, NOVEMBER 15TH</h2>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">AAA</span>'
            f'<span class="nfl-c-matchup-strip__team-abbreviation">BBB</span>{sections}</body></html>'
            ).encode("utf-8")


GOOD_SECTION = (
    TEAM_HEAD.format(team="Lions") + TABLE_HEAD
    + player_row("Alpha One", "alpha-one", "S", "Knee", "Did Not Participate In Practice", "Out")
    + player_row("Beta Two", "beta-two", "WR", "Rib", "Limited Participation in Practice", "Questionable")
    + player_row("Gamma Three", "gamma-three", "QB", "", "Full Participation in Practice", "")
    + "</tbody></table>"
)

INACTIVES = """
<html><body><h1>NFL Week 10 inactives: Players ruled out for Sunday's 2026 NFL season games</h1>
<h2>EARLY GAMES</h2><h3>LIONS</h3>
<ul><li>CB Alpha One</li><li>C Beta Two</li><li>QB Delta Four (emergency third QB)</li></ul>
<h3>BEARS</h3><ul><li>S Epsilon Five</li></ul>
</body></html>
""".encode("utf-8")


class InjuryParse(unittest.TestCase):
    def test_clean_page_parses(self):
        parsed = lib.parse_injuries(injury_page(GOOD_SECTION), "https://www.nfl.com/injuries/league/2026/REG10",
                                    "2026-11-16T00:00:00Z")
        self.assertEqual(parsed["failures"], [])
        self.assertEqual(parsed["injury_rows"], 3)
        self.assertEqual({r["game_status"] for r in parsed["rows"]}, {"Out", "Questionable", ""})
        self.assertEqual(parsed["week"], 10)
        self.assertEqual(parsed["season"], 2026)

    def test_unrecognised_label_is_a_failure_not_a_mapping(self):
        bad = GOOD_SECTION.replace("Questionable", "Probable")
        parsed = lib.parse_injuries(injury_page(bad), "https://www.nfl.com/injuries/", "2026-11-16T00:00:00Z")
        self.assertTrue(any("unrecognised game status" in f for f in parsed["failures"]))

    def test_missing_column_is_a_failure(self):
        bad = GOOD_SECTION.replace("<th scope=\"col\">Game Status</th>", "")
        parsed = lib.parse_injuries(injury_page(bad), "https://www.nfl.com/injuries/", "2026-11-16T00:00:00Z")
        self.assertTrue(any("missing column" in f for f in parsed["failures"]))

    def test_non_official_player_link_is_a_failure(self):
        bad = GOOD_SECTION.replace("https://www.nfl.com/players/alpha-one/", "https://example.com/a/")
        parsed = lib.parse_injuries(injury_page(bad), "https://www.nfl.com/injuries/", "2026-11-16T00:00:00Z")
        self.assertTrue(any("not an official nfl.com player page" in f for f in parsed["failures"]))


class InactivesParse(unittest.TestCase):
    NICK = {"LIONS", "BEARS"}

    def test_clean_article_parses(self):
        parsed = lib.parse_inactives(INACTIVES, "https://www.nfl.com/news/x", "2026-11-16T00:00:00Z", self.NICK)
        self.assertEqual(parsed["failures"], [])
        self.assertEqual(sorted(parsed["clubs"]), ["BEARS", "LIONS"])
        self.assertEqual(len(parsed["rows"]), 4)
        lions = parsed["clubs"]["LIONS"]["players"]
        self.assertEqual(lions[0], {"club": "LIONS", "position": "CB", "player": "Alpha One",
                                    "raw": "CB Alpha One", "emergency_qb": False})
        self.assertTrue(lions[2]["emergency_qb"])
        self.assertEqual(parsed["clubs"]["LIONS"]["game_section"], "EARLY GAMES")

    def test_compound_position_token(self):
        position, player = lib.split_inactive_item("C/G Keylan Rutledge")
        self.assertEqual((position, player), ("C/G", "Keylan Rutledge"))

    def test_unknown_heading_is_flagged(self):
        article = INACTIVES.decode().replace("<h3>BEARS</h3>", "<h3>SHARKS</h3>").encode()
        parsed = lib.parse_inactives(article, "https://www.nfl.com/news/x", "2026-11-16T00:00:00Z", self.NICK)
        self.assertTrue(any("unrecognised club heading" in f for f in parsed["failures"]))

    def test_positionless_entry_is_kept_verbatim(self):
        article = INACTIVES.decode().replace("<li>CB Alpha One</li>", "<li>Alpha One</li>").encode()
        parsed = lib.parse_inactives(article, "https://www.nfl.com/news/x", "2026-11-16T00:00:00Z", self.NICK)
        self.assertEqual(parsed["clubs"]["LIONS"]["players"][0]["position"], "")
        self.assertEqual(parsed["clubs"]["LIONS"]["players"][0]["player"], "Alpha One")


class Join(unittest.TestCase):
    def setUp(self):
        self.injury = lib.parse_injuries(injury_page(GOOD_SECTION), "https://www.nfl.com/injuries/",
                                         "2026-11-16T00:00:00Z")
        self.inactives = lib.parse_inactives(INACTIVES, "https://www.nfl.com/news/x",
                                             "2026-11-16T00:00:00Z", {"LIONS", "BEARS"})

    def test_designated_players_join_by_name_and_club(self):
        joined = lib.join_week(self.injury, self.inactives)
        outcomes = {(o["player"], o["outcome"]) for o in joined["observations"]}
        self.assertIn(("Alpha One", "inactive (on the official inactive list)"), outcomes)
        self.assertIn(("Beta Two", "inactive (on the official inactive list)"), outcomes)

    def test_blank_designation_is_out_of_scope(self):
        joined = lib.join_week(self.injury, self.inactives)
        self.assertNotIn("Gamma Three", {o["player"] for o in joined["observations"]})

    def test_uncovered_club_is_excluded_not_counted_active(self):
        injury = lib.parse_injuries(
            injury_page(TEAM_HEAD.format(team="Bears") + TABLE_HEAD
                        + player_row("Zeta Six", "zeta-six", "LB", "Ankle", "Did Not Participate In Practice", "Out")
                        + "</tbody></table>"),
            "https://www.nfl.com/injuries/", "2026-11-16T00:00:00Z")
        inactives = lib.parse_inactives(INACTIVES, "https://www.nfl.com/news/x",
                                        "2026-11-16T00:00:00Z", {"BEARS"})
        inactives["clubs"].pop("BEARS")
        joined = lib.join_week(injury, inactives)
        row = joined["observations"][0]
        self.assertEqual(row["outcome"], "club not in the inactives article")
        summary = lib.summarise(joined["observations"])[0]
        self.assertEqual((summary["n"], summary["uncovered"]), (0, 1))

    def test_suffix_insensitive_match(self):
        article = INACTIVES.decode().replace("Alpha One", "Alpha One Jr.").encode()
        inactives = lib.parse_inactives(article, "https://www.nfl.com/news/x", "2026-11-16T00:00:00Z",
                                        {"LIONS", "BEARS"})
        joined = lib.join_week(self.injury, inactives)
        row = next(o for o in joined["observations"] if o["player"] == "Alpha One")
        self.assertEqual(row["match_method"], "suffix-insensitive")

    def test_name_normalisation_handles_punctuation(self):
        self.assertEqual(lib.norm_name("D.J. Reed"), "dj reed")
        self.assertEqual(lib.norm_name("Ar'maj Reed- Adams"), "armaj reed adams")
        self.assertEqual(lib.norm_name("Riley Leonard (emergency third QB)"), "riley leonard")
        self.assertEqual(lib.norm_name_no_suffix("Dont'e Thornton Jr."), "donte thornton")


class Interval(unittest.TestCase):
    def test_wilson_is_sane(self):
        low, high = lib.wilson(0, 10)
        self.assertTrue(0.0 <= low < 0.001 and 0.2 < high < 0.35)
        low, high = lib.wilson(10, 10)
        self.assertTrue(0.6 < low < 0.8 and high > 0.999)

    def test_zero_n_publishes_no_interval_and_no_rate(self):
        summary = lib.summarise([{"game_status": "Out", "outcome": "club not in the inactives article",
                                  "emergency_qb": False}])[0]
        self.assertIsNone(summary["inactive_rate"])
        self.assertEqual(summary["n"], 0)

    def test_rate_and_components_add_up(self):
        rows = [
            {"game_status": "Out", "outcome": "inactive (on the official inactive list)", "emergency_qb": False},
            {"game_status": "Out", "outcome": "active (not on the inactive list)", "emergency_qb": False},
            {"game_status": "Out", "outcome": "ambiguous name match", "emergency_qb": False},
        ]
        summary = lib.summarise(rows)[0]
        self.assertEqual((summary["n"], summary["inactive"], summary["active"], summary["ambiguous"]),
                         (2, 1, 1, 1))
        self.assertAlmostEqual(summary["inactive_rate"], 0.5)


class Urls(unittest.TestCase):
    def test_source_url_patterns(self):
        self.assertEqual(lib.injuries_url(2021, 1), "https://www.nfl.com/injuries/league/2021/REG1")
        self.assertEqual(lib.inactives_url(2026, 10),
                         "https://www.nfl.com/news/nfl-week-10-inactives-players-ruled-out-sunday-2026-season")

    def test_nickname_of_official_club_names(self):
        self.assertEqual(lib.nickname("New England Patriots"), "PATRIOTS")
        self.assertEqual(lib.nickname("San Francisco 49ers"), "49ERS")
        self.assertEqual(lib.nickname("Washington Commanders"), "COMMANDERS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
