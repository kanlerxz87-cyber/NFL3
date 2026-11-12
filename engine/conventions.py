"""The single place where sign conventions live.

Getting a sign wrong silently flips every graded bet, so every module imports from here and
nothing else re-derives a convention inline.  Verified against the official nflverse schedule
dictionary (data-raw/dictionary_schedules.csv) and spot-checked against real rows:

    spread_line : positive  => HOME team is favoured by that many points
    result      : home_score - away_score   (positive => home won)
    total       : home_score + away_score

Examples from the official file that pin this down:
    2025_01_DAL_PHI  result +4   spread_line +8.5   -> PHI were 8.5-point home favourites
    2025_01_KC_LAC   result +6   spread_line -3.0   -> KC were 3-point road favourites
    2025_01_ARI_NO   result -7   spread_line -6.0   -> NO were 6-point home favourites
"""
from __future__ import annotations


def home_margin(result: float) -> float:
    """Points the home team won by (negative if they lost)."""
    return result


def home_cover_margin(result: float, spread_line: float) -> float:
    """How much the home side beat its number by, in points.

    ``spread_line`` is the number of points added to the home team's margin for settlement.  With
    the official schema (positive = home favoured), the home side covers when
    ``result - spread_line > 0``.  Worked example: 2025_01_DAL_PHI, PHI won by 4 (result +4) but
    were 8.5-point favourites (spread_line +8.5) -> 4 - 8.5 = -4.5, so the home side did not cover.
    Positive return value means the home side covered.
    """
    return result - spread_line


def home_covers(result: float, spread_line: float) -> tuple[bool, bool]:
    m = home_cover_margin(result, spread_line)
    return (m > 0, m == 0)


def away_covers(result: float, spread_line: float) -> tuple[bool, bool]:
    m = home_cover_margin(result, spread_line)
    return (m < 0, m == 0)


def over_wins(total: float, total_line: float) -> tuple[bool, bool]:
    if total == total_line:
        return (False, True)
    return (total > total_line, False)


def model_edge_home(model_spread: float, spread_line: float) -> float:
    """Positive: our number makes the home side better than the market's number."""
    return model_spread - spread_line


def model_edge_over(model_total: float, total_line: float) -> float:
    """Positive: our number makes the over better than the market's number."""
    return model_total - total_line
