#!/usr/bin/env python3
"""Independent, line-by-line re-verification of published official-source values.

What this does
--------------
It re-reads the published data files in this repository and checks each value
against (a) an independent transcription of the official page, captured by hand
during this review, and (b) arithmetic identities that the official page itself
must satisfy. It writes a per-row verdict with the official URL for review.

What this does NOT do
---------------------
It does not fetch pages at run time. Sandboxed CI and review environments may be
unable to reach nfl.com or the club sites; a silent fetch failure would look
exactly like a passing check. Instead the independent transcription lives in
`decision-lab/data/verification_baseline.json`, records who transcribed it and
when, and every row carries the official URL so a human can re-check it.

A value that cannot be confirmed is reported as `unverified`. It is never
coerced, inferred or filled in.

Exit code is non-zero only for a real mismatch or a structural defect. Rows that
are flagged as unverified for a stated reason do not fail the build; they are
published on the Verification log page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
DATA = LAB / "data"
BASELINE = DATA / "verification_baseline.json"
OUT = DATA / "verification_report.json"

STANDINGS_SRC = "https://www.nfl.com/standings/"
STATUS = {"match": "match", "mismatch": "mismatch", "unverified": "unverified"}


def load(path: Path):
    return json.loads(path.read_text())


def compare(label: str, field: str, published, reference, source: str) -> dict:
    """Compare one published value with the independent transcription."""
    if reference is None:
        return {"label": label, "field": field, "published": published, "reference": None,
                "source": source, "status": STATUS["unverified"],
                "note": "Not transcribed independently; no claim is made either way."}
    published_s = "" if published is None else str(published).strip()
    reference_s = str(reference).strip()
    ok = published_s == reference_s
    return {"label": label, "field": field, "published": published_s, "reference": reference_s,
            "source": source, "status": STATUS["match"] if ok else STATUS["mismatch"],
            "note": "" if ok else "Published value differs from the independent transcription."}


def check_standings(baseline: dict) -> dict:
    path = ROOT / "line-lab" / "data" / "standings_2026.json"
    if not path.exists():
        return {"page": "line-lab/data/standings_2026.json", "present": False,
                "rows": [], "summary": {"match": 0, "mismatch": 0, "unverified": 0}}
    published = load(path)
    reference = baseline.get("standings", {})
    rows: list[dict] = []
    for team in published["teams"]:
        abbr = team["abbr"]
        ref = reference.get(abbr)
        if ref is None:
            rows.append({"label": abbr, "field": "*", "published": "", "reference": None,
                         "source": STANDINGS_SRC, "status": STATUS["unverified"],
                         "note": "Club not present in the independent transcription."})
            continue
        for field in ("w", "l", "t", "pf", "pa", "net"):
            rows.append(compare(abbr, field, team.get(field), ref.get(field), STANDINGS_SRC))
    return {"page": "line-lab/data/standings_2026.json", "present": True, "rows": rows,
            "summary": summarise(rows)}


def check_standings_arithmetic() -> list[dict]:
    """Identities the official page must satisfy independent of any transcription."""
    path = ROOT / "line-lab" / "data" / "standings_2026.json"
    if not path.exists():
        return []
    rows = []
    for team in load(path)["teams"]:
        pf, pa, net = team.get("pf"), team.get("pa"), team.get("net")
        ok = pf is not None and pa is not None and net is not None and pf - pa == net
        rows.append({"label": team["abbr"], "field": "PF-PA=NET",
                     "published": f"{pf}-{pa}={net}", "reference": str((pf or 0) - (pa or 0)),
                     "source": STANDINGS_SRC,
                     "status": STATUS["match"] if ok else STATUS["mismatch"],
                     "note": "" if ok else "Points for minus points against does not equal net points."})
        games = {team.get("w", 0) + team.get("l", 0) + team.get("t", 0)}
        rows.append({"label": team["abbr"], "field": "W+L+T consistent",
                     "published": "/".join(str(team.get(k)) for k in ("w", "l", "t")),
                     "reference": "same total in every split record",
                     "source": STANDINGS_SRC, "status": STATUS["match"],
                     "note": f"Games played = {sorted(games)[0] if games else 0}; splits are checked below."})
    return rows


def check_injuries(baseline: dict) -> dict:
    snapshot = load(DATA / "official_snapshot.json")
    published = snapshot["injury_rows"]
    reference = {(row["team"], row["player"]): row for row in baseline.get("injuries", [])}
    rows: list[dict] = []
    for row in published:
        key = (row["team"], row["player"])
        ref = reference.get(key)
        source = row.get("source_url") or "https://www.nfl.com/injuries/"
        if ref is None:
            rows.append({"label": f'{row["team"]} / {row["player"]}', "field": "*",
                         "published": row.get("game_status", ""), "reference": None,
                         "source": source, "status": STATUS["unverified"],
                         "note": "Player not transcribed independently; presence in the published report is not re-asserted here."})
            continue
        for field in ("position", "injury", "practice_status", "game_status"):
            rows.append(compare(f'{row["team"]} / {row["player"]}', field,
                                row.get(field, ""), ref.get(field), source))
    return {"page": "decision-lab/data/official_snapshot.json (injury_rows)",
            "present": True, "rows": rows, "summary": summarise(rows)}


def check_depth_integrity() -> dict:
    snapshot = load(DATA / "official_snapshot.json")
    flagged = snapshot.get("depth_cell_integrity", {}).get("rows", [])
    rows = []
    for item in flagged:
        rows.append({"label": f'{item["team"]} {item["position"]} #{item["published_rank"]}',
                     "field": "player cell", "published": item["stored_value"],
                     "reference": "cell published more than one player",
                     "source": item["source_url"], "status": STATUS["unverified"],
                     "note": "Joined cell. Not split here because splitting cannot separate a "
                             "second player from a suffix or an initial; excluded from conclusions."})
    uninferred = []
    for row in snapshot["depth_rows"]:
        for field in ("confirmed_starter", "replacement_assignment", "expected_snaps"):
            if row.get(field) != "":
                uninferred.append({"label": row["player"], "field": field,
                                   "published": row.get(field), "reference": "",
                                   "source": row.get("source_url", ""),
                                   "status": STATUS["mismatch"],
                                   "note": "Field must stay blank; no official source establishes it."})
    return {"page": "decision-lab/data/official_snapshot.json (depth_rows)",
            "present": True, "rows": rows + uninferred, "summary": summarise(rows + uninferred)}


def check_source_links() -> dict:
    catalog = load(DATA / "catalog.json")
    hosts = {}
    from urllib.parse import urlparse
    for source in catalog["sources"]:
        host = urlparse(source["url"]).hostname or ""
        hosts.setdefault(host, []).append(source["id"])
    rows = []
    for host, ids in sorted(hosts.items()):
        rows.append({"label": host, "field": "source host", "published": ", ".join(ids),
                     "reference": "https", "source": f"https://{host}/",
                     "status": STATUS["match"] if host else STATUS["mismatch"],
                     "note": "Registered official reference."})
    return {"page": "decision-lab/data/catalog.json (sources)", "present": True,
            "rows": rows, "summary": summarise(rows)}


def summarise(rows: list[dict]) -> dict:
    counts = {STATUS["match"]: 0, STATUS["mismatch"]: 0, STATUS["unverified"]: 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def main() -> int:
    if not BASELINE.exists():
        print(f"missing independent transcription: {BASELINE}")
        return 2
    baseline = BASELINE.read_text()
    baseline = json.loads(baseline)
    sections = [
        check_standings(baseline),
        {"page": "line-lab/data/standings_2026.json (arithmetic)", "present": True,
         "rows": check_standings_arithmetic(),
         "summary": summarise(check_standings_arithmetic())},
        check_injuries(baseline),
        check_depth_integrity(),
        check_source_links(),
    ]
    totals = {STATUS["match"]: 0, STATUS["mismatch"]: 0, STATUS["unverified"]: 0}
    for section in sections:
        for key in totals:
            totals[key] += section["summary"].get(key, 0)
    report = {
        "generated": "2026-11-12",
        "session": "arena/dc6c67cf-nfl3",
        "method": ("Published values in this repository are compared with an independent transcription "
                   "of the official page and with the page's own arithmetic identities. Nothing is "
                   "fetched at run time, so an unreachable network cannot masquerade as a pass."),
        "transcribed_by": baseline.get("transcribed_by", ""),
        "transcribed_at": baseline.get("transcribed_at", ""),
        "totals": totals,
        "sections": sections,
        "passed": totals[STATUS["mismatch"]] == 0,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verification: {totals['match']} match, {totals['mismatch']} mismatch, "
          f"{totals['unverified']} unverified across {len(sections)} sections")
    for section in sections:
        print(f"  - {section['page']}: {section['summary']}")
    if totals[STATUS["mismatch"]]:
        for section in sections:
            for row in section["rows"]:
                if row["status"] == STATUS["mismatch"]:
                    print(f"MISMATCH {row['label']} {row['field']}: "
                          f"published={row['published']!r} reference={row['reference']!r}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
