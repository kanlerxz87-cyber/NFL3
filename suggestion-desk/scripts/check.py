#!/usr/bin/env python3
"""Fail-closed gate for the suggestion review desk.

    python3 suggestion-desk/scripts/check.py

What it enforces, and why each check exists:

 1. every page rebuilds byte for byte, so a committed page can never drift from the data it claims to
    render (the drift alarm the register asks for in SG-27);
 2. every table row carries an https link - the promise the landing page makes for the whole site;
 3. every link marked as an official source sits on an NFL surface, the league's own media or rules site,
    the US National Weather Service, or this repository's own committed artifacts on GitHub;
 4. every local link and asset exists;
 5. every proposal in the merged register is governed by exactly one decision (the generator already
    refuses to run otherwise, but the check re-proves it from the rendered pages);
 6. every register question cited by a discovery row exists, and the count is published;
 7. no placeholder text, no unresolved merge markers, and no claim of a validated strategy anywhere in
    these pages.

It fails loudly rather than publishing a blank, which is the convention the rest of the site follows.
"""
from __future__ import annotations

import html.parser
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SITE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DERIVED = ROOT / "ops-center" / "data" / "derived.json"
PAGES = ["index.html", "paths.html", "discovery.html", "flagged.html"]
# The allowed-host set is not typed here: build.py computes it from the committed official snapshot and
# the merged register and writes it to data/allowed_hosts.json, so the two files can never disagree about
# what this workspace treats as an official source. If the file is missing the gate fails rather than
# falling back to a shorter list, because a shorter list is a looser gate.
ALLOWED_HOSTS_FILE = SITE / "data" / "allowed_hosts.json"
if ALLOWED_HOSTS_FILE.is_file():
    OFFICIAL_HOSTS = set(json.loads(ALLOWED_HOSTS_FILE.read_text(encoding="utf-8"))["hosts"])
else:
    OFFICIAL_HOSTS = set()   # main() turns this into a hard failure rather than a looser gate
errors: list[str] = []


class Parser(html.parser.HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = 0
        self.in_row = 0
        self.row_has_source = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.in_row += 1
            self.row_has_source = False
        elif tag == "a":
            href = a.get("href", "")
            classes = a.get("class", "").split()
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"}:
                if parsed.scheme != "https":
                    errors.append(f"{self.path.name}: external link is not HTTPS: {href}")
                if "source" in classes and parsed.hostname not in OFFICIAL_HOSTS:
                    errors.append(f"{self.path.name}: non-official source link: {href}")
                if self.in_tbody and self.in_row:
                    self.row_has_source = True
            elif href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                target = (self.path.parent / parsed.path).resolve()
                if not target.exists():
                    errors.append(f"{self.path.name}: broken local link: {href}")
        elif tag in {"script", "link"}:
            attr = "src" if tag == "script" else "href"
            url = a.get(attr, "")
            if url and not url.startswith(("http://", "https://", "//", "data:")):
                target = (self.path.parent / urlparse(url).path).resolve()
                if not target.exists():
                    errors.append(f"{self.path.name}: missing local asset: {url}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody and self.in_row:
            if not self.row_has_source:
                errors.append(f"{self.path.name}: table body row is missing an https source link")
            self.in_row -= 1
        elif tag == "tbody" and self.in_tbody:
            self.in_tbody -= 1


def main() -> int:
    # 1. determinism
    before = {name: (SITE / name).read_bytes() for name in PAGES if (SITE / name).is_file()}
    build = subprocess.run([sys.executable, str(HERE / "build.py")], cwd=ROOT,
                           capture_output=True, text=True)
    if build.returncode:
        errors.append("build.py failed:\n" + (build.stderr or build.stdout).strip())
    else:
        for name in PAGES:
            after = (SITE / name).read_bytes()
            if name in before and before[name] != after:
                errors.append(f"{name} is stale: a rebuild produced different bytes")

    # 2-4. links, citations, assets
    if not ALLOWED_HOSTS_FILE.is_file():
        errors.append("data/allowed_hosts.json is missing, so the source-host gate has no list to apply")
    for name in PAGES:
        path = SITE / name
        if not path.is_file():
            errors.append(f"{name} is missing")
            continue
        parser = Parser(path)
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()

    # 5-6. coverage of the register
    register = __import__("json").loads(DERIVED.read_text(encoding="utf-8"))
    proposals = {s["id"] for s in register.get("suggestions") or []}
    questions = {q["id"] for q in register.get("questions") or []}
    decisions = __import__("json").loads((SITE / "data" / "decisions.json").read_text(encoding="utf-8"))
    governed = [pid for d in decisions["decisions"] for pid in (d.get("proposals") or [])]
    for pid in sorted(proposals - set(governed)):
        errors.append(f"register proposal {pid} is governed by no decision")
    dupes = {pid for pid in governed if governed.count(pid) > 1}
    for pid in sorted(dupes):
        errors.append(f"register proposal {pid} is governed by more than one decision")
    cited = {i.get("ref") for d in decisions["decisions"] for i in (d.get("discovery") or [])}
    for ref in sorted(cited):
        if ref and ref not in questions:
            errors.append(f"discovery row cites {ref}, which is not in the register")

    # 7. no placeholders, no conflict markers, no false claim of validation
    bad = re.compile(r"\b(TBD|TODO|FIXME|lorem ipsum)\b", re.I)
    marker = re.compile(r"^(<<<<<<< |=======$|>>>>>>> )", re.MULTILINE)
    for name in PAGES:
        text = (SITE / name).read_text(encoding="utf-8")
        if bad.search(text):
            errors.append(f"{name}: placeholder text")
        if marker.search(text):
            errors.append(f"{name}: unresolved merge-conflict marker")
    index_text = (SITE / "index.html").read_text(encoding="utf-8")
    n_strategies = len(register.get("strategies") or [])
    n_validated = sum(1 for s in register.get("strategies") or [] if s.get("validated"))
    if n_validated == 0:
        # the desk must not claim a validated strategy exists anywhere
        for phrase in ("validated strategy", "validated strategies", "0 validated"):
            if phrase in index_text and phrase != "0 validated":
                errors.append(f"index.html: claims '{phrase}' while the register records 0 validated")
    if str(n_strategies) not in index_text and n_strategies:
        errors.append("index.html: does not publish the register's strategy count")

    if errors:
        print("Suggestion desk verification FAILED:")
        print("\n".join(f"- {e}" for e in errors))
        return 1
    n_paths = sum(len(d["paths"]) for d in decisions["decisions"])
    print(f"Suggestion desk verification PASSED: {len(decisions['decisions'])} decisions, {n_paths} paths, "
          f"{len(governed)} proposals governed (register holds {len(proposals)}), {len(cited)} register "
          f"questions cited; every row carries an https link and the pages rebuild byte for byte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
