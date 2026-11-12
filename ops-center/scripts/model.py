#!/usr/bin/env python3
"""Model layer for the ops centre.

Rules this file obeys, without exception:

1. Every value it emits is either copied from an official row already in the
   repository capture, copied from a value this session read on an official page,
   or is a count of official rows. Nothing is inferred.
2. Replacement, workload, snap share and performance impact are never estimated.
   Those cells are emitted empty and are flagged.
3. Where the published source is ambiguous (two players share one published
   string) the row says so instead of picking one.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops-center"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"

# ---------------------------------------------------------------------------
# Name and team normalisation
# ---------------------------------------------------------------------------
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.I)


def norm_name(value: str) -> str:
    text = (value or "").lower().replace(".", "").replace(",", "").replace("'", "")
    text = _SUFFIX.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


TEAM_ALIAS = {
    "Bears": "Chicago Bears",
    "Broncos": "Denver Broncos",
    "Eagles": "Philadelphia Eagles",
    "Buccaneers": "Tampa Bay Buccaneers",
}

# Injury-report position -> published club depth-chart positions that could hold
# that player. Deliberately conservative: a family only contains labels that
# unambiguously denote the same role on a club chart.
POSITION_FAMILY = {
    "QB": ["QB"],
    "RB": ["RB", "HB"],
    "FB": ["FB"],
    "WR": ["WR"],
    "TE": ["TE"],
    "C": ["C"],
    "G": ["G", "LG", "RG"],
    "T": ["T", "LT", "RT", "LOT", "ROT", "OT"],
    "OT": ["T", "LT", "RT", "OT"],
    "OL": ["C", "G", "LG", "RG", "T", "LT", "RT"],
    "LS": ["LS"],
    "K": ["K", "PK"],
    "P": ["P"],
    "H": ["H"],
    "PR": ["PR"],
    "KR": ["KR", "KOR"],
    "CB": ["CB", "LCB", "RCB", "NCB"],
    "S": ["S", "SS", "FS"],
    "DB": ["CB", "S", "SS", "FS", "DB", "NB", "LCB", "RCB", "NCB"],
    "LB": ["LB", "ILB", "OLB", "MLB", "WLB", "SLB", "LILB", "RILB",
           "LOLB", "ROLB", "MIKE", "SAM", "WILL"],
    "DE": ["DE", "LDE", "RDE"],
    "DT": ["DT", "NT", "LDT", "RDT", "N"],
    "NT": ["NT", "DT"],
    "DL": ["DL", "DE", "DT", "NT", "LDE", "RDE", "LDT", "RDT", "N"],
    "EDGE": ["EDGE", "DE", "RUSH", "OLB", "LOLB", "ROLB"],
}

# Practice-status severity used only for ordering and counting. The official
# policy (OS-02) defines these as categories, not probabilities, so this order
# is a display convention, never a likelihood.
PRACTICE_ORDER = {
    "Did Not Participate In Practice": 0,
    "Limited Participation in Practice": 1,
    "Full Participation in Practice": 2,
}


def _clean(obj):
    """Replace None with the empty string so a null never reaches a page."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if obj is None:
        return ""
    if isinstance(obj, str):
        low = obj.strip().lower()
        if low in ("nan", "null", "n/a", "-") or (low.startswith("none") and len(low) < 24):
            return ""
    return obj


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def load_recheck() -> dict:
    return json.loads((OPS / "data" / "live_recheck.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Replacement chains
# ---------------------------------------------------------------------------
def merge_recheck(snapshot: dict, recheck: dict) -> list[dict]:
    """The freshest official injury picture available to this repository.

    Starts from the 06:32Z capture and applies the 22:25Z re-observation:
    changed practice statuses are overwritten, rows published during the day are
    appended. Every returned row records which observation it came from, so the
    table can show it.
    """
    base_at = snapshot["injury_rows"][0]["observed_at"]
    re_at = recheck["reobservation"]["observed_at"]

    changes = {(c["team"], norm_name(c["player"])): c for c in recheck["practice_status_changes"]}
    known = {(r["team"], norm_name(r["player"])) for r in snapshot["injury_rows"]}

    rows: list[dict] = []
    for row in snapshot["injury_rows"]:
        out = dict(row)
        out["observed_at"] = base_at
        out["origin"] = "06:32Z capture"
        change = changes.get((row["team"], norm_name(row["player"])))
        if change:
            out["practice_status"] = change["reobserved_practice_status"]
            out["baseline_practice_status"] = change["baseline_practice_status"]
            out["observed_at"] = re_at
            out["origin"] = "22:25Z re-check (status changed)"
        rows.append(out)

    for row in recheck["added_rows"]:
        if (row["team"], norm_name(row["player"])) in known:
            continue
        out = dict(row)
        out["injury"] = row.get("injury", "")
        out["player_url"] = row.get("player_url", "")
        out["source_url"] = recheck["source_url"]
        out["observed_at"] = re_at
        out["origin"] = "22:25Z re-check (row published during the day)"
        out["confirmed_active"] = ""
        out["replacement_player"] = ""
        out["replacement_rank"] = ""
        out["expected_snaps"] = ""
        rows.append(out)
    return rows


def build_chains(snapshot: dict, injury_rows: list[dict] | None = None) -> list[dict]:
    injury_rows = list(injury_rows if injury_rows is not None else snapshot["injury_rows"])
    depth_rows = snapshot["depth_rows"]

    depth_teams = {r["team"] for r in depth_rows}
    by_team: dict[str, list[dict]] = defaultdict(list)
    for row in depth_rows:
        by_team[row["team"]].append(row)

    # Index the injury report so we can say "this team-mate is also on it".
    report_index: dict[str, dict] = {}
    for row in injury_rows:
        report_index[f"{row['team']}::{norm_name(row['player'])}"] = row

    chains: list[dict] = []
    for inj in injury_rows:
        dteam = inj["team"] if inj["team"] in depth_teams else TEAM_ALIAS.get(inj["team"])
        family = POSITION_FAMILY.get(inj["position"], [inj["position"]])

        if dteam is None:
            chains.append(_chain_row(inj, None, [], "no-depth-capture-for-club", {}, report_index))
            continue

        groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in by_team[dteam]:
            if row["position"] in family:
                groups[(row["unit"], row["position"])].append(row)

        if not groups:
            chains.append(_chain_row(inj, dteam, [], "no-published-depth-at-position", {}, report_index,
                                     all_depth=by_team[dteam]))
            continue

        # Where the player appears on the chart, report that group. Where he does
        # not, emit one row naming every group searched rather than one row per
        # candidate position.
        found = [g for g in sorted(groups)
                 if any(norm_name(e["player"]) == norm_name(inj["player"]) for e in groups[g])]
        searched = sorted(f"{u}/{p}" for u, p in groups)
        if found:
            for (unit, position) in found:
                entries = sorted(groups[(unit, position)], key=lambda r: (r["published_rank"], r["player"]))
                chains.append(_chain_row(inj, dteam, entries, "",
                                         {"unit": unit, "position": position}, report_index,
                                         all_depth=by_team[dteam], groups_searched=searched))
        else:
            entries = [e for g in sorted(groups) for e in groups[g]]
            chains.append(_chain_row(inj, dteam, entries, "injured-player-not-on-published-chart",
                                     {"unit": "", "position": "/".join(sorted({p for _, p in groups}))},
                                     report_index, all_depth=by_team[dteam],
                                     groups_searched=searched))

    chains.sort(key=lambda c: (
        c["game_status"] not in ("Out", "Doubtful"),
        c["game_status"] != "Questionable",
        PRACTICE_ORDER.get(c["practice_status"], 9),
        c["team"], c["player"], c["position_group"],
    ))
    return chains


def _chain_row(inj: dict, dteam, entries: list[dict], forced_status: str,
               group: dict, report_index: dict, all_depth: list[dict] | None = None,
               groups_searched: list[str] | None = None) -> dict:
    player_key = norm_name(inj["player"])
    mine = [e for e in entries if norm_name(e["player"]) == player_key]
    rank = mine[0]["published_rank"] if mine else None

    shares: list[str] = []
    nxt: list[dict] = []
    deeper: list[dict] = []
    also: list[dict] = []

    if entries and rank is not None:
        shares = [e["player"] for e in entries
                  if e["published_rank"] == rank and norm_name(e["player"]) != player_key]
        nxt = [{"player": e["player"], "rank": e["published_rank"]}
               for e in entries if e["published_rank"] == rank + 1]
        deeper = [{"player": e["player"], "rank": e["published_rank"]}
                  for e in entries if e["published_rank"] > rank + 1]

    if entries:
        seen: set[str] = set()
        for e in entries:
            if norm_name(e["player"]) == player_key:
                continue
            mate = report_index.get(f"{inj['team']}::{norm_name(e['player'])}")
            if mate is not None and e["player"] not in seen:
                seen.add(e["player"])
                also.append({
                    "player": e["player"],
                    "published_rank": e["published_rank"],
                    "practice_status": mate["practice_status"],
                    "game_status": mate["game_status"],
                })

    # The same player may hold a string at a position outside the searched
    # family (Ben Brown is the Patriots' first-string LG and second-string C).
    # That is a fact on the chart and changes what his absence means.
    other_listings = []
    for e in all_depth or []:
        if norm_name(e["player"]) != player_key:
            continue
        if group.get("unit") == e["unit"] and group.get("position") == e["position"]:
            continue
        other_listings.append(f'{e["unit"][0]}/{e["position"]} #{e["published_rank"]}')
    other_listings = sorted(set(other_listings))

    if forced_status:
        status = forced_status
    elif rank is None:
        status = "injured-player-not-on-published-chart"
    else:
        status = "chain-identified"

    authorities = sorted({e["authority"] for e in entries}) if entries else []
    depth_url = entries[0]["source_url"] if entries else ""

    return {
        "team": inj["team"],
        "matchup": inj["matchup"],
        "day": inj["day"],
        "player": inj["player"],
        "injury_position": inj["position"],
        "injury": inj["injury"],
        "practice_status": inj["practice_status"],
        "game_status": inj["game_status"],
        "player_url": inj["player_url"],
        "injury_source_url": inj["source_url"],
        "depth_team": dteam or "",
        "unit": group.get("unit", ""),
        "position_group": group.get("position", ""),
        "published_rank": rank if rank is not None else "",
        "rank_shared_with": shares,
        "next_string": nxt,
        "deeper_strings": deeper,
        "also_on_report": also,
        "other_listings": other_listings,
        "groups_searched": groups_searched or [],
        "chain_status": status,
        "depth_authority": "; ".join(authorities),
        "depth_source_url": depth_url,
        # Never filled by this build. Present so the table always shows the gap.
        "confirmed_replacement": "",
        "expected_snaps": "",
        "performance_delta": "",
    }


# ---------------------------------------------------------------------------
# Depth coverage: how deep does each club actually publish?
# ---------------------------------------------------------------------------
def build_coverage(snapshot: dict) -> list[dict]:
    depth_rows = snapshot["depth_rows"]
    injury_teams = {r["team"] for r in snapshot["injury_rows"]} | {
        s["team"] for s in snapshot["no_injury_sections"]
    }
    # Depth charts use full club names ("Tampa Bay Buccaneers"); the injury
    # report uses short ones ("Buccaneers"). Map both ways before comparing.
    for short, full in TEAM_ALIAS.items():
        if short in injury_teams:
            injury_teams.add(full)
    groups: dict[str, dict[tuple[str, str], list[dict]]] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, dict] = {}
    for row in depth_rows:
        groups[row["team"]][(row["unit"], row["position"])].append(row)
        meta.setdefault(row["team"], {
            "source_url": row["source_url"],
            "authority": row["authority"],
            "observed_at": row["observed_at"],
            "sha256": row["source_sha256"],
        })
        if row["authority"] != "club depth chart":
            meta[row["team"]]["authority"] = row["authority"]

    out = []
    for team, g in sorted(groups.items()):
        depths = [max(r["published_rank"] for r in rows) for rows in g.values()]
        single = sum(1 for d in depths if d == 1)
        two = sum(1 for d in depths if d == 2)
        three_plus = sum(1 for d in depths if d >= 3)
        out.append({
            "team": team,
            "in_week_10_report": team in injury_teams,
            "position_groups": len(g),
            "max_string_published": max(depths),
            "groups_with_1_string": single,
            "groups_with_2_strings": two,
            "groups_with_3plus_strings": three_plus,
            "pct_groups_without_3rd_string": round(100.0 * (single + two) / len(g), 1),
            "authority": meta[team]["authority"],
            "source_url": meta[team]["source_url"],
            "observed_at": meta[team]["observed_at"],
            "source_sha256": meta[team]["sha256"],
        })
    out.sort(key=lambda r: (-r["pct_groups_without_3rd_string"], r["team"]))
    return out


def build_exposure(chains: list[dict]) -> list[dict]:
    """Counts of compromised published strings, by club and side of the ball.

    A 'compromised' string is a published player at that rank who appears on the
    official injury report as Did Not Participate, Out, Doubtful or Questionable.
    It is a count of official rows. It is not a performance estimate.
    """
    per: dict[str, dict] = defaultdict(lambda: {
        "offense": set(), "defense": set(), "compounded": [], "matchup": "",
    })
    for c in chains:
        if c["chain_status"] != "chain-identified":
            continue
        team = c["team"]
        per[team]["matchup"] = c["matchup"]
        compromised = _is_compromised(c)
        mates_compromised = [a for a in c["also_on_report"] if _is_compromised(a)]
        if compromised:
            key = (c["unit"], c["position_group"], c["published_rank"])
            if c["unit"] == "Offense":
                per[team]["offense"].add(key)
            elif c["unit"] == "Defense":
                per[team]["defense"].add(key)
        if compromised and mates_compromised:
            per[team]["compounded"].append({
                "position_group": f'{c["unit"][0]}/{c["position_group"]}',
                "player": c["player"],
                "status": c["game_status"] or c["practice_status"],
                "also": "; ".join(
                    f'{a["player"]} ({a["game_status"] or a["practice_status"]})'
                    for a in mates_compromised
                ),
                "next_string": ", ".join(n["player"] for n in c["next_string"]) or "",
            })

    rows = []
    for team, data in per.items():
        rows.append({
            "team": team,
            "matchup": data["matchup"],
            "offense_strings_on_report": len(data["offense"]),
            "defense_strings_on_report": len(data["defense"]),
            "total_strings_on_report": len(data["offense"]) + len(data["defense"]),
            "compounded_positions": len(data["compounded"]),
            "compounded_detail": data["compounded"],
            # Unverified by design.
            "confirmed_snaps_lost": "",
            "points_impact": "",
        })
    rows.sort(key=lambda r: (-r["total_strings_on_report"], -r["compounded_positions"], r["team"]))
    return rows


def _is_compromised(row: dict) -> bool:
    if row.get("game_status") in ("Out", "Doubtful", "Questionable"):
        return True
    return row.get("practice_status") == "Did Not Participate In Practice"


# ---------------------------------------------------------------------------
# Consolidated decision registers (merged across workspaces, deduplicated)
# ---------------------------------------------------------------------------
_STOP = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "is", "are",
         "be", "do", "does", "what", "which", "who", "how", "we", "our", "us", "it",
         "this", "that", "any", "all", "can", "should", "will", "would", "there", "they"}


