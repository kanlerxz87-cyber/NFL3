#!/usr/bin/env python3
"""Offline structural and source-row audit for the static dashboard."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted(ROOT.glob("*.html"))
OFFICIAL_HOSTS = {"www.nfl.com", "nfl.com", "operations.nfl.com"}


class AuditParser(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.refs: list[tuple[str, str]] = []
        self.ids: list[str] = []
        self.rows: list[dict[str, object]] = []
        self.row: dict[str, object] | None = None
        self.td_depth = 0
        self.th_count = 0
        self.body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(str(a["id"]))
        if tag in {"a", "link", "script"}:
            attr = "href" if tag in {"a", "link"} else "src"
            if a.get(attr):
                self.refs.append((tag, str(a[attr])))
        if tag == "tbody":
            self.body = True
        elif tag == "tr" and self.body:
            self.row = {"cells": 0, "official": False}
        elif tag in {"td", "th"} and self.row is not None:
            if tag == "td":
                self.row["cells"] = int(self.row["cells"]) + 1
            else:
                self.th_count += 1
        elif tag == "a" and self.row is not None:
            href = str(a.get("href", ""))
            parsed = urlparse(href)
            if parsed.scheme == "https" and parsed.hostname in OFFICIAL_HOSTS:
                self.row["official"] = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row is not None:
            if int(self.row["cells"]) > 0:
                self.rows.append(self.row)
            self.row = None
        elif tag == "tbody":
            self.body = False


def main() -> int:
    errors: list[str] = []
    if not PAGES:
        errors.append("No root HTML pages found")
    all_ids: dict[Path, set[str]] = {}
    parsers: dict[Path, AuditParser] = {}
    for page in PAGES:
        parser = AuditParser(page)
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"{page.relative_to(ROOT)}: cannot read/parse: {exc}")
            continue
        if len(parser.ids) != len(set(parser.ids)):
            errors.append(f"{page.relative_to(ROOT)}: duplicate id attributes")
        all_ids[page.resolve()] = set(parser.ids)
        parsers[page] = parser
        for index, row in enumerate(parser.rows, start=1):
            if not row["official"]:
                errors.append(f"{page.relative_to(ROOT)}: data row {index} has no HTTPS official NFL source link")

    for page, parser in parsers.items():
        for tag, href in parser.refs:
            parsed = urlparse(href)
            if parsed.scheme or href.startswith("//") or not parsed.path:
                continue
            target_path = (page.parent / unquote(parsed.path)).resolve()
            if not target_path.exists():
                errors.append(f"{page.relative_to(ROOT)}: broken local {tag} reference {href!r}")
                continue
            if parsed.fragment and target_path.suffix.lower() == ".html":
                target_ids = all_ids.get(target_path)
                if target_ids is None:
                    target_parser = AuditParser(target_path)
                    target_parser.feed(target_path.read_text(encoding="utf-8"))
                    target_ids = set(target_parser.ids)
                if unquote(parsed.fragment) not in target_ids:
                    errors.append(f"{page.relative_to(ROOT)}: missing local fragment in {href!r}")

    if errors:
        print("SITE CHECK FAILED")
        print("\n".join(f" - {error}" for error in errors))
        return 1
    print(f"SITE CHECK PASSED: {len(PAGES)} HTML pages; local assets and page links resolve; {sum(len(p.rows) for p in parsers.values())} data-table rows each link to an HTTPS official NFL source.")
    print("External URLs were not crawled by this offline check; see sources.html for the manual official-source access audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
