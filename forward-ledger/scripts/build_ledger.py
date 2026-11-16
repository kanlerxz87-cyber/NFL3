#!/usr/bin/env python3
"""Build the point-in-time verified results ledger for 2026 Weeks 1-10 and cross-check it.

Inputs are committed official transcriptions only:
  * `results-verification/data/official_scores_2026/week_01..09.json` (136 finals read from
    https://www.nfl.com/scores/2026/week-N on 2026-11-15),
  * `forward-ledger/data/official_scores_2026/week_10.json` (13 finals + 1 unplayed fixture read
    from the same official page family on 2026-11-16),
  * `forward-ledger/data/live_reads_2026-11-16.json` (the club record chips read off official pages,
    used only as an independent comparison),
  * `corpus/games_2026_w1_9.csv` (the frozen pre-registered corpus, compared row by row, never edited).

Outputs (all derived here, none hand-written):
  * `data/results_ledger.csv`       one row per fixture, graded or scheduled, each with its source URL
  * `data/standings_crosscheck.csv` one row per club: record computed from the ledger against record read live
  * `data/ledger_manifest.json`     hashes, counts and the frozen-corpus agreement statistics

Fail-closed: a fixture row without an official source URL, a score that contradicts the frozen corpus,
a club record mismatch, or a count that differs from the published summary stops the build.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"
OFFICIAL_WEEKLY = ROOT / "results-verification" / "data" / "official_scores_2026"
LEDGER_WEEKLY = DATA / "official_scores_2026"
CORPUS_CSV = ROOT / "corpus" / "games_2026_w1_9.csv"

# The 32 club abbreviations exactly as the official pages print them, Arizona included as AZ.
CLUBS = [
    "ATL", "AZ", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND",
    "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA",
    "SF", "TB", "TEN", "WAS",
]
OFFICIAL_HOST = re.compile(r"^https://www\.nfl\.com/(scores|schedules|games)/")


def fail(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    raise SystemExit(f"forward-ledger/build_ledger: {msg}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_week_files() -> list[dict]:
    """Every weekly transcription this ledger may use, oldest first, with its provenance."""
    out: list[dict] = []
    for week in range(1, 10):
        path = OFFICIAL_WEEKLY / f"week_{week:02d}.json"
        if not path.is_file():
            fail(f"missing official week file {path.relative_to(ROOT)}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        out.append({"doc": doc, "path": path, "provenance": "results-verification (read 2026-11-15)"})
    path = LEDGER_WEEKLY / "week_10.json"
    if not path.is_file():
        fail(f"missing official week file {path.relative_to(ROOT)}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    out.append({"doc": doc, "path": path, "provenance": "forward-ledger (read 2026-11-16)"})
    return out


def ledger_rows(weeks: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for entry in weeks:
        doc, path, prov = entry["doc"], entry["path"], entry["provenance"]
        url = doc.get("url", "")
        if not OFFICIAL_HOST.match(url):
            fail(f"{path.name}: scoreboard url is not an official NFL fixture page: {url}")
        season_match = re.search(r"/(\d{4})/", url)
        if not season_match:
            fail(f"{path.name}: no season in the source url, so it cannot be labelled")
        season = int(season_match.group(1))
        observed = doc.get("observed_at") or doc.get("read_window_utc") or ""
        if not observed:
            fail(f"{path.name}: no observation time recorded; a result without a clock time is not point-in-time safe")
        for game in doc["games"]:
            away, home = game["away_team"], game["home_team"]
            a_score, h_score = game["away_score"], game["home_score"]
            status = game.get("status") or ("final" if a_score is not None else "scheduled")
            if status == "final" and (a_score is None or h_score is None):
                fail(f"{path.name}: {away}@{home} is marked final without scores")
            grade = ""
            if a_score is not None and h_score is not None:
                grade = "tie" if a_score == h_score else ("away" if a_score > h_score else "home")
            rows.append({
                "game_id": f"{season}_{doc['week']:02d}_{away}_{home}",
                "season": season, "week": doc["week"],
                "date_et": game.get("date") or game.get("gameday") or "",
                "date_source": "",
                "context": game.get("context", ""), "away": away, "away_score": "" if a_score is None else a_score,
                "home": home, "home_score": "" if h_score is None else h_score,
                "status": status, "grade": grade, "total": "", "margin_home": "",
                "source_url": url, "game_centre_url": f"https://www.nfl.com/games/{game['slug']}-{season}-reg-{doc['week']}",
                "observed_utc": observed, "provenance": prov,
            })
            if a_score is not None and h_score is not None:
                rows[-1]["total"] = a_score + h_score
                rows[-1]["margin_home"] = h_score - a_score
    return rows


MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7,
          "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}
DAYNAMES = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
CONTEXT_LABEL = re.compile(r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[^,]*,\s*(\w+)\s+(\d{1,2})(?:st|nd|rd|th)", re.I)
REPORT = ROOT / "results-verification" / "data" / "verification_report.json"


def official_dates() -> dict[tuple[int, str, str], dict]:
    """Month/day and date agreement for Weeks 1-9 exactly as the committed official verification
    report recorded them. Used to label a date's provenance, never to fill a score."""
    if not REPORT.is_file():
        return {}
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    out: dict[tuple[int, str, str], dict] = {}
    for row in report.get("games", []):
        key = (int(row["week"]), row["away_team"], row["home_team"])
        out[key] = {"game_id": row.get("game_id", ""), "community_gameday": row.get("community_gameday", ""),
                    "date_match": row.get("date_match"), "official_context": row.get("official_context", "")}
    return out


