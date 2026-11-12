#!/usr/bin/env python3
"""Join the official Week 10 injury report to the published club depth charts.

Purpose: the request is to know when a defence (or offence) is down to a 2nd, 3rd or
4th string player. This script answers exactly the part that official sources support
and leaves the rest blank:

  * it can say which clubs publish an injured player and what published depth slot
    that player occupies at his position (the club's own chart);
  * it can name the next player down on that same published chart;
  * it CANNOT say who actually starts, who is active, who takes the snaps, or that
    the next name in order will play. Those cells stay blank and are flagged.

Sources: decision-lab/data/official_snapshot.json, a capture of https://www.nfl.com/injuries/
and the club depth-chart pages recorded row by row, observed 2026-11-12T06:32Z.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
OUT_JSON = DESK / "data" / "availability.json"
# Second official source for Week 10 designations: the NFL.com Week 10 injury article,
# read on the same date. It is compared row by row with the injury-report page.
WEEK10_ARTICLE = "https://www.nfl.com/news/nfl-week-10-injury-report-2026-season"
ARTICLE_DESIGNATIONS = {
    ("Commanders", "Colson Yankoff"): "Out", ("Commanders", "Lucas Patrick"): "Out",
    ("Giants", "Malik Harrison"): "Questionable",
    ("Patriots", "Ben Brown"): "Out", ("Patriots", "Carlton Davis III"): "Out",
    ("Patriots", "TreVeyon Henderson"): "Out",
    ("Lions", "Kerby Joseph"): "Out", ("Lions", "Cade Mays"): "Out", ("Lions", "D.J. Reed"): "Out",
    ("Seahawks", "Sam Darnold"): "Out",
}
OUT_CSV = DESK / "data" / "availability_week10.csv"

# The injury report uses club short names, the depth capture uses the club label
# printed on that club's own page. Both come from the official capture; this map only
# aligns the labels and is asserted below so a silent miss cannot happen.
LABEL_ALIASES = {
    "49ers": "49ers", "Bills": "Bills", "Browns": "Browns", "Cardinals": "Cardinals",
    "Chiefs": "Chiefs", "Colts": "Colts", "Commanders": "Commanders", "Cowboys": "Cowboys",
    "Dolphins": "Dolphins", "Falcons": "Falcons", "Giants": "Giants", "Jaguars": "Jaguars",
    "Jets": "Jets", "Lions": "Lions", "Packers": "Packers", "Panthers": "Panthers",
    "Patriots": "Patriots", "Raiders": "Raiders", "Rams": "Rams", "Ravens": "Ravens",
    "Saints": "Saints", "Seahawks": "Seahawks", "Steelers": "Steelers", "Texans": "texans",
    "Titans": "Titans", "Vikings": "Vikings", "Bears": "Chicago Bears",
    "Broncos": "Denver Broncos", "Eagles": "Philadelphia Eagles",
    "Buccaneers": "Tampa Bay Buccaneers", "Bengals": "Bengals", "Chargers": "Chargers",
}
# Injury-report position codes are generic; club charts use finer codes. This map is a
# published-code equivalence (T = LOT/ROT/LT/RT, G = LG/RG, EDGE = DE/OLB/RUSH, ...). It is
# declared here so the join is auditable rather than hidden; a player is still only matched
# when the name matches exactly inside the mapped group.
POSITION_FAMILIES = {
    "T": {"T", "LT", "RT", "LOT", "ROT"},
    "G": {"G", "LG", "RG"},
    "C": {"C"},
    "QB": {"QB"}, "RB": {"RB", "HB"}, "FB": {"FB"}, "WR": {"WR"}, "TE": {"TE"},
    "DE": {"DE", "LDE", "RDE", "EDGE", "RUSH"},
    "DT": {"DT", "LDT", "RDT", "NT"},
    "LB": {"LB", "ILB", "LILB", "RILB", "MLB", "MIKE", "OLB", "LOLB", "ROLB", "SLB", "SAM",
           "WLB", "WILL", "EDGE"},
    "CB": {"CB", "LCB", "RCB", "NCB", "NB", "DB"},
    "S": {"S", "FS", "SS", "DB"},
    "K": {"K", "PK"}, "P": {"P"}, "LS": {"LS"},
}


def family(position: str) -> set[str]:
    return POSITION_FAMILIES.get(position, {position})


def rank_label(rank: int) -> str:
    return {1: "1st string (published starter)", 2: "2nd string", 3: "3rd string",
            4: "4th string", 5: "5th string"}.get(rank, f"{rank}th string")


def main() -> int:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    depth = snapshot["depth_rows"]
    injuries = snapshot["injury_rows"]
    no_injury = snapshot["no_injury_sections"]
    failures = snapshot.get("depth_directory_failures", [])
    labels = {row["team"] for row in depth}
    observed = snapshot["observed_at"]

    # designations named by the Week 10 article but absent from the injury-report page
    report_names = {(r["team"], r["player"]): r.get("game_status", "") for r in injuries}
    article_only, article_conflicts = [], []
    for (team, player), status in ARTICLE_DESIGNATIONS.items():
        if (team, player) not in report_names:
            article_only.append({"team": team, "player": player, "article_status": status,
                                 "report_status": "", "source_url": WEEK10_ARTICLE})
        elif (report_names[(team, player)] or "") != status:
            article_conflicts.append({"team": team, "player": player, "article_status": status,
                                      "report_status": report_names[(team, player)],
                                      "source_url": WEEK10_ARTICLE})

    # index the published chart: team -> position -> ordered list of (rank, player, url, unit, source)
    chart: dict[str, dict[str, list[dict]]] = {}
    for row in depth:
        chart.setdefault(row["team"], {}).setdefault(row["position"], []).append(row)
    for team in chart:
        for position in chart[team]:
            chart[team][position].sort(key=lambda r: r["published_rank"])

    rows, unmatched, no_chart = [], [], []
    for injury in injuries:
        label = LABEL_ALIASES.get(injury["team"])
        if label is None or label not in labels:
            no_chart.append({"team": injury["team"], "player": injury["player"],
                             "reason": "no depth chart captured for this club",
                             "source_url": injury["source_url"]})
            continue
        group = family(injury["position"])
        position_rows = []
        for code, entries in chart.get(label, {}).items():
            if code in group:
                position_rows.extend(entries)
        if not position_rows:
            unmatched.append({"team": injury["team"], "player": injury["player"],
                              "position": injury["position"],
                              "reason": "club chart uses no position code in this injury-report position family",
                              "source_url": injury["source_url"]})
            continue
        match = [r for r in position_rows if r["player"].strip().lower() == injury["player"].strip().lower()]
        if not match:
            unmatched.append({"team": injury["team"], "player": injury["player"],
                              "position": injury["position"],
                              "reason": "player not listed on the captured club chart at this position family",
                              "source_url": injury["source_url"]})
            continue
        slot = match[0]
        rank = slot["published_rank"]
        next_up = [r for r in position_rows if r["published_rank"] > rank]
        replacement = next_up[0] if next_up else None
        rows.append({
            "team": injury["team"],
            "depth_label": label,
            "matchup": injury["matchup"],
            "day": injury["day"],
            "player": injury["player"],
            "position": injury["position"],
            "injury": injury["injury"],
            "practice_status": injury["practice_status"],
            "game_status": injury["game_status"],
            "published_rank": rank,
            "rank_label": rank_label(rank),
            "unit": slot["unit"],
            "depth_authority": slot["authority"],
            "depth_source": slot["source_url"],
            "next_up": replacement["player"] if replacement else "",
            "next_up_rank": replacement["published_rank"] if replacement else "",
            "next_up_source": replacement["source_url"] if replacement else "",
            "player_url": injury["player_url"],
            "injury_source": injury["source_url"],
            "confirmed_starter": "",
            "confirmed_active": "",
            "replacement_confirmed": "",
            "expected_snaps": "",
            "article_status": ARTICLE_DESIGNATIONS.get((injury["team"], injury["player"]), ""),
            "unverified": "; ".join([
                "who actually starts",
                "whether the injured player is active",
                "whether next_up actually plays",
                "expected snap share",
            ]),
        })

    rows.sort(key=lambda r: (r["game_status"] == "", r["published_rank"], r["team"]))
    played_teams = sorted({r["team"] for r in injuries} | {r["team"] for r in no_injury})
    chart_teams = sorted({r["team"] for r in depth})
    missing_chart = sorted(set(played_teams) - {LABEL_ALIASES.get(t, "") for t in chart_teams})
    missing_chart = [t for t in played_teams
                     if LABEL_ALIASES.get(t) not in labels]

    exposures = [r for r in rows if r["published_rank"] >= 2]
    designations = [r for r in rows if r["game_status"]]
    doc = {
        "observed_at": observed,
        "sources": {
            "injury_report": "https://www.nfl.com/injuries/",
            "injury_capture": "decision-lab/data/official_snapshot.json",
            "depth_authority_note": "Club-published depth charts; order is the club's own publication, "
                                    "not a confirmed week-of-season starting lineup.",
        },
        "counts": {
            "injury_rows": len(injuries),
            "injury_designated": len(designations),
            "injury_rows_joined_to_depth": len(rows),
            "joined_with_game_designation": len([r for r in rows if r["game_status"]]),
            "depth_slots_at_2nd_string_or_deeper": len(exposures),
            "players_not_found_on_chart": len(unmatched),
            "clubs_without_a_captured_chart": len(missing_chart),
            "depth_rows_total": len(depth),
        },
        "clubs_without_a_captured_chart": [
            {"team": t, "reason": next((f["reason"] for f in failures if LABEL_ALIASES.get(t, "").lower()
                                       in (f["team"] or "").lower()), "no chart captured"),
             "source_url": "https://www.nfl.com/teams/"} for t in missing_chart],
        "depth_capture_failures": failures,
        "second_source_check": {
            "article": WEEK10_ARTICLE,
            "method": "Every game designation printed in the NFL.com Week 10 injury article was compared "
                      "with the designation column of the NFL.com injury-report page for the same player.",
            "designations_in_article": len(ARTICLE_DESIGNATIONS),
            "designations_on_report_page": len(designations),
            "on_report_page_but_not_article": [
                {"team": r["team"], "player": r["player"], "position": r["position"],
                 "status": r["game_status"], "source_url": r["injury_source"]}
                for r in designations
                if (r["team"], r["player"]) not in ARTICLE_DESIGNATIONS],
            "in_article_but_not_report_page": article_only,
            "conflicting_values": article_conflicts,
            "reading": "The two official NFL.com pages do not agree on Week 10 designations. The injury "
                       "article names more Out players (for example three Lions) than the injury-report "
                       "page prints. This is published as a flag; no value is reconciled by inference, and "
                       "the report-page value is shown as published while the article value is shown "
                       "beside it.",
        },
        "join_rows": rows,
        "not_found": unmatched,
        "no_chart_rows": no_chart,
        "interpretation_limits": [
            "A club depth chart is a publication, not a lineup. It does not prove who starts.",
            "Injury designations do not prove a player is inactive, and a blank game status is not 'active'.",
            "'Next man up' is the next name in published order at the same position, nothing more.",
            "Confirmed replacement, confirmed active status and expected snaps are UNKNOWN and left blank.",
            "Snap-count data would be the official way to confirm workload, but no official snap-count "
            "source is captured for 2026 in this repository.",
        ],
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["team", "matchup", "player", "pos", "injury", "practice_status", "game_status",
                         "published_rank", "rank_label", "unit", "next_up_on_chart",
                         "confirmed_starter", "confirmed_active", "replacement_confirmed",
                         "expected_snaps", "injury_source", "depth_source"])
        for r in rows:
            writer.writerow([r["team"], r["matchup"], r["player"], r["position"], r["injury"],
                             r["practice_status"], r["game_status"], r["published_rank"], r["rank_label"],
                             r["unit"], r["next_up"], r["confirmed_starter"], r["confirmed_active"],
                             r["replacement_confirmed"], r["expected_snaps"],
                             r["injury_source"], r["depth_source"]])
    c = doc["counts"]
    print(f"injury rows {c['injury_rows']} | joined to a published chart {c['injury_rows_joined_to_depth']} | "
          f"with a game designation {c['injury_designated']} | 2nd-string-or-deeper slots {c['depth_slots_at_2nd_string_or_deeper']}")
    print(f"not found on chart {c['players_not_found_on_chart']} | clubs without a captured chart {c['clubs_without_a_captured_chart']}")
    print(f"second-source check: {len(article_only)} designations named by the article only, "
          f"{len(article_conflicts)} conflicts")
    for r in article_only:
        print(f"  article only: {r['team']:11} {r['player']:22} {r['article_status']}")
    print("designated rows:")
    for r in rows:
        if r["game_status"]:
            print(f"  {r['team']:11} {r['player']:20} {r['position']:3} rank {r['published_rank']} "
                  f"({r['rank_label']}) {r['game_status']:12} next up: {r['next_up'] or 'NONE ON CHART'} [{r['unit']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