def _tokens(text: str) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()
    return {w for w in words if w not in _STOP and len(w) > 2}


def _near(existing_keys: dict, text: str, threshold: float = 0.55) -> str | None:
    """Find an existing key that is the same question phrased differently.

    Deliberately conservative: it merges only when a majority of content words
    are shared, so genuinely different questions stay separate.
    """
    toks = _tokens(text)
    if not toks:
        return None
    best, best_score = None, 0.0
    for key, key_toks in existing_keys.items():
        if not key_toks:
            continue
        score = len(toks & key_toks) / len(toks | key_toks)
        if score > best_score:
            best, best_score = key, score
    return best if best_score >= threshold else None


def _norm_question(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower())[:110].strip()


def build_questions() -> list[dict]:
    merged: dict[str, dict] = {}
    keys: dict[str, set[str]] = {}

    def add(area, question, known, answer, missing, discovery, blocking, prov, urls):
        key = _norm_question(question)
        if not key:
            return
        target = key if key in merged else _near(keys, question)
        if target is None:
            keys[key] = _tokens(question)
            merged[key] = {
                "area": area, "question": question, "known": known, "answer": answer,
                "missing": missing, "discovery": discovery, "blocking": blocking,
                "provenance": [prov], "sources": [u for u in urls if u],
            }
            return
        merged[target]["provenance"].append(prov)
        if blocking:
            merged[target]["blocking"] = True
        for field, value in (("known", known), ("answer", answer), ("missing", missing),
                             ("discovery", discovery), ("area", area)):
            if value and not merged[target][field]:
                merged[target][field] = value
        for u in urls:
            if u and u not in merged[target]["sources"]:
                merged[target]["sources"].append(u)

    cat = json.loads((ROOT / "decision-lab" / "data" / "catalog.json").read_text())
    for q in cat["questions"]:
        add(q.get("area", ""), q.get("question", ""), q.get("known", ""), q.get("answer", ""),
            q.get("missing", ""), q.get("discovery", ""), bool(q.get("blocking")),
            "decision-lab/" + q.get("id", ""), [cat["sources"][i]["url"] for i, s in
             enumerate(cat["sources"]) if s["id"] == q.get("source")])

    for q in json.loads((ROOT / "decision-hub" / "data" / "questions_discovery.json").read_text()):
        add(q.get("domain", ""), q.get("question", ""), q.get("known_info", ""),
            q.get("verified_answer", ""), q.get("missing_info", ""),
            q.get("discovery_suggestion", ""), q.get("status", "") != "answered",
            "decision-hub/" + q.get("q_id", ""), [q.get("source_url", "")])

    ll = json.loads((ROOT / "line-lab" / "data" / "questions.json").read_text())
    src_by_id = {s["id"]: s["url"] for s in json.loads(
        (ROOT / "line-lab" / "data" / "sources.json").read_text())["sources"]}
    for q in ll["questions"]:
        add(q.get("domain", ""), q.get("question", ""), q.get("current_answer", ""),
            q.get("current_answer", "") if q.get("status") == "answered" else "",
            "" if q.get("status") == "answered" else q.get("how_to_close", ""),
            q.get("how_to_close", ""), q.get("status", "") != "answered",
            "line-lab/" + q.get("id", ""),
            [src_by_id.get(s, "") for s in q.get("source_ids", [])])

    vlq = ROOT / "verification-lab" / "data" / "questions.json"
    if vlq.exists():
        for q in json.loads(vlq.read_text()).get("questions", []):
            add(q.get("area", ""), q.get("question", ""), q.get("known", ""),
                "" if q.get("blocking") else q.get("known", ""),
                q.get("unknown", ""), q.get("discovery", ""), bool(q.get("blocking")),
                "verification-lab/" + q.get("id", ""), [q.get("source_url", "")])

    with (ROOT / "dashboard" / "data" / "questions.csv").open(newline="", encoding="utf-8") as fh:
        for q in csv.DictReader(fh):
            add("Dashboard", q.get("question", ""), q.get("what_we_known") or q.get("what_we_know", ""),
                "" if q.get("status") != "Known" else q.get("what_we_know", ""),
                q.get("what_is_missing", ""), q.get("how_to_discover", ""),
                (q.get("decision_needed_from_owner") or "").strip().lower() == "yes",
                "dashboard/" + q.get("id", ""), [q.get("source_link", "")])

    rows = list(merged.values())
    rows.sort(key=lambda r: (not r["blocking"], r["area"], r["question"]))
    for i, r in enumerate(rows, 1):
        r["id"] = f"Q-{i:02d}"
    return rows


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower())[:90].strip()


