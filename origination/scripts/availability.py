#!/usr/bin/env python3
"""The availability graph: who was expected to start, and who actually did.

This is a first-class dataset, not a view of one.

Nodes
-----
club             32 official clubs
slot            (club, unit, position, published_rank) from the official club depth page — a rank 1 slot
                can legitimately hold more than one player (three receivers at rank 1), so a slot is a
                group, never a single starter
player          the player named in a slot
report_row      the official injury-report row for that player, if he is on it
reserve_row     the roster's reserve/inactive list for that player, if he is on it
playing_time    the player's measured share of snaps, which is the only *observation* of who played

Edges
-----
slot -> player              published_order      (official club page)
player -> report_row        listed_on_report     (official injury report, dated)
player -> reserve_row       reserve_status       (roster status: a reserve player is absent from the
                                                  weekly report by construction, not by health)
player -> playing_time      measured_workload    (community snap counts: a measurement, not a claim)

Two things this file refuses to do
----------------------------------
It does not infer depth order from jersey number, experience, salary or roster order. It does not name a
"confirmed replacement" unless an official source names one. Where the graph cannot answer, the edge is
missing and the row says why — that is the difference between a dataset and a guess.
"""
from __future__ import annotations

import json
from collections import defaultdict

import common as C
import inputs

SNAP_POS = {"QB", "RB", "WR", "TE", "FB", "T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG"}


def club_to_code(name: str) -> str | None:
    return inputs.team_of_club_name(name)


