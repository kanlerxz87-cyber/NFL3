#!/usr/bin/env python3
"""Capture and normalize public NFL/club source pages.

Authority boundary: this script verifies that bytes came from an official HTTPS
host and preserves published values exactly. It does not infer health, depth,
workload, replacement assignment or market probabilities. Blank cells stay blank.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UA = "NFL3-OfficialSourceAudit/1.0 (+https://github.com/kanlerxz87-cyber/NFL3)"
SOURCES = {
    "nfl-injuries": ("https://www.nfl.com/injuries/", {"www.nfl.com"}),
    "nfl-teams": ("https://www.nfl.com/teams/", {"www.nfl.com"}),
    "commanders-depth": ("https://www.commanders.com/team/depth-chart", {"www.commanders.com"}),
    "giants-depth": ("https://www.giants.com/team/depth-chart", {"www.giants.com"}),
    "colts-depth": ("https://www.colts.com/news/colts-release-unofficial-depth-chart-for-week-10", {"www.colts.com"}),
}
TAG = re.compile(r"<[^>]+>")
TOKEN = re.compile(
    r'<h2 class="d3-o-section-title">(?P<day>.*?)</h2>'
    r'|<span class="nfl-c-matchup-strip__team-abbreviation">\s*(?P<abbr>[A-Z]+)\s*</span>'
    r'|<div class="d3-o-section-sub-title"><span>(?P<team>.*?)</span></div>'
    r'|<p class="nfl-o-no-results__text">(?P<no_results>.*?)</p>'
    r'|<table(?P<table_attrs>[^>]*)>(?P<table>.*?)</table>',
    re.S,
)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t([dh])[^>]*>(.*?)</t\1>", re.S)
HREF = re.compile(r'href="([^"]+)"')


def clean(fragment: str) -> str:
    return html.unescape(TAG.sub("", fragment)).strip()


def fetch(url: str, allowed_hosts: set[str], timeout: int = 45) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme != "https" or urlparse(final_url).hostname not in allowed_hosts:
            raise ValueError(f"Unexpected official-source redirect: {final_url}")
        raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise ValueError(f"Source exceeds capture limit: {url}")
    return raw, final_url


def parse_injuries(raw: str, source_url: str, observed_at: str, digest: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    no_results: list[dict] = []
    day = ""
    team = ""
    matchup: list[str] = []
    for match in TOKEN.finditer(raw):
        if match.group("day") is not None:
            day = clean(match.group("day"))
            matchup = []
        elif match.group("abbr") is not None:
            if len(matchup) >= 2:
                matchup = []
            matchup.append(match.group("abbr"))
        elif match.group("team") is not None:
            team = clean(match.group("team"))
        elif match.group("no_results") is not None:
            text = clean(match.group("no_results"))
            if text and team:
                no_results.append({"team": team, "matchup": " @ ".join(matchup), "day": day,
                                   "text": text, "source_url": source_url, "observed_at": observed_at,
                                   "source_sha256": digest})
        elif match.group("table") is not None:
            parsed_rows = []
            headers: list[str] = []
            for row_match in ROW.finditer(match.group("table")):
                cells = CELL.findall(row_match.group(1))
                values = [clean(value) for _, value in cells]
                if not values:
                    continue
                if cells and cells[0][0] == "h":
                    headers = values
                    continue
                if headers[:2] != ["Player", "Position"]:
                    continue
                href = HREF.search(cells[0][1])
                player_url = href.group(1) if href else ""
                if player_url.startswith("/"):
                    player_url = "https://www.nfl.com" + player_url
                record = dict(zip(headers, values))
                parsed_rows.append({
                    "day": day, "matchup": " @ ".join(matchup), "team": team,
                    "player": record.get("Player", ""), "position": record.get("Position", ""),
                    "injury": record.get("Injuries", ""), "practice_status": record.get("Practice Status", ""),
                    "game_status": record.get("Game Status", ""), "player_url": player_url,
                    "source_url": source_url, "observed_at": observed_at, "source_sha256": digest,
                    "confirmed_active": "", "replacement_player": "", "replacement_rank": "", "expected_snaps": "",
                })
            if parsed_rows:
                rows.extend(parsed_rows)
    return rows, no_results


def cell_entries(inner: str) -> list[tuple[str, str]]:
    """Split one published table cell into (player name, player url) entries.

    Several official club pages put more than one player in a single published
    cell (for example Steelers TE1 lists "Pat Freiermuth" and "Darnell
    Washington" together). Concatenating the cell text would invent a player
    who does not exist, so each anchor is treated as one player. A cell with no
    anchor falls back to its full cleaned text as a single unnamed-source entry.

    Returns an empty list for a genuinely blank cell: blank stays blank.
    """
    anchors = re.findall(r"<a\b([^>]*)>(.*?)</a>", inner, re.S)
    if anchors:
        entries = []
        for attrs, body in anchors:
            name = clean(body)
            if not name:
                continue
            href = re.search(r'href="([^"]+)"', attrs)
            entries.append((name, href.group(1) if href else ""))
        if entries:
            return entries
    text = clean(inner)
    return [(text, "")] if text else []


def page_authority(raw: str, default: str = "club depth chart") -> tuple[str, str]:
    """Read the page's own wording about how authoritative its chart is.

    Some clubs publish a chart that they explicitly call *unofficial*, written by
    site writers rather than the coaching staff. That caveat changes what the
    rows can support, so it is captured instead of assumed away. The exact page
    sentence is returned so it can be published alongside the rows.

    Returns (authority label, the page's own caveat sentence or "").
    """
    text = html.unescape(TAG.sub(" ", raw))
    text = re.sub(r"\s+", " ", text)
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        low = sentence.lower()
        if "unofficial" in low and ("depth" in low or "chart" in low):
            if "not necessarily reflect" in low or "opinions" in low or "writers" in low:
                return "club-published UNOFFICIAL depth chart", sentence.strip()[:400]
            return "club-published UNOFFICIAL depth chart", sentence.strip()[:400]
    return default, ""


def parse_depth_tables(raw: str, team: str, source_url: str, observed_at: str, digest: str,
                       authority: str | None = None) -> list[dict]:
    caveat = ""
    if authority is None:
        authority, caveat = page_authority(raw)
    rows: list[dict] = []
    for table_match in re.finditer(r"<table([^>]*)>(.*?)</table>", raw, re.S):
        attrs = table_match.group(1)
        body = table_match.group(2)
        summary = re.search(r'(?:summary|caption)[^>]*>([^<]+)', attrs)
        caption = re.search(r"<caption[^>]*>(.*?)</caption>", body, re.S)
        unit = clean(caption.group(1) if caption else (summary.group(1) if summary else ""))
        if unit.lower() not in {"offense", "defense", "special teams"}:
            continue
        headers: list[str] = []
        for row_match in ROW.finditer(body):
            cells = CELL.findall(row_match.group(1))
            values = [clean(value) for _, value in cells]
            if not values:
                continue
            if cells[0][0] == "h":
                headers = values
                continue
            if not headers or headers[0].lower() != "position":
                continue
            position = values[0]
            rank = 0
            for column, cell in enumerate(cells[1:], start=1):
                for player, href in cell_entries(cell[1]):
                    rank += 1
                    player_url = href
                    if player_url.startswith("/"):
                        player_url = urlparse(source_url).scheme + "://" + urlparse(source_url).hostname + player_url
                    header = headers[column].lower() if column < len(headers) else ""
                    rows.append({
                        "team": team, "unit": unit, "position": position, "player": player,
                        "published_rank": rank, "rank_basis": "explicit tier header" if header in {"first", "second", "third", "fourth", "fifth", "sixth"} else "published column order",
                        "authority": authority, "player_url": player_url, "source_url": source_url,
                        "observed_at": observed_at, "source_sha256": digest,
                        "authority_caveat": caveat,
                        "confirmed_starter": "", "replacement_assignment": "", "expected_snaps": "",
                    })
    return rows


def parse_colts_article(raw: str, source_url: str, observed_at: str, digest: str) -> list[dict]:
    article_body = ""
    for script in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', raw, re.S):
        try:
            doc = json.loads(script.group(1))
        except json.JSONDecodeError:
            continue
        candidates = doc if isinstance(doc, list) else [doc]
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(candidate.get("articleBody"), str):
                article_body = candidate["articleBody"]
                break
        if article_body:
            break
    rows: list[dict] = []
    unit = ""
    for line in article_body.splitlines():
        line = line.strip()
        if line.upper() in {"OFFENSE", "DEFENSE", "SPECIAL TEAMS"}:
            unit = line.title()
            continue
        match = re.match(r"^([A-Z0-9+]+):\s*(.+)$", line)
        if not match or unit not in {"Offense", "Defense", "Special Teams"}:
            continue
        position, names = match.groups()
        for rank, player in enumerate((name.strip() for name in names.split(",")), start=1):
            if player:
                rows.append({"team": "Colts", "unit": unit, "position": position, "player": player,
                             "published_rank": rank, "rank_basis": "published list order",
                             "authority": "club-published UNOFFICIAL depth chart",
                             "authority_caveat": "club article headline labels the chart unofficial", "player_url": "",
                             "source_url": source_url, "observed_at": observed_at, "source_sha256": digest,
                             "confirmed_starter": "", "replacement_assignment": "", "expected_snaps": ""})
    return rows


def club_directory(raw: str) -> list[tuple[str, str]]:
    """Extract official club website links from the NFL team directory."""
    found: dict[str, str] = {}
    for match in re.finditer(r'title="View ([^"]+) Website"\s+href="(https://[^"]+)"', raw):
        name, url = match.groups()
        host = urlparse(url).hostname or ""
        if host and host not in found:
            found[host] = name.strip()
    return [(name, "https://" + host + "/") for host, name in sorted(found.items())]


def discover_depth_charts(directory_raw: str, observed_at: str, timeout: int = 25) -> tuple[list[dict], list[dict], list[dict]]:
    """Probe club depth-chart URLs listed by the official directory.

    A failed probe is recorded as missing coverage; no player values are inferred.
    """
    clubs = club_directory(directory_raw)
    rows: list[dict] = []
    successes: list[dict] = []
    failures: list[dict] = []

    def probe(club: tuple[str, str]) -> tuple[str, str, list[dict], dict | None, str]:
        name, base = club
        host = urlparse(base).hostname or ""
        allowed = {host, host.removeprefix("www."), "www." + host.removeprefix("www.")}
        errors = []
        for path in ("team/depth-chart", "team/depth-chart/"):
            url = base.rstrip("/") + "/" + path
            try:
                raw, final_url = fetch(url, allowed, timeout)
                text = raw.decode("utf-8", errors="replace")
                digest = hashlib.sha256(raw).hexdigest()
                parsed = parse_depth_tables(text, name, final_url, observed_at, digest)
                if parsed:
                    return name, url, parsed, {"team": name, "url": final_url, "sha256": digest,
                                               "observed_at": observed_at, "rows": len(parsed)}, ""
                errors.append(f"{url}: no depth table parsed")
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        return name, base, [], None, "; ".join(errors)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for name, url, parsed, manifest, error in pool.map(probe, clubs):
            if parsed:
                rows.extend(parsed)
                successes.append(manifest)
            else:
                failures.append({"team": name, "directory_url": url, "reason": error,
                                 "source_url": "https://www.nfl.com/teams/", "observed_at": observed_at})
    return rows, successes, failures


def build_snapshot(captures: dict[str, tuple[bytes, str]], observed_at: str | None = None) -> dict:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    manifest = []
    injuries: list[dict] = []
    no_results: list[dict] = []
    depth: list[dict] = []
    for name, (raw, final_url) in captures.items():
        url, _ = SOURCES[name]
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace")
        manifest.append({"id": name, "url": url, "final_url": final_url, "observed_at": observed_at,
                         "sha256": digest, "bytes": len(raw), "authority": "official HTTPS publisher"})
        if name == "nfl-injuries":
            injury_rows, empty = parse_injuries(text, final_url, observed_at, digest)
            injuries.extend(injury_rows)
            no_results.extend(empty)
        elif name == "commanders-depth":
            depth.extend(parse_depth_tables(text, "Commanders", final_url, observed_at, digest))
        elif name == "giants-depth":
            depth.extend(parse_depth_tables(text, "Giants", final_url, observed_at, digest))
        elif name == "colts-depth":
            depth.extend(parse_colts_article(text, final_url, observed_at, digest))
    return {
        "schema_version": 1, "observed_at": observed_at, "manifest": manifest,
        "injury_rows": injuries, "no_injury_sections": no_results, "depth_rows": depth,
        "coverage": {
            "injury_rows": len(injuries), "no_injury_sections": len(no_results), "depth_rows": len(depth),
            "depth_teams": sorted({row["team"] for row in depth}),
            "official_outcome_history": False, "licensed_market_history": False,
            "confirmed_replacement_assignments": False,
        },
        "rules": [
            "Blank source cells remain blank; no health, active status, workload or replacement is inferred.",
            "Published depth rank is not confirmed starter status or actual participation.",
            "A source hash proves capture integrity, not future source stability or reuse rights.",
        ],
    }


def load_captures(directory: Path) -> dict[str, tuple[bytes, str]]:
    manifest = json.loads((directory / "manifest.json").read_text())
    captures = {}
    for item in manifest:
        path = directory / (item["id"] + ".html.gz")
        captures[item["id"]] = (gzip.decompress(path.read_bytes()), item.get("final_url", item["url"]))
    return captures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-captures", type=Path, help="Parse temporary gzip captures instead of fetching")
    parser.add_argument("--output", type=Path, default=DATA / "official_snapshot.json")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--discover-depth", action="store_true", help="Probe official club depth-chart URLs from the NFL directory")
    args = parser.parse_args()
    if args.from_captures:
        captures = load_captures(args.from_captures)
        manifest = json.loads((args.from_captures / "manifest.json").read_text())
        observed_at = manifest[0]["observed_at"] if manifest else None
    else:
        captures = {}
        for name, (url, hosts) in SOURCES.items():
            try:
                captures[name] = fetch(url, hosts, args.timeout)
            except Exception as exc:
                print(f"CAPTURE FAILED {name}: {exc}", file=sys.stderr)
                return 1
        observed_at = None
    snapshot = build_snapshot(captures, observed_at)
    if args.discover_depth and "nfl-teams" in captures:
        directory_raw = captures["nfl-teams"][0].decode("utf-8", errors="replace")
        discovered, successes, failures = discover_depth_charts(directory_raw, snapshot["observed_at"], min(args.timeout, 25))
        short_names = {row["team"] for row in snapshot["injury_rows"]} | {row["team"] for row in snapshot["no_injury_sections"]} | {"Colts", "Commanders", "Giants"}
        def normalize_team(name: str) -> str:
            for short in sorted(short_names, key=len, reverse=True):
                if name == short or name.endswith(" " + short):
                    return short
            return name
        existing = {(row["team"], row["player"], row["unit"], row["position"], row["published_rank"]) for row in snapshot["depth_rows"]}
        for row in discovered:
            row["team"] = normalize_team(row["team"])
            key = (row["team"], row["player"], row["unit"], row["position"], row["published_rank"])
            if key not in existing:
                snapshot["depth_rows"].append(row)
                existing.add(key)
        snapshot["depth_directory_successes"] = successes
        snapshot["depth_directory_failures"] = failures
        snapshot["coverage"]["depth_rows"] = len(snapshot["depth_rows"])
        snapshot["coverage"]["depth_teams"] = sorted({row["team"] for row in snapshot["depth_rows"]})
        snapshot["coverage"]["depth_directory_successes"] = len(successes)
        snapshot["coverage"]["depth_directory_failures"] = len(failures)
    if not snapshot["injury_rows"] and not snapshot["no_injury_sections"]:
        print("No injury evidence parsed; refusing to replace snapshot with an empty report", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(snapshot["coverage"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
