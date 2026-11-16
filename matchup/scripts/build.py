#!/usr/bin/env python3
"""Build the matchup workspace artifacts from two committed, independently sourced inputs.

Inputs (both read-only, both already committed elsewhere in this repository):

  1. matchup/data/captures/2026-11-16-nfl-injuries/rows.tsv
     A row-by-row transcript of the official NFL injury report page
     (https://www.nfl.com/injuries/, titled "Injuries - WEEK 10" for the 2026 season)
     as it rendered when read on 2026-11-16. One line per published row, fields
     separated by tabs: day, matchup, team, player, position, injury,
     practice_status, game_status, player_url.

  2. decision-lab/data/official_snapshot.json
     The committed official snapshot captured on 2026-11-12T06:32:36Z. Its
     `injury_rows` (254) are the earlier read of the same page; its `depth_rows`
     (1,745) are the published club depth charts for 30 clubs captured the same day.

Nothing here is inferred. Every output value is either copied from one of those two
files, or is an arithmetic difference between two copied values. Where a value cannot
be produced from the published data the cell is the empty string and is counted on the
flagged page.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
CAPTURE = DATA / "captures" / "2026-11-16-nfl-injuries"

SOURCE_URL = "https://www.nfl.com/injuries/"
SOURCE_LABEL = "NFL official injury report, Week 10 2026 (nfl.com/injuries)"
DEPTH_SOURCE_LABEL = "Committed club depth-chart capture, 2026-11-12T06:32Z"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"

OBSERVED_AT = "2026-11-16T14:44:41Z"

# Statuses that the NFL publishes as a game status. "Out" and "Doubtful" are treated as
# "expected not to play" for the purpose of finding the next man in a published slot.
# "Questionable" is NOT treated as out: the league publishes no probability for it, so
# a questionable player is counted as present but flagged as compromised.
NOT_EXPECTED = {"Out", "Doubtful"}
COMPROMISED = {"Questionable"}

# ---------------------------------------------------------------- name matching

SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v", "x"}


def norm_name(name: str) -> str:
    """Casefold, strip accents/punctuation and common generational suffixes."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    parts = [p for p in s.split() if p and p not in SUFFIXES]
    return " ".join(parts)


def name_key(name: str) -> str:
    """Last name + first initial, used as a fallback when the full name differs."""
    parts = norm_name(name).split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[-1] + " " + parts[0][0]


# ---------------------------------------------------------------- position groups
# Club depth charts use club-specific labels (LDE, MIKE, NCB, ...). These maps collapse
# them to five generic defensive and seven generic offensive groups. The mapping is a
# labelling convention of this workspace, not something any official source publishes.

OFFENCE_GROUP = {
    "QB": "QB",
    "RB": "RB", "HB": "RB",
    "FB": "FB",
    "WR": "WR",
    "TE": "TE",
    "LT": "OT", "RT": "OT", "LOT": "OT", "ROT": "OT", "T": "OT",
    "LG": "OG", "RG": "OG", "G": "OG",
    "C": "OC",
}
DEFENCE_GROUP = {
    "DE": "EDGE", "LDE": "EDGE", "RDE": "EDGE", "EDGE": "EDGE", "RUSH": "EDGE",
    "DT": "IDL", "LDT": "IDL", "RDT": "IDL", "NT": "IDL", "N": "IDL", "DL": "IDL",
    "LB": "LB", "MLB": "LB", "WLB": "LB", "SLB": "LB", "ILB": "LB", "LILB": "LB",
    "RILB": "LB", "MIKE": "LB", "WILL": "LB", "SAM": "LB", "OLB": "LB",
    "LOLB": "LB", "ROLB": "LB",
    "CB": "CB", "LCB": "CB", "RCB": "CB", "NB": "CB", "NCB": "CB", "DB": "CB",
    "S": "S", "SS": "S", "FS": "S",
}
# Which defending group is published opposite which offensive group. This pairing is
# the workspace's stated convention; nfl.com does not publish a coverage assignment.
OFFENCE_TO_DEFENCE = {
    "OT": "EDGE",
    "OG": "IDL",
    "OC": "IDL",
    "QB": "EDGE",
    "RB": "LB",
    "FB": "LB",
    "TE": "S",
    "WR": "CB",
}
DEFENCE_TO_OFFENCE = {
    "EDGE": "OT",
    "IDL": "OG",
    "LB": "RB",
    "S": "TE",
    "CB": "WR",
}
# Groups that are published for the offence but have no one-on-one published opposite
# number on defence, and vice versa.
GROUP_LABEL = {
    "QB": "Quarterback", "RB": "Running back", "FB": "Fullback", "WR": "Wide receiver",
    "TE": "Tight end", "OT": "Offensive tackle", "OG": "Offensive guard",
    "OC": "Centre", "EDGE": "Edge rusher", "IDL": "Interior defensive line",
    "LB": "Linebacker", "CB": "Cornerback", "S": "Safety",
}