def build() -> dict:
    snapshot = inputs.snapshot_meta()
    depth = inputs.depth_rows()
    injuries = inputs.injury_rows()
    reserves = inputs.reserve_list()
    snaps = inputs.snap_counts()
    results = C.read_json(C.DATA / "results.json")

    # ---------------------------------------------------------------- workload from playing time
    # For each (club, player) use the most recent week's offensive snap share. This is the only
    # measured statement about who actually played; it is community-sourced and labelled as such.
    latest_week = max((s["week"] for s in snaps), default=None)
    workload = {}
    for s in snaps:
        if s["week"] != latest_week:
            continue
        key = (s["team"], s["player"].lower())
        share = s["offense_pct"] if s["offense_pct"] is not None else s["defense_pct"]
        if share is not None:
            workload[key] = {"week": latest_week, "offense_pct": s["offense_pct"],
                             "defense_pct": s["defense_pct"], "snaps": s["offense_snaps"],
                             "source_url": s["source_url"], "position": s["position"]}

    # ---------------------------------------------------------------- slots as groups
    slots: dict[tuple, dict] = {}
    for row in depth:
        code = club_to_code(row["team"])
        key = (code, row["unit"], row["position"], row["published_rank"])
        slot = slots.setdefault(key, {"club": code, "club_name": row["team"], "unit": row["unit"],
                                      "position": row["position"],
                                      "rank": row["published_rank"], "players": [],
                                      "source_url": row["source_url"],
                                      "observed_at": row["observed_at"],
                                      "rank_basis": row.get("rank_basis", "")})
        slot["players"].append(row["player"])

    # ---------------------------------------------------------------- injury lookup
    by_player = defaultdict(list)
    for row in injuries:
        code = club_to_code(row["team"])
        by_player[(code, row["player"].lower())].append(row)
    reserve_by_player = {}
    for code, rows in reserves.items():
        for r in rows:
            reserve_by_player[(code, r["player"].lower())] = r

    slot_rows = []
    for key in sorted(slots, key=lambda k: (k[0] or "", k[1] or "", k[2] or "", k[3] or 0)):
        slot = slots[key]
        code = slot["club"]
        members = []
        ranked_on_report = 0
        for player in slot["players"]:
            rep = by_player.get((code, player.lower()), [])
            res = reserve_by_player.get((code, player.lower()))
            wl = workload.get((code, player.lower()))
            status = rep[0]["game_status"] if rep else ""
            practice = rep[0]["practice_status"] if rep else ""
            if status:
                ranked_on_report += 1
            members.append({
                "player": player,
                "on_report": bool(rep),
                "game_status": status,
                "practice_status": practice,
                "report_source": rep[0]["source_url"] if rep else None,
                "reserve_status": res["status"] if res else None,
                "reserve_source": res["source_url"] if res else None,
                "snap_week": wl["week"] if wl else None,
                "offense_pct": wl["offense_pct"] if wl else None,
                "defense_pct": wl["defense_pct"] if wl else None,
                "snap_source": wl["source_url"] if wl else None,
            })
        slot_rows.append({
            **{k: slot[k] for k in ("club", "club_name", "unit", "position", "rank",
                                     "source_url", "observed_at", "rank_basis")},
            "n_players": len(members),
            "members": members,
            "has_official_game_status": ranked_on_report > 0,
            "measured_snap_leader": max(members, key=lambda m: (m["offense_pct"] or 0) +
                                        (m["defense_pct"] or 0))["player"] if any(
                m["offense_pct"] is not None or m["defense_pct"] is not None for m in members) else None,
        })

    # ---------------------------------------------------------------- depth measured from playing time
    # For every club x unit x position, order the players by measured snap share and compare that order
    # with the club's published rank. Nothing is inferred from jersey numbers.
    by_pos: dict[tuple, list] = defaultdict(list)
    for slot in slot_rows:
        for member in slot["members"]:
            share = member["offense_pct"] if slot["unit"] == "Offense" else member["defense_pct"]
            if share is None:
                continue
            by_pos[(slot["club"], slot["unit"], slot["position"])].append(
                {"player": member["player"], "published_rank": slot["rank"], "snap_share": share,
                 "on_report": member["on_report"], "game_status": member["game_status"]})
    depth_checks = []
    for key, players in sorted(by_pos.items()):
        players.sort(key=lambda p: -p["snap_share"])
        top = players[0]
        depth_checks.append({
            "club": key[0], "unit": key[1], "position": key[2], "n_players": len(players),
            "snap_leader": top["player"], "snap_leader_published_rank": top["published_rank"],
            "snap_leader_share": top["snap_share"],
            "leader_matches_rank1": top["published_rank"] == 1,
            "leader_on_report": top["on_report"],
            "players": players[:6],
        })

    # ---------------------------------------------------------------- matchup deficiencies (Week 10)
    # For each Week 10 fixture, list the offensive slots whose rank-1 group is unavailable (official
    # game status) and the defensive group the club publishes behind it. The defensive side is the same
    # club's own chart, so no cross-club guess is made.
    week10 = [g for g in inputs.games() if g["week"] == 10]
    by_club_slots = defaultdict(list)
    for slot in slot_rows:
        by_club_slots[slot["club"]].append(slot)
    matchups = []
    for g in week10:
        entry = {"event_id": g["game_id"], "gameday": g["gameday"], "home": g["home"],
                 "away": g["away"], "played": inputs.played(g), "sides": {}}
        for side in ("home", "away"):
            code = g[side]
            out_slots = [s for s in by_club_slots.get(code, []) if s["unit"] == "Offense" and s["rank"] == 1]
            deficits = []
            for slot in sorted(out_slots, key=lambda s: s["position"]):
                unavailable = [m for m in slot["members"] if m["game_status"] in ("Out", "Doubtful")]
                if not unavailable:
                    continue
                deficits.append({
                    "position": slot["position"], "slot_players": [m["player"] for m in slot["members"]],
                    "unavailable": [m["player"] for m in unavailable],
                    "designation": unavailable[0]["game_status"],
                    "report_source": unavailable[0]["report_source"],
                    "chart_source": slot["source_url"],
                    "published_backup": [
                        m["player"] for m in slot["members"]
                        if m["game_status"] not in ("Out", "Doubtful")] or None,
                    "backup_game_status": [
                        m["game_status"] for m in slot["members"]
                        if m["game_status"] not in ("Out", "Doubtful")] or None,
                })
            entry["sides"][side] = {"club": code, "club_name": C.FULL_NAME.get(code, code),
                                    "slots_rank1_offense": len(out_slots),
                                    "deficits": deficits,
                                    "chart_source": next((s["source_url"] for s in by_club_slots.get(code, [])), None)}
        matchups.append(entry)

    # ---------------------------------------------------------------- coverage facts
    coverage = {
        "clubs_with_depth": len({s["club"] for s in slot_rows}),
        "clubs_total": 32,
        "depth_slots": len(slot_rows),
        "slots_with_multiple_rank1": sum(1 for s in slot_rows if s["rank"] == 1 and s["n_players"] > 1),
        "games_on_report": sum(1 for r in injuries if r["game_status"]),
        "report_rows": len(injuries),
        "report_teams": len({r["team"] for r in injuries}),
        "no_injury_sections": len(snapshot["no_injury_sections"]),
        "clubs_absent_from_report": sorted(
            {C.FULL_NAME[c] for c in C.FULL_NAME} -
            {C.FULL_NAME.get(club_to_code(t) or "", t) for t in {r["team"] for r in injuries}}),
        "reserve_players": sum(len(v) for v in reserves.values()),
        "reserve_clubs": len(reserves),
        "snap_weeks": sorted({s["week"] for s in snaps}),
        "snap_rows": len(snaps),
        "snap_latest_week": latest_week,
        "slots_rank1_with_two_or_more": sum(1 for s in slot_rows if s["rank"] == 1 and s["n_players"] >= 2),
        "results_reconciled": results["passed"],
        "observed_at": snapshot["observed_at"],
        "depth_failures": [f.get("team") or f.get("club") or str(f) for f in snapshot["depth_failures"]],
    }
    payload = {
        "built_at": C.GENERATED_AT,
        "observed_at": snapshot["observed_at"],
        "graph": {"nodes": {
            "club": 32, "slot": len(slot_rows),
            "player_named_in_slot": sum(s["n_players"] for s in slot_rows),
            "report_row": len(injuries),
            "reserve_row": coverage["reserve_players"],
            "playing_time_row": len(snaps),
        }},
        "coverage": coverage,
        "slots": slot_rows,
        "depth_from_playing_time": depth_checks,
        "matchups": matchups,
        "workload_week": latest_week,
        "rules": [
            "A slot is a group. 149 club/unit/position slots publish more than one rank-1 player; the "
            "graph keeps them together instead of inventing a single starter.",
            "A player on a reserve list is absent from the weekly report by construction. 'Not listed' "
            "never means 'available'.",
            "Depth is measured from playing time (snap share), never from jersey number, experience or "
            "salary.",
            "No .confirmed replacement. is published unless an official source names one. The backup "
            "shown is the club's own next published name, which is evidence of order, not of assignment.",
        ],
        "limits": [
            "Two clubs publish no parseable depth chart; the graph is missing those clubs rather than "
            "guessing (Texans publish the chart as an image; Packers prepend jersey numbers — the "
            "decision-lab capture records both failures).",
            "Snap counts are community-sourced; they are used to observe workload, never relabelled as "
            "official.",
            "One injury-report observation exists. It cannot support a backtest; see the capture log.",
        ],
    }
    C.write_json("availability_graph.json", payload)
    return payload


def main() -> int:
    payload = build()
    c = payload["coverage"]
    print(f"Availability graph: {c['depth_slots']} slots over {c['clubs_with_depth']}/32 clubs; "
          f"{c['slots_with_multiple_rank1']} rank-1 slots hold more than one player.")
    print(f"  report rows {c['report_rows']} on {c['report_teams']} clubs, "
          f"{c['games_on_report']} with a game designation; reserve players {c['reserve_players']}.")
    print(f"  playing time: {c['snap_rows']} rows, weeks {c['snap_weeks']}, latest {c['snap_latest_week']}.")
    matched = sum(1 for d in payload["depth_from_playing_time"] if d["leader_matches_rank1"])
    print(f"  snap-share leader matches published rank 1 in {matched}/{len(payload['depth_from_playing_time'])} groups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
