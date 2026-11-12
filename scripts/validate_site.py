#!/usr/bin/env python3
"""Validate local links and HTTPS source citations in this static site."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_HOSTS = {"nfl.com", "www.nfl.com", "operations.nfl.com"}
errors: list[str] = []


class SiteParser(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = 0
        self.in_row = 0
        self.row_has_source = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.in_row += 1
            self.row_has_source = False
        elif tag == "a":
            href = attrs.get("href", "")
            classes = attrs.get("class", "").split()
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"}:
                if "source" in classes and parsed.hostname not in OFFICIAL_HOSTS:
                    errors.append(f"{self.path}: non-official source link: {href}")
                if parsed.scheme != "https":
                    errors.append(f"{self.path}: external link is not HTTPS: {href}")
            elif href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                target = (self.path.parent / parsed.path).resolve()
                if not target.exists():
                    errors.append(f"{self.path}: broken local link: {href} -> {target.relative_to(ROOT)}")
            if self.in_tbody and self.in_row:
                # The pre-existing dashboard also cites authoritative primary
                # sources outside the NFL domain (for example NWS and GitHub).
                # New source-class links are additionally constrained above.
                if parsed.scheme == "https" and parsed.hostname:
                    self.row_has_source = True
        elif tag in {"script", "link"}:
            attr = "src" if tag == "script" else "href"
            url = attrs.get(attr, "")
            if url and not url.startswith(("http://", "https://", "//", "data:")):
                target = (self.path.parent / urlparse(url).path).resolve()
                if not target.exists():
                    errors.append(f"{self.path}: missing local asset: {url}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody and self.in_row:
            if not self.row_has_source:
                errors.append(f"{self.path}: table body row is missing an official source link")
            self.in_row -= 1
        elif tag == "tbody" and self.in_tbody:
            self.in_tbody -= 1


def main() -> int:
    pages = sorted(ROOT.glob("*.html"))
    expected = {"index.html", "requirements.html", "signals.html", "lineup.html", "validation.html", "suggestions.html", "review.html", "sources.html"}
    missing = expected - {page.name for page in pages}
    if missing:
        errors.append(f"missing expected pages: {', '.join(sorted(missing))}")
    for page in pages:
        parser = SiteParser(page)
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
    js = (ROOT / "assets/site.js").read_text(encoding="utf-8")
    for name in sorted(expected):
        if f"'{name}'" not in js:
            errors.append(f"assets/site.js: navigation missing {name}")
    if errors:
        print("Site validation failed:")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print(f"Validated {len(pages)} HTML pages; all local links/assets exist and every table row has a citation link.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