# Injury-report positions (nfl.com) -> generic group, used only to describe a row.
REPORT_POS_GROUP = {
    "QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE",
    "T": "OT", "G": "OG", "C": "OC",
    "DE": "EDGE", "DT": "IDL", "NT": "IDL", "LB": "LB", "OLB": "LB", "MLB": "LB",
    "CB": "CB", "S": "S", "K": "ST", "P": "ST", "LS": "ST",
}


# Roster/reserve event classes that mean the player cannot play in the game the
# dated article refers to. Classes that mean he can, and announcements, are kept
# separate so an agreement can be checked rather than assumed.
CANNOT_PLAY = {"placed on IR", "remains on IR", "ruled out"}
CAN_PLAY = {"activated from IR", "cleared, no designation", "no designation"}
ANNOUNCEMENTS = {"announced starter", "announced backup"}
NEUTRAL = {"questionable", "did not practice", "signed", "elevated"}


def load_roster_events():
    """Read the hand-transcribed, dated official roster-event ledger.

    Every row was copied from the body of an nfl.com article that was opened and read
    on 2026-11-16. Nothing is derived from a headline alone; each row carries the verbatim
    sentence and the URL it was read from.
    """
    path = DATA / "roster_events.tsv"
    out = []
    with path.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for ln, line in enumerate(fh, 2):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            f = line.split("\t")
            if len(f) != len(header):
                raise SystemExit(f"roster_events.tsv line {ln}: "
                                 f"expected {len(header)} fields, got {len(f)}")
            rec = dict(zip(header, f))
            rec["effect"] = ("cannot play" if rec["event_class"] in CANNOT_PLAY else
                             "can play" if rec["event_class"] in CAN_PLAY else
                             "announcement" if rec["event_class"] in ANNOUNCEMENTS else
                             "neutral")
            out.append(rec)
    return out


