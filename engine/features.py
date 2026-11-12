"""Feature construction from the digest-verified snapshots.

Design rules that keep this honest:

* Every feature for a game is built only from information available *before* that game's kickoff.
  Anything derived from the game itself (score, result) is a target, never a feature.
* Rolling form uses only prior weeks of the same season, so no result of a future week can leak in.
* Availability features come from the weekly injury report and depth chart releases of the same
  week; they describe *what was known* when the game was played.
"""
from __future__ import annotations

import collections
import math
from typing import Iterable

import loader
import stats

TEAM_ALIASES = {"JAC": "JAX", "LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV", "LV": "LV",
                "WAS": "WAS", "WSH": "WAS", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
                "HST": "HOU", "SL": "LAR", "OAK ": "LV"}


def canon(team: str) -> str:
    t = (team or "").strip().upper()
    return TEAM_ALIASES.get(t, t)


def reg_games(seasons: Iterable[int] | None = None) -> list[dict]:
    out = [g for g in loader.games()
           if g["game_type"] == "REG" and g["home_score"] is not None and g["away_score"] is not None]
    if seasons is not None:
        keep = set(seasons)
        out = [g for g in out if g["season"] in keep]
    return out


def elo_ratings(games: list[dict], k: float = 20.0, hfa: float = 2.0, regress: float = 1.0 / 3.0,
                initial: float = 1505.0) -> dict[str, float]:
    """End-of-game Elo with a season regression toward the mean.

    Pre-game ratings are what a bettor could use, so they are stored on the game record as
    ``home_elo_pre`` / ``away_elo_pre`` *before* the result is applied.  This is the standard
    club-Elo-style scheme (FiveThirtyEight NFL Elo): margin-of-victory multiplier, home field
    worth `hfa` points on the rating scale, mean reversion between seasons.
    """
    ratings: dict[str, float] = {}
    last_season: dict[str, int] = {}
    for g in sorted(games, key=lambda x: (x["gameday"], x["game_id"])):
        h, a = canon(g["home"]), canon(g["away"])
        for t in (h, a):
            if t not in ratings:
                ratings[t] = initial
            if last_season.get(t) != g["season"]:
                if t in last_season:
                    ratings[t] = initial + (ratings[t] - initial) * regress
                last_season[t] = g["season"]
        rh, ra = ratings[h], ratings[a]
        g["home_elo_pre"], g["away_elo_pre"] = rh, ra
        # point expectation implied by the ratings, in the same sign convention as spread_line
        g["elo_expected_spread"] = (rh - ra) / 25.0
        expected_home = 1.0 / (1.0 + 10 ** ((ra - rh - hfa) / 400.0))
        margin = g["home_score"] - g["away_score"]
        # margin-of-victory multiplier damps blowouts of weak opponents (538 / PFR style)
        winner_elo = rh if margin > 0 else ra
        loser_elo = ra if margin > 0 else rh
        winner_elo += hfa if margin > 0 else 0
        elo_diff = abs(winner_elo - (loser_elo + (0 if margin > 0 else hfa)))
        mov_mult = math.log(abs(margin) + 1.0) * (2.2 / (elo_diff * 0.001 + 2.2))
        score = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
        delta = k * mov_mult * (score - expected_home)
        ratings[h] = rh + delta
        ratings[a] = ra - delta
        g["home_elo_post"], g["away_elo_post"] = ratings[h], ratings[a]
    return ratings


def rolling_team_form(games: list[dict], window: int = 6) -> None:
    """Attach leak-free prior-game rolling averages to every game."""
    hist: dict[str, list[dict]] = collections.defaultdict(list)
    for g in sorted(games, key=lambda x: (x["gameday"], x["game_id"])):
        for side, team, opp in (("home", canon(g["home"]), canon(g["away"])),
                                ("away", canon(g["away"]), canon(g["home"]))):
            opp_side = "away" if side == "home" else "home"
            past = hist[team][-window:]
            opp_past = hist[opp][-window:]
            for stat, vals in _agg(past).items():
                g[f"{side}_{stat}"] = vals
            for stat, vals in _agg(opp_past).items():
                g[f"{opp_side}_{stat}"] = vals  # opponent's form, mapped onto the same side key
            g[f"{side}_games_played"] = len(past)
            g[f"{side}_rest"] = g["home_rest"] if side == "home" else g["away_rest"]
        # append after features are computed (no leakage within the same game)
        hist[canon(g["home"])].append({"pts": g["home_score"], "opp": g["away_score"],
                                       "total": g["home_score"] + g["away_score"],
                                       "result": g["home_score"] - g["away_score"]})
        hist[canon(g["away"])].append({"pts": g["away_score"], "opp": g["home_score"],
                                       "total": g["home_score"] + g["away_score"],
                                       "result": g["away_score"] - g["home_score"]})


def _agg(past: list[dict]) -> dict[str, float]:
    if not past:
        return {k: float("nan") for k in ("form_pts", "form_opp_pts", "form_total", "form_diff")}
    return {
        "form_pts": stats.mean([p["pts"] for p in past]),
        "form_opp_pts": stats.mean([p["opp"] for p in past]),
        "form_total": stats.mean([p["total"] for p in past]),
        "form_diff": stats.mean([p["result"] for p in past]),
    }


