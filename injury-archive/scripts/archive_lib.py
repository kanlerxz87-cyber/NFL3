"""Official availability archive: fetching, parsing, joining and the fail-closed rules.

Authority boundary
------------------
Every row in this module is read from a page on an official NFL host. Nothing is inferred,
estimated, transcribed or repaired:

* blank source cells stay blank;
* an unrecognised label is a structural failure that is recorded, not mapped;
* a page that does not parse produces zero rows plus a named failure — never a guess;
* the join between the injury report and the inactive list is a *name and club* join on two
  official documents for the same club and week. A row that cannot be joined is published as
  unjoined and is excluded from every rate. It is never counted as a player who played.

The injury-report parser is imported from `decision-lab/scripts/capture_official.py`, the parser
already verified against the live page by earlier sessions (it produced the 347-row Week 10 read
in `captures/nfl-injuries/`). This module does not re-implement it, so both paths read the page
identically.
"""
from __future__ import annotations

import gzip
import hashlib
import html
import importlib.util
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "injury-archive" / "data"
RAW = DATA / "raw"
INDEX = DATA / "index.jsonl"
INJURIES_JSON = DATA / "injuries.json"
INACTIVES_JSON = DATA / "inactives.json"
DESIGNATIONS_JSON = DATA / "designations.json"
COVERAGE_JSON = DATA / "coverage.json"
CLUBS_JSON = DATA / "clubs.json"

UA = "NFL3-InjuryArchive/1.0 (+https://github.com/kanlerxz87-cyber/NFL3)"
INJURY_HOSTS = {"www.nfl.com"}
INACTIVES_HUB_URL = "https://www.nfl.com/inactives/"

# Pinned vocabularies. An unseen label is a drift alarm, never a value to be guessed.
PRACTICE_VOCAB = {
    "Did Not Participate In Practice",
    "Limited Participation in Practice",
    "Full Participation in Practice",
}
GAME_VOCAB = {"", "Out", "Doubtful", "Questionable"}
DESIGNATIONS = ("Out", "Doubtful", "Questionable")

# Positions the inactive articles print before the player name. Used only to split a published
# list item into its own two fields; the raw string is always stored as well.
POSITION_TOKENS = {
    "QB", "RB", "FB", "WR", "TE", "C", "G", "T", "OL", "OT", "OG", "C/G", "G/T", "T/G",
    "DE", "DT", "NT", "DL", "EDGE", "LB", "ILB", "OLB", "MLB", "CB", "DB", "S", "FS", "SS",
    "K", "P", "LS", "KR", "PR", "CB/S", "S/CB", "LB/EDGE", "EDGE/LB", "DT/DE", "DE/DT",
}

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
EMERGENCY = re.compile(r"emergency\s+(?:third|3rd)\s+(?:qb|quarterback)|designated\s+third\s+qb", re.I)
TITLE_WEEK = re.compile(r"Week\s+(\d+)\s+of\s+the\s+(\d{4})\s+Season", re.I)
TAG = re.compile(r"<[^>]+>")