def main() -> int:
    # ------------------------------------------------------------ 1. transcript
    rows = []
    with (CAPTURE / "rows.tsv").open(encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            f = line.split("\t")
            if len(f) != 9:
                raise SystemExit(f"rows.tsv line {ln}: expected 9 fields, got {len(f)}")
            rows.append({
                "day": f[0], "matchup": f[1], "team": f[2], "player": f[3],
                "position": f[4], "injury": f[5], "practice_status": f[6],
                "game_status": f[7], "player_url": f[8],
                "source_url": SOURCE_URL,
                "source_label": SOURCE_LABEL,
                "observed_at": OBSERVED_AT,
            })

    tsv_bytes = (CAPTURE / "rows.tsv").read_bytes()
    transcript_sha = hashlib.sha256(tsv_bytes).hexdigest()

    with (DATA / "injury_live_2026-11-16.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ------------------------------------------------------------ 2. reconcile
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    old_rows = snap["injury_rows"]
    old_observed = snap["observed_at"]
    old_sha = snap["manifest"][0]["sha256"] if snap.get("manifest") else ""

    old_by = {}
    for r in old_rows:
        old_by[(r["team"], norm_name(r["player"]))] = r
    new_by = {}
    for r in rows:
        new_by[(r["team"], norm_name(r["player"]))] = r

    old_keys, new_keys = set(old_by), set(new_by)
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = []
    for k in sorted(old_keys & new_keys):
        o, n = old_by[k], new_by[k]
        diffs = []
        for field, label in (("practice_status", "practice status"),
                             ("game_status", "game status"),
                             ("position", "position"),
                             ("injury", "injury description")):
            if (o.get(field) or "") != (n.get(field) or ""):
                diffs.append({
                    "field": label,
                    "was": o.get(field) or "",
                    "now": n.get(field) or "",
                })
        if diffs:
            changed.append({
                "team": k[0], "player": o["player"], "player_url": n["player_url"],
                "changes": diffs,
                "source_url": SOURCE_URL,
            })

    # The committed snapshot is not necessarily a single read: a later session patched three
    # Lions rows into it from a second capture. Publish the mix rather than labelling the whole
    # file with whichever hash happens to sit first in the manifest.
    prev_sources = Counter((r.get("observed_at", ""), r.get("source_sha256", ""))
                           for r in old_rows)
    prev_sources = [
        {"observed_at": k[0], "source_sha256": k[1], "rows": v}
        for k, v in sorted(prev_sources.items())
    ]

    old_no_injury = snap.get("no_injury_sections", [])
    old_no_injury_teams = sorted({s["team"] for s in old_no_injury})
    new_teams = sorted({r["team"] for r in rows})

    # Teams published as "No Injuries Reported" on 2026-11-12 that now list players.
    no_injury_now_listed = sorted(
        t for t in old_no_injury_teams
        if any(r["team"] == t for r in rows)
    )

    gained_designation = sum(
        1 for c in changed
        if any(d["field"] == "game status" and not d["was"] and d["now"]
               for d in c["changes"]))
    status_counts = Counter(r["game_status"] or "(blank)" for r in rows)
    old_status_counts = Counter(r["game_status"] or "(blank)" for r in old_rows)
    practice_counts = Counter(r["practice_status"] or "(blank)" for r in rows)

    reconciliation = {
        "source_url": SOURCE_URL,
        "source_label": SOURCE_LABEL,
        "observed_at": OBSERVED_AT,
        "transcript_sha256": transcript_sha,
        "live_rows": len(rows),
        "live_teams": len(new_teams),
        "live_matchups": len({r["matchup"] for r in rows}),
        "live_out": status_counts["Out"],
        "live_doubtful": status_counts["Doubtful"],
        "live_questionable": status_counts["Questionable"],
        "live_blank_game_status": status_counts["(blank)"],
        "live_practice_counts": dict(sorted(practice_counts.items())),
        "live_no_injury_sections": 0,
        "previous": {
            "source_url": SOURCE_URL,
            "observed_at": old_observed,
            "source_sha256": old_sha,
            "captures": prev_sources,
            "rows": len(old_rows),
            "teams": len({r["team"] for r in old_rows}),
            "no_injury_sections": len(old_no_injury),
            "out": old_status_counts["Out"],
            "doubtful": old_status_counts["Doubtful"],
            "questionable": old_status_counts["Questionable"],
            "blank_game_status": old_status_counts["(blank)"],
            "no_injury_teams": old_no_injury_teams,
        },
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
        "gained_designation_count": gained_designation,
        "added": [{"team": t, "player": new_by[(t, p)]["player"],
                   "position": new_by[(t, p)]["position"],
                   "game_status": new_by[(t, p)]["game_status"] or "(blank)",
                   "player_url": new_by[(t, p)]["player_url"],
                   "source_url": SOURCE_URL} for t, p in added],
        "removed": [{"team": t, "player": old_by[(t, p)]["player"],
                     "position": old_by[(t, p)]["position"],
                     "game_status": old_by[(t, p)]["game_status"] or "(blank)",
                     "player_url": old_by[(t, p)]["player_url"],
                     "source_url": SOURCE_URL} for t, p in removed],
        "changed": changed,
        "no_injury_now_listed": [
            {"team": t,
             "rows_now": sum(1 for r in rows if r["team"] == t),
             "was": "No Injuries Reported",
             "source_url": SOURCE_URL} for t in no_injury_now_listed
        ],
    }
    (DATA / "injury_reconciliation.json").write_text(
        json.dumps(reconciliation, indent=1, sort_keys=False) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ 3. depth slots
    depth_rows = snap["depth_rows"]
    slots = defaultdict(list)          # (team, unit, position) -> [row]
    for r in depth_rows:
        slots[(r["team"], r["unit"], r["position"])].append(r)
    for v in slots.values():
        v.sort(key=lambda r: (r["published_rank"], r["player"]))

    # status lookups from the fresh transcript
    status_full = {}                   # (team, norm_name) -> row
    for r in rows:
        status_full[(r["team"], norm_name(r["player"]))] = r
    status_last = {}
    for r in rows:
        status_last.setdefault((r["team"], name_key(r["player"])), r)

    def status_for(team: str, player: str):
        """Return the transcript row for a depth-chart player, or None if not listed."""
        return (status_full.get((team, norm_name(player)))
                or status_last.get((team, name_key(player))))

    # ------------------------------------------------------------ 4b. roster events
    events = load_roster_events()

    # Club-name normaliser between the injury report, the depth capture and the news
    # roundups. Where a club publishes a long form (for example "Denver Broncos") the
    # short form used by the injury report ("Broncos") is returned.
    CLUB_ALIAS = {
        "Chicago Bears": "Bears", "Denver Broncos": "Broncos",
        "Philadelphia Eagles": "Eagles", "Tampa Bay Buccaneers": "Buccaneers",
        "New England Patriots": "Patriots", "New Orleans Saints": "Saints",
        "New York Giants": "Giants", "New York Jets": "Jets",
        "Green Bay Packers": "Packers", "Kansas City Chiefs": "Chiefs",
        "Las Vegas Raiders": "Raiders", "Los Angeles Chargers": "Chargers",
        "Los Angeles Rams": "Rams", "San Francisco 49ers": "49ers",
        "Jacksonville Jaguars": "Jaguars", "Indianapolis Colts": "Colts",
        "Cleveland Browns": "Browns", "Detroit Lions": "Lions",
        "Minnesota Vikings": "Vikings", "New Orleans": "Saints",
    }

    def club(name: str) -> str:
        return CLUB_ALIAS.get(name, name)

    # Does a dated event about a player still describe Week 10 (12-16 November 2026)?
    #  - "placed on IR" / "remains on IR" are durable roster states: they hold until an
    #    official activation is published. The ledger contains no activation for any
    #    player it lists as being on IR.
    #  - "ruled out" is written about one named game. The 5 November entry names the
    #    Thursday 5 November game, so it does not describe Week 10; the 13/14 November
    #    entries name the Sunday 15 / Monday 16 games, so they do.
    def applies_to_week_10(ev: dict) -> bool:
        if ev["event_class"] in {"placed on IR", "remains on IR"}:
            return True
        if ev["event_class"] == "ruled out":
            return ev["date"] >= "2026-11-13"
        return ev["date"] >= "2026-11-11"

    for ev in events:
        ev["applies_to_week_10"] = "yes" if applies_to_week_10(ev) else "no"

    cannot_play = {(club(ev["club"]), norm_name(ev["player"]))
                   for ev in events
                   if ev["effect"] == "cannot play" and applies_to_week_10(ev)}

    # Cross-check: for each dated event, does the injury report say the same thing?
    for ev in events:
        rep = status_full.get((club(ev["club"]), norm_name(ev["player"])))
        ev["injury_report_row"] = rep["player"] if rep else ""
        ev["injury_report_game_status"] = (rep["game_status"] or "(not on the report)"
                                           if rep else "")
        if not applies_to_week_10(ev):
            ev["agreement"] = "not applicable to Week 10"
        elif ev["effect"] == "cannot play":
            if rep and rep["game_status"] in NOT_EXPECTED:
                ev["agreement"] = "agrees with the injury report"
            elif rep:
                ev["agreement"] = ("CONTRADICTS the injury report: the report shows "
                                   f"'{rep['game_status'] or 'no game status'}'")
            else:
                ev["agreement"] = ("the player is absent from the injury report, so the "
                                   "report alone would treat him as available")
        elif ev["effect"] == "announcement":
            ev["agreement"] = "announced in the article body; the injury report carries no starter field"
        else:
            ev["agreement"] = "recorded"
    (DATA / "roster_events.json").write_text(json.dumps(events, indent=1) + "\n",
                                             encoding="utf-8")

    # Depth rows the dated ledger says cannot play: the club chart is stale for them.
    depth_flags = []
    for (team, unit, position), members in sorted(slots.items()):
        for m in members:
            key = (club(team), norm_name(m["player"]))
            if key not in cannot_play:
                continue
            ev = next(e for e in events
                      if club(e["club"]) == club(team)
                      and norm_name(e["player"]) == norm_name(m["player"])
                      and e["effect"] == "cannot play" and applies_to_week_10(e))
            depth_flags.append({
                "team": team, "unit": unit, "position": position,
                "player": m["player"], "published_rank": m["published_rank"],
                "event_date": ev["date"], "event": ev["event"],
                "verbatim": ev["verbatim"],
                "on_week_10_injury_report": status_full.get(key, {}).get("player", ""),
                "depth_source_url": m["source_url"],
                "event_source_url": ev["source_url"],
            })
    depth_flags.sort(key=lambda r: (r["team"], r["unit"], r["position"], r["published_rank"]))
    (DATA / "depth_flags.json").write_text(json.dumps(depth_flags, indent=1) + "\n",
                                           encoding="utf-8")

    # ------------------------------------------------------------ 4. replacement depth
    replacement_depth = []
    for (team, unit, position), members in sorted(slots.items()):
        group = (OFFENCE_GROUP.get(position) if unit == "Offense"
                 else DEFENCE_GROUP.get(position) if unit == "Defense" else None)
        if group is None:
            continue                    # special teams are out of scope
        enriched = []
        for m in members:
            st = status_for(team, m["player"])
            enriched.append({
                "player": m["player"],
                "rank": m["published_rank"],
                "player_url": m["player_url"],
                "game_status": st["game_status"] if st else "",
                "practice_status": st["practice_status"] if st else "",
                "on_report": bool(st),
            })
        available = [e for e in enriched if e["game_status"] not in NOT_EXPECTED
                     and (club(team), norm_name(e["player"])) not in cannot_play]
        # Depth of the replacement for each player the NFL expects not to play, either
        # because the injury report says Out or Doubtful, or because a dated official
        # roster event places him on the reserve list.
        for e in enriched:
            reserve_listed = (club(team), norm_name(e["player"])) in cannot_play
            if e["game_status"] not in NOT_EXPECTED and not reserve_listed:
                continue
            later = [a for a in available if a["rank"] > e["rank"]]
            deeper = [a for a in available if a["rank"] >= e["rank"]]
            if later:
                nxt = later[0]
                replacement_depth.append({
                    "team": team,
                    "unit": unit,
                    "position": position,
                    "group": group,
                    "out_player": e["player"],
                    "out_rank": e["rank"],
                    "out_game_status": e["game_status"] or "(not on the injury report)",
                    "out_practice_status": e["practice_status"] or "(not on the injury report)",
                    "out_basis": ("reserve list, dated official roster event"
                                  if e["game_status"] not in NOT_EXPECTED
                                  else "Out/Doubtful on the official injury report"),
                    "replacement_player": nxt["player"],
                    "replacement_rank": nxt["rank"],
                    "replacement_game_status": nxt["game_status"] or "(not on report)",
                    "replacement_is_compromised": "yes" if nxt["game_status"] in COMPROMISED else "no",
                    "strings_skipped": nxt["rank"] - e["rank"],
                    "published_depth_of_slot": max(x["rank"] for x in enriched),
                    "players_still_available_in_slot": len(deeper),
                    "source_url": m["source_url"],
                    "depth_source_label": DEPTH_SOURCE_LABEL,
                    "report_source_url": SOURCE_URL,
                })
            else:
                replacement_depth.append({
                    "team": team,
                    "unit": unit,
                    "position": position,
                    "group": group,
                    "out_player": e["player"],
                    "out_rank": e["rank"],
                    "out_game_status": e["game_status"] or "(not on the injury report)",
                    "out_practice_status": e["practice_status"] or "(not on the injury report)",
                    "out_basis": ("reserve list, dated official roster event"
                                  if e["game_status"] not in NOT_EXPECTED
                                  else "Out/Doubtful on the official injury report"),
                    "replacement_player": "",
                    "replacement_rank": "",
                    "replacement_game_status": "",
                    "replacement_is_compromised": "",
                    "strings_skipped": "",
                    "published_depth_of_slot": max(x["rank"] for x in enriched),
                    "players_still_available_in_slot": 0,
                    "source_url": m["source_url"],
                    "depth_source_label": DEPTH_SOURCE_LABEL,
                    "report_source_url": SOURCE_URL,
                })
    replacement_depth.sort(key=lambda r: (r["team"], r["unit"], r["position"], r["out_rank"]))
    (DATA / "replacement_depth.json").write_text(
        json.dumps(replacement_depth, indent=1) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ 5. slot state per team/group
    # group -> ordered list of (rank, player, status) merged across the club's labels
    team_groups = defaultdict(lambda: defaultdict(list))   # team -> group -> members
    for (team, unit, position), members in slots.items():
        group = (OFFENCE_GROUP.get(position) if unit == "Offense"
                 else DEFENCE_GROUP.get(position) if unit == "Defense" else None)
        if group is None:
            continue
        for m in members:
            st = status_for(team, m["player"])
            team_groups[team][group].append({
                "rank": m["published_rank"],
                "player": m["player"],
                "game_status": st["game_status"] if st else "",
                "reserve_listed": "yes" if (club(team), norm_name(m["player"]))
                in cannot_play else "no",
            })
    for team in team_groups:
        for group in team_groups[team]:
            team_groups[team][group].sort(key=lambda x: (x["rank"], x["player"]))

    def top_string(team: str, group: str):
        """Return (rank, player, status, members) for the shallowest published player in
        the group who is not Out or Doubtful, plus a reason string when there is none."""
        blocked_reason = ""
        if team not in team_groups:
            return None, "", "", [], f"unverified: no depth chart captured for the {team}"
        members = team_groups.get(team, {}).get(group, [])
        if not members:
            return None, "", "", [], (
                f"unverified: the {team} depth chart publishes no player in this group")
        for m in members:
            if m["game_status"] in NOT_EXPECTED:
                blocked_reason = ("Out/Doubtful on the injury report"
                                  if not blocked_reason else blocked_reason)
                continue
            if (club(team), norm_name(m["player"])) in cannot_play:
                blocked_reason = "on the reserve list per a dated official roster event"
                continue
            return m["rank"], m["player"], m["game_status"], members, "published"
        if blocked_reason == "on the reserve list per a dated official roster event":
            return None, "", "", members, (
                f"unverified: every remaining player the {team} publish in this group is "
                "on the reserve list per a dated official roster event")
        return None, "", "", members, (
            f"unverified: every player the {team} publish in this group is Out or Doubtful")

    # ------------------------------------------------------------ 6. per-team view
    teams_view = []
    for team in sorted({r["team"] for r in rows}):
        club_rows = [r for r in rows if r["team"] == team]
        out_rows = [r for r in club_rows if r["game_status"] == "Out"]
        doubtful = [r for r in club_rows if r["game_status"] == "Doubtful"]
        questionable = [r for r in club_rows if r["game_status"] == "Questionable"]
        has_depth = team in team_groups
        # starters out: report rows whose club publishes them at rank 1
        starters_out, named_replacements, unnamed = [], [], []
        for r in out_rows + doubtful:
            placed = None
            for (t, unit, position), members in slots.items():
                if t != team:
                    continue
                for m in members:
                    if norm_name(m["player"]) == norm_name(r["player"]) or (
                            name_key(m["player"]) == name_key(r["player"])):
                        placed = (unit, position, m["published_rank"], m["source_url"])
                        break
                if placed:
                    break
            if placed is None:
                unnamed.append({
                    "player": r["player"], "position": r["position"],
                    "game_status": r["game_status"], "player_url": r["player_url"],
                    "reason": ("no captured depth chart for this club"
                               if not has_depth else
                               "player does not appear on the club's published depth chart"),
                    "source_url": SOURCE_URL,
                })
                continue
            unit, position, rank, durl = placed
            starters_out.append({
                "player": r["player"], "position": r["position"],
                "club_slot": f"{unit} {position}", "published_rank": rank,
                "game_status": r["game_status"], "player_url": r["player_url"],
                "depth_source_url": durl, "report_source_url": SOURCE_URL,
            })
            group = (OFFENCE_GROUP.get(position) if unit == "Offense"
                     else DEFENCE_GROUP.get(position))
            later = [m for m in team_groups.get(team, {}).get(group, [])
                     if m["rank"] > rank and m["game_status"] not in NOT_EXPECTED
                     and norm_name(m["player"]) != norm_name(r["player"])]
            if later:
                named_replacements.append({
                    "out_player": r["player"], "club_slot": f"{unit} {position}",
                    "replacement_player": later[0]["player"],
                    "replacement_rank": later[0]["rank"],
                    "replacement_game_status": later[0]["game_status"] or "(not on report)",
                    "depth_source_url": durl, "report_source_url": SOURCE_URL,
                })
            else:
                named_replacements.append({
                    "out_player": r["player"], "club_slot": f"{unit} {position}",
                    "replacement_player": "", "replacement_rank": "",
                    "replacement_game_status": "",
                    "depth_source_url": durl, "report_source_url": SOURCE_URL,
                })
        teams_view.append({
            "team": team,
            "matchup": next((r["matchup"] for r in club_rows), ""),
            "rows_on_report": len(club_rows),
            "out": len(out_rows),
            "doubtful": len(doubtful),
            "questionable": len(questionable),
            "net_designation_count": len(out_rows) + len(doubtful),
            "depth_chart_captured": "yes" if has_depth else "no",
            "starters_out": starters_out,
            "replacements_named": named_replacements,
            "not_on_depth_chart": unnamed,
            "source_url": SOURCE_URL,
        })
    (DATA / "teams.json").write_text(json.dumps(teams_view, indent=1) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ 7. matchup matrix
    abbrs = {
        "Commanders": "WAS", "Giants": "NYG", "Patriots": "NE", "Lions": "DET",
        "Chiefs": "KC", "Falcons": "ATL", "Vikings": "MIN", "Packers": "GB",
        "Jaguars": "JAX", "Titans": "TEN", "Bills": "BUF", "Jets": "NYJ",
        "Dolphins": "MIA", "Colts": "IND", "Panthers": "CAR", "Saints": "NO",
        "Texans": "HOU", "Browns": "CLE", "Rams": "LAR", "Cardinals": "AZ",
        "Seahawks": "SEA", "Raiders": "LV", "49ers": "SF", "Cowboys": "DAL",
        "Steelers": "PIT", "Bengals": "CIN", "Chargers": "LAC", "Ravens": "BAL",
        "Broncos": "DEN", "Bears": "CHI", "Buccaneers": "TB", "Eagles": "PHI",
    }
    team_by_abbr = {v: k for k, v in abbrs.items()}

    matchup_order, days = [], {}
    for r in rows:
        if r["matchup"] not in matchup_order:
            matchup_order.append(r["matchup"])
            days[r["matchup"]] = r["day"]

    def build_matrix(blocked):
        """Compute every offence-vs-defence cell for every game.

        `blocked` is the set of (team, normalised name) pairs treated as unavailable:
        the empty set gives the injury-report-only reading, the reserve-list set adds the
        dated roster events. Running both makes the correction auditable.
        """
        out = []

        def top(team, group):
            if team not in team_groups:
                return None, "", "", [], f"unverified: no depth chart captured for the {team}"
            members = team_groups.get(team, {}).get(group, [])
            if not members:
                return None, "", "", [], (
                    f"unverified: the {team} depth chart publishes no player in this group")
            why = ""
            for m in members:
                if m["game_status"] in NOT_EXPECTED:
                    why = why or "Out/Doubtful on the injury report"
                    continue
                if (club(team), norm_name(m["player"])) in blocked:
                    why = "on the reserve list per a dated official roster event"
                    continue
                return m["rank"], m["player"], m["game_status"], members, "published"
            return None, "", "", members, f"unverified: no remaining player ({why})"

        for matchup in matchup_order:
            away_abbr, home_abbr = [x.strip() for x in matchup.split("@")]
            away, home = team_by_abbr.get(away_abbr, ""), team_by_abbr.get(home_abbr, "")
            for off_team, def_team in ((away, home), (home, away)):
                if not off_team or not def_team:
                    continue
                for off_group, def_group in OFFENCE_TO_DEFENCE.items():
                    o_rank, o_player, o_status, o_members, o_state = top(off_team, off_group)
                    d_rank, d_player, d_status, d_members, d_state = top(def_team, def_group)
                    o_out = [m["player"] for m in o_members
                             if m["game_status"] in NOT_EXPECTED
                             or (club(off_team), norm_name(m["player"])) in blocked]
                    d_out = [m["player"] for m in d_members
                             if m["game_status"] in NOT_EXPECTED
                             or (club(def_team), norm_name(m["player"])) in blocked]
                    cell = {
                        "matchup": matchup, "day": days[matchup],
                        "offence_team": off_team, "defence_team": def_team,
                        "offence_group": off_group, "defence_group": def_group,
                        "offence_group_label": GROUP_LABEL.get(off_group, off_group),
                        "defence_group_label": GROUP_LABEL.get(def_group, def_group),
                        "offence_effective_string": o_rank, "offence_player": o_player,
                        "offence_player_status": o_status or "(not on the injury report)",
                        "defence_effective_string": d_rank, "defence_player": d_player,
                        "defence_player_status": d_status or "(not on the injury report)",
                        "deficiency": (d_rank - o_rank) if (o_rank and d_rank) else "",
                        "offence_outs": "; ".join(o_out), "defence_outs": "; ".join(d_out),
                        "cell_status": ("published" if (o_rank and d_rank)
                                        else "; ".join(
                                            s for s, ok in ((o_state, not o_rank),
                                                            (d_state, not d_rank)) if ok)),
                        "source_url": SOURCE_URL,
                    }
                    flags = []
                    if o_rank and o_status in COMPROMISED:
                        flags.append(f"offence top string is {o_status}")
                    if d_rank and d_status in COMPROMISED:
                        flags.append(f"defence top string is {d_status}")
                    cell["flags"] = "; ".join(flags)
                    kinds = set()
                    for st, ok in ((o_state, not o_rank), (d_state, not d_rank)):
                        if not ok:
                            continue
                        if "no depth chart captured" in st:
                            kinds.add("no depth chart captured")
                        elif "publishes no player" in st:
                            kinds.add("group not published")
                        else:
                            kinds.add("group exhausted")
                    cell["cell_reason_kind"] = "; ".join(sorted(kinds)) if kinds else "published"
                    out.append(cell)
        return out

    baseline = build_matrix(set())
    matchups = build_matrix(cannot_play)

    corrections = []
    for a, b in zip(baseline, matchups):
        if (a["offence_player"], a["defence_player"]) != (b["offence_player"],
                                                          b["defence_player"]):
            corrections.append({
                "matchup": b["matchup"],
                "offence_team": b["offence_team"], "defence_team": b["defence_team"],
                "group": f"{b['offence_group_label']} vs {b['defence_group_label']}",
                "before_offence": f"{a['offence_player']} (string {a['offence_effective_string']})",
                "after_offence": f"{b['offence_player']} (string {b['offence_effective_string']})",
                "before_defence": f"{a['defence_player']} (string {a['defence_effective_string']})",
                "after_defence": f"{b['defence_player']} (string {b['defence_effective_string']})",
                "source_url": SOURCE_URL,
            })
    (DATA / "matrix_corrections.json").write_text(
        json.dumps(corrections, indent=1) + "\n", encoding="utf-8")
    (DATA / "matrix.json").write_text(json.dumps(matchups, indent=1) + "\n",
                                      encoding="utf-8")

    # ------------------------------------------------------------ 8. coverage census
    groups_present = sorted({g for t in team_groups for g in team_groups[t]})
    depth_by_group = Counter()
    for team in team_groups:
        for group, members in team_groups[team].items():
            depth_by_group[group] += 1
            for rank in (1, 2, 3, 4):
                pass
    group_rank_depth = {}
    for group in groups_present:
        counts = Counter()
        for team in team_groups:
            members = team_groups[team].get(group, [])
            for rank in (1, 2, 3, 4):
                if any(m["rank"] == rank for m in members):
                    counts[rank] += 1
        group_rank_depth[group] = {str(k): counts[k] for k in (1, 2, 3, 4)}

    census = {
        "live_rows": len(rows),
        "live_teams": len(new_teams),
        "teams_with_depth_chart": len(team_groups),
        "teams_on_report_without_depth_chart": sorted(
            {r["team"] for r in rows} - set(team_groups)),
        "depth_rows_used": len(depth_rows),
        "slots": len(slots),
        "slots_with_multiple_rank1": sum(
            1 for v in slots.values() if sum(1 for m in v if m["published_rank"] == 1) > 1),
        "report_positions": dict(sorted(Counter(r["position"] for r in rows).items())),
        "group_rank_depth": group_rank_depth,
        "matrix_rows": len(matchups),
        "matrix_cells_published": sum(1 for m in matchups if m["cell_status"] == "published"),
        "matrix_cells_unverified": sum(1 for m in matchups if m["cell_status"] != "published"),
        "matrix_cells_published_before_correction": sum(
            1 for m in baseline if m["cell_status"] == "published"),
        "matrix_corrections": len(corrections),
        "matrix_cell_reasons": dict(sorted(Counter(
            m["cell_reason_kind"] for m in matchups).items())),
        "replacement_depth_rows": len(replacement_depth),
        "replacement_depth_unresolved": sum(
            1 for r in replacement_depth if not r["replacement_player"]),
    }
    # Which position labels each club uses, so an empty group can be explained
    # (a club that publishes "DL"/"OLB" has no player under an edge-rusher label).
    vocabulary = {}
    for group in sorted({g for t in team_groups for g in team_groups[t]}
                        | set(OFFENCE_TO_DEFENCE) | set(DEFENCE_TO_OFFENCE)):
        missing = sorted(t for t in team_groups
                         if group not in team_groups[t]
                         or not team_groups[t][group])
        labels = {}
        for team in missing:
            unit = "Offense" if group in set(OFFENCE_GROUP.values()) else "Defense"
            labs = sorted({pos for (t, u, pos) in slots
                           if t == team and u == unit})
            labels[team] = labs
        vocabulary[group] = {
            "label": GROUP_LABEL.get(group, group),
            "clubs_with_no_player_in_group": missing,
            "count": len(missing),
            "labels_those_clubs_publish": labels,
        }
    (DATA / "vocabulary.json").write_text(json.dumps(vocabulary, indent=1) + "\n",
                                          encoding="utf-8")

    (DATA / "census.json").write_text(json.dumps(census, indent=1) + "\n", encoding="utf-8")

    print(f"transcript rows        : {len(rows)}  (sha256 {transcript_sha[:16]}…)")
    print(f"previous snapshot rows : {len(old_rows)}  ({old_observed})")
    print(f"added / removed / changed: {len(added)} / {len(removed)} / {len(changed)}")
    print(f"replacement-depth rows : {len(replacement_depth)}")
    print(f"matrix cells           : {len(matchups)} "
          f"({census['matrix_cells_published']} published, "
          f"{census['matrix_cells_unverified']} unverified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