# --------------------------------------------------------------------- availability
DEF_KEY_POSITIONS = {"CB", "S", "FS", "SS", "DB", "NB", "LB", "ILB", "OLB", "MLB", "DE", "DT",
                     "NT", "DL", "EDGE"}
OFF_KEY_POSITIONS = {"QB", "WR", "TE", "RB", "FB", "T", "G", "C", "OT", "OG", "OL"}


def depth_lookup(depth_rows: list[dict], week_of: dict[str, int] | None = None
                 ) -> dict[tuple[str, int, str], dict]:
    """(team, week, player name) -> depth record, normalised across both release schemas.

    nflverse changed the depth-chart schema after 2024.  Older files carry `depth_team`
    (1 = starter, 2/3/4 = backups) plus `club_code`/`full_name`; 2025+ files carry `pos_slot` and
    `pos_rank` plus `team`/`player_name`.  The loader normalises both to team/name/pos/rank, and an
    older row keeps its `depth_team` and maps it onto the same `rank` field so one code path works.
    """
    out: dict[tuple[str, int, str], dict] = {}
    for r in depth_rows:
        if week_of is not None:
            week = week_of.get((r.get("dt") or "")[:10])
            if week is None:
                continue
        else:
            week = int(r.get("week") or 0)
        name = (r.get("name") or r.get("full_name") or "").strip().lower()
        team = canon(r.get("team") or r.get("club_code") or "")
        if not name or not team:
            continue
        rank = r.get("rank")
        depth_team = r.get("depth_team")
        if rank is None or rank != rank:
            rank = float(depth_team) if depth_team not in (None, "") else float("nan")
        rec = {"rank": rank, "position": r.get("pos") or r.get("position", ""),
               "depth_position": r.get("depth_position", ""),
               "formation": r.get("formation", ""),
               "side": _side_of(r)}
        key = (team, week, name)
        prev = out.get(key)
        if prev is None or _rank_key(rank) < _rank_key(prev.get("rank")):
            out[key] = rec
    return out


def _rank_key(rank) -> float:
    if rank is None or rank != rank:
        return 99.0
    return float(rank)


def _side_of(r: dict) -> str:
    """Offence / defence / special teams, from the formation text or the position code."""
    formation = (r.get("formation") or "").lower().replace("base 4-3 d","defense").replace("base 3-4 d","defense").replace("base 4-3 o","offense").replace("base 3-4 o","offense")
    if formation:
        if formation.startswith("off"):
            return "off"
        if formation.startswith("def"):
            return "def"
        return "st"
    pos = (r.get("pos") or r.get("position") or "").upper()
    if pos in DEF_KEY_POSITIONS:
        return "def"
    if pos in OFF_KEY_POSITIONS:
        return "off"
    return "st"


def starter_depth_by_position(depth_rows: list[dict], week_of: dict[str, int] | None = None
                              ) -> dict[tuple[str, int], dict[str, int]]:
    """(team, week) -> {position: number of distinct players listed at the first depth slot}."""
    out: dict[tuple[str, int], dict[str, set]] = collections.defaultdict(
        lambda: collections.defaultdict(set))
    for r in depth_rows:
        team = canon(r.get("team") or r.get("club_code") or "")
        name = (r.get("name") or r.get("full_name") or "").strip().lower()
        if not team or not name:
            continue
        rank = r.get("rank")
        if rank is None or rank != rank:
            depth_team = r.get("depth_team")
            rank = float(depth_team) if depth_team not in (None, "") else float("nan")
        if _rank_key(rank) != 1.0:
            continue
        wk = week_of.get((r.get("dt") or "")[:10]) if week_of is not None else int(r.get("week") or 0)
        if wk is None:
            continue
        out[(team, wk)][r.get("pos") or r.get("position", "")].add(name)
    return {k: {p: len(v) for p, v in d.items()} for k, d in out.items()}