def _load_verified_parser():
    path = ROOT / "decision-lab" / "scripts" / "capture_official.py"
    spec = importlib.util.spec_from_file_location("capture_official", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CO = _load_verified_parser()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", fragment))).strip()


def num(value) -> str:
    """Thousands-separated integer for display. Blank stays blank."""
    if value is None or value == "":
        return ""
    return f"{int(value):,}"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------------------------
# Fetch and store
# ---------------------------------------------------------------------------------------------

def fetch(url: str, hosts: set[str], timeout: int = 45) -> tuple[bytes, str, int]:
    """Read one official page. Any redirect off the official host is refused, not followed."""
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url, status = response.geturl(), response.status
        raw = response.read(12_000_001)
    parsed = urlparse(final_url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError(f"redirect outside the official host: {final_url}")
    if len(raw) > 12_000_000:
        raise ValueError("source exceeds the 12 MB capture limit")
    return raw, final_url, status


def store_raw(raw: bytes) -> str:
    """Content-addressed store. The same bytes are never written twice."""
    RAW.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(raw)
    path = RAW / f"{digest}.html.gz"
    if not path.exists():
        path.write_bytes(gzip.compress(raw, mtime=0))
    if gzip.decompress(path.read_bytes()) != raw:
        raise RuntimeError("stored capture does not round-trip to the fetched bytes")
    return str(path.relative_to(ROOT))


def load_raw(rel: str) -> bytes:
    return gzip.decompress((ROOT / rel).read_bytes())


def read_index() -> list[dict]:
    if not INDEX.exists():
        return []
    return [json.loads(line) for line in INDEX.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_index(entry: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------------------------
# Injury report (official weekly report page)
# ---------------------------------------------------------------------------------------------

def injuries_url(season: int, week: int) -> str:
    return f"https://www.nfl.com/injuries/league/{season}/REG{week}"


def parse_injuries(raw: bytes, url: str, observed_at: str) -> dict:
    """Parse one official weekly injury report page.

    Returns rows, no-injury notices and a list of structural failures. A non-empty `failures`
    means the read must not be used for a published rate.
    """
    text = raw.decode("utf-8", errors="replace")
    digest = sha256_bytes(raw)
    failures: list[str] = []

    title = TITLE_WEEK.search(text)
    season = week = None
    if title:
        week, season = int(title.group(1)), int(title.group(2))
    else:
        failures.append("title: no 'Week N of the YYYY Season' label")

    day_sections = team_sections = injury_tables = no_results = 0
    table_data_rows = 0
    header_problems: list[str] = []
    for match in CO.TOKEN.finditer(text):
        if match.group("day") is not None:
            day_sections += 1
        elif match.group("team") is not None:
            team_sections += 1
        elif match.group("no_results") is not None:
            if clean(match.group("no_results")):
                no_results += 1
        elif match.group("table") is not None:
            table_html = match.group("table")
            if not re.search(r"<th[^>]*>\s*Player\s*</th>", table_html, re.I):
                continue
            injury_tables += 1
            headers = {clean(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.S | re.I)}
            missing = sorted({"Player", "Position", "Injuries", "Practice Status", "Game Status"} - headers)
            if missing:
                header_problems.append(f"injury table {injury_tables}: missing column(s) {', '.join(missing)}")
            for row_match in CO.ROW.finditer(table_html):
                cells = CO.CELL.findall(row_match.group(1))
                if cells and cells[0][0] == "d":
                    table_data_rows += 1
    failures.extend(header_problems)
    if day_sections < 1:
        failures.append("structure: no day headings")
    if team_sections != injury_tables + no_results:
        failures.append(
            f"structure: {team_sections} team sections vs {injury_tables} tables + {no_results} notices"
        )

    rows, empty = CO.parse_injuries(text, url, observed_at, digest)
    if table_data_rows != len(rows):
        failures.append(f"rows: {table_data_rows} data rows in tables but {len(rows)} parsed")
    if not rows and not empty:
        failures.append("rows: no injury evidence parsed")

    for row in rows:
        label = f"{row['team']} / {row['player'] or '(no name)'}"
        for field in ("team", "player", "position", "day"):
            if not row.get(field):
                failures.append(f"row {label}: required field '{field}' blank")
        if row["practice_status"] not in PRACTICE_VOCAB:
            failures.append(f"row {label}: unrecognised practice status {row['practice_status']!r}")
        if row["game_status"] not in GAME_VOCAB:
            failures.append(f"row {label}: unrecognised game status {row['game_status']!r}")
        if not row["player_url"].startswith("https://www.nfl.com/players/"):
            failures.append(f"row {label}: player link is not an official nfl.com player page")

    return {
        "season": season, "week": week, "source_url": url, "observed_at": observed_at,
        "sha256": digest, "rows": rows, "no_injury_sections": empty,
        "day_sections": day_sections, "team_sections": team_sections,
        "injury_rows": len(rows), "failures": failures,
    }


# ---------------------------------------------------------------------------------------------
# Inactive list (official weekly inactives article)
# ---------------------------------------------------------------------------------------------

def inactives_url(season: int, week: int) -> str:
    return (f"https://www.nfl.com/news/nfl-week-{week}-inactives-"
            f"players-ruled-out-sunday-{season}-season")


HEADING = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.S | re.I)
LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
GAME_SECTION = re.compile(r"^(MUNICH GAME|EARLY GAMES?|LATE GAMES?|SUNDAY NIGHT FOOTBALL|"
                          r"MONDAY NIGHT FOOTBALL|THURSDAY NIGHT FOOTBALL|SATURDAY GAMES?|"
                          r"INTERNATIONAL GAME)", re.I)


def split_inactive_item(text: str) -> tuple[str, str]:
    """Split one published list item into (position, player) without inventing either.

    The source prints e.g. "CB Carlton Davis", "C/G Keylan Rutledge", "QB Behren Morton
    (emergency third QB)". Only a leading token that is in the pinned position vocabulary is
    treated as a position; everything else is kept as the player string, verbatim.
    """
    cleaned = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", text))).strip()
    if not cleaned:
        return "", ""
    head, _, tail = cleaned.partition(" ")
    if head.upper() in POSITION_TOKENS and tail:
        return head.upper(), tail.strip()
    return "", cleaned


def nickname(club: str) -> str:
    """The heading token the article prints for a club. 'New England Patriots' -> 'PATRIOTS'."""
    words = re.sub(r"\s+", " ", html.unescape(club or "")).strip().split(" ")
    return words[-1].upper() if words and words[-1] else ""


def parse_inactives(raw: bytes, url: str, observed_at: str, club_nicknames: set[str]) -> dict:
    """Parse one official inactives article into per-club lists.

    The article is an ordered document: a game-section heading, then for each club a heading
    carrying the club nickname, then the club's inactive players as list items. The parser walks
    that order. A short heading that is neither a game section nor a known club nickname is a
    structural failure: it is not silently skipped and it is never treated as a club.
    """
    text = raw.decode("utf-8", errors="replace")
    digest = sha256_bytes(raw)
    failures: list[str] = []

    # Recover document order: headings and list items interleave, so sort by source offset.
    ordered: list[tuple[int, str, str]] = []
    for match in HEADING.finditer(text):
        ordered.append((match.start(), "h", match.group(2)))
    for match in LI.finditer(text):
        ordered.append((match.start(), "li", match.group(1)))
    ordered.sort(key=lambda t: t[0])

    season = week = None
    title = re.search(r"Week\s+(\d+)\s+inactives", clean(text[:4000]), re.I)
    if title:
        week = int(title.group(1))
    year = re.search(r"(\d{4})\s+NFL\s+season", clean(text[:8000]), re.I)
    if year:
        season = int(year.group(1))

    clubs: dict[str, dict] = {}
    section = ""
    current: str | None = None
    for _offset, kind, payload in ordered:
        if kind == "h":
            label = clean(payload)
            if not label:
                continue
            if GAME_SECTION.match(label):
                section = label.upper()
                current = None
                continue
            key = label.upper()
            if key in club_nicknames:
                current = key
                clubs.setdefault(key, {"club": key, "game_section": section, "players": []})
                continue
            if len(label) > 40:  # editorial copy, not a club heading
                current = None
                continue
            failures.append(f"heading: unrecognised club heading {label!r}")
            current = None
            continue
        if current is None:
            continue
        position, player = split_inactive_item(payload)
        if not player:
            continue
        clubs[current]["players"].append({
            "club": current, "position": position, "player": player,
            "raw": re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", payload))).strip(),
            "emergency_qb": bool(EMERGENCY.search(player)),
        })

    rows = [row for club in clubs.values() for row in club["players"]]
    if not clubs:
        failures.append("clubs: no club heading recognised in the article")
    for key, club in clubs.items():
        if not club["players"]:
            failures.append(f"club {key}: heading with no inactive players")
    return {
        "season": season, "week": week, "source_url": url, "observed_at": observed_at,
        "sha256": digest, "clubs": clubs, "rows": rows, "failures": failures,
    }


# ---------------------------------------------------------------------------------------------
# Names, clubs and the join
# ---------------------------------------------------------------------------------------------

def norm_name(name: str) -> str:
    text = html.unescape(name or "").lower()
    text = text.replace("’", "'")
    text = re.sub(r"\([^)]*\)", " ", text)          # "Riley Leonard (emergency third QB)"
    text = re.sub(r"[^a-z0-9 ]", "", text)          # D.J. -> dj ; Ar'maj -> armaj
    text = re.sub(r"\s+", " ", text).strip()
    return text


def norm_name_no_suffix(name: str) -> str:
    parts = norm_name(name).split(" ")
    while parts and parts[-1] in SUFFIXES:
        parts.pop()
    return " ".join(parts)


def wilson(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval. Returns (low, high); (0.0, 1.0) when n == 0, and n is published."""
    if n <= 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def join_week(injury: dict, inactives: dict) -> dict:
    """Join one week's report rows to one week's inactive lists, club by club.

    Returns row-level observations and the counts needed to explain every exclusion.
    """
    clubs_in_article = {k.upper(): v for k, v in inactives["clubs"].items()}
    report_clubs = {row["team"].upper() for row in injury["rows"]}
    matched_clubs = sorted(report_clubs & set(clubs_in_article))
    uncovered_clubs = sorted(report_clubs - set(clubs_in_article))
    extra_clubs = sorted(set(clubs_in_article) - report_clubs)

    observations: list[dict] = []
    for row in injury["rows"]:
        club = row["team"].upper()
        if row["game_status"] not in DESIGNATIONS:
            continue
        record = {
            "season": injury["season"], "week": injury["week"], "club": row["team"],
            "player": row["player"], "position": row["position"],
            "injury": row["injury"], "practice_status": row["practice_status"],
            "game_status": row["game_status"], "player_url": row["player_url"],
            "injury_source_url": injury["source_url"],
            "inactives_source_url": inactives["source_url"],
            "injury_sha256": injury["sha256"], "inactives_sha256": inactives["sha256"],
            "injury_observed_at": injury["observed_at"],
            "inactives_observed_at": inactives["observed_at"],
            "club_covered": club in clubs_in_article,
            "outcome": "", "match_method": "", "inactive_position": "", "raw_inactive": "",
            "emergency_qb": False,
        }
        if club not in clubs_in_article:
            record["outcome"] = "club not in the inactives article"
            observations.append(record)
            continue
        target = norm_name(row["player"])
        target_loose = norm_name_no_suffix(row["player"])
        exact = [p for p in clubs_in_article[club]["players"] if norm_name(p["player"]) == target]
        loose = [p for p in clubs_in_article[club]["players"] if norm_name_no_suffix(p["player"]) == target_loose]
        if len(exact) == 1:
            hit, method = exact[0], "exact"
        elif len(loose) == 1:
            hit, method = loose[0], "suffix-insensitive"
        elif len(exact) > 1 or len(loose) > 1:
            record["outcome"] = "ambiguous name match"
            record["match_method"] = "ambiguous"
            observations.append(record)
            continue
        else:
            record["outcome"] = "active (not on the inactive list)"
            record["match_method"] = "no match"
            observations.append(record)
            continue
        record.update({
            "outcome": "inactive (on the official inactive list)",
            "match_method": method,
            "inactive_position": hit["position"],
            "raw_inactive": hit["raw"],
            "emergency_qb": hit["emergency_qb"],
        })
        observations.append(record)

    return {
        "observations": observations,
        "matched_clubs": matched_clubs,
        "uncovered_clubs": uncovered_clubs,
        "extra_clubs": extra_clubs,
        "report_clubs": sorted(report_clubs),
    }


def summarise(observations: list[dict], key=lambda r: r["game_status"]) -> list[dict]:
    """Inactive rate per group with a Wilson interval. Every excluded row is counted."""
    groups: dict[str, dict] = {}
    for row in observations:
        group = key(row)
        bucket = groups.setdefault(group, {"group": group, "n": 0, "inactive": 0,
                                           "active": 0, "uncovered": 0, "ambiguous": 0,
                                           "emergency": 0})
        if row["outcome"].startswith("club not in"):
            bucket["uncovered"] += 1
            continue
        if row["outcome"].startswith("ambiguous"):
            bucket["ambiguous"] += 1
            continue
        bucket["n"] += 1
        if row["outcome"].startswith("inactive"):
            bucket["inactive"] += 1
            if row["emergency_qb"]:
                bucket["emergency"] += 1
        else:
            bucket["active"] += 1
    out: list[dict] = []
    for bucket in sorted(groups.values(), key=lambda b: b["group"]):
        n = bucket["n"]
        low, high = wilson(bucket["inactive"], n)
        out.append({
            **bucket,
            "inactive_rate": (bucket["inactive"] / n) if n else None,
            "inactive_ci_low": low if n else None,
            "inactive_ci_high": high if n else None,
            "play_rate": (bucket["active"] / n) if n else None,
            "source_url": "",
        })
    return out
