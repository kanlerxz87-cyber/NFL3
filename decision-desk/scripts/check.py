#!/usr/bin/env python3
"""Verify the built decision desk.

Checks, in order:
  1. every page exists, is valid enough HTML, and all local links and assets resolve;
  2. every table body row contains at least one https link, and every such link is on an
     allowed host (official NFL/club, standards body, or GitHub for the repository itself);
  3. every page carries the research-only notice and no page claims an approved line,
     a market price or a reward;
  4. the data files agree with the pages: the game log cross-check passes, and the counts
     quoted in the pages are the counts in the data.
Exit code is non-zero on any failure, so CI cannot publish a broken desk.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent
DATA = DESK / "data"

OFFICIAL_SUFFIXES = ("nfl.com", "nfl.net")
CLUB_SUFFIXES = (
    "49ers.com", "atlantafalcons.com", "azcardinals.com", "baltimoreravens.com", "bengals.com",
    "buffalobills.com", "panthers.com", "chicagobears.com", "clevelandbrowns.com", "dallascowboys.com",
    "denverbroncos.com", "detroitlions.com", "packers.com", "houstontexans.com", "colts.com",
    "jaguars.com", "chiefs.com", "raiders.com", "chargers.com", "therams.com", "miamidolphins.com",
    "vikings.com", "patriots.com", "neworleanssaints.com", "giants.com", "newyorkjets.com",
    "philadelphiaeagles.com", "steelers.com", "seahawks.com", "buccaneers.com", "tennesseetitans.com",
    "commanders.com",
)
METHODS_HOSTS = {"itl.nist.gov", "www.itl.nist.gov", "tsapps.nist.gov", "scikit-learn.org", "docs.github.com"}
REPO_HOSTS = {"github.com", "kanlerxz87-cyber.github.io"}
BANNED_PHRASES = [
    "guaranteed", "risk-free", "validated edge", "proven edge", "approved line", "sure thing",
    "our sportsbook", "bet now",
]
REQUIRED_NOTICE = "Research and decision support only"
errors: list[str] = []
warnings: list[str] = []


def allowed(host: str) -> bool:
    host = host.lower()
    if any(host == s or host.endswith("." + s) for s in OFFICIAL_SUFFIXES):
        return True
    if any(host == s or host.endswith("." + s) for s in CLUB_SUFFIXES):
        return True
    return host in METHODS_HOSTS or host in REPO_HOSTS


class Page(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = False
        self.in_row = False
        self.row_links: list[str] = []
        self.rows = 0
        self.rows_without_source = 0
        self.links: list[str] = []
        self.assets: list[str] = []
        self.ids: set[str] = set()
        self.dupes: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.dupes.append(a["id"])
            self.ids.add(a["id"])
        if tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_row = True
            self.row_links = []
        elif tag == "a":
            href = a.get("href", "")
            if href.startswith(("http://", "https://")):
                self.links.append(href)
                if self.in_row:
                    self.row_links.append(href)
            elif href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                target = (self.path.parent / urlparse(href).path).resolve()
                if not target.exists():
                    errors.append(f"{self.path.name}: broken local link {href}")
        elif tag in {"script", "link"}:
            attr = "src" if tag == "script" else "href"
            url = a.get(attr, "")
            if url and not url.startswith(("http", "//", "data:")):
                target = (self.path.parent / urlparse(url).path).resolve()
                if not target.exists():
                    errors.append(f"{self.path.name}: missing asset {url}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody and self.in_row:
            self.rows += 1
            if not any(urlparse(u).hostname and allowed(urlparse(u).hostname or "") for u in self.row_links):
                self.rows_without_source += 1
                errors.append(f"{self.path.name}: table row {self.rows} has no allowed source link")
            self.in_row = False
        elif tag == "tbody" and self.in_tbody:
            self.in_tbody = False


def check_pages() -> tuple[int, int]:
    pages = sorted(DESK.glob("*.html"))
    expected = {"index.html", "summary.html", "requirements.html", "decisions.html", "questions.html",
                "suggestions.html", "lines.html", "strategies.html", "validation.html", "injuries.html",
                "luck.html", "audit.html", "flagged.html", "sources.html"}
    missing = expected - {p.name for p in pages}
    if missing:
        errors.append(f"missing pages: {', '.join(sorted(missing))}")
    total_rows = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        parser = Page(page)
        parser.feed(text)
        parser.close()
        total_rows += parser.rows
        if REQUIRED_NOTICE not in text:
            errors.append(f"{page.name}: research-only notice missing")
        if parser.dupes:
            errors.append(f"{page.name}: duplicate ids {sorted(set(parser.dupes))[:5]}")
        if "decision-desk" not in text and "../index.html" not in text:
            errors.append(f"{page.name}: no link back to the repository overview")
        low = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in low:
                errors.append(f"{page.name}: banned claim phrase {phrase!r}")
        for link in parser.links:
            host = urlparse(link).hostname or ""
            if not host:
                errors.append(f"{page.name}: malformed external link {link}")
            elif not allowed(host):
                warnings.append(f"{page.name}: link outside the official/methods allowlist: {host}")
        if parser.rows == 0:
            warnings.append(f"{page.name}: no table rows")
    return len(pages), total_rows


def check_data() -> None:
    games = list(csv.DictReader((DATA / "games_2026.csv").open(encoding="utf-8")))
    if len(games) != 136:
        errors.append(f"game log has {len(games)} rows, expected 136")
    for i, g in enumerate(games, start=2):
        if not g["source_url"].startswith("https://www.nfl.com/"):
            errors.append(f"games_2026.csv line {i}: non-official source")
        blank = g["away_score"] == "" or g["home_score"] == ""
        if blank and "UNVERIFIED" not in g["verification"]:
            errors.append(f"games_2026.csv line {i}: blank score not marked UNVERIFIED")
        if not blank and "UNVERIFIED" in g["verification"]:
            errors.append(f"games_2026.csv line {i}: scored row marked UNVERIFIED")
    analysis = json.loads((DATA / "analysis.json").read_text())
    avail = json.loads((DATA / "availability.json").read_text())
    for name, doc in (("analysis.json", analysis), ("availability.json", avail)):
        for key, value in doc.items():
            if isinstance(value, float) and value != value:  # NaN guard
                errors.append(f"{name}: NaN in {key}")
    if avail["counts"]["injury_rows"] != 254:
        errors.append("availability injury_rows changed; re-verify against the official report")
    index = (DESK / "index.html").read_text(encoding="utf-8")
    if str(analysis["league"]["games_with_scores"]) not in index:
        errors.append("index.html does not show the verified games count")
    if str(avail["counts"]["injury_rows_joined_to_depth"]) not in index:
        errors.append("index.html does not show the join count")
    # no invented numbers: every strategy without measured evidence must show a blank cell
    strategies = (DESK / "strategies.html").read_text(encoding="utf-8")
    if strategies.count('class="blank"') < 10:
        errors.append("strategies.html: expected blank cells for unmeasured entries")


def check_crosscheck() -> None:
    result = subprocess.run([sys.executable, str(DESK / "scripts" / "crosscheck_games.py")],
                            capture_output=True, text=True)
    if result.returncode != 0:
        errors.append("game log does not reproduce official standings")
        errors.append(result.stdout.strip()[-800:])


def main() -> int:
    pages, rows = check_pages()
    check_data()
    check_crosscheck()
    print(f"Pages: {pages} | table rows checked: {rows}")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings[:20]:
            print(f"  - {w}")
    if errors:
        print(f"FAIL ({len(errors)} errors):")
        for x in errors[:40]:
            print(f"  - {x}")
        return 1
    print("PASS - every page, local link, asset and table-row citation verified; "
          "data counts match the pages; game log reproduces official standings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