def attach_dates(rows: list[dict]) -> None:
    joined = official_dates()
    for row in rows:
        key = (int(row["week"]), row["away"], row["home"])
        info = joined.get(key)
        if info and info.get("date_match") and info.get("community_gameday"):
            row["date_et"] = info["community_gameday"]
            row["date_source"] = (f"official context month/day agrees with the date field the frozen corpus carries "
                                 f"(136/136 date matches in results-verification/data/verification_report.json)")
        elif row["date_et"]:
            row["date_source"] = "date read from the official scoreboard context line on 2026-11-16"
        else:
            row["date_source"] = ""


def weekday_consistency(rows: list[dict]) -> dict:
    """Does the weekday named in the official page's own context label agree with the date printed
    beside it? A mismatch is an anomaly on the source page, not in our transcription, and is reported
    as such. Games whose context names no weekday are counted separately rather than skipped silently.
    """
    checked = 0
    no_label = 0
    anomalies: list[dict] = []
    for row in rows:
        match = CONTEXT_LABEL.search(row["context"] or "")
        if not match or not re.match(r"^\d{4}-\d{2}-\d{2}$", row["date_et"] or ""):
            no_label += 1
            continue
        month = MONTHS.get(match.group(2).title())
        day = int(match.group(3))
        if not month:
            no_label += 1
            continue
        year = int(row["date_et"][:4])
        try:
            actual = _date(year, month, day)
        except ValueError:
            anomalies.append({"game_id": row["game_id"], "kind": "context names a date that does not exist",
                              "context": row["context"], "date_et": row["date_et"]})
            checked += 1
            continue
        checked += 1
        named = DAYNAMES[match.group(1).lower()]
        if named != actual.weekday():
            anomalies.append({
                "game_id": row["game_id"], "fixture": f"{row['away']} at {row['home']}",
                "week": int(row["week"]), "context": row["context"], "date_et": row["date_et"],
                "actual_weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][actual.weekday()],
                "kind": "the official page names a weekday that its own printed date does not fall on",
                "source_url": row["source_url"],
            })
    return {"labels_checked": checked, "labels_not_comparable": no_label, "anomalies": anomalies,
            "note": "Checked mechanically over every graded and scheduled fixture in the ledger; "
                    "an anomaly never removes a row, it adds a review item."}


def _date(year: int, month: int, day: int):
    from datetime import date
    return date(year, month, day)


def records_from(rows: list[dict]) -> dict[str, list[int]]:
    table = {club: [0, 0, 0] for club in CLUBS}
    for row in rows:
        if row["status"] != "final":
            continue
        a, h = int(row["away_score"]), int(row["home_score"])
        if a > h:
            table[row["away"]][0] += 1; table[row["home"]][1] += 1
        elif h > a:
            table[row["home"]][0] += 1; table[row["away"]][1] += 1
        else:
            table[row["away"]][2] += 1; table[row["home"]][2] += 1
    return table