def build_suggestions() -> list[dict]:
    merged: dict[str, dict] = {}
    keys: dict[str, set[str]] = {}

    def add(title, area, summary, priority, effort, impact, depends, path, rec, prov, urls):
        key = _norm_title(title)
        if not key:
            return
        target = key if key in merged else _near(keys, title, 0.6)
        if target is None:
            keys[key] = _tokens(title)
            merged[key] = _clean({
                "title": title, "area": area, "summary": summary, "priority": priority,
                "effort": effort, "impact": impact, "depends": depends, "path": path,
                "recommendation": rec, "provenance": [prov], "sources": [u for u in urls if u]})
            return
        merged[target]["provenance"].append(prov)
        for field, value in (("area", area), ("summary", summary), ("priority", priority),
                             ("effort", effort), ("impact", impact), ("depends", depends),
                             ("path", path), ("recommendation", rec)):
            if value and not merged[target][field]:
                merged[target][field] = value
        for u in urls:
            if u and u not in merged[target]["sources"]:
                merged[target]["sources"].append(u)

    cat = json.loads((ROOT / "decision-lab" / "data" / "catalog.json").read_text())
    src = {s["id"]: s["url"] for s in cat["sources"]}
    for s in cat["suggestions"]:
        add(s.get("title", ""), "Decision lab", s.get("detail", ""), s.get("priority", ""),
            s.get("effort", ""), s.get("impact", ""), s.get("depends", ""), s.get("path", ""),
            s.get("recommendation", ""), "decision-lab/" + s.get("id", ""), [src.get(s.get("source", ""), "")])

    for s in json.loads((ROOT / "decision-hub" / "data" / "suggestions.json").read_text()):
        add(s.get("title", ""), s.get("category", ""), s.get("decision_improvement", ""),
            "", "", "", s.get("prerequisites", ""), "", s.get("status", ""),
            "decision-hub/" + s.get("id", ""), [s.get("source_url", "")])

    ll = json.loads((ROOT / "line-lab" / "data" / "suggestions.json").read_text())
    lsrc = {s["id"]: s["url"] for s in json.loads(
        (ROOT / "line-lab" / "data" / "sources.json").read_text())["sources"]}
    for s in ll["suggestions"]:
        add(s.get("title", ""), s.get("category", ""), s.get("proposal", ""),
            "Critical" if s.get("critical_path") else "", s.get("effort", ""),
            s.get("impact", ""), ", ".join(s.get("dependencies", []) or []), "",
            s.get("recommendation", ""), "line-lab/" + s.get("id", ""),
            [lsrc.get(x, "") for x in s.get("source_ids", [])])

    vlq2 = ROOT / "verification-lab" / "data" / "queue.json"
    if vlq2.exists():
        for s2 in json.loads(vlq2.read_text()).get("items", []):
            add(s2.get("title", ""), s2.get("kind", ""), s2.get("why", ""),
                s2.get("priority", ""), s2.get("effort", ""), s2.get("fixes", ""),
                "", "", s2.get("acceptance", ""), "verification-lab/" + s2.get("id", ""),
                [s2.get("source_url", "")])

    with (ROOT / "dashboard" / "data" / "suggestions.csv").open(newline="", encoding="utf-8") as fh:
        for s in csv.DictReader(fh):
            add(s.get("suggestion", ""), s.get("area", ""), s.get("why_it_helps", ""),
                "", "", "", s.get("what_it_needs", ""), "", s.get("status", ""),
                "dashboard/" + s.get("id", ""), [s.get("source_link", "")])

    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rows = list(merged.values())
    rows.sort(key=lambda r: (order.get(r["priority"], 4), r["title"]))
    for i, r in enumerate(rows, 1):
        r["id"] = f"SG-{i:02d}"
    return rows


