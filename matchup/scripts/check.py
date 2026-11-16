#!/usr/bin/env python3
"""Fail-closed gate for the matchup workspace. Run before every publication.

    python3 matchup/scripts/check.py

It checks four things, and exits non-zero on any failure:

  1. Provenance  — every table row in every page carries an https link, and every link
                   marked class="source" points at an official host. Club sites qualify
                   only if that exact host appears as a source_url in the committed
                   capture, so an arbitrary new host cannot slip in.
  2. Integrity   — local links and assets referenced by the pages exist.
  3. Arithmetic  — the counts published on the pages are recomputed from the committed
                   transcript and the committed snapshot, not trusted from a stale file.
  4. Blanks      — every empty value in the matrix has a written reason. A cell may be
                   blank; it may not be blank without saying why.

No network access is required or used.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WS = HERE.parent                       # matchup/
DATA = WS / "data"

NFL_HOSTS = {
    "www.nfl.com", "nfl.com", "operations.nfl.com", "support.nfl.com",
    "nextgenstats.nfl.com", "static.www.nfl.com",
}

errors: list[str] = []
checks = 0


def ok(message: str) -> None:
    global checks
    checks += 1
    print(f"  ok  {message}")


def fail(message: str) -> None:
    errors.append(message)


# ----------------------------------------------------------------- provenance
def official_hosts() -> set[str]:
    """NFL hosts, plus every club host recorded as a source in the committed capture."""
    snap = json.loads((ROOT / "decision-lab" / "data" / "official_snapshot.json")
                      .read_text(encoding="utf-8"))
    hosts = set(NFL_HOSTS)
    for row in snap["depth_rows"]:
        h = urlparse(row["source_url"]).hostname
        if h:
            hosts.add(h)
    for entry in snap.get("manifest", []):
        h = urlparse(entry.get("final_url") or entry.get("url", "")).hostname
        if h:
            hosts.add(h)
    return hosts


class PageParser(HTMLParser):
    def __init__(self, path: Path, hosts: set[str]):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.hosts = hosts
        self.in_tbody = 0
        self.in_row = 0
        self.row_has_link = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.in_row += 1
            self.row_has_link = False
        elif tag == "a":
            href = a.get("href", "")
            parsed = urlparse(href)
            if parsed.scheme == "https" and parsed.hostname:
                if self.in_tbody and self.in_row:
                    self.row_has_link = True
                if "source" in a.get("class", "").split() and parsed.hostname not in self.hosts:
                    fail(f"{self.path.name}: non-official source link: {href}")
            elif parsed.scheme == "http":
                fail(f"{self.path.name}: link is not HTTPS: {href}")
            elif href and not href.startswith(("#", "mailto:", "javascript:")):
                target = (self.path.parent / parsed.path).resolve()
                if not target.exists():
                    fail(f"{self.path.name}: broken local link: {href}")
        elif tag in {"script", "link"}:
            url = a.get("src" if tag == "script" else "href", "")
            if url and not url.startswith(("http://", "https://", "//", "data:")):
                target = (self.path.parent / urlparse(url).path).resolve()
                if not target.exists():
                    fail(f"{self.path.name}: missing local asset: {url}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody and self.in_row:
            if not self.row_has_link:
                fail(f"{self.path.name}: table body row is missing a source link")
            self.in_row -= 1
        elif tag == "tbody" and self.in_tbody:
            self.in_tbody -= 1


# ----------------------------------------------------------------- arithmetic
def check_arithmetic() -> None:
    rows = list(csv.DictReader((DATA / "injury_live_2026-11-16.csv").open(encoding="utf-8")))
    rec = json.loads((DATA / "injury_reconciliation.json").read_text(encoding="utf-8"))
    cen = json.loads((DATA / "census.json").read_text(encoding="utf-8"))

    if len(rows) != rec["live_rows"]:
        fail(f"transcript has {len(rows)} rows but the reconciliation says {rec['live_rows']}")
    else:
        ok(f"transcript row count {len(rows)} matches the published figure")

    teams = len({r["team"] for r in rows})
    if teams != rec["live_teams"]:
        fail(f"transcript has {teams} clubs but the reconciliation says {rec['live_teams']}")
    else:
        ok(f"transcript club count {teams} matches the published figure")

    for label, key in (("Out", "live_out"), ("Doubtful", "live_doubtful"),
                       ("Questionable", "live_questionable")):
        n = sum(1 for r in rows if r["game_status"] == label)
        if n != rec[key]:
            fail(f"{label}: transcript has {n}, reconciliation says {rec[key]}")
    ok("Out / Doubtful / Questionable counts recomputed from the transcript")

    if any(not r["source_url"].startswith("https://www.nfl.com/") for r in rows):
        fail("a transcript row carries a source URL that is not an nfl.com page")
    else:
        ok("every transcript row cites the official nfl.com report")

    if any(not r["player_url"].startswith("https://www.nfl.com/players/") for r in rows):
        fail("a transcript row carries a player URL that is not an nfl.com player page")
    else:
        ok("every transcript row links the player's own nfl.com page")

    added, removed = rec["added_count"], rec["removed_count"]
    if len(rec["added"]) != added or len(rec["removed"]) != removed:
        fail("the added/removed counts do not match the listed rows")
    else:
        ok(f"{added} added rows and {removed} removed rows are listed individually")

    # The reconciliation must reconcile: previous + added - removed == live.
    prev = rec["previous"]["rows"]
    if prev + added - removed != rec["live_rows"]:
        fail(f"the reconciliation does not add up: {prev} + {added} - {removed} "
             f"!= {rec['live_rows']}")
    else:
        ok(f"reconciliation adds up: {prev} + {added} - {removed} = {rec['live_rows']}")

    # Matrix blanks must all carry a written reason.
    matrix = json.loads((DATA / "matrix.json").read_text(encoding="utf-8"))
    bad = [m for m in matrix
           if (m["offence_effective_string"] == "" or m["defence_effective_string"] == "")
           and not m["cell_status"].startswith("unverified")]
    if bad:
        fail(f"{len(bad)} matrix cells are blank without a written reason")
    else:
        ok("every blank matrix cell carries a written reason")

    published = [m for m in matrix if m["cell_status"] == "published"]
    if len(published) != cen["matrix_cells_published"]:
        fail("published matrix cell count disagrees with the census")
    else:
        ok(f"{len(published)} published matrix cells agree with the census")

    # A published cell must never name a player the injury report says cannot play.
    for m in published:
        for side, status in (("offence", m["offence_player_status"]),
                             ("defence", m["defence_player_status"])):
            if status in {"Out", "Doubtful"}:
                fail(f"{m['matchup']} {m['offence_group']}/{m['defence_group']}: "
                     f"{side} top string is {status}")
    ok("no published cell names a player the report says is Out or Doubtful")

    # Roster events must each carry a verbatim quote and an official URL.
    ev = json.loads((DATA / "roster_events.json").read_text(encoding="utf-8"))
    if any(not e["verbatim"].strip() or not e["source_url"].startswith("https://www.nfl.com/")
           for e in ev):
        fail("a roster event is missing its verbatim quote or its official URL")
    else:
        ok(f"all {len(ev)} roster events carry a verbatim quote and an official URL")

    # Replacement depth: a replacement must never be the player he replaces.
    rd = json.loads((DATA / "replacement_depth.json").read_text(encoding="utf-8"))
    if any(r["replacement_player"] and r["replacement_player"] == r["out_player"] for r in rd):
        fail("a replacement row names the injured player as his own replacement")
    else:
        ok(f"all {len(rd)} replacement chains name a different player")


def main() -> int:
    print("matchup workspace gate")
    hosts = official_hosts()
    pages = sorted(WS.glob("*.html"))
    if len(pages) < 9:
        fail(f"expected 9 pages, found {len(pages)}")
    for page in pages:
        p = PageParser(page, hosts)
        p.feed(page.read_text(encoding="utf-8"))
        p.close()
    ok(f"{len(pages)} pages checked for provenance and local links")

    check_arithmetic()

    # No merge-conflict markers anywhere in the workspace.
    marker = re.compile(r"^(<<<<<<< |=======$|>>>>>>> )", re.MULTILINE)
    for f in sorted(WS.rglob("*")):
        if f.is_file() and f.suffix.lower() in {".html", ".py", ".json", ".tsv", ".csv", ".md", ".css"}:
            if marker.search(f.read_text(encoding="utf-8")):
                fail(f"{f}: unresolved merge-conflict marker")
    ok("no merge-conflict markers in the workspace")

    if errors:
        print("\nFAILED:")
        print("\n".join(f"  - {e}" for e in errors[:40]))
        if len(errors) > 40:
            print(f"  … and {len(errors) - 40} more")
        return 1
    print(f"\nAll {checks} matchup checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