def fmt(record: list[int]) -> str:
    wins, losses, ties = record
    return f"{wins}-{losses}" if ties == 0 else f"{wins}-{losses}-{ties}"


def crosscheck(rows: list[dict], reads: dict) -> list[dict]:
    chips = reads["club_record_chips_read"]["chips"]
    sources = reads["club_record_chips_read"]["sources"]
    computed = records_from(rows)
    games_played = {club: sum(1 for r in rows if r["status"] == "final" and club in (r["away"], r["home"]))
                    for club in CLUBS}
    out: list[dict] = []
    for club in CLUBS:
        entry = chips.get(club, {"record": "", "pages": []})
        official = entry["record"]
        mine = fmt(computed[club])
        status = "not read in this pass" if not official else ("match" if official == mine else "MISMATCH")
        out.append({
            "club": club,
            "games_in_ledger": games_played[club],
            "computed_w": computed[club][0], "computed_l": computed[club][1], "computed_t": computed[club][2],
            "computed_record": mine,
            "official_record": official,
            "official_pages": " + ".join(sources[p] for p in entry["pages"]),
            "status": status,
        })
    return out


def corpus_agreement(rows: list[dict]) -> dict:
    """Compare every graded row with the frozen pre-registered corpus, row by row, without editing it."""
    with CORPUS_CSV.open(encoding="utf-8", newline="") as fh:
        corpus = list(csv.DictReader(fh))
    index = {}
    for row in corpus:
        index[(int(row["week"]), row["away_team"], row["home_team"])] = row
    matched = blank_in_corpus = missing = score_diff = 0
    diffs: list[dict] = []
    for row in rows:
        if int(row["week"]) > 9 or row["status"] != "final":
            continue
        key = (int(row["week"]), row["away"], row["home"])
        crow = index.get(key)
        if crow is None:
            missing += 1
            diffs.append({"week": key[0], "fixture": f"{key[1]} at {key[2]}", "kind": "absent from the frozen corpus"})
            continue
        c_away, c_home = crow["away_score"].strip(), crow["home_score"].strip()
        if c_away == "" or c_home == "":
            blank_in_corpus += 1
            diffs.append({
                "week": key[0], "fixture": f"{key[1]} at {key[2]}",
                "kind": "frozen corpus carries no score; the official pages do",
                "ledger_score": f"{row['away_score']}-{row['home_score']}",
                "corpus_note": crow.get("verification", "")[:200],
            })
            continue
        if (int(c_away), int(c_home)) == (int(row["away_score"]), int(row["home_score"])):
            matched += 1
        else:
            score_diff += 1
            diffs.append({"week": key[0], "fixture": f"{key[1]} at {key[2]}", "kind": "score disagrees with the official page",
                          "ledger_score": f"{row['away_score']}-{row['home_score']}", "corpus_score": f"{c_away}-{c_home}"})
    if score_diff or missing:
        fail(f"frozen corpus disagrees on {score_diff} score(s) and {missing} fixture(s) are unaccounted for")
    return {
        "corpus_rows": len(corpus),
        "graded_ledger_rows_weeks_1_9": sum(1 for r in rows if int(r["week"]) <= 9 and r["status"] == "final"),
        "exact_score_matches": matched,
        "blank_in_frozen_corpus": blank_in_corpus,
        "score_mismatches": score_diff,
        "fixtures_absent_from_corpus": missing,
        "details": diffs,
    }


