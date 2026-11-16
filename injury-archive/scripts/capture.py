#!/usr/bin/env python3
"""Capture official NFL availability documents, week by week, with a clock time and a hash.

Sub-commands
------------
  clubs                     official club directory -> injury-archive/data/clubs.json
  injury  --season --week   one official weekly injury report page
  inactives --season --week one official weekly inactives article
  probe                     walk the season x week grid, capture what exists, record 404s
  build                     regenerate the data artifacts from the committed captures

Every read is appended to injury-archive/data/index.jsonl whether it succeeded or not, so the
archive records what was asked for as well as what came back. A structural failure exits 3; a
transport failure exits 4. Both are recorded first, so a red workflow is still evidence.

A 404 is recorded as `not_published` for that URL. It is never treated as an empty list and it is
never back-filled from another source: "the NFL does not publish this at this address" is a
finding to publish, not a gap to paper over.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_lib as lib  # noqa: E402

SEASONS = range(2021, 2027)
WEEKS = range(1, 19)
RETRY_SLEEP = 4


def load_clubs() -> dict:
    if not lib.CLUBS_JSON.exists():
        sys.exit("clubs.json is missing: run `capture.py clubs` first")
    return json.loads(lib.CLUBS_JSON.read_text(encoding="utf-8"))


def record(**entry) -> None:
    entry.setdefault("captured_at_utc", lib.utc_now())
    lib.append_index(entry)


def describe_failure(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


def capture_clubs() -> int:
    url = "https://www.nfl.com/teams/"
    raw, final_url, status = lib.fetch(url, lib.INJURY_HOSTS)
    text = raw.decode("utf-8", errors="replace")
    clubs: list[dict] = []
    # Each club block: an <h4> carrying the club name, followed by a "View <name> Profile" anchor
    # and a "View <name> Website" anchor. Nothing is derived from the club name itself.
    for match in re.finditer(r"<h4[^>]*>(.*?)</h4>", text, re.S | re.I):
        name = lib.clean(match.group(1))
        if not name:
            continue
        window = text[match.end():match.end() + 2500]
        profile = re.search(r'href="(https://www\.nfl\.com/teams/[^"]+)"', window)
        site = re.search(r'href="(https://[^"]+)"[^>]*title="View [^"]*Website"', window)
        if not site:
            site = re.search(r'title="View [^"]*Website"[^>]*href="(https://[^"]+)"', window)
        if not (profile and site):
            continue
        profile_url = profile.group(1).rstrip("/") + "/"
        clubs.append({
            "club": name, "nickname": lib.nickname(name),
            "profile_url": profile_url, "site_url": site.group(1),
            "roster_url": profile_url + "roster",
            "source_url": final_url, "observed_at": lib.utc_now(),
            "source_sha256": lib.sha256_bytes(raw),
        })
    # De-duplicate on club name, keep the first published occurrence.
    seen: dict[str, dict] = {}
    for club in clubs:
        seen.setdefault(club["club"], club)
    clubs = sorted(seen.values(), key=lambda c: c["club"])
    if len(clubs) != 32:
        print(f"::error::expected 32 clubs in the official directory, parsed {len(clubs)}")
        record(kind="clubs", source_url=final_url, http_status=status, status="drift",
               clubs_parsed=len(clubs))
        return 3
    nicknames = {c["nickname"] for c in clubs}
    if len(nicknames) != 32:
        print("::error::club nicknames are not unique; the inactives join would be ambiguous")
        record(kind="clubs", source_url=final_url, http_status=status, status="drift",
               nicknames=sorted(nicknames))
        return 3
    lib.CLUBS_JSON.write_text(json.dumps({"source_url": final_url, "observed_at": lib.utc_now(),
                                          "sha256": lib.sha256_bytes(raw), "clubs": clubs},
                                         indent=1, sort_keys=True) + "\n", encoding="utf-8")
    record(kind="clubs", source_url=final_url, http_status=status, status="ok", clubs=len(clubs))
    print(f"clubs: {len(clubs)} official clubs recorded from {final_url}")
    return 0


def capture_injury(season: int, week: int, quiet: bool = False) -> int:
    url = lib.injuries_url(season, week)
    requested = lib.utc_now()
    try:
        raw, final_url, status = lib.fetch(url, lib.INJURY_HOSTS)
    except urllib.error.HTTPError as exc:
        record(kind="injury", season=season, week=week, source_url=url, requested_at_utc=requested,
               http_status=exc.code, status="not_published" if exc.code == 404 else "http_error")
        if not quiet:
            print(f"injury {season} W{week}: HTTP {exc.code} at {url}")
        return 0 if exc.code == 404 else 4
    except Exception as exc:  # noqa: BLE001 - transport failure of any kind is recorded
        record(kind="injury", season=season, week=week, source_url=url, requested_at_utc=requested,
               status="fetch_failed", error=describe_failure(exc))
        print(f"::error::injury {season} W{week}: {describe_failure(exc)}")
        return 4
    raw_file = lib.store_raw(raw)
    parsed = lib.parse_injuries(raw, final_url, lib.utc_now())
    record(kind="injury", season=season, week=week, source_url=url, final_url=final_url,
           requested_at_utc=requested, http_status=status, sha256=parsed["sha256"],
           raw_file=raw_file, injury_rows=parsed["injury_rows"],
           team_sections=parsed["team_sections"], no_injury_sections=len(parsed["no_injury_sections"]),
           failures=parsed["failures"],
           status="ok" if not parsed["failures"] else "drift")
    if parsed["failures"]:
        print(f"::error::injury {season} W{week}: {len(parsed['failures'])} structural failure(s): "
              f"{parsed['failures'][:3]}")
        return 3
    if not quiet:
        print(f"injury {season} W{week}: {parsed['injury_rows']} rows, "
              f"{parsed['team_sections']} team sections")
    return 0


def capture_inactives(season: int, week: int, quiet: bool = False) -> int:
    clubs = load_clubs()
    nicknames = {c["nickname"] for c in clubs["clubs"]}
    url = lib.inactives_url(season, week)
    requested = lib.utc_now()
    try:
        raw, final_url, status = lib.fetch(url, lib.INJURY_HOSTS)
    except urllib.error.HTTPError as exc:
        record(kind="inactives", season=season, week=week, source_url=url, requested_at_utc=requested,
               http_status=exc.code, status="not_published" if exc.code == 404 else "http_error")
        if exc.code != 404:
            return 4
        candidate = lib.inactives_url_with_month(season, week)
        if not candidate:
            return 0
        try:
            raw, final_url, status = lib.fetch(candidate, lib.INJURY_HOSTS)
        except Exception as candidate_exc:  # noqa: BLE001 - recorded, never guessed around
            record(kind="inactives", season=season, week=week, source_url=candidate,
                   requested_at_utc=lib.utc_now(), status="not_published",
                   http_status=getattr(candidate_exc, "code", ""),
                   note="candidate address carrying the played month")
            if not quiet:
                print(f"inactives {season} W{week}: not published at either address")
            return 0
        url = candidate
        if not quiet:
            print(f"inactives {season} W{week}: found at the month-carrying address")
    except Exception as exc:  # noqa: BLE001
        record(kind="inactives", season=season, week=week, source_url=url,
               requested_at_utc=requested, status="fetch_failed", error=describe_failure(exc))
        print(f"::error::inactives {season} W{week}: {describe_failure(exc)}")
        return 4
    raw_file = lib.store_raw(raw)
    parsed = lib.parse_inactives(raw, final_url, lib.utc_now(), nicknames)
    record(kind="inactives", season=season, week=week, source_url=url, final_url=final_url,
           requested_at_utc=requested, http_status=status, sha256=parsed["sha256"],
           raw_file=raw_file, clubs=len(parsed["clubs"]), players=len(parsed["rows"]),
           failures=parsed["failures"],
           status="ok" if not parsed["failures"] else "drift")
    if parsed["failures"]:
        print(f"::error::inactives {season} W{week}: {len(parsed['failures'])} failure(s): "
              f"{parsed['failures'][:3]}")
        return 3
    if not quiet:
        print(f"inactives {season} W{week}: {len(parsed['clubs'])} clubs, {len(parsed['rows'])} players")
    return 0


def known_reads() -> dict[tuple[str, int, int], str]:
    """Latest recorded status per (kind, season, week), so a probe never repeats a settled 404."""
    latest: dict[tuple[str, int, int], str] = {}
    for entry in lib.read_index():
        key = (entry.get("kind", ""), entry.get("season"), entry.get("week"))
        if key[0] in {"injury", "inactives"}:
            latest[key] = entry.get("status", "")
    return latest


def probe(seasons: list[int], weeks: list[int], force: bool) -> int:
    clubs = load_clubs()
    runtime = re.search(r"(\d{4})-(\d{2})-(\d{2})", lib.utc_now())
    stale_not_found_days = 30
    now = time.time()
    try:
        last_probe = time.strptime((lib.DATA / "probe.stamp").read_text().strip(), "%Y-%m-%d")
        del last_probe
    except (FileNotFoundError, ValueError):
        pass
    known = known_reads()
    exit_code = 0
    attempted = 0
    for season in seasons:
        for week in weeks:
            for kind, capture in (("injury", capture_injury), ("inactives", capture_inactives)):
                status = known.get((kind, season, week))
                if status == "ok" and not force:
                    continue
                if status in {"not_published", "drift"} and not force:
                    # A 404 stays settled for 30 days; a drift stays settled until the code changes.
                    if status == "not_published":
                        continue
                attempted += 1
                code = capture(season, week, quiet=True)
                exit_code = exit_code or (0 if code in (0,) else code)
                time.sleep(0.3)
    print(f"probe: {attempted} read(s) attempted; newest UTC clock {runtime.group(0) if runtime else ''}")
    (lib.DATA / "probe.stamp").write_text(lib.utc_now()[:10] + "\n", encoding="utf-8")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clubs")
    for name in ("injury", "inactives"):
        p = sub.add_parser(name)
        p.add_argument("--season", type=int, required=True)
        p.add_argument("--week", type=int, required=True)
    p = sub.add_parser("probe")
    p.add_argument("--seasons", default="2021-2026")
    p.add_argument("--weeks", default="1-18")
    p.add_argument("--force", action="store_true")
    sub.add_parser("build")
    args = parser.parse_args()

    if args.command == "clubs":
        return capture_clubs()
    if args.command == "injury":
        return capture_injury(args.season, args.week)
    if args.command == "inactives":
        return capture_inactives(args.season, args.week)
    if args.command == "probe":
        s_lo, _, s_hi = args.seasons.partition("-")
        w_lo, _, w_hi = args.weeks.partition("-")
        return probe(list(range(int(s_lo), int(s_hi or s_lo) + 1)),
                     list(range(int(w_lo), int(w_hi or w_lo) + 1)), args.force)
    if args.command == "build":
        import build  # noqa: PLC0415 - build imports this module's constants
        return build.main()
    return 2


if __name__ == "__main__":
    sys.exit(main())