def build_strategies() -> list[dict]:
    merged: dict[str, dict] = {}
    keys: dict[str, set[str]] = {}

    def add(name, kind, thesis, status, prov, urls, note=""):
        key = _norm_title(name)
        if not key:
            return
        target = key if key in merged else _near(keys, name, 0.6)
        if target is None:
            keys[key] = _tokens(name)
            merged[key] = _clean({
                "name": name, "kind": kind, "thesis": thesis, "status": status,
                "note": note, "provenance": [prov], "sources": [u for u in urls if u],
                "validated": False, "edge": "", "clv": "", "rank": "", "reward": ""})
            return
        merged[target]["provenance"].append(prov)
        for field, value in (("kind", kind), ("thesis", thesis), ("status", status), ("note", note)):
            if value and not merged[target][field]:
                merged[target][field] = value
        for u in urls:
            if u and u not in merged[target]["sources"]:
                merged[target]["sources"].append(u)

    cat = json.loads((ROOT / "decision-lab" / "data" / "catalog.json").read_text())
    src = {s["id"]: s["url"] for s in cat["sources"]}
    for s in cat["strategies"]:
        add(s.get("name", ""), s.get("division", ""), s.get("hypothesis", ""),
            s.get("status", ""), "decision-lab/" + s.get("id", ""), [src.get(s.get("source", ""), "")],
            s.get("test", ""))

    ll = json.loads((ROOT / "line-lab" / "data" / "strategies.json").read_text())
    lsrc = {s["id"]: s["url"] for s in json.loads(
        (ROOT / "line-lab" / "data" / "sources.json").read_text())["sources"]}
    for s in ll["strategies"]:
        add(s.get("name", ""), s.get("type", ""), s.get("thesis", ""), s.get("verdict", ""),
            "line-lab/" + s.get("id", ""), [lsrc.get(x, "") for x in s.get("source_ids", [])],
            s.get("rule", ""))

    with (ROOT / "dashboard" / "data" / "strategies.csv").open(newline="", encoding="utf-8") as fh:
        for s in csv.DictReader(fh):
            add(s.get("name", ""), s.get("bet_type", ""), s.get("signal_hypothesis", ""),
                s.get("gate_status", ""), "dashboard/" + s.get("strategy_id", ""),
                [s.get("source_link", "")], s.get("notes", ""))

    rows = list(merged.values())
    rows.sort(key=lambda r: r["name"])
    for i, r in enumerate(rows, 1):
        r["id"] = f"ST-{i:02d}"
    return rows


