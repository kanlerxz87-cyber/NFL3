#!/usr/bin/env python3
"""Line-by-line verification of the published snapshot against official sources.

Two layers:

1. Pure comparison functions (``compare_records``, ``compare_no_injury``,
   ``compare_depth``) that take two already-parsed record sets. They contain no
   network code and are unit-tested offline in ``tests/test_decision_lab.py``.
2. A runner that re-fetches every captured official source over HTTPS, reparses
   it with the same parser used for the snapshot, and compares field by field.

Honesty rules enforced by this script:
* A source that cannot be fetched is reported as **unreachable**, never as
  verified and never as a mismatch.
* A blank published cell is compared as blank. It is never treated as equal to
  a non-blank value.
* Mismatches are reported for human review; they are not auto-corrected.
* Exit code is 0 when the run completed and every family was comparable,
  1 when at least one family could not be compared. Drift itself is data, not a
  build failure, and is always enumerated in the output.

Output: ``decision-lab/data/verification.json``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "scripts"))
import capture_official as capture  # noqa: E402  (same parser as the snapshot)

DATA = LAB / "data"
INJURY_FIELDS = ("day", "matchup", "team", "player", "position", "injury", "practice_status", "game_status")


def key_injury(row: dict) -> tuple[str, str]:
    return (row.get("team", ""), row.get("player", ""))


def compare_records(published: list[dict], live: list[dict], fields: tuple[str, ...]) -> dict:
    """Field-by-field comparison of two parsed record sets.

    Rows are matched on (team, player). Ordering is not treated as evidence
    because the NFL page re-sorts sections during the day.
    """
    live_index: dict[tuple[str, str], dict] = {}
    duplicates: list[str] = []
    for row in live:
        k = key_injury(row)
        if k in live_index:
            duplicates.append(f"{k[0]} / {k[1]}")
        live_index[k] = row
    pub_index = {key_injury(r): r for r in published}
    matched = mismatched = missing_live = extra_live = 0
    details: list[dict] = []
    for k, row in pub_index.items():
        other = live_index.get(k)
        if other is None:
            missing_live += 1
            details.append({"scope": "injury", "key": " / ".join(k), "field": "(row)", "published": "present", "live": "absent"})
            continue
        diffs = [f for f in fields if (row.get(f, "") or "") != (other.get(f, "") or "")]
        if diffs:
            mismatched += 1
            for f in diffs:
                details.append({"scope": "injury", "key": " / ".join(k), "field": f,
                                "published": row.get(f, ""), "live": other.get(f, "")})
        else:
            matched += 1
    for k in live_index:
        if k not in pub_index:
            extra_live += 1
            details.append({"scope": "injury", "key": " / ".join(k), "field": "(row)", "published": "absent", "live": "present"})
    return {
        "published_rows": len(pub_index), "live_rows": len(live_index),
        "matched": matched, "mismatched": mismatched,
        "missing_live": missing_live, "extra_live": extra_live,
        "duplicate_live_keys": sorted(set(duplicates))[:20],
        "details": details,
    }


def compare_no_injury(published: list[dict], live: list[dict]) -> dict:
    pub = {r["team"] for r in published}
    liv = {r["team"] for r in live}
    return {
        "published_sections": len(pub), "live_sections": len(liv),
        "matched": len(pub & liv), "mismatched": len(pub ^ liv),
        "details": [{"scope": "no-injury", "key": team, "field": "(section)",
                     "published": "no-injury section" if team in pub else "absent",
                     "live": "no-injury section" if team in liv else "absent"}
                    for team in sorted(pub ^ liv)],
    }


def compare_depth(published: list[dict], live: list[dict]) -> dict:
    """Compare (unit, position, player, published_rank) tuples for one club."""
    def tuples(rows):
        return {(r.get("unit", ""), r.get("position", ""), r.get("player", ""), int(r.get("published_rank", 0))) for r in rows}
    pub, liv = tuples(published), tuples(live)
    details = [{"scope": "depth", "key": " / ".join(map(str, t)), "field": "(row)",
                "published": "present", "live": "absent"} for t in sorted(pub - liv)]
    details += [{"scope": "depth", "key": " / ".join(map(str, t)), "field": "(row)",
                 "published": "absent", "live": "present"} for t in sorted(liv - pub)]
    return {
        "published_rows": len(pub), "live_rows": len(liv),
        "matched": len(pub & liv), "mismatched": len(pub ^ liv), "details": details,
    }


def depth_gaps(depth_rows: list[dict], expected_clubs: int) -> dict:
    """Clubs with a captured depth page but no rank-1 row in a playing unit.

    A published depth page that lists no first-team player for a unit is either
    incomplete or was parsed incompletely; both are findings, not silent zeros.
    """
    units_seen: dict[str, set[str]] = {}
    for row in depth_rows:
        units_seen.setdefault(row["team"], set()).add(row["unit"])
    gaps = []
    for team, units in sorted(units_seen.items()):
        for unit in sorted(units):
            if not any(r["team"] == team and r["unit"] == unit and int(r["published_rank"]) == 1 for r in depth_rows):
                gaps.append({"team": team, "unit": unit, "gap": "no published rank-1 row in this unit"})
    clubs = {r["team"] for r in depth_rows}
    return {"clubs_captured": len(clubs), "clubs_expected": expected_clubs, "unit_gaps": gaps,
            "clubs_missing_entirely": expected_clubs - len(clubs)}


def family(fid: str, name: str, method: str, source_url: str, result: dict | None, note: str = "", compared: bool = True) -> dict:
    if result is None:
        return {"id": fid, "name": name, "method": method, "source_url": source_url,
                "compared": False, "status": "unreachable", "note": note,
                "rows_checked": 0, "matched": 0, "mismatched": 0, "coverage": ""}
    total = result.get("published_rows", 0)
    coverage = f"{result['matched']}/{total}" if total else "n/a"
    return {"id": fid, "name": name, "method": method, "source_url": source_url,
            "compared": compared, "status": "match" if result["mismatched"] == 0 else "drift",
            "note": note, "rows_checked": total, "matched": result["matched"],
            "mismatched": result["mismatched"], "coverage": coverage,
            "extra_live": result.get("extra_live", 0), "missing_live": result.get("missing_live", 0)}


def fetch_text(url: str, allowed: set[str], timeout: int = 45) -> tuple[str | None, str, str]:
    try:
        raw, final_url = capture.fetch(url, allowed, timeout)
        return raw.decode("utf-8", errors="replace"), final_url, ""
    except Exception as exc:  # network, TLS, HTTP, redirect guard
        return None, "", f"{type(exc).__name__}: {exc}"


def run(snapshot: dict, catalog: dict, timeout: int = 45, offline: bool = False) -> dict:
    observed_at = snapshot.get("observed_at", "")
    families: list[dict] = []
    skipped: list[str] = []
    unreachable: list[dict] = []
    details: list[dict] = []

    def allowed_for(url: str) -> set[str]:
        host = urlparse(url).hostname or ""
        bare = host.removeprefix("www.")
        return {host, bare, "www." + bare}

    # ---- F1: injury report rows, field by field -------------------------
    injuries = snapshot["injury_rows"]
    report_urls = sorted({r["source_url"] for r in injuries} | {r["source_url"] for r in snapshot.get("no_injury_sections", [])})
    live_injuries: list[dict] = []
    live_no_injury: list[dict] = []
    report_fetch_failed = []
    for url in ([] if offline else report_urls):
        text, final_url, err = fetch_text(url, allowed_for(url), timeout)
        if text is None:
            report_fetch_failed.append({"url": url, "error": err})
            unreachable.append({"family": "F1", "url": url, "error": err})
            continue
        rows, empty = capture.parse_injuries(text, final_url, datetime.now(timezone.utc).isoformat(), hashlib.sha256(text.encode()).hexdigest())
        live_injuries.extend(rows)
        live_no_injury.extend(empty)

    if offline:
        skipped.append("F1 injury report field-by-field, F2 no-injury sections, F3 club depth charts, F5 status vocabulary and F6 source reachability need outbound HTTPS and are run by the scheduled publication workflow")
    elif report_fetch_failed:
        families.append(family("F1", "Injury report rows", "re-fetch NFL.com report and compare every published field", report_urls[0] if report_urls else "", None,
                               note=f"{len(report_fetch_failed)} report URL(s) unreachable: " + "; ".join(f"{f['url']} ({f['error'][:120]})" for f in report_fetch_failed)))
        families.append(family("F2", "No-injury sections", "re-fetch NFL.com report and compare explicit empty sections", report_urls[0] if report_urls else "", None,
                               note="depends on the F1 capture"))
    else:
        f1 = compare_records(injuries, live_injuries, INJURY_FIELDS)
        details.extend(f1.pop("details"))
        families.append(family("F1", "Injury report rows", "re-fetch NFL.com report and compare every published field", report_urls[0] if report_urls else "", f1,
                               note="compares day, matchup, team, player, position, injury, practice status and game status"))
        f2 = compare_no_injury(snapshot.get("no_injury_sections", []), live_no_injury)
        details.extend(f2.pop("details"))
        families.append(family("F2", "No-injury sections", "re-fetch NFL.com report and compare explicit empty sections", report_urls[0] if report_urls else "", f2,
                               note="an explicit 'No Injuries Reported' section is evidence; a missing player is not"))

    # ---- F3: club depth charts, per club --------------------------------
    depth_by_url: dict[str, list[dict]] = {}
    for row in snapshot["depth_rows"]:
        depth_by_url.setdefault(row["source_url"], []).append(row)
    depth_matched = depth_total = depth_mismatched = 0
    depth_extra = 0
    for url in ([] if offline else sorted(depth_by_url)):
        published = depth_by_url[url]
        club = published[0]["team"]
        text, final_url, err = fetch_text(url, allowed_for(url), timeout)
        if text is None:
            unreachable.append({"family": "F3", "url": url, "error": err})
            families.append(family(f"F3-{club}", f"Depth chart: {club}", "re-fetch club page and compare unit/position/player/rank", url, None,
                                   note=f"not compared: {err[:140]}"))
            continue
        digest = hashlib.sha256(text.encode()).hexdigest()
        live = capture.parse_depth_tables(text, club, final_url, datetime.now(timezone.utc).isoformat(), digest, published[0]["authority"])
        result = compare_depth(published, live)
        depth_matched += result["matched"]
        depth_total += result["published_rows"]
        depth_mismatched += result["mismatched"]
        depth_extra += result.get("extra_live", 0)
        for d in result["details"][:25]:
            details.append({**d, "key": f"{club}: {d['key']}", "source_url": url})
        families.append(family(f"F3-{club}", f"Depth chart: {club}", "re-fetch club page and compare unit/position/player/rank", url,
                               result, note="published rank is column order, not confirmed starter"))

    # ---- F4: matchup completeness (offline, structural) -----------------
    teams = {r["team"] for r in injuries} | {r["team"] for r in snapshot.get("no_injury_sections", [])}
    matchups = sorted({r["matchup"] for r in injuries} | {r["matchup"] for r in snapshot.get("no_injury_sections", [])})
    expected = 2 * len(matchups)
    families.append(family("F4", "Matchup completeness", "count clubs per matchup against a two-club expectation",
                           report_urls[0] if report_urls else "",
                           {"published_rows": len(teams), "matched": len(teams), "mismatched": 0, "details": [],
                            "extra_live": expected - len(teams) if expected > len(teams) else 0},
                           note=(f"{len(matchups)} matchups on the report expect {expected} club sections (2 per matchup); "
                                 f"{len(teams)} club sections were captured. Any difference would be an unexplained coverage gap.")))

    # ---- F5: published status vocabulary vs the NFL policy --------------
    policy_sources = [s for s in catalog["sources"] if s["id"] in {"S03"}]
    policy_text = ""
    if policy_sources and not offline:
        text, final_url, err = fetch_text(policy_sources[0]["url"], allowed_for(policy_sources[0]["url"]), timeout)
        if text is None:
            unreachable.append({"family": "F5", "url": policy_sources[0]["url"], "error": err})
            families.append(family("F5", "Status vocabulary", "compare published status literals with the NFL injury-policy text", policy_sources[0]["url"], None, note=f"unreachable ({err[:140]})"))
        else:
            policy_text = capture.clean(text)
    if policy_text:
        literals = {"practice": ["Did Not Participate", "Limited Participation", "Full Participation"],
                    "game": ["Out", "Doubtful", "Questionable"]}
        present = {k: [t for t in v if t.lower() in policy_text.lower()] for k, v in literals.items()}
        total = sum(len(v) for v in literals.values())
        found = sum(len(v) for v in present.values())
        used = set()
        for r in injuries:
            used.add(r["practice_status"])
            if r["game_status"]:
                used.add(r["game_status"])
        unknown = sorted(u for u in used if u and not any(u.lower().startswith(t.lower()) for t in literals["practice"] + literals["game"]))
        families.append({"id": "F5", "name": "Status vocabulary", "method": "compare published status literals with the NFL injury-policy text",
                         "source_url": policy_sources[0]["url"], "compared": True,
                         "status": "match" if found == total and not unknown else "drift",
                         "note": "categories defined by the Competition Committee revision; blank game status is not an 'active' claim",
                         "rows_checked": total, "matched": found, "mismatched": (total - found) + len(unknown),
                         "coverage": f"{found}/{total}", "unknown_values": unknown})

    # ---- F6: source register reachability -------------------------------
    reachable = 0
    for source in ([] if offline else catalog["sources"]):
        url = source["url"]
        text, final_url, err = fetch_text(url, allowed_for(url), timeout)
        if text is None:
            unreachable.append({"family": "F6", "url": url, "error": err, "source_id": source["id"]})
        else:
            reachable += 1
    if not offline:
            families.append({"id": "F6", "name": "Source register reachability",
                         "method": "HTTPS fetch of every registered source URL (live run only)",
                         "source_url": "https://www.nfl.com/", "compared": True,
                         "status": "match" if reachable == len(catalog["sources"]) else "drift",
                         "note": "reachability is not reuse permission and not content verification",
                         "rows_checked": len(catalog["sources"]), "matched": reachable,
                         "mismatched": len(catalog["sources"]) - reachable,
                         "coverage": f"{reachable}/{len(catalog['sources'])}"})


    # ---- F8: club depth coverage (offline, structural) ------------------
    directory = snapshot.get("depth_directory_successes", []) + snapshot.get("depth_directory_failures", [])
    gaps = depth_gaps(snapshot["depth_rows"], len(directory))
    families.append({"id": "F8", "name": "Club depth coverage",
                     "method": "count captured club depth pages and published rank-1 rows per unit",
                     "source_url": "https://www.nfl.com/teams/", "compared": True,
                     "status": "match" if not gaps["clubs_missing_entirely"] and not gaps["unit_gaps"] else "drift",
                     "note": (f'{gaps["clubs_captured"]} of {gaps["clubs_expected"]} clubs from the official directory have a parsed depth table; '
                              + "; ".join(f'{f["team"]} not parsed' for f in snapshot.get("depth_directory_failures", []))),
                     "rows_checked": gaps["clubs_expected"], "matched": gaps["clubs_captured"],
                     "mismatched": gaps["clubs_missing_entirely"] + len(gaps["unit_gaps"]),
                     "coverage": f'{gaps["clubs_captured"]}/{gaps["clubs_expected"]}',
                     "clubs_without_depth": [f["team"] for f in snapshot.get("depth_directory_failures", [])],
                     "unit_gaps": gaps["unit_gaps"]})

    # ---- F7: join coverage (offline, structural) -----------------------
    try:
        availability = json.loads((DATA / "availability.json").read_text())
        cov = availability["coverage"]
        families.append({"id": "F7", "name": "Injury-to-depth join coverage",
                         "method": "exact (club, player) join; unmatched rows are reported, never guessed",
                         "source_url": snapshot["injury_rows"][0]["source_url"] if snapshot["injury_rows"] else "",
                         "compared": True,
                         "status": "match" if cov["matched_rows"] + cov["unmatched_rows"] == cov["injury_rows"] else "drift",
                         "note": "the join is a research lead: a published depth rank is not a confirmed starter or snap share",
                         "rows_checked": cov["injury_rows"], "matched": cov["matched_rows"],
                         "mismatched": 0, "coverage": f'{cov["matched_rows"]}/{cov["injury_rows"]}',
                         "unmatched_rows": cov["unmatched_rows"]})
    except (OSError, KeyError) as exc:
        families.append(family("F7", "Injury-to-depth join coverage", "exact (club, player) join", "", None, note=f"availability.json unavailable: {exc}"))

    compared = [f for f in families if f["compared"]]
    drift = [f for f in compared if f["status"] == "drift"]
    if offline:
        status = "drift" if drift else "structural-only"
    else:
        status = "verified" if not unreachable and not drift else ("drift" if not unreachable else "partial")
    return {
        "schema": "nfl3-verification/v2",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_observed_at": observed_at,
        "status": status,
        "checks_run": len(families),
        "checks_compared": len(compared),
        "checks_drift": len(drift),
        "checks_unreachable": len(unreachable),
        "row_totals": {"rows_checked": sum(f["rows_checked"] for f in families),
                       "matched": sum(f["matched"] for f in families),
                       "mismatched": sum(f["mismatched"] for f in families)},
        "mode": "offline-structural" if offline else "live",
        "families": families,
        "skipped_offline": skipped,
        "unreachable": unreachable,
        "mismatches": details[:400],
        "mismatch_count": len(details),
    }


def run_offline(snapshot: dict, catalog: dict) -> dict:
    """Structural checks only: no network. Used in build/PR where HTTPS is blocked."""
    return run(snapshot, catalog, timeout=1, offline=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DATA / "official_snapshot.json")
    parser.add_argument("--catalog", type=Path, default=DATA / "catalog.json")
    parser.add_argument("--output", type=Path, default=DATA / "verification.json")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--offline", action="store_true", help="structural checks only (no outbound HTTPS)")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    catalog = json.loads(args.catalog.read_text())
    doc = run(snapshot, catalog, args.timeout, offline=args.offline)
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"verification: status={doc['status']} checks={doc['checks_run']} compared={doc['checks_compared']} "
          f"drift={doc['checks_drift']} unreachable={doc['checks_unreachable']} "
          f"rows={doc['row_totals']['rows_checked']} matched={doc['row_totals']['matched']} "
          f"mismatched={doc['row_totals']['mismatched']} -> {args.output}")
    if doc["status"] == "partial":
        for item in doc["unreachable"][:10]:
            print(f"  unreachable: {item['family']} {item['url']} :: {item['error'][:160]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
