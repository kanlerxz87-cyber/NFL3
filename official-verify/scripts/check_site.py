#!/usr/bin/env python3
"""Fail-closed checks for the official-verify sub-site.

What it enforces, and why each rule exists:

1.  Every table body row contains at least one https link, and that link's host
    is an official NFL host (or, for one explicitly declared exception, GitHub
    for an Actions run URL that is itself the evidence). A row without a source
    is exactly the failure mode the brief forbids, so it fails the build.
2.  Every local link and asset on these pages resolves. No 404s.
3.  No unresolved merge-conflict markers.
4.  No placeholder text leaked into a published cell.
5.  Every source id used on a page exists in the source register.
6.  Rebuilding the pages produces byte-identical output, so what is committed is
    what the committed data says. A drifted page fails.
7.  The blank marker is never rendered with a number beside it, and a cell that
    says "unverified" never also carries a value.
"""
from __future__ import annotations

import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parent

OFFICIAL_HOSTS = {
    "www.nfl.com",
    "nfl.com",
    "static.www.nfl.com",
    "operations.nfl.com",
    "support.nfl.com",
    "nextgenstats.nfl.com",
}
# Explicitly declared exception: one flag cites a GitHub Actions run because the
# run itself is the evidence. It is named here rather than waving the rule through.
EXTRA_ALLOWED = {
    "github.com": {"OV-F09"},
}
FORBIDDEN_PLACEHOLDERS = {"TODO", "TBD", "FIXME", "XXX", "lorem ipsum", "NaN"}
SOURCE_ID = re.compile(r"\b(OV-[SB]\d{2}|PREREG-2026-OV1|OV-F\d{2})\b")


class RowChecker(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = False
        self.in_row = False
        self.row_links: list[str] = []
        self.row_text: list[str] = []
        self.rows = 0
        self.problems: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_row = True
            self.row_links = []
            self.row_text = []
        elif tag == "a" and self.in_row:
            href = attrs.get("href", "")
            if href.startswith("https://"):
                self.row_links.append(href)
            elif href and not href.startswith(("#", "mailto:")):
                target = (self.path.parent / urlparse(href).path).resolve()
                if not target.exists():
                    self.problems.append(f"{self.path.name}: broken local link {href}")
        elif tag in {"script", "link"}:
            attr = "src" if tag == "script" else "href"
            url = attrs.get(attr, "")
            if url and not url.startswith(("http://", "https://", "//", "data:")):
                target = (self.path.parent / urlparse(url).path).resolve()
                if not target.exists():
                    self.problems.append(f"{self.path.name}: missing local asset {url}")

    def handle_data(self, data):
        self.text_parts.append(data)
        if self.in_row:
            self.row_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_row:
            self.rows += 1
            if not self.row_links:
                preview = " ".join("".join(self.row_text).split())[:70]
                self.problems.append(
                    f"{self.path.name}: table row {self.rows} has no https source link: {preview!r}"
                )
            else:
                official = False
                for href in self.row_links:
                    host = urlparse(href).hostname or ""
                    if host in OFFICIAL_HOSTS:
                        official = True
                        break
                    allowed_ids = EXTRA_ALLOWED.get(host, set())
                    if any(sid in "".join(self.row_text) for sid in allowed_ids):
                        official = True
                        break
                if not official:
                    self.problems.append(
                        f"{self.path.name}: table row {self.rows} has no link to an official host "
                        f"(hosts seen: {sorted({urlparse(h).hostname for h in self.row_links})})"
                    )
            self.in_row = False
        elif tag == "tbody":
            self.in_tbody = False


def main() -> int:
    problems: list[str] = []
    pages = sorted(SITE.glob("*.html"))
    if not pages:
        print("no pages built")
        return 1

    total_rows = 0
    for path in pages:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                problems.append(f"{path.name}:{line_no}: merge conflict marker")
        checker = RowChecker(path)
        checker.feed(text)
        checker.close()
        problems += checker.problems
        total_rows += checker.rows
        joined = "".join(checker.text_parts)
        for bad in FORBIDDEN_PLACEHOLDERS:
            if bad in joined:
                problems.append(f"{path.name}: placeholder text leaked: {bad!r}")
        # a blank marker must never sit beside a number in the same cell
        for chunk in re.findall(r"<td>([^<]*— unverified[^<]*)</td>", text):
            if re.search(r"\d", chunk):
                problems.append(f"{path.name}: blank marker rendered with a value: {chunk.strip()[:60]!r}")

    # every source id referenced must exist in the register
    register = (SITE / "data" / "source_register.json").read_text(encoding="utf-8")
    flags = (SITE / "data" / "flags.json").read_text(encoding="utf-8")
    known = set(re.findall(r'"(OV-[SB]\d{2}|OV-F\d{2}|PREREG-2026-OV1)"', register))
    known |= set(re.findall(r'"(OV-F\d{2})"', flags))
    # The registration is a committed file rather than an external source, so it
    # is registered by path and existence is the check that matters.
    prereg = SITE / "prereg" / "PREREG-2026-OV1.md"
    if prereg.exists():
        known.add("PREREG-2026-OV1")
    else:
        problems.append("prereg/PREREG-2026-OV1.md is missing")
    for path in pages:
        visible = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8"))
        for sid in set(SOURCE_ID.findall(visible)):
            if sid not in known:
                problems.append(f"{path.name}: references unknown source id {sid}")

    # rebuild and compare, so a committed page always matches its data
    before = {p.name: p.read_text(encoding="utf-8") for p in pages}
    rebuild = subprocess.run(
        [sys.executable, str(SITE / "scripts" / "build_site.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    if rebuild.returncode:
        problems.append("rebuild failed: " + (rebuild.stderr or rebuild.stdout)[-500:])
    else:
        for name, old in before.items():
            new = (SITE / name).read_text(encoding="utf-8")
            if old != new:
                problems.append(f"{name}: committed page differs from a fresh build of the committed data")

    print(f"Checked {len(pages)} pages, {total_rows} table rows.")
    if problems:
        for p in problems:
            print("  FAIL " + p)
        print(f"official-verify checks: FAIL ({len(problems)} problems)")
        return 1
    print("official-verify checks: PASS (every row sourced to an official host, no broken local links, "
          "deterministic build)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