def build_community_evidence() -> dict:
    """Community-source empirical results computed by another session.

    These are real computed numbers, but they rest on nflverse community data,
    which is not NFL-authored. They are published for completeness and are
    excluded from every official-only gate. Every row says so.
    """
    path = ROOT / "lab" / "results" / "computed.json"
    if not path.exists():
        return {"available": False, "rows": []}
    data = json.loads(path.read_text())
    rows = []
    for item in data.get("corr", {}).get("rows", []):
        rows.append({
            "pair": item["pair"], "statistic": "phi (same-game, binary)",
            "value": round(item["phi"], 4),
            "value_display": (f'{item["phi"]:.4f}' if abs(item["phi"]) >= 0.001
                              else f'{item["phi"]:.2e}'),
            "n": item["n"],
            "ci95": f'{item["ci95"][0]:.3f} to {item["ci95"][1]:.3f}',
            "p_value": ("< 0.001" if item["p_value"] < 0.001 else f'{item["p_value"]:.3f}'),
        })
    stacked = data.get("corr", {}).get("stacked", {})
    strategy_rows = []
    for s in data.get("strategies", []) if isinstance(data.get("strategies"), list) else []:
        strategy_rows.append(s)
    return {
        "available": True,
        "authority": "community (nflverse), not NFL-authored; excluded from official-only gates",
        "source_url": "https://github.com/nflverse/nflverse-data/releases",
        "rows": rows,
        "stacked": {
            "p_triple_if_independent": stacked.get("p_triple_if_independent"),
            "p_triple_observed": stacked.get("p_triple_observed"),
            "lift": stacked.get("lift"),
            "overstatement": stacked.get("overstatement"),
            "n": stacked.get("n"),
        },
        "clv": data.get("clv", {}),
    }