def weekly_availability(injury_rows: list[dict], depth_rows: list[dict],
                        season: int, week_of: dict[str, int] | None = None
                        ) -> dict[tuple[str, int], dict]:
    """Per team-week availability features from the injury report + that week's chart.

    * ``out_starters_def`` / ``out_starters_off``: players at the first depth slot that week whose
      report game status is Out or Doubtful.
    * ``q_starters_*``: first-slot players listed Questionable.
    * ``out_any_def`` / ``out_any_off``: every injury-report player in that position group, so a
      loss at the 2nd or 3rd string is still counted.
    * ``dnp_starters_*``: first-slot players who did not practise at all during the week.
    """
    depth = depth_lookup(depth_rows, week_of)
    starter_counts = starter_depth_by_position(depth_rows, week_of)

    def blank() -> dict:
        return {"out_starters_def": 0, "out_starters_off": 0, "q_starters_def": 0,
                "q_starters_off": 0, "out_any_def": 0, "out_any_off": 0,
                "dnp_starters_def": 0, "dnp_starters_off": 0, "report_rows": 0,
                "def_starter_slots": 0, "off_starter_slots": 0, "join_hits": 0}

    feats: dict[tuple[str, int], dict] = {}
    for r in injury_rows:
        if int(r["season"]) != season:
            continue
        team, week = canon(r["team"]), int(r["week"])
        f = feats.setdefault((team, week), blank())
        f["report_rows"] += 1
        pos = (r.get("position") or "").upper()
        is_def, is_off = pos in DEF_KEY_POSITIONS, pos in OFF_KEY_POSITIONS
        if not (is_def or is_off):
            continue
        if is_def:
            f["out_any_def"] += 1 if r["report_status"] in ("Out", "Doubtful") else 0
        else:
            f["out_any_off"] += 1 if r["report_status"] in ("Out", "Doubtful") else 0
        d = depth.get((team, week, (r.get("name") or "").strip().lower()))
        if d is None:
            continue
        if _rank_key(d.get("rank")) != 1.0:
            continue
        f["join_hits"] += 1
        side = d.get("side") or ("def" if is_def else "off")
        if r["report_status"] in ("Out", "Doubtful"):
            f["out_starters_def" if side == "def" else "out_starters_off"] += 1
        elif r["report_status"] == "Questionable":
            f["q_starters_def" if side == "def" else "q_starters_off"] += 1
        if (r.get("practice_status") or "").strip() == "Did Not Participate In Practice":
            f["dnp_starters_def" if side == "def" else "dnp_starters_off"] += 1

    for (team, week), pos_counts in starter_counts.items():
        f = feats.setdefault((team, week), blank())
        f["def_starter_slots"] = sum(n for p, n in pos_counts.items() if p in DEF_KEY_POSITIONS)
        f["off_starter_slots"] = sum(n for p, n in pos_counts.items() if p in OFF_KEY_POSITIONS)
    return feats


def availability_for_game(g: dict, feats: dict[tuple[str, int], dict]) -> dict:
    """Join the team-week availability features onto a game (same week's report)."""
    wk = g["week"]
    out = {}
    for side in ("home", "away"):
        team = canon(g[side])
        f = feats.get((team, wk))
        if f is None:
            out[f"{side}_avail_missing"] = 1
            for k in ("out_starters_def", "out_starters_off", "q_starters_def", "q_starters_off",
                      "out_any_def", "out_any_off", "dnp_starters_def", "dnp_starters_off",
                      "report_rows", "def_starter_slots", "off_starter_slots"):
                out[f"{side}_{k}"] = float("nan")
        else:
            out[f"{side}_avail_missing"] = 0
            for k, v in f.items():
                out[f"{side}_{k}"] = v
    return out


def snap_shares(snap_rows: list[dict], week: int, window: int = 1) -> dict[tuple[str, str], float]:
    """(team, player) -> mean offensive snap share over the last `window` completed weeks."""
    by_week: dict[int, list[dict]] = collections.defaultdict(list)
    for r in snap_rows:
        try:
            w = int(r["week"])
        except (TypeError, ValueError):
            continue
        if w < week and w >= week - window:
            by_week[w].append(r)
    shares: dict[tuple[str, str], float] = {}
    for w, rows in by_week.items():
        by_team_snaps: dict[str, float] = collections.defaultdict(float)
        for r in rows:
            if r["off_snaps"] and r["off_snaps"] > 0:
                by_team_snaps[(canon(r["team"]), r["game_id"])] = max(
                    by_team_snaps.get((canon(r["team"]), r["game_id"]), 0.0), r["off_snaps"])
        for r in rows:
            if not r["off_snaps"] or r["off_snaps"] <= 0:
                continue
            total = by_team_snaps.get((canon(r["team"]), r["game_id"]))
            if not total:
                continue
            key = (canon(r["team"]), (r["player"] or "").strip().lower())
            shares.setdefault(key, []).append(r["off_snaps"] / total)
    return {k: sum(v) / len(v) for k, v in shares.items()}


def snapshot_week_map(depth_rows: list[dict], games: list[dict], season: int) -> dict[str, int]:
    """Map each daily depth-chart snapshot date onto the game week whose report it precedes.

    A game's injury report is filed for its week, so the chart that matters is the last one
    published *before that week's first kickoff*.  Snapshots that fall inside a week's play window
    (after the first kickoff and before the next week's report) are attributed to the following week,
    because they describe the roster build-up to the next game.
    """
    kicks = sorted({(g["week"], g["gameday"]) for g in games
                    if g["season"] == season and g["game_type"] == "REG"})
    if not kicks:
        return {}
    first_kick: dict[int, str] = {}
    for week, day in kicks:
        if week not in first_kick or day < first_kick[week]:
            first_kick[week] = day
    weeks = sorted(first_kick)
    out: dict[str, int] = {}
    dates = sorted({(r.get("dt") or "")[:10] for r in depth_rows if r.get("dt")})
    for d in dates:
        target = None
        for week in weeks:
            if d < first_kick[week]:
                target = week
                break
        if target is None:
            target = weeks[-1]
        out[d] = target
    return out