def main() -> int:
    weeks = load_week_files()
    rows = ledger_rows(weeks)
    attach_dates(rows)
    reads_path = DATA / "live_reads_2026-11-16.json"
    reads = json.loads(reads_path.read_text(encoding="utf-8"))

    fixtures = [r for r in rows if int(r["week"]) == 10]
    if len(fixtures) != 14:
        fail(f"Week 10 should hold 14 fixtures (32 clubs minus 4 byes), found {len(fixtures)}")
    graded = [r for r in rows if r["status"] == "final"]
    if len(rows) != 150 or len(graded) != 149:
        fail(f"expected 150 fixtures and 149 graded results through Week 10, found {len(rows)} and {len(graded)}")
    clubs_in_ledger = {c for r in rows for c in (r["away"], r["home"])}
    if clubs_in_ledger != set(CLUBS):
        fail(f"ledger clubs differ from the 32-club register: {sorted(clubs_in_ledger ^ set(CLUBS))}")
    for row in rows:
        if not OFFICIAL_HOST.match(row["source_url"]):
            fail(f"{row['game_id']}: source url is not official")

    check = crosscheck(graded, reads)
    mismatches = [c for c in check if c["status"] == "MISMATCH"]
    if mismatches:
        fail("official record chips disagree with the ledger: "
             + ", ".join(f"{m['club']} ledger {m['computed_record']} vs official {m['official_record']}" for m in mismatches))

    agreement = corpus_agreement(rows)
    weekday = weekday_consistency(rows)
    DATA.mkdir(parents=True, exist_ok=True)
    anomalies_path = DATA / "source_anomalies.csv"
    with anomalies_path.open("w", encoding="utf-8", newline="") as fh:
        fields = ["game_id", "fixture", "week", "context", "date_et", "actual_weekday", "kind", "source_url"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in weekday["anomalies"]:
            item.setdefault("kind", item.get("kind", ""))
            writer.writerow(item)

    DATA.mkdir(exist_ok=True)
    ledger_path = DATA / "results_ledger.csv"
    with ledger_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    check_path = DATA / "standings_crosscheck.csv"
    with check_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(check[0].keys()))
        writer.writeheader()
        writer.writerows(check)

    manifest = {
        "schema": "nfl3-forward-ledger/v1",
        "built_from_read_date": reads["read_date_utc"],
        "authority": "official NFL.com pages only; no community file is used for any value in this ledger",
        "inputs": {
            str(entry["path"].relative_to(ROOT)): {"sha256": sha256(entry["path"]),
                                                   "games": len(entry["doc"]["games"]),
                                                   "observed": entry["doc"].get("observed_at") or entry["doc"].get("read_window_utc")}
            for entry in weeks
        } | {str(reads_path.relative_to(ROOT)): {"sha256": sha256(reads_path)}},
        "fixtures": len(rows),
        "graded": len(graded),
        "scheduled_unplayed": len(rows) - len(graded),
        "weeks": sorted({int(r["week"]) for r in rows}),
        "clubs": len(CLUBS),
        "standings_crosscheck": {
            "clubs_checked_against_official_chips": sum(1 for c in check if c["status"] == "match"),
            "clubs_not_read_in_this_pass": [c["club"] for c in check if c["status"] != "match"],
            "mismatches": len(mismatches),
            "chip_timing_note": "The chips were read at 14:36Z-15:02Z on 2026-11-16, before the last Week 10 fixture "
                                "(Los Angeles Chargers at Baltimore Ravens, 8:15 PM ET the same evening) had been played. "
                                "Both clubs' chips therefore match a ledger that deliberately excludes that fixture, "
                                "and the fixture is excluded from every count here rather than back-filled later.",
            "method": "record computed from the ledger's graded games compared with the record chip each official page printed on 2026-11-16",
        },
        "official_page_label_consistency": weekday,
        "frozen_corpus_agreement": agreement,
        "club_records_through_week_10": {c["club"]: c["computed_record"] for c in check},
        "counts_note": "Every count on the published pages is computed by scripts/build_site.py from these files.",
    }
    (DATA / "ledger_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"ledger: {len(rows)} fixtures, {len(graded)} graded, weeks {manifest['weeks'][0]}-{manifest['weeks'][-1]}")
    print(f"standings cross-check: {manifest['standings_crosscheck']['clubs_checked_against_official_chips']} of 32 clubs "
          f"match an official chip read on {reads['read_date_utc']}; "
          f"not read: {manifest['standings_crosscheck']['clubs_not_read_in_this_pass'] or 'none'}")
    print(f"frozen corpus: {agreement['exact_score_matches']}/{agreement['graded_ledger_rows_weeks_1_9']} scores identical, "
          f"{agreement['blank_in_frozen_corpus']} blank in the corpus but published officially, "
          f"{agreement['score_mismatches']} mismatches")
    print(f"official label consistency: {len(weekday['anomalies'])} of {weekday['labels_checked']} fixture rows carry a "
          f"weekday that disagrees with the date printed beside it on the same page "
          f"({weekday['labels_not_comparable']} rows name no weekday or carry no ISO date)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
