#!/usr/bin/env python3
"""Strict line-by-line verifier for NFL3 Decision & Line Origination Hub."""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HUB_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HUB_ROOT.parent
DATA_DIR = HUB_ROOT / "data"

EXPECTED_PAGES = [
    "index.html",
    "executive-summary.html",
    "suggestions.html",
    "questions.html",
    "origination.html",
    "depth-injuries.html",
    "repo-audit.html",
    "flagged.html",
]

ALLOWED_OFFICIAL_HOSTS = {
    "www.nfl.com",
    "nfl.com",
    "operations.nfl.com",
    "nextgenstats.nfl.com",
    "support.nfl.com",
    "media.nfl.com",
    "www.commanders.com",
    "commanders.com",
    "www.giants.com",
    "giants.com",
    "www.patriots.com",
    "patriots.com",
    "www.detroitlions.com",
    "detroitlions.com",
    "www.baltimoreravens.com",
    "baltimoreravens.com",
    "www.denverbroncos.com",
    "denverbroncos.com",
    "www.seahawks.com",
    "seahawks.com",
    "www.gaming.nv.gov",
    "gaming.nv.gov",
    "www.itl.nist.gov",
    "itl.nist.gov",
    "tsapps.nist.gov",
    "www.weather.gov",
    "weather.gov",
    "scikit-learn.org",
    "kansspelautoriteit.nl",
    "docs.github.com",
    "github.com",
}


class HubHTMLVerifier(HTMLParser):
    def __init__(self, page_path: Path):
        super().__init__(convert_charrefs=True)
        self.page_path = page_path
        self.errors: list[str] = []
        self.ids: set[str] = set()
        self.local_anchors: list[str] = []
        self.in_thead = False
        self.in_tbody = False
        self.in_tr = False
        self.in_blank_td = False
        self.header_cols = 0
        self.current_cols = 0
        self.row_official_links = 0
        self.total_tbody_rows = 0
        self.blank_cells = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        elem_id = a.get("id")
        if elem_id:
            if elem_id in self.ids:
                self.errors.append(f"duplicate id #{elem_id}")
            self.ids.add(elem_id)

        if tag == "table":
            self.header_cols = 0
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "tr":
            self.in_tr = True
            self.current_cols = 0
            self.row_official_links = 0
        elif tag in ("th", "td") and self.in_tr:
            self.current_cols += 1
            classes = (a.get("class") or "").split()
            if tag == "td" and "cell-blank" in classes:
                self.in_blank_td = True
                self.blank_cells += 1
        elif tag == "a":
            href = a.get("href") or ""
            if not href:
                self.errors.append("anchor with empty href")
                return
            parsed = urlparse(href)
            if parsed.scheme in ("http", "https"):
                if parsed.scheme != "https":
                    self.errors.append(f"non-HTTPS external link: {href}")
                if parsed.hostname not in ALLOWED_OFFICIAL_HOSTS:
                    self.errors.append(f"disallowed/non-official external host ({parsed.hostname}): {href}")
                elif self.in_tbody and self.in_tr:
                    self.row_official_links += 1
            elif href.startswith("#"):
                self.local_anchors.append(href[1:])
            elif not href.startswith(("mailto:", "tel:")):
                target = (self.page_path.parent / parsed.path).resolve()
                if not target.is_file():
                    self.errors.append(f"broken local link: {href} -> {target}")
        elif tag in ("link", "script", "img"):
            attr_name = "href" if tag == "link" else "src"
            ref = a.get(attr_name) or ""
            if ref and not ref.startswith(("https://", "http://", "data:")):
                target = (self.page_path.parent / urlparse(ref).path).resolve()
                if not target.is_file():
                    self.errors.append(f"missing local asset ({tag}): {ref}")

    def handle_data(self, data: str) -> None:
        if self.in_blank_td and data.strip():
            self.errors.append(f"cell-blank must be empty (''), found text: {data!r}")

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_blank_td:
            self.in_blank_td = False
        elif tag == "tr" and self.in_tr:
            if self.in_thead:
                self.header_cols = self.current_cols
            elif self.in_tbody:
                self.total_tbody_rows += 1
                if self.header_cols and self.current_cols != self.header_cols:
                    self.errors.append(
                        f"row column mismatch: expected {self.header_cols}, got {self.current_cols}"
                    )
                if self.row_official_links < 1:
                    self.errors.append("tbody row missing verified official HTTPS source link")
            self.in_tr = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False

    def finalize(self) -> None:
        for anchor in self.local_anchors:
            if anchor and anchor not in self.ids:
                self.errors.append(f"missing in-page anchor target #{anchor}")


def verify_json_integrity(errors: list[str]) -> None:
    orig = json.loads((DATA_DIR / "origination_leaderboard.json").read_text(encoding="utf-8"))
    for s in orig["strategies"]:
        for field in ("effective_n", "oos_brier_skill", "clv_bps", "leaderboard_rank"):
            if s[field] != "":
                errors.append(f"Strategy {s['strat_id']} field {field} must remain '' until validated")
    for c in orig["correlations"]:
        for field in ("empirical_rho", "ci_95"):
            if c[field] != "":
                errors.append(f"Correlation {c['pair_id']} field {field} must remain '' until validated")

    inj = json.loads((DATA_DIR / "injuries_depth.json").read_text(encoding="utf-8"))
    for d in inj["depth_deficiencies"]:
        if d["epa_dropoff"] != "":
            errors.append(f"Depth chain {d['chain_id']} epa_dropoff must remain '' until play-by-play feed")

    flg = json.loads((DATA_DIR / "flagged_review.json").read_text(encoding="utf-8"))
    for b in flg["unverified_blanks"]:
        if b["verified_value"] != "":
            errors.append(f"Flagged blank item {b['blank_id']} verified_value must be ''")


def main() -> int:
    errors: list[str] = []
    verify_json_integrity(errors)

    total_rows = 0
    total_blanks = 0
    for page_name in EXPECTED_PAGES:
        p = HUB_ROOT / page_name
        if not p.is_file():
            errors.append(f"missing expected page: {page_name}")
            continue
        verifier = HubHTMLVerifier(p)
        verifier.feed(p.read_text(encoding="utf-8"))
        verifier.finalize()
        total_rows += verifier.total_tbody_rows
        total_blanks += verifier.blank_cells
        for err in verifier.errors:
            errors.append(f"{page_name}: {err}")

    if errors:
        print("FAILED decision-hub verification:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(
        f"PASSED decision-hub verification: {len(EXPECTED_PAGES)} pages, "
        f"{total_rows} verified table rows, {total_blanks} strictly empty unverified cells, "
        f"0 broken local links, 100% official HTTPS citations."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
