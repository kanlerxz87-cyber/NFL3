"""Load the repository's verified inputs and normalise them for origination work.

Inputs
------
data/raw/games.csv                     community nflverse release `schedules` (SHA-256 in manifest)
data/raw/snap_counts_2026.csv          community nflverse release `snap_counts`
data/raw/roster_2026.csv               community nflverse release `rosters` (reserve/inactive list)
decision-lab/data/official_snapshot.json   official nfl.com injury report + 30 club depth pages

Nothing here is scraped live. Every loader returns records carrying the URL of the page or release
asset they came from, so a published row can always cite its own origin.
"""
from __future__ import annotations

import csv
from collections import defaultdict

import common as C


# ----------------------------------------------------------------------------- games
def games() -> list[dict]:
    rows = C.read_csv(C.RAW / "games.csv")
    out = []
    for row in rows:
        if row["season"] != str(C.SEASON) or row["game_type"] != C.SEASON_TYPE:
            continue
        out.append({
            "game_id": row["game_id"],
            "week": int(row["week"]),
            "gameday": row["gameday"],
            "gametime": row["gametime"],
            "away": row["away_team"],
            "home": row["home_team"],
            "away_score": _int(row["away_score"]),
            "home_score": _int(row["home_score"]),
            "away_moneyline": _int(row["away_moneyline"]),
            "home_moneyline": _int(row["home_moneyline"]),
            "spread_line": _float(row["spread_line"]),
            "total_line": _float(row["total_line"]),
            "over_odds": _int(row["over_odds"]),
            "under_odds": _int(row["under_odds"]),
            "away_spread_odds": _int(row["away_spread_odds"]),
            "home_spread_odds": _int(row["home_spread_odds"]),
            "roof": row["roof"],
            "surface": row["surface"],
            "temp": _int(row["temp"]),
            "wind": _int(row["wind"]),
            "div_game": row["div_game"] == "1",
            "rest_away": _int(row["away_rest"]),
            "rest_home": _int(row["home_rest"]),
            "stadium": row["stadium"],
            "source_url": C.G["schedules"],
        })
    out.sort(key=lambda g: (g["week"], g["gameday"], g["gametime"], g["game_id"]))
    return out


def played(g: dict) -> bool:
    return g["home_score"] is not None and g["away_score"] is not None


def _int(value):
    try:
        if value in (None, "", "NA"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        if value in (None, "", "NA"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------- official standings
def standings() -> list[dict]:
    """The official 2026 division standings, transcribed once and stored with its observation time.

    This is the only official block that is typed into this workspace. It is stored verbatim with its
    source URL and observation timestamp, and the whole of it is reconciled against the community
    game log (136 games = 272 team-games) so any transcription error fails the build rather than
    being published.
    """
    payload = C.read_json(C.DATA / "official_standings_2026.json")
    return [{"code": code, "w": w, "l": l, "t": t, "pf": pf, "pa": pa,
             "source_url": payload["source"], "observed_at": payload["observed_at"]}
            for code, w, l, t, pf, pa in payload["rows"]]


# ----------------------------------------------------------------------------- availability
def injury_rows() -> list[dict]:
    snap = C.read_json(C.LAB / "official_snapshot.json")
    return snap["injury_rows"]


def depth_rows() -> list[dict]:
    snap = C.read_json(C.LAB / "official_snapshot.json")
    return snap["depth_rows"]


def snapshot_meta() -> dict:
    snap = C.read_json(C.LAB / "official_snapshot.json")
    return {"observed_at": snap["observed_at"], "coverage": snap["coverage"],
            "injury_rows": len(snap["injury_rows"]), "depth_rows": len(snap["depth_rows"]),
            "depth_failures": snap.get("depth_directory_failures", []),
            "no_injury_sections": snap.get("no_injury_sections", [])}


def snap_counts(weeks: range | None = None) -> list[dict]:
    rows = C.read_csv(C.RAW / "snap_counts_2026.csv")
    out = []
    for row in rows:
        if weeks is not None and int(row["week"]) not in weeks:
            continue
        out.append({"week": int(row["week"]), "team": row["team"], "player": row["player"],
                    "position": row["position"], "game_id": row["game_id"],
                    "offense_snaps": _int(row["offense_snaps"]),
                    "offense_pct": _float(row["offense_pct"]),
                    "defense_snaps": _int(row["defense_snaps"]),
                    "defense_pct": _float(row["defense_pct"]),
                    "source_url": C.G["snaps"]})
    return out


def roster() -> list[dict]:
    rows = C.read_csv(C.RAW / "roster_2026.csv")
    return [{"team": r["team"], "player": r["full_name"], "position": r["position"],
             "depth_pos": r["depth_chart_position"], "status": r["status"],
             "status_abbr": r["status_description_abbr"], "week": _int(r["week"]),
             "source_url": C.G["rosters"]} for r in rows]


def reserve_list() -> dict[str, list[dict]]:
    """Players on a reserve/inactive list at the roster snapshot. 'Not on the injury report' does not
    mean available: a player on injured reserve is absent from the weekly report by construction."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in roster():
        if row["status"] in {"RES", "INA", "EXE", "RET"}:
            buckets[row["team"]].append(row)
    return buckets


def team_of_club_name(name: str) -> str | None:
    mapping = C.club_name_to_code()
    return mapping.get(name.strip().lower())


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    g = games()
    print(f"{len(g)} scheduled games, {sum(1 for x in g if played(x))} played")
    print(f"{len(injury_rows())} official injury rows, {len(depth_rows())} official depth rows")
    print(f"{len(snap_counts())} community snap rows")
