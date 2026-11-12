"""Load the digest-verified snapshots from data/raw/ (gzip kept in the repo).

Every loader returns plain dicts/lists so the engine stays dependency-free, and every loader
records which release asset it came from so the published tables can carry a real source link.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
from typing import Iterator

RAW = os.environ.get("NFL3_RAW", os.path.join(os.path.dirname(__file__), "..", "data", "raw"))


def manifest() -> dict:
    path = os.path.join(RAW, "manifest.json")
    if not os.path.exists(path):
        return {"files": {}, "failures": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _open_csv(basename: str) -> io.TextIOWrapper | None:
    for name in (basename + ".gz", basename):
        p = os.path.join(RAW, name)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            if p.endswith(".gz"):
                return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8", newline="")
            return open(p, encoding="utf-8", newline="")
    return None


def rows(basename: str) -> Iterator[dict]:
    f = _open_csv(basename)
    if f is None:
        return iter(())
    try:
        for r in csv.DictReader(f):
            yield r
    finally:
        f.close()


def available(basename: str) -> bool:
    return _open_csv(basename) is not None


def asset_url(basename: str) -> str | None:
    """Resolve the release URL for a stored file name."""
    m = manifest().get("files", {})
    for rec in m.values():
        if rec.get("stored_as", "").endswith(basename) or os.path.basename(rec.get("asset_url", "")) == basename:
            return rec.get("asset_url")
    # manifests store the gzip base name; do a suffix match too
    for rec in m.values():
        if basename in rec.get("stored_as", ""):
            return rec.get("asset_url")
    return None


def num(v: str | None) -> float:
    if v is None:
        return float("nan")
    v = v.strip()
    if not v:
        return float("nan")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def opt(v: str | None) -> float | None:
    x = num(v)
    return None if x != x else x


# ------------------------------------------------------------------ domain loaders
def games() -> list[dict]:
    """Schedule + results + closing lines (nflverse `games.csv`)."""
    out = []
    for r in rows("games.csv"):
        g = {
            "game_id": r["game_id"], "season": int(r["season"]), "week": int(r["week"] or 0),
            "game_type": r["game_type"], "gameday": r["gameday"],
            "away": r["away_team"], "home": r["home_team"],
            "away_score": opt(r.get("away_score")), "home_score": opt(r.get("home_score")),
            "result": opt(r.get("result")), "total": opt(r.get("total")),
            "spread_line": opt(r.get("spread_line")), "total_line": opt(r.get("total_line")),
            "away_ml": opt(r.get("away_moneyline")), "home_ml": opt(r.get("home_moneyline")),
            "away_spread_odds": opt(r.get("away_spread_odds")),
            "home_spread_odds": opt(r.get("home_spread_odds")),
            "over_odds": opt(r.get("over_odds")), "under_odds": opt(r.get("under_odds")),
            "roof": r.get("roof") or "", "surface": r.get("surface") or "",
            "temp": opt(r.get("temp")), "wind": opt(r.get("wind")),
            "away_rest": opt(r.get("away_rest")), "home_rest": opt(r.get("home_rest")),
            "div_game": r.get("div_game") or "", "location": r.get("location") or "",
            "referee": r.get("referee") or "",
            "away_qb": r.get("away_qb_id") or "", "home_qb": r.get("home_qb_id") or "",
            "overtime": r.get("overtime") or "",
        }
        out.append(g)
    out.sort(key=lambda g: (g["gameday"], g["game_id"]))
    return out


def injuries() -> list[dict]:
    out = []
    for r in rows("injuries_2026.csv"):
        out.append({
            "season": int(r["season"]), "week": int(r["week"] or 0), "team": r["team"],
            "gsis_id": r.get("gsis_id", ""), "position": r.get("position", ""),
            "name": r.get("full_name", ""),
            "report_injury": r.get("report_primary_injury", ""),
            "report_status": r.get("report_status", ""),
            "practice_status": r.get("practice_status", ""),
            "practice_injury": r.get("practice_primary_injury", ""),
        })
    return out


def depth_charts() -> list[dict]:
    out = []
    for r in rows("depth_charts_2026.csv"):
        if not r.get("dt"):
            continue
        out.append({
            "dt": r["dt"], "team": r.get("team", ""), "name": r.get("player_name", ""),
            "gsis_id": r.get("gsis_id", ""), "pos": r.get("pos_abb") or r.get("pos_name", ""),
            "pos_grp": r.get("pos_grp", ""), "slot": num(r.get("pos_slot")),
            "rank": num(r.get("pos_rank")),
        })
    return out


def snaps() -> list[dict]:
    out = []
    for r in rows("snap_counts_2026.csv"):
        out.append({
            "game_id": r.get("game_id", ""), "season": r.get("season", ""), "week": r.get("week", ""),
            "team": r.get("team", ""), "player": r.get("player", ""), "gsis_id": r.get("gsis_id", ""),
            "position": r.get("position", ""),
            "off_snaps": num(r.get("offense_snaps")), "off_pct": num(r.get("offense_pct")),
            "def_snaps": num(r.get("defense_snaps")), "def_pct": num(r.get("defense_pct")),
        })
    return out


def stats_team_week() -> list[dict]:
    out = []
    for r in rows("stats_team_week_2026.csv"):
        if r.get("season_type") != "REG":
            continue
        out.append({
            "season": int(r["season"]), "week": int(r["week"] or 0), "team": r["team"],
            "opponent": r.get("opponent_team", ""),
            "points": num(r.get("points")), "points_allowed": num(r.get("points_allowed")),
            "pass_yards": num(r.get("passing_yards")), "rush_yards": num(r.get("rushing_yards")),
            "pass_yards_allowed": num(r.get("passing_yards_allowed")),
            "rush_yards_allowed": num(r.get("rushing_yards_allowed")),
            "pass_td": num(r.get("passing_tds")), "rush_td": num(r.get("rushing_tds")),
            "sacks": num(r.get("def_sacks")), "turnovers": num(r.get("turnovers")),
            "epa_off": num(r.get("passing_epa")) + num(r.get("rushing_epa")),
        })
    return out


def rosters() -> list[dict]:
    out = []
    for r in rows("roster_2026.csv"):
        out.append({
            "team": r.get("team", ""), "player": r.get("full_name", ""),
            "gsis_id": r.get("gsis_id", ""), "position": r.get("position", ""),
            "status": r.get("status", ""), "depth_chart_position": r.get("depth_chart_position", ""),
        })
    return out


def depth_rows_for_season(season: int) -> list[dict]:
    """Depth chart rows for any season, normalised across the two release schemas.

    Pre-2025 files:  season, club_code, week, game_type, depth_team, formation, gsis_id, position,
                     depth_position, full_name
    2025+ files:     dt, team, player_name, pos_grp, pos_abb, pos_slot, pos_rank  (no week field)

    Normalised record: {team, name, gsis_id, pos, slot, rank, formation, week, dt}
    For the older schema ``rank`` is filled from ``depth_team`` (1 = starter) so one code path works.
    """
    out = []
    for r in rows(f"depth_charts_{season}.csv"):
        if r.get("depth_team") is not None or "club_code" in r:
            team = r.get("club_code", "")
            name = r.get("full_name", "")
            rank = r.get("depth_team", "")
            week = r.get("week", "")
            dt = ""
            pos = r.get("position", "")
            formation = r.get("formation", "")
            slot = ""
        else:
            team = r.get("team", "")
            name = r.get("player_name", "")
            rank = r.get("pos_rank", "")
            week = ""
            dt = r.get("dt", "")
            pos = r.get("pos_abb") or r.get("pos_name", "")
            formation = r.get("pos_grp", "")
            slot = r.get("pos_slot", "")
        out.append({
            "team": team, "name": name, "gsis_id": r.get("gsis_id", ""), "pos": pos,
            "slot": num(slot), "rank": num(rank), "formation": formation,
            "depth_position": r.get("depth_position", ""), "week": week, "dt": dt,
        })
    return out


def injuries_for_season(season: int) -> list[dict]:
    """Injury-report rows for any season, from the same release family."""
    out = []
    for r in rows(f"injuries_{season}.csv"):
        out.append({
            "season": int(r["season"]), "week": int(r["week"] or 0), "team": r["team"],
            "gsis_id": r.get("gsis_id", ""), "position": r.get("position", ""),
            "name": r.get("full_name", ""),
            "report_injury": r.get("report_primary_injury", ""),
            "report_status": (r.get("report_status") or "").strip(),
            "practice_status": (r.get("practice_status") or "").strip(),
            "practice_injury": r.get("practice_primary_injury", ""),
        })
    return out
