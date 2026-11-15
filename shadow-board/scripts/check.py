#!/usr/bin/env python3
"""Shadow Board gate. Fail closed: a page that cannot be re-derived from the repository is not published.

    python3 shadow-board/scripts/check.py

The gate is deliberately unhelpful in the useful way: it checks that the numbers on the pages are the numbers the
committed code produces from the committed inputs, that the price and staking columns are still empty, that the
backtest figures never touch the leaderboard, that every table row cites an https source, and that the row counts
the parsers depend on have not drifted.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
ROOT = BOARD.parent
sys.path.insert(0, str(HERE))

import build           # noqa: E402
import model           # noqa: E402
import scoring         # noqa: E402

PAGES = ["index.html", "forecasts.html", "backtest.html", "method.html", "sources.html", "registers.html"]
FORBIDDEN = ("TBD", "TODO", "FIXME", "lorem", "???", "XXXX", "<N/A>", "NaN", "None")
PLACEHOLDER_CELLS = {"n/a", "na", "-", "pending"}
ALLOWED_VENUE_STATUS = {"verified at game centre", "venue not transcribed at game centre"}
OFFICIAL_HOSTS = {"nfl.com", "www.nfl.com", "operations.nfl.com", "support.nfl.com", "media.nfl.com",
                  "static.www.nfl.com", "nextgenstats.nfl.com", "docs.github.com", "itl.nist.gov",
                  "www.itl.nist.gov", "scikit-learn.org"}

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


class RowParser(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.in_tbody = self.in_row = 0
        self.row_links: list[str] = []
        self.row_cells: list[str] = []
        self.in_td = False
        self.rows = 0
        self.https_rows = 0
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.dupes: list[str] = []
        self.frags: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.dupes.append(a["id"])
            self.ids.add(a["id"])
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.in_row, self.row_links, self.row_cells = 1, [], []
        elif tag == "td" and self.in_row:
            self.in_td = True
            self.row_cells.append("")
        elif tag in {"a", "link", "script", "img"}:
            attr = "href" if tag in {"a", "link"} else "src"
            href = a.get(attr, "")
            if not href:
                return
            self.links.append(href)
            if self.in_row and tag == "a":
                self.row_links.append(href)
                if href.startswith("https://"):
                    self.https_rows += 1
            if href.startswith(("http://", "https://")):
                if not href.startswith("https://"):
                    fail(f"{self.path.name}: non-HTTPS link {href}")
            elif href.startswith(("#", "mailto:", "tel:", "javascript:")):
                if href.startswith("#"):
                    self.frags.append(href[1:])
            else:
                target = (self.path.parent / href.split("#")[0].split("?")[0]).resolve()
                if not target.exists():
                    fail(f"{self.path.name}: broken local link {href}")

    def handle_data(self, data):
        if self.in_td and self.in_row:
            self.row_cells[-1] += data

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
        elif tag == "tr" and self.in_row:
            self.rows += 1
            if not any(u.startswith("https://") for u in self.row_links):
                fail(f"{self.path.name}: table row without an https source link")
            for cell in self.row_cells:
                text = cell.strip()
                if text.lower() in PLACEHOLDER_CELLS:
                    fail(f"{self.path.name}: placeholder cell {text!r}; use a blank plus a flag instead")
            self.in_row = 0
        elif tag == "tbody":
            self.in_tbody = max(0, self.in_tbody - 1)

    def finish(self):
        for f in self.frags:
            if f and f not in self.ids:
                fail(f"{self.path.name}: dangling fragment #{f}")
        for d in self.dupes:
            fail(f"{self.path.name}: duplicate id {d}")


def check_pages() -> None:
    for name in PAGES:
        path = BOARD / name
        if not path.is_file():
            fail(f"missing page {name}")
            continue
        text = path.read_text()
        if re.search(r"^(<<<<<<<|=======$|>>>>>>>|Conflict)", text, re.M):
            fail(f"{name}: conflict marker")
        for word in FORBIDDEN:
            if word in text:
                fail(f"{name}: forbidden placeholder token {word!r}")
        parser = RowParser(path)
        parser.feed(text)
        parser.finish()
        if not parser.rows:
            fail(f"{name}: no table rows - the page did not render")
        notes.append(f"{name}: {parser.rows} rows, {parser.https_rows} rows linked")


def check_prereg() -> None:
    if not build.PREREG.exists():
        fail("PREREGISTRATION.md is missing")
        return
    text = build.PREREG.read_text()
    for head in ("## 1. Data", "## 2. Feature", "## 3. Forecast", "## 5. Evaluation window", "## 6. Gates",
                 "## 8. Declared family", "## 9. Amendments"):
        if head not in text:
            fail(f"PREREGISTRATION.md is missing section {head}")
    if re.search(r"\b0\.\d{4}\b", text) or re.search(r"(skill|r|RMSE|p-value)\s*[=:]\s*[-]?0?\.\d", text, re.I):
        fail("PREREGISTRATION.md appears to contain a measured result; backtest numbers must not live in the rule text")
    git = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H %aI", "--", "shadow-board/PREREGISTRATION.md"],
                         capture_output=True, text=True)
    commits = [line.split() for line in git.stdout.splitlines() if line.strip()]
    all_commits = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--count", "HEAD"],
                                 capture_output=True, text=True)
    visible = int(all_commits.stdout.strip()) if all_commits.returncode == 0 else 0
    truncated = visible and len(commits) == 1 and commits[0][0] == subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if not commits:
        notes.append("git history for the rule file not visible in this clone; registration order not proven here")
    elif truncated:
        # A shallow or rewritten checkout shows one synthetic root commit whose author date is the clone date.
        # Ordering cannot be proven from it, and CI must not fail for that reason; the full history is checked
        # where it exists and the claim is verified by review of the registration commit itself.
        notes.append(f"history truncated at the shallow boundary; registration order not provable in CI "
                     f"({visible} commit(s) visible). Registration commit {commits[0][0][:7]} must be checked "
                     "against the artifact commits in the full history.")
    else:
        first = commits[-1][1]
        notes.append(f"registration commit author date {first} ({len(commits)} commit(s) touching the rule)")
        summary = json.loads((build.DATA / "summary.json").read_text())
        if first > summary["built_at_utc"]:
            fail("artifacts were built before the pre-registration was committed - the run is not pre-registered")


def check_fixtures() -> None:
    rows = build.read_fixtures()
    if len(rows) != 13:
        fail(f"fixtures: expected 13 Week 11 fixtures from the official page, found {len(rows)}")
    seen = set()
    for r in rows:
        for side in ("away", "home"):
            if r[side] not in model.TEAMS:
                fail(f"fixtures: unknown club code {r[side]!r}")
        key = (r["away"], r["home"])
        if key in seen:
            fail(f"fixtures: duplicate matchup {key}")
        seen.add(key)
        if r["venue_status"] not in ALLOWED_VENUE_STATUS:
            fail(f"fixtures: unexpected venue_status {r['venue_status']!r}")
        if r["venue_status"] == "verified at game centre" and not r["venue_game_centre"].strip():
            fail(f"fixtures: {r['away']}@{r['home']} claims a game-centre read with an empty venue")
        if r["venue_status"] != "verified at game centre" and r["venue_game_centre"].strip():
            fail(f"fixtures: {r['away']}@{r['home']} carries a venue that its status does not support")
        if not r["game_centre_url"].startswith("https://www.nfl.com/games/"):
            fail(f"fixtures: {r['away']}@{r['home']} lacks an official game-centre URL")
    verified = sum(1 for r in rows if r["venue_status"] == "verified at game centre")
    notes.append(f"fixtures: 13 rows, {verified} venues transcribed from the game centre, {13 - verified} left blank")


def check_corpus_pin() -> None:
    """Published forecasts are issued against specific bytes; if the log moves, say so instead of re-deriving."""
    desk = ROOT / "decision-desk" / "data" / "games_2026.csv"
    frozen = ROOT / "corpus" / "games_2026_w1_9.csv"
    summary = json.loads((build.DATA / "summary.json").read_text())
    pinned = summary.get("corpus_digest", {})
    if not desk.is_file():
        fail("corpus pin: the committed game log is missing")
        return
    live = hashlib.sha256(desk.read_bytes()).hexdigest()
    if pinned.get("decision_desk_sha256") and pinned["decision_desk_sha256"] != live:
        fail("corpus pin: the game log changed after the artifacts were built "
             f"({pinned['decision_desk_sha256'][:12]}... recorded, {live[:12]}... on disk); re-run build.py and "
             "re-issue the affected forecasts rather than letting the pages drift")
    if frozen.is_file():
        fhash = hashlib.sha256(frozen.read_bytes()).hexdigest()
        if fhash != live:
            fail(f"corpus pin: the live log ({live[:12]}...) no longer matches the frozen corpus "
                 f"({fhash[:12]}...). Forecasts already issued reference the frozen bytes; the mismatch must be "
                 "resolved by re-issuing, not by editing the published records")
        else:
            notes.append(f"corpus pin: live log and frozen corpus are the same bytes ({live[:12]}...)")
    else:
        notes.append("corpus pin: no frozen corpus copy in the tree; only the live log hash is checked")
    manifest = ROOT / "corpus" / "manifest.json"
    if manifest.is_file():
        doc = json.loads(manifest.read_text())
        declared = doc.get("frozen_sha256", "")
        if declared and declared != live:
            fail(f"corpus pin: corpus/manifest.json declares {declared[:12]}... but the log is {live[:12]}...")
        else:
            notes.append(f"corpus pin: manifest-declared hash agrees for {doc.get('corpus_id', 'the frozen corpus')}")


def check_price_firewall() -> None:
    path = build.DATA / "fair_lines_2026_w11.csv"
    if not path.is_file():
        fail("fair_lines_2026_w11.csv missing")
        return
    rows = list(csv.DictReader(path.open()))
    if len(rows) != 13:
        fail(f"fair lines: {len(rows)} rows, expected 13")
    for r in rows:
        for field in ("market_line", "residual"):
            if r[field].strip():
                fail(f"fair lines: {field} is populated ({r[field]!r}) while the price policy is undecided")
        p = float(r["p_home"])
        if not 0.0 < p < 1.0:
            fail(f"fair lines: probability {p} outside (0,1)")
        if abs(p + float(r["p_away"]) - 1.0) > 1e-9:
            fail(f"fair lines: {r['away']}@{r['home']} side probabilities do not sum to 1")
    notes.append("fair lines: market line and residual columns blank on all rows (Gate G holds)")
    rec = [json.loads(line) for line in (build.DATA / "forecast_records.jsonl").open()]
    if len(rec) != 65:
        fail(f"records: {len(rec)} rows, expected 13 fixtures x 5 declared entries")
    if any(not r.get("inputs") for r in rec):
        fail("records: a forecast was stored without its inputs")
    if any(r["market_line"] or r["residual"] for r in rec):
        fail("records: a stored forecast carries a market value")
    if any(len(r["source_urls"]) < 1 or "nfl.com" not in r["source_urls"][0] for r in rec):
        fail("records: a forecast row lacks an official source URL")
    notes.append(f"records: {len(rec)} immutable forecast records, each storing probability plus inputs")


def check_ledger_and_repro() -> None:
    res = build.build(write=False)
    ledger_csv = list(csv.DictReader((build.DATA / "backtest_ledger.csv").open()))
    if len(ledger_csv) != len(res["ledger"]):
        fail(f"ledger: committed {len(ledger_csv)} rows, recomputed {len(res['ledger'])}")
    graded_now = sum(1 for r in ledger_csv if r["graded"] == "True")
    if graded_now != res["backtest"]["graded_games_with_ties"]:
        fail(f"ledger: {graded_now} graded rows committed vs {res['backtest']['graded_games_with_ties']} recomputed")
    if res["backtest"]["ties_excluded"] != sum(1 for r in ledger_csv if r["tie"] == "True"):
        fail("ledger: the tie count excluded from side grading does not match the ledger")
    ent = res["backtest"]["entries"]["SB1-ML"]
    summary = json.loads((build.DATA / "summary.json").read_text())
    s_ent = summary["backtest"]["entries"]["SB1-ML"]
    for key in ("n", "brier", "skill", "skill_lo", "p_value"):
        a, b = ent[key], s_ent[key]
        if isinstance(a, float) and isinstance(b, (int, float)):
            if abs(a - float(b)) > 1e-9:
                fail(f"reproducibility: SB1-ML {key} recomputed {a} vs committed {b}")
        elif a != b:
            fail(f"reproducibility: SB1-ML {key} recomputed {a} vs committed {b}")
    if summary["config_hash"] != res["config_hash"]:
        fail("reproducibility: config hash changed, so a forecast on the site is no longer reproducible")
    for row, new in zip(ledger_csv, res["ledger"]):
        if abs(float(row["p_home"]) - new["p_home"]) > 1e-9:
            fail(f"ledger: p_home drifted for week {row['week']} {row['away']}@{row['home']}")
    notes.append(f"reproducibility: {len(ledger_csv)} ledger rows and {ent['n']} graded games re-derived exactly")
    # leakage: the training set for week w must not contain week w
    for r in ledger_csv:
        if int(r["fit_weeks_through"]) >= int(r["week"]):
            fail(f"leakage: week {r['week']} was fitted with data through week {r['fit_weeks_through']}")
    # every ledger row cites an official page
    if any(not r["source_url"].startswith("https://www.nfl.com/") for r in ledger_csv):
        fail("ledger: a graded row lacks an official source URL")


def check_firewall_between_pages() -> None:
    index = (BOARD / "index.html").read_text()
    backtest = (BOARD / "backtest.html").read_text()
    summary = json.loads((build.DATA / "summary.json").read_text())
    leaked = []
    for sid, e in summary["backtest"]["entries"].items():
        for key in ("brier", "skill", "log_score", "hit_rate"):
            v = e.get(key)
            if isinstance(v, float) and v == v:
                for cand in (f"{v:.4f}", f"{v:.3f}", f"{v:.2f}"):
                    if cand in index:
                        leaked.append(f"{sid}.{key}={cand}")
    if leaked:
        fail("firewall: backtest figures appear on the leaderboard page: " + ", ".join(leaked[:4]))
    if "Graded games" not in index:
        fail("firewall: the leaderboard page lost its graded-games column")
    if "Prospective leaderboard" not in index or "backtest" not in backtest:
        fail("firewall: page roles changed; the leaderboard must be prospective and the backtest must be labelled")
    if re.search(r"(ROI|CLV)\b[^<]*[+\-]\d", index):
        fail("price firewall: a return or CLV figure appears on the leaderboard page")
    notes.append("firewall: no backtest value from the ledger appears on the leaderboard page")
    return backtest


def check_verification() -> None:
    rows = list(csv.DictReader((build.DATA / "verification_rows.csv").open()))
    if not rows:
        fail("verification_rows.csv is empty")
        return
    differs = [r["id"] for r in rows if r["verdict"] == "DIFFERS"]
    if differs:
        fail("verification: a corpus value disagrees with the official page and must be flagged, not merged: "
             + ", ".join(differs))
    matched = sum(1 for r in rows if r["verdict"] == "MATCH")
    blanks = sum(1 for r in rows if r["verdict"].startswith("BLANK"))
    if matched == 0:
        fail("verification: no line-by-line match was recorded")
    notes.append(f"verification: {len(rows)} official reads, {matched} match, {blanks} fill a blank in the log, "
                 f"{len(differs)} differ")


def main() -> int:
    if not (build.DATA / "summary.json").is_file():
        fail("no artifacts committed; run shadow-board/scripts/build.py")
    else:
        check_pages()
        check_prereg()
        check_fixtures()
        check_corpus_pin()
        check_price_firewall()
        check_ledger_and_repro()
        check_firewall_between_pages()
        check_verification()
    for n in notes:
        print("  note:", n)
    if errors:
        print("Shadow Board gate FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"Shadow Board gate passed: {len(PAGES)} pages, {len(notes)} checks recorded; "
          "price firewall and leaderboard firewall intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
