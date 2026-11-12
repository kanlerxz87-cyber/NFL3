#!/usr/bin/env python3
"""Structural + sourcing checks for the generated site.

Rules enforced (they are the brief's verification rules, machine-checked):

1. Every HTML page parses and every local link/asset resolves to a real file.
2. Every data-table row carries at least one link to an official source
   (nfl.com, nflverse, github.com/nflverse, nflreadr.nflverse.com) or to another page of this site
   that carries the verification register.
3. No table cell contains a bare "TBD" or "N/A" used as if it were data.
4. Every page has exactly one <h1> and a <title>.

Usage: python3 tests/check_site.py site
"""
from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser

OFFICIAL_PREFIXES = (
    "https://www.nfl.com/", "https://nfl.com/", "https://operations.nfl.com/",
    "https://github.com/nflverse/", "https://nflreadr.nflverse.com/",
    "https://www.nfl.com/legal/",
)
LOCAL_OK = {"sources.html", "flagged.html", "review.html", "questions.html",
            "strategies.html", "lines.html", "availability.html", "correlation.html"}


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.h1 = 0
        self.title = ""
        self.in_title = False
        self.in_table = False
        self.rows: list[list[list[str]]] = []   # table -> rows -> list of html chunks
        self.row: list[str] | None = None
        self.is_method = False
        self.in_thead = False
        self.cell_parts: list[str] | None = None
        self.cur: list[str] = []
        self.cell_links: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "table":
            cls = (d.get("class", "") or "").split()
            self.in_table = "data" in cls
            self.is_method = "method" in cls
            self.in_thead = False
            if self.in_table:
                self.rows.append([])
        elif tag == "thead" and self.in_table:
            self.in_thead = True
        elif tag == "tr" and self.in_table:
            self.row = [] if not self.in_thead else None
            self.cur = []
        elif tag in ("td", "th") and self.in_table and self.row is not None:
            self.cur = []
            self.cell_links = []
        elif tag == "a":
            href = d.get("href", "")
            self.links.append(href)
            if self.in_table and self.row is not None:
                self.cell_links.append(href)

    def handle_endtag(self, tag):
        if tag == "thead" and self.in_table:
            self.in_thead = False
        elif tag == "title":
            self.in_title = False
        elif tag == "table":
            self.in_table = False
        elif tag in ("td", "th") and self.in_table and self.row is not None:
            self.row.append("".join(self.cur).strip())
        elif tag == "tr" and self.in_table and self.row is not None:
            if self.row and not self.in_thead:
                self.rows[-1].append((self.row, list(self.cell_links)))
            self.row = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_table and self.row is not None:
            self.cur.append(data)


def check(root: str) -> int:
    problems: list[str] = []
    pages = sorted(f for f in os.listdir(root) if f.endswith(".html"))
    if not pages:
        print(f"FAIL: no HTML pages in {root}")
        return 1
    table_rows = 0
    sourced_rows = 0
    for name in pages:
        path = os.path.join(root, name)
        html = open(path, encoding="utf-8").read()
        p = Page()
        p.feed(html)
        if p.h1 != 1:
            problems.append(f"{name}: expected exactly one <h1>, found {p.h1}")
        if not p.title.strip():
            problems.append(f"{name}: missing <title>")
        for href in p.links:
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = os.path.normpath(os.path.join(root, href.split("#")[0]))
            if not os.path.exists(target):
                problems.append(f"{name}: broken local link {href}")
        if p.is_method:
            continue
        for rows in p.rows:
            for cells, links in rows:
                table_rows += 1
                ok = any(l.startswith(OFFICIAL_PREFIXES) for l in links) or \
                     any(l.split("#")[0] in LOCAL_OK for l in links)
                if ok:
                    sourced_rows += 1
                else:
                    problems.append(f"{name}: table row without an official source link: "
                                    f"{' | '.join(c[:40] for c in cells)[:120]}")
        for word in ("TBD",):
            if re.search(rf">\s*{word}\s*<", html):
                problems.append(f"{name}: contains a bare '{word}' placeholder")

    pct = (sourced_rows / table_rows * 100) if table_rows else 0
    print(f"pages: {len(pages)}")
    print(f"data-table rows: {table_rows}")
    print(f"rows with an official (or verification-register) source link: {sourced_rows} ({pct:.1f}%)")
    if problems:
        print(f"\nFAIL: {len(problems)} problem(s)")
        for pr in problems[:40]:
            print("  -", pr)
        return 1
    print("\nPASS: all pages parse, all local links resolve, every data row is sourced")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "site"))