def build_gates() -> list[dict]:
    """Consolidated validation gates, merged across workspaces."""
    merged: dict[str, dict] = {}
    keys: dict[str, set[str]] = {}

    def add(name, criterion, needs, failure, prov, urls):
        key = _norm_title(name)
        if not key:
            return
        target = key if key in merged else _near(keys, name, 0.7)
        if target is None:
            keys[key] = _tokens(name)
            merged[key] = _clean({"name": name, "criterion": criterion, "needs": needs,
                                  "failure": failure, "provenance": [prov],
                                  "sources": [u for u in urls if u]})
            return
        merged[target]["provenance"].append(prov)
        for field, value in (("criterion", criterion), ("needs", needs), ("failure", failure)):
            if value and len(str(value)) > len(str(merged[target][field])):
                merged[target][field] = value
        for u in urls:
            if u and u not in merged[target]["sources"]:
                merged[target]["sources"].append(u)

    cat = json.loads((ROOT / "decision-lab" / "data" / "catalog.json").read_text())
    src = {s["id"]: s["url"] for s in cat["sources"]}
    for g in cat["gates"]:
        add(g.get("name", ""), g.get("rule", ""), "", g.get("fail", ""),
            "decision-lab/" + g.get("id", ""), [src.get(g.get("source", ""), "")])

    ll = json.loads((ROOT / "line-lab" / "data" / "gates.json").read_text())
    lsrc = {s["id"]: s["url"] for s in json.loads(
        (ROOT / "line-lab" / "data" / "sources.json").read_text())["sources"]}
    for g in ll["gates"]:
        add(g.get("name", ""), g.get("criterion", ""), g.get("needs", ""), g.get("failure", ""),
            "line-lab/" + g.get("id", ""), [ll["meta"].get("numbers_source", "") and
             "https://www.nfl.com/standings/"])

    with (ROOT / "dashboard" / "data" / "validation_gates.csv").open(newline="", encoding="utf-8") as fh:
        for g in csv.DictReader(fh):
            add(g.get("gate", ""), g.get("rule", ""), "", g.get("status", ""),
                "dashboard/" + g.get("gate_id", ""), ["https://www.nfl.com/injuries/"])

    rows = list(merged.values())
    rows.sort(key=lambda r: r["name"])
    for i, r in enumerate(rows, 1):
        r["id"] = f"G-{i:02d}"
    return rows


