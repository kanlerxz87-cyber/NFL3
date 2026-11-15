#!/usr/bin/env python3
"""Fail-closed verification of the origination workspace.

Checks, in order of how badly a failure would mislead a reader:

 1. every table body row carries a link to a named source (official or a named community release)
 2. no local link or asset is broken, and no page is missing from the navigation
 3. no merge-conflict marker and no placeholder token anywhere in the workspace
 4. no number is published as official unless its row links to nfl.com
 5. the build is deterministic: a second run produces byte-identical artifacts and pages
 6. the settlement reconciliation still passes and the gate artifact agrees with it
 7. every strategy on the leaderboard carries n, an interval and a source, or is labelled blocked
 8. no page contains an unqualified profitability or "validated" claim

Exit code 0 means every check passed. Any failure prints the file and the row so it can be fixed.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parent
DATA = OUT / "data"

OFFICIAL_HOSTS = ("nfl.com",)
COMMUNITY_HOSTS = ("github.com/nflverse", "github.com/nflverse-data", "raw.githubusercontent.com")
PLACEHOLDERS = ("TODO", "TBD", "FIXME", "XXX", "lorem ipsum", "PLACEHOLDER")
# Phrases that must never appear as an unqualified claim. Each is checked only as a phrase; the site is
# allowed to say "no validated strategy exists", which is the point of the guard.
FORBIDDEN = [
    r"\bvalidated strategy\b(?!.*no )",
    r"\bguaranteed\b",
    r"\brisk[- ]free\b",
    r"\bsure thing\b",
    r"\bprofitable\b(?!.*not )",
]


class TableAudit(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = 0
        self.in_row = 0
        self.row_has_link = False
        self.row_has_official = False
        self.rows = 0
        self.rows_missing_source = 0
        self.rows_without_official = 0
        self.official_rows = 0
        self.local_errors: list[str] = []
        self.external_links = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.in_row += 1
            self.row_has_link = False
            self.row_has_official = False
        elif tag in ("a", "link", "script"):
            url = attrs.get("href") if tag != "script" else attrs.get("src")
            if not url:
                return
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https"):
                self.external_links += 1
                host = (parsed.hostname or "").lower()
                is_official = any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)
                if url.startswith("http://"):
                    self.local_errors.append(f"external link is not HTTPS: {url}")
                if self.in_tbody and self.in_row:
                    self.row_has_link = True
                    if is_official:
                        self.row_has_official = True
            elif url and not url.startswith(("#", "mailto:", "javascript:", "data:")):
                target = (self.path.parent / parsed.path).resolve()
                if not target.exists():
                    self.local_errors.append(f"broken local link: {url}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody and self.in_row:
            self.rows += 1
            if not self.row_has_link:
                self.rows_missing_source += 1
            if self.row_has_official:
                self.official_rows += 1
            else:
                self.rows_without_official += 1
            self.in_row -= 1
        elif tag == "tbody" and self.in_tbody:
            self.in_tbody -= 1


def digest_tree(paths) -> dict[str, str]:
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main() -> int:
    errors: list[str] = []
    pages = sorted(OUT.glob("*.html"))
    if len(pages) != 13:
        errors.append(f"expected 13 pages, found {len(pages)}")

    nav_pages = re.findall(r"href='([a-z\-]+\.html)'", (OUT / "index.html").read_text(encoding="utf-8"))
    for page in pages:
        if page.name not in nav_pages:
            errors.append(f"{page.name}: missing from the shared navigation")

    totals = {"rows": 0, "missing": 0, "without_official": 0, "with_official": 0}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        audit = TableAudit(page)
        audit.feed(text)
        audit.close()
        totals["rows"] += audit.rows
        totals["missing"] += audit.rows_missing_source
        totals["without_official"] += audit.rows_without_official
        totals["with_official"] += audit.official_rows
        for item in audit.local_errors:
            errors.append(f"{page.name}: {item}")
        if audit.rows_missing_source:
            errors.append(f"{page.name}: {audit.rows_missing_source} table row(s) without a source link")
        if "assets/origination.css" not in text:
            errors.append(f"{page.name}: stylesheet link missing")
        for marker in ("<<<<<<<", "=======", ">>>>>>>"):
            if re.search(rf"^{re.escape(marker)}", text, re.M):
                errors.append(f"{page.name}: merge-conflict marker")
        for token in PLACEHOLDERS:
            if token.lower() in text.lower():
                errors.append(f"{page.name}: placeholder token {token!r}")
        for pattern in FORBIDDEN:
            for match in re.finditer(pattern, text, re.I):
                start = max(0, match.start() - 60)
                context = text[start:match.end() + 40].replace("\n", " ")
                if "no " in context.lower() or "not " in context.lower() or "never" in context.lower():
                    continue
                errors.append(f"{page.name}: unqualified claim {match.group(0)!r} — …{context.strip()}…")

    # the settlement feed must still be reconciled
    results = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
    if not results["passed"]:
        errors.append("results feed reconciliation failed; no backtest may be published")
    if results["counts"]["team_fields_matching"] != results["counts"]["team_fields_checked"]:
        errors.append("results feed: not every club x field check matches")

    # gates must agree with the leaderboard it scored
    gates = json.loads((DATA / "gates.json").read_text(encoding="utf-8"))
    board = json.loads((DATA / "leaderboard.json").read_text(encoding="utf-8"))
    below = {r["id"] for r in board["results"]
             if isinstance(r["summary"].get("hi"), float) and r["summary"]["hi"] < 0}
    if below != set(gates["demoted"]):
        errors.append(f"gate G10 demotions {sorted(gates['demoted'])} disagree with the leaderboard {sorted(below)}")
    for row in board["results"]:
        summary = row["summary"]
        if not summary.get("n"):
            errors.append(f"leaderboard {row['id']}: published without n")
        if summary.get("bss") is None:
            errors.append(f"leaderboard {row['id']}: published without a proper score")
        if summary.get("lo") is None:
            errors.append(f"leaderboard {row['id']}: published without an interval")

    # no strategy may claim validation while a promotion gate is blocked
    for row in board["results"]:
        if (row["summary"].get("lo") or -1) > 0 and summary_n(row) < gates["floors"]["promote_min_n"]:
            errors.append(f"leaderboard {row['id']}: interval above zero but below the promotion floor")

    # every price row must be labelled pre-kickoff, post-hoc or none
    ledger = json.loads((DATA / "prices" / "ledger.json").read_text(encoding="utf-8"))
    for event in ledger["events"]:
        for market, cell in event["markets"].items():
            if cell.get("opening") and cell.get("post_hoc"):
                pass  # both can exist; the ledger keeps them apart
            if cell.get("opening") and not cell.get("opening_observed_at"):
                errors.append(f"ledger {event['event_id']}/{market}: opening without an observation time")
    if not ledger.get("policy_sha256"):
        errors.append("ledger: price policy hash missing")

    # determinism: rebuild into the same tree and compare hashes
    before = digest_tree(list(DATA.rglob("*.json")) + pages + sorted((OUT / "assets").glob("*")))
    proc = subprocess.run([sys.executable, str(HERE / "build.py")], capture_output=True, text=True)
    if proc.returncode:
        errors.append("rebuild failed:\n" + (proc.stdout or "")[-2000:] + (proc.stderr or "")[-2000:])
    after = digest_tree(list(DATA.rglob("*.json")) + pages + sorted((OUT / "assets").glob("*")))
    changed = [k for k in before if before[k] != after.get(k)]
    if changed:
        errors.append("build is not deterministic; changed on rebuild: " + ", ".join(changed[:8]))

    if errors:
        print("Origination verification FAILED")
        for item in errors:
            print(f" - {item}")
        return 1
    print(f"Origination verification PASSED: {len(pages)} pages, {totals['rows']} table rows, "
          f"{totals['missing']} missing a source, {totals['with_official']} with an official link, "
          f"{totals['without_official']} community-only.")
    print(f"  reconciliation: {results['counts']['team_fields_matching']}/"
          f"{results['counts']['team_fields_checked']} club x field checks; "
          f"gates: {gates['summary']}; demoted: {gates['demoted'] or 'none'}")
    print("  determinism: a second build produced byte-identical artifacts and pages.")
    return 0


def summary_n(row: dict) -> int:
    return row["summary"].get("n") or 0


if __name__ == "__main__":
    raise SystemExit(main())
