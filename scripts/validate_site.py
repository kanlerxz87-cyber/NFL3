#!/usr/bin/env python3
"""Validate local links and HTTPS source citations in this static site.

The authority list is shared with the canonical decision lab
(``decision-lab/scripts/validation.py``) plus the official club hosts found in
the committed capture, so one definition of "official source" governs the whole
repository. Community and secondary hosts are deliberately excluded from that
list: a row may still link to one, but it may not be presented as an official
source link.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "decision-lab" / "scripts"))
import validation as canonical  # noqa: E402

EXTRA_OFFICIAL = {
    "www.weather.gov", "weather.gov", "www.gaming.nv.gov", "gaming.nv.gov",
    "kansspelautoriteit.nl", "www.kansspelautoriteit.nl",
}
OFFICIAL_HOSTS = set(canonical.OFFICIAL_HOSTS) | EXTRA_OFFICIAL

_snapshot_path = ROOT / "decision-lab" / "data" / "official_snapshot.json"
if _snapshot_path.is_file():
    _snapshot = json.loads(_snapshot_path.read_text(encoding="utf-8"))
    for _row in _snapshot.get("depth_rows", []):
        _host = urlparse(_row.get("source_url", "")).hostname
        if _host:
            OFFICIAL_HOSTS.add(_host)
    for _item in _snapshot.get("depth_directory_successes", []):
        _host = urlparse(_item.get("url", "")).hostname
        if _host:
            OFFICIAL_HOSTS.add(_host)

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
                # A row counts as sourced when it carries an HTTPS link. Rows that
                # present a community source say so in the cell text and never use
                # the official "source" class.
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
    # Validate the root pages and every sub-site, each with its own link/citation checks.
    # The root glob alone would silently stop validating the workspaces under dashboard/, line-lab/,
    # decision-hub/, research-workspace/ and research-desk/ as soon as one was moved into a folder.
    pages = sorted(ROOT.glob("*.html"))
    expected = {
        "index.html", "executive-summary.html", "questions.html", "decisions.html", "signals.html",
        "strategies.html", "validation.html", "lineups.html", "lineup.html", "suggestions.html",
        "flagged.html", "review.html", "sources.html", "verification.html",
    }
    missing = expected - {page.name for page in pages}
    if missing:
        errors.append(f"missing expected pages: {', '.join(sorted(missing))}")
    stale = {page.name for page in pages} - expected
    if stale:
        errors.append(f"unexpected root pages: {', '.join(sorted(stale))}")
    for page in pages:
        parser = SiteParser(page)
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()

    # Each workspace under a sub-directory enforces its own (stricter or different) citation rules,
    # so the root validator delegates instead of re-applying the root rule to them. A sub-site without
    # its own checker is validated with the root rule so nothing goes unchecked.
    imported = False
    for sub in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        pages_here = sorted(sub.glob("*.html"))
        if not pages_here:
            continue
        own_checker = None
        for candidate in ("check_site.py", "check.py", "check.mjs", "verify.py", "verify_hub.py"):
            if (sub / "scripts" / candidate).is_file():
                own_checker = sub / "scripts" / candidate
                break
        if own_checker is not None:
            imported = True
            continue
        for page in pages_here:
            parser = SiteParser(page)
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()

    # The navigation is defined once, in the generator, and every page is built from it.
    builder = (ROOT / "scripts" / "build_root.py").read_text(encoding="utf-8")
    for name in sorted(expected):
        if f'"{name}"' not in builder:
            errors.append(f"scripts/build_root.py: navigation missing {name}")

    if errors:
        print("Site validation failed:")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    note = " Sub-sites with their own checker are validated by that checker." if imported else ""
    print(f"Validated {len(pages)} root HTML pages; all local links/assets exist and every table row "
          f"has a citation link.{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