def build_math() -> dict:
    path = ROOT / "line-lab" / "data" / "strategy_math.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {
        "meta": data.get("meta", {}),
        "sample_size": data.get("sample_size", {}),
        "deflated_sharpe": data.get("deflated_sharpe", {}),
    }


def build_rewards() -> list[dict]:
    path = ROOT / "decision-hub" / "data" / "origination_leaderboard.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    out = []
    for r in data.get("reward_governance", []):
        out.append({
            "rule": r.get("rule_id", ""), "mechanism": r.get("mechanism", ""),
            "anti_luck_effect": r.get("anti_luck_effect", ""), "status": r.get("status", ""),
            "source_url": r.get("source_url", ""),
        })
    return out


def build_flags(chains: list[dict], coverage: list[dict], snapshot: dict) -> list[dict]:
    """Irregularities this session observed and could not resolve from sources."""
    not_on_chart = [c for c in chains if c["chain_status"] == "injured-player-not-on-published-chart"]
    no_capture = sorted({c["team"] for c in chains if c["chain_status"] == "no-depth-capture-for-club"})
    groups = sum(r["position_groups"] for r in coverage)
    without_third = sum(r["groups_with_1_string"] + r["groups_with_2_strings"] for r in coverage)

    return [
        {"id": "OF-01", "severity": "Critical",
         "title": "The official injury page changed 25 rows in sixteen hours",
         "detail": "The 06:32Z capture holds 254 rows across 24 clubs with four 'No Injuries Reported' sections. Re-read at 22:25Z the same day the page held 279 rows: Seattle and Cincinnati had published 19 rows that did not exist in the morning, six more rows were added to four clubs, and four Colts practice statuses moved in both directions. Nothing was removed.",
         "impact": "A single capture cannot support any availability feature. Questionable to Out transitions and the Thursday to Friday practice progression are only recoverable from a dated series.",
         "action": "Store every capture with its timestamp and hash and keep the history. Treat any figure computed from one capture as provisional.",
         "source": "https://www.nfl.com/injuries/"},
        {"id": "OF-02", "severity": "Critical",
         "title": "Patriots depth rows are labelled 'club depth chart' but the page disclaims itself",
         "detail": "The committed capture labels all 60 Patriots depth rows with authority 'club depth chart'. The page itself states: 'The 2026 depth chart is unofficial and is published by the writers of Patriots.com. The depth chart reflects the opinions of the Patriots.com writers and don't necessarily reflect those of the organization.'",
         "impact": "Any chain built on Patriots rows inherits an opinion, not a club statement. Ben Brown, Carlton Davis III and TreVeyon Henderson are all ruled Out and all three chains come from this page.",
         "action": "Re-label those rows as club-published unofficial and exclude them from official-only gates until the source says otherwise.",
         "source": "https://www.patriots.com/team/depth-chart"},
        {"id": "OF-03", "severity": "High",
         "title": f"{len(not_on_chart)} injured players do not appear at their position on their own club chart",
         "detail": "Players the league report lists, who hold no published string at the matching position on the club depth chart. Lucas Patrick (Commanders C, ruled Out) and Malik Harrison (Giants LB, Questionable) are two of them; both were checked against the live club page this session.",
         "impact": "For these players no published next-man-up exists. A replacement cannot be named from official data and must stay blank.",
         "action": "Treat as unresolved. Do not substitute a roster order or a third-party depth chart.",
         "source": "https://www.nfl.com/injuries/"},
        {"id": "OF-04", "severity": "High",
         "title": f"Third and fourth strings are not published for {without_third} of {groups} position groups",
         "detail": "Across the 30 captured club charts, most positions publish one or two strings. Only a minority publish a third, and a handful publish a fourth.",
         "impact": "The requirement to track second, third and fourth string replacements cannot be met from official club charts at their current depth. Where a third string is needed and not published, the cell is blank.",
         "action": "Source a participation or snap-count feed, or accept that depth beyond the published second string is unknown.",
         "source": "https://www.commanders.com/team/depth-chart"},
        {"id": "OF-05", "severity": "High",
         "title": "Two Week 10 clubs have no depth capture at all",
         "detail": f"No club depth rows were captured for: {', '.join(no_capture)}. Every injury row for those clubs resolves to 'no depth capture'.",
         "impact": "Availability for those clubs cannot be assessed end to end.",
         "action": "Extend the capture to all 32 clubs and fail the build when Week 10 coverage is incomplete.",
         "source": "https://www.nfl.com/teams/"},
        {"id": "OF-06", "severity": "Medium",
         "title": "Published strings are not always one player",
         "detail": "The Seahawks chart packs Cooper Kupp and Rashid Shaheed into a single first-string wide-receiver cell; the Commanders and Patriots publish two and three separate rows at the same position, so more than one player carries the same published rank.",
         "impact": "'First string' and 'second string' are ambiguous at those positions. The chain table reports every player sharing a string instead of choosing one.",
         "action": "Keep the ambiguity visible; do not resolve it by guess.",
         "source": "https://www.seahawks.com/team/depth-chart/"},
        {"id": "OF-07", "severity": "Medium",
         "title": "Status is a category, not a probability",
         "detail": "The official policy defines Did Not Participate, Limited (less than 100 percent of normal repetitions) and Full (100 percent). Game status: Questionable means uncertain, Doubtful means unlikely, Out means will not play. The policy states a player certain to play is not listed in the Game Status Report at all.",
         "impact": "A Questionable designation carries no calibrated playing probability. Any model that converts these labels into likelihoods is inventing numbers.",
         "action": "Use status as an ordinal feature only, and calibrate probabilities against graded outcomes once a licensed result history exists.",
         "source": "https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693"},
        {"id": "OF-09", "severity": "Medium",
         "title": "Inherited strategy text carries figures computed on community data",
         "detail": "Some strategy rows merged from other workspaces quote correlations, p-values and "
                   "matchup constants in their thesis or risk text. Those numbers were computed on nflverse "
                   "community assets, not on official NFL data, but the row they sit in carries an official "
                   "source link, which makes them look better sourced than they are.",
         "impact": "A reader can mistake a community-data figure for an official-source finding.",
         "action": "Each row now carries a Basis marker: 'carries computed figures' or 'hypothesis only'. "
                   "Treat any marked row as exploratory until it is recomputed on a licensed source.",
         "source": "https://github.com/nflverse/nflverse-data/releases"},
        {"id": "OF-10", "severity": "Medium",
         "title": "One question row cites a secondary news source as its evidence",
         "detail": "A question about which prop bets the NFL restricts cites a Yahoo Sports article. The "
                   "league's own memo has not been located on an official host, so the underlying claim is "
                   "unverified even though the row is not blank.",
         "impact": "The row looks evidenced when it is not. This repeats a flag already raised by the "
                   "dashboard session (R-12).",
         "action": "Find the primary NFL policy document or mark the answer unverified.",
         "source": "https://sports.yahoo.com/article/nfl-says-worked-ban-more-152200232.html"},
        {"id": "OF-08", "severity": "Medium",
         "title": "No licensed odds, prop or settlement archive is held",
         "detail": "No odds history, player-prop line history or settlement record exists in this repository. Every strategy on the leaderboard is therefore blocked at the data gate, and no closing line value, return or rank can be computed.",
         "impact": "Nothing can be scored. Every strategy stays at 'not run' by construction, not by choice.",
         "action": "Obtain written terms for historical and live prices before any leaderboard can produce a result.",
         "source": "https://www.nfl.com/injuries/"},
    ]
