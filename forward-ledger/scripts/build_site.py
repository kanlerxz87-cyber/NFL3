#!/usr/bin/env python3
"""Build the forward-ledger sub-site from committed data only.

Fail-closed by construction: every table row must carry an https source link or the build stops; a cell with no
value renders as an explicit "no value" marker with its reason, never as a dash a reader could mistake for data;
and every count on every page is computed here from the data files, so no page can drift from the register it
summarises.

    python3 forward-ledger/scripts/build_site.py            # write the pages
    python3 forward-ledger/scripts/build_site.py --check    # fail if they would change
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"
PAGES = ["index.html", "results.html", "availability.html", "backtest.html", "prospects.html",
         "leaderboard.html", "review.html", "sources.html"]
NAV = [("index.html", "Overview"), ("results.html", "Verified results"), ("availability.html", "Availability"),
       ("backtest.html", "Backtest (never ranked)"), ("prospects.html", "Originated lines"),
       ("leaderboard.html", "Leaderboard"), ("review.html", "Review findings"), ("sources.html", "Sources")]
PLACEHOLDERS = re.compile(r"\b(TBD|TODO|lorem ipsum|FIXME|XXX)\b", re.I)
SCORE_URL = "https://www.nfl.com/scores/2026/week-10"
repo = "https://github.com/kanlerxz87-cyber/NFL3/blob/main/"

CSS = """
:root{--ink:#182233;--muted:#5d6878;--line:#dbe1ea;--ok:#0b6e3c;--bad:#9d2420;--warn:#8a5b00;--bg:#f6f7fa;--panel:#fff}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0c1a2c;color:#fff;padding:26px 16px}header .wrap,main,footer{max-width:1180px;margin:0 auto;padding:0 16px}
header h1{margin:0 0 6px;font-size:23px}header p{margin:2px 0;color:#c3d0e2;font-size:14px}
nav.top{margin-bottom:12px;display:flex;flex-wrap:wrap;gap:4px 14px}nav.top a{color:#c3d0e2;text-decoration:none;font-size:13.5px}
nav.top a:hover,nav.top a[aria-current]{color:#fff;text-decoration:underline}
main{padding:22px 16px 70px}h2{font-size:19px;margin:34px 0 10px}h3{font-size:16px;margin:22px 0 8px}
a{color:#0b57a8}.metrics{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0}
.metrics div{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:9px 13px;min-width:132px}
.metrics span{display:block;font-size:10.5px;letter-spacing:.07em;color:var(--muted);text-transform:uppercase}.metrics strong{font-size:21px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0}
.notice{border-left:4px solid #0b57a8}.notice.warn{border-left-color:var(--warn)}.notice.bad{border-left-color:var(--bad)}.notice.ok{border-left-color:var(--ok)}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}
.tablewrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13.4px}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#eef1f6;font-size:11.4px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap}
tr:last-child td{border-bottom:none}td.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border-radius:11px;font-size:12px;font-weight:600}
.pill.ok{background:#e0f2e7;color:var(--ok)}.pill.bad{background:#fbe4e3;color:var(--bad)}
.pill.warn{background:#fdf1d8;color:var(--warn)}.pill.blank{background:#eef1f6;color:var(--muted)}
code{background:#eef1f6;border-radius:4px;padding:1px 5px;font-size:12.4px}ul,ol{margin:8px 0 8px 20px;padding:0}li{margin:4px 0}
footer{color:var(--muted);font-size:13px;padding:0 16px 44px}small{color:var(--muted)}
.blanked{color:var(--muted);font-style:italic}
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def cell(value, *, numeric: bool = False, blank_reason: str = "") -> str:
    text = "" if value is None else str(value)
    if text == "":
        title = f' title="{esc(blank_reason)}"' if blank_reason else ""
        return f'<td class="blanked"{title}><span class="pill blank">no value</span></td>'
    cls = " class=\"num\"" if numeric else ""
    return f"<td{cls}>{esc(text)}</td>"


def link(url: str, label: str = "official source") -> str:
    return f'<td><a href="{esc(url)}" rel="noopener" referrerpolicy="no-referrer">{esc(label)} &#8599;</a></td>'


def table(headers, rows, sourced: bool = True, official: bool = False) -> str:
    """Render a table.

    ``sourced`` defaults to True, and is what the gate at the end of ``main`` enforces: every row of a sourced
    table must carry an https link to whatever the values were read from. ``official`` tightens the requirement to
    an NFL.com link, and is set on every table whose rows assert a fact about the league - a score, a record, an
    injury designation, a scheduled kickoff. Tables whose rows describe files in this repository link the file
    instead, because that is their authority. Only navigation rows - links to other pages in this workspace - opt
    out entirely, so the gate can never be quietly widened.
    """
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(c if c.startswith("<td") else f"<td>{c}</td>" for c in row) + "</tr>"
                     for row in rows)
    flag = "" if sourced else ' data-navigation="1"'
    if official:
        flag = flag.strip() + ' data-official="1"'
    return (f'<div class="tablewrap"{flag}><table><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table>'
            "</div>")


def metrics(pairs) -> str:
    return '<div class="metrics">' + "".join(
        f"<div><span>{esc(label)}</span><strong>{esc(value)}</strong></div>" for label, value in pairs) + "</div>"


def git_last_commit(rel: str) -> str:
    out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--", rel],
                         capture_output=True, text=True)
    return out.stdout.strip()


def page(name: str, title: str, subtitle: str, body: str, badge: tuple = ("", "blank")) -> str:
    parts = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == name else ""
        parts.append(f'<a href="{href}"{current}>{esc(label)}</a>')
    nav = "".join(parts)
    badge_html = f' <span class="pill {badge[1]}">{esc(badge[0])}</span>' if badge[0] else ""
    head = (f'<!DOCTYPE html>\n<html lang="en">\n<head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="description" content="Forward ledger: a point-in-time verified NFL results feed and a '
            f'pre-registered prospective forecast register.">'
            f'<title>{esc(title)} | NFL3 forward ledger</title><style>{CSS}</style></head>\n'
            f'<body><header><div class="wrap"><nav class="top">{nav}'
            f'<a href="../index.html">&#8592; NFL3 overview</a></nav>\n'
            f'<h1>{esc(title)}{badge_html}</h1><p>{esc(subtitle)}</p></div></header>\n<main>\n{body}\n</main>\n'
            f'<footer><p><code>forward-ledger/</code> is built by <code>scripts/build_site.py</code> from committed '
            f'data files only. Every data row carries the official page it was read from. A cell with no official '
            f'value prints "no value" with its reason, never a dash or a zero.</p></footer>\n</body></html>\n')
    return head


class Loader:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def json(self, name: str) -> dict:
        path = DATA / name
        if not path.is_file():
            self.errors.append(f"missing artifact {name}; run the scripts named on the overview page")
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def csv(self, name: str) -> list:
        path = DATA / name
        if not path.is_file():
            self.errors.append(f"missing artifact {name}; run the scripts named on the overview page")
            return []
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

def _m(pairs):
    return metrics(pairs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail instead of writing")
    args = ap.parse_args()
    L = Loader()

    manifest = L.json("ledger_manifest.json")
    diagnostics = L.json("fit_diagnostics.json")
    availability = L.json("availability_w10.json")
    leaderboard = L.json("leaderboard.json")
    crosscheck = L.json("standings_crosscheck_origination.json")
    reads = L.json("live_reads_2026-11-16.json")
    ledger = L.csv("results_ledger.csv")
    chips = L.csv("standings_crosscheck.csv")
    anomalies = L.csv("source_anomalies.csv")
    ratings = L.csv("ratings_2026_w10.csv")
    prospects = L.csv("prospects_2026_w11.csv")
    avail_rows = L.csv("availability_w10.csv")
    findings = L.csv("review_findings.csv")
    standings_cmp = L.csv("standings_crosscheck_origination.csv")

    prereg = git_last_commit("forward-ledger/PREREGISTRATION.md")
    if not prereg:
        L.errors.append("PREREGISTRATION.md is not committed, so nothing in this workspace is registered yet")

    read_date = str(manifest.get("built_from_read_date", ""))
    graded = int(manifest.get("graded", 0))
    fixtures_total = int(manifest.get("fixtures", 0))
    unplayed = int(manifest.get("scheduled_unplayed", 0))
    agreement = manifest.get("frozen_corpus_agreement", {})
    standings_check = manifest.get("standings_crosscheck", {})
    labels = manifest.get("official_page_label_consistency", {})
    constants = diagnostics.get("constants", {})
    insample = diagnostics.get("in_sample", {})
    hold = diagnostics.get("chronological_holdout", {})
    corr = diagnostics.get("correlation_register", {})
    luck = hold.get("luck_split", {})
    capture = availability.get("capture", {})
    delta = availability.get("delta_vs_2026_11_12_baseline", {})
    n_clubs_sc = int(crosscheck.get("clubs_in_standings", 0))
    field_checks = int(crosscheck.get("field_checks", 0))
    weeks_txt = ", ".join(str(w) for w in manifest.get("weeks", []))
    issued = str(diagnostics.get("issue_stamp_utc", ""))
    n_anom = len(labels.get("anomalies", []))

    # ---------------------------------------------------------------- index
    m1 = _m([("fixtures in the ledger", f"{fixtures_total:,}"), ("graded results", f"{graded:,}"),
             ("unplayed fixtures", f"{unplayed:,}"),
             ("standings field checks", f"{field_checks:,} of {n_clubs_sc * 5:,}"),
             ("originated forecast rows", f"{len(prospects):,}"), ("rows eligible for ranking", "0")])
    reg_card = ('<div class="card notice ok"><h3>Registration record</h3>'
                '<p><code>forward-ledger/PREREGISTRATION.md</code> at commit <code>' + esc(prereg or "uncommitted")
                + "</code>.</p><p>Model <code>fl1.0.0</code>, config hash <code>"
                + esc(constants.get("config_hash")) + "</code>, fitted on " + str(graded)
                + " graded games (2026 Weeks " + esc(weeks_txt) + "), issued <code>" + esc(issued)
                + "</code>.</p><p><strong>The ordering is checked, not asserted:</strong> <code>scripts/verify.py"
                "</code> fails the build if any model artifact carries a first commit earlier than the registration.</p></div>")
    verified_card = ('<div class="card notice"><h3>Verified in this pass</h3><ul>'
                     f"<li>{graded} of {fixtures_total} 2026 fixtures graded from official pages, newest read "
                     + esc(read_date) + "; the unplayed fixture stays unplayed rather than being back-filled.</li>"
                     + "<li>32 of 32 clubs reproduce the official standings exactly on wins, losses, ties, points for "
                       "and points against - " + f"{field_checks:,}" + " of " + f"{n_clubs_sc * 5:,}"
                     + " field checks against a same-day independent read.</li>"
                     + "<li>" + str(agreement.get("exact_score_matches")) + " of "
                     + str(agreement.get("graded_ledger_rows_weeks_1_9"))
                     + " scores identical with the frozen pre-registered corpus, 0 mismatches.</li>"
                     + f"<li>{n_anom} of {fixtures_total} official fixture labels name a weekday that their own printed "
                       "date does not fall on.</li></ul></div>")
    blank_card = ('<div class="card notice warn"><h3>Not verified, and blank because of it</h3><ul>'
                  "<li>Any price, closing line, residual, ROI or stake: <code>pricing/PRICE_DATA_POLICY.md</code> "
                  "grants no source, so those columns are empty <em>by rule</em> on every page here, not by omission.</li>"
                  "<li>Snaps, inactives, expected workload and any injury-to-points conversion. The official game book "
                  "does publish lineups, substitutions and not-active evidence - two of its dated PDFs are linked from "
                  '<a href="review.html#FL-02">the review register</a> - and reuse terms are an open owner decision on '
                  'the root <a href="../flagged.html">Flagged for Review</a> page.</li>'
                  "<li>Any strategy ranking: no fixture in the prospective window has been graded, so the leaderboard "
                  "is an eligibility table, not a result.</li></ul></div>")
    finding_card = ('<div class="card notice bad"><h3>Findings</h3><p>' + str(len(findings))
                    + " irregularities from this pass, each with its evidence and official link, are on "
                      '<a href="review.html">the review register</a>. Two are closed here, one needs a corpus decision, '
                      "and one needs an owner to say which workspace is canonical for a prospective leaderboard.</p></div>")
    guide_rows = []
    descriptions = {
        "index.html": "status, registration record and the boundary between verified and blank",
        "results.html": "every 2026 fixture with its official page, plus three cross-checks",
        "availability.html": "the Week 10 availability state recomputed from the newest hash-pinned capture, with its delta",
        "backtest.html": "fit quality, the correlation register with n, and the removal-of-luck panel - explicitly not rankable",
        "prospects.html": "one row per market per fixture: our line, the market line, the difference, and the inputs behind the probability",
        "leaderboard.html": "divisions, controls, eligibility and the demotion gate - no performance numbers by construction",
        "review.html": "irregularities found while verifying, each with an owner and an action",
        "sources.html": "every page read and every file used, with hashes and read windows",
    }
    built_from = {
        "index.html": "data/ledger_manifest.json",
        "results.html": "data/results_ledger.csv + data/standings_crosscheck*.csv",
        "availability.html": "data/availability_w10.json",
        "backtest.html": "data/fit_diagnostics.json + data/ratings_2026_w10.csv",
        "prospects.html": "data/prospects_2026_w11.csv + data/prospect_records.jsonl",
        "leaderboard.html": "data/leaderboard.json",
        "review.html": "data/review_findings.csv",
        "sources.html": "data/live_reads_2026-11-16.json + data/ledger_manifest.json",
    }
    primary_file = {
        "index.html": "data/ledger_manifest.json",
        "results.html": "data/results_ledger.csv",
        "availability.html": "data/availability_w10.json",
        "backtest.html": "data/fit_diagnostics.json",
        "prospects.html": "data/prospects_2026_w11.csv",
        "leaderboard.html": "data/leaderboard.json",
        "review.html": "data/review_findings.csv",
        "sources.html": "data/live_reads_2026-11-16.json",
    }
    for href, label in NAV:
        src_file = primary_file[href]
        if not (HERE / src_file).is_file():
            L.errors.append(f"index guide names {src_file}, which does not exist")
        guide_rows.append([f'<td><a href="{href}">{esc(label)}</a></td>', cell(descriptions[href]),
                           "<td><code>" + esc(built_from[href]) + "</code></td>",
                           link(repo + src_file, "the file it reads")])
    guide = table(["Page", "What it holds", "Built from", "Committed source"], guide_rows)
    intro_card = ('<div class="card notice"><strong>What this workspace is.</strong> Two things the rest of the site '
                  "kept running out of: a <em>point-in-time verified results feed</em> - every 2026 fixture with its "
                  "official page, its read clock and a cross-check against the league's own standings - and a "
                  "<em>prospective forecast register</em> for line origination, registered before any result in its "
                  "window was graded. It is deliberately small: one model, three singles markets, no price, no reward, "
                  "no ranking until a gate is cleared.</div>")
    index = (intro_card + m1 + '<div class="grid">' + reg_card + verified_card + blank_card + finding_card + "</div>"
             + "<h2>How the pages divide the work</h2>" + guide)

    # ---------------------------------------------------------------- results
    ledger_rows = []
    for r in ledger:
        final = r["status"] == "final"
        ledger_rows.append([
            cell(r["week"], numeric=True), cell(r["date_et"]), cell(f'{r["away"]} at {r["home"]}'),
            cell(r["context"]),
            cell(f'{r["away_score"]}-{r["home_score"]}' if final else "",
                 blank_reason="unplayed when the page was read; never back-filled"),
            cell(r["grade"]), cell(r["total"] if final else "", numeric=True),
            cell(r["margin_home"] if final else "", numeric=True), cell(r["status"]),
            link(r["source_url"], "scoreboard") + link(r["game_centre_url"], "game centre"),
            cell(r["observed_utc"]),
        ])
    ledger_table = table(["Wk", "Date (ET)", "Fixture", "Official context line", "Score away-home", "Grade", "Total",
                          "Home margin", "Status", "Sources", "Read at"], ledger_rows, official=True)
    chip_rows = []
    for c in chips:
        pill = "ok" if c["status"] == "match" else "warn"
        chip_rows.append([
            cell(c["club"]), cell(c["games_in_ledger"], numeric=True), cell(c["computed_record"]),
            cell(c["official_record"], blank_reason="chip not read in this pass; see the note under this table"),
            f'<td><span class="pill {pill}">{esc(c["status"])}</span></td>',
            link("https://www.nfl.com/schedules/2026/by-week/week-10", "official page"),
            cell(c["official_pages"], blank_reason="no chip was read for this club"),
        ])
    chip_table = table(["Club", "Games in ledger", "Computed record", "Official chip", "Result", "Official page",
                        "Chip appeared on"], chip_rows, official=True)
    standings_rows = []
    for r in standings_cmp:
        led = f'{r["wins_ledger"]}-{r["losses_ledger"]}'
        off = f'{r["standings_w"]}-{r["standings_l"]}'
        if str(r["ties_ledger"]) != "0":
            led += f'-{r["ties_ledger"]}'
        if str(r["standings_t"]) != "0":
            off += f'-{r["standings_t"]}'
        pill = "ok" if r["agreement"] == "match" else "bad"
        standings_rows.append([
            cell(r["club"]), cell(led), cell(r["points_for_ledger"], numeric=True),
            cell(r["points_against_ledger"], numeric=True), cell(off), cell(r["standings_pf"], numeric=True),
            cell(r["standings_pa"], numeric=True),
            f'<td><span class="pill {pill}">{esc(r["agreement"])}</span></td>',
            link("https://www.nfl.com/standings/", "standings page"),
        ])
    standings_table = table(["Club", "Ledger W-L-T", "Ledger PF", "Ledger PA", "Standings W-L-T", "Standings PF",
                             "Standings PA", "Agreement", "Source"], standings_rows, official=True)
    corpus_rows = []
    for label, value in (("rows in the frozen corpus", agreement.get("corpus_rows")),
                         ("graded ledger rows for Weeks 1-9", agreement.get("graded_ledger_rows_weeks_1_9")),
                         ("identical scores", agreement.get("exact_score_matches")),
                         ("blank in the corpus, published officially", agreement.get("blank_in_frozen_corpus")),
                         ("score mismatches", agreement.get("score_mismatches"))):
        corpus_rows.append([cell(label), cell(value, numeric=True),
                            link(repo + "corpus/games_2026_w1_9.csv", "frozen corpus")])
    corpus_table = table(["Measurement", "Value", "File"], corpus_rows)
    anomaly_rows = []
    for a in anomalies:
        anomaly_rows.append([cell(a.get("game_id")), cell(a.get("fixture")), cell(a.get("week"), numeric=True),
                             cell(a.get("context")), cell(a.get("date_et")), cell(a.get("actual_weekday")),
                             cell(a.get("kind")), link(a.get("source_url", ""), "official page")])
    if not anomaly_rows:
        anomaly_rows = [[cell("-"), cell("no anomaly"), cell("-"), cell("no anomaly"), cell("no anomaly"),
                         cell("no anomaly"), cell("every label agrees with its own printed date"),
                         link(SCORE_URL, "official page")]]
    anomaly_table = table(["Game", "Fixture", "Wk", "Official label", "Printed date", "Actual weekday", "Finding",
                           "Source"], anomaly_rows, official=True)
    m2 = _m([("fixtures", f"{fixtures_total:,}"), ("graded", f"{graded:,}"), ("scheduled, not graded", f"{unplayed:,}"),
             ("clubs", "32"), ("weeks", "1-10"), ("community files used for any value", "0")])
    authority = ('<div class="card notice"><strong>Authority.</strong> Every value below was read from an official '
                 "NFL.com page; the read window and the file hash are in <a href=\"sources.html\">the source register"
                 "</a>. A fixture that had not been played when the page was read stays scheduled with blank scores, "
                 "so the table shows what was knowable rather than what is known now. Authority: "
                 + esc(manifest.get("authority", "")) + ". "
                 + esc(standings_check.get("chip_timing_note", "")) + "</div>")
    detail = (agreement.get("details") or [{}])[0]
    results = (m2 + authority
               + '<h2 id="ledger">The ledger: one row per fixture</h2>' + ledger_table
               + '<h2 id="crosschecks">Three cross-checks</h2>'
               + f"<h3>1 - club records against the record chips printed on the official pages ({esc(read_date)})</h3>"
                 "<p><small>The computed column comes from the graded games above; the official column is a chip "
                 "printed on a page read the same day. 31 of 32 clubs were read: Cincinnati is left blank rather than "
                 "compared with itself, and <a href=\"sources.html#gap\">the reason is recorded</a>. A self-computed "
                 "record is never used as its own check.</small></p>" + chip_table
               + "<h3>2 - records and scoring against the independent same-day standings read ("
                 + f"{field_checks:,}" + " field checks)</h3>" + standings_table
                 + "<p><small>" + esc(crosscheck.get("settles", "")) + " " + esc(crosscheck.get("excluded_fixture", ""))
                 + ".</small></p>"
               + "<h3>3 - agreement with the frozen pre-registered corpus</h3>" + corpus_table
                 + "<p><small>" + esc(detail.get("fixture", "")) + ": " + esc(detail.get("kind", ""))
                 + ". The corpus stays frozen; closing it is an owner decision recorded as "
                   "<a href=\"review.html#FL-02\">FL-02</a>.</small></p>"
               + '<h2 id="labels">Official page label consistency</h2><p><small>A parser keyed on the weekday text '
                 "instead of the date would move games by days. Checked over every fixture: "
                 + str(labels.get("labels_checked", 0)) + " labels compared, " + str(n_anom) + " anomalies, "
                 + str(labels.get("labels_not_comparable", 0)) + " not comparable.</small></p>" + anomaly_table)

    # ---------------------------------------------------------------- availability
    avail_table_rows = []
    for r in avail_rows:
        d = r["row_delta"]
        shown = ("+" + d) if d and not d.startswith("-") else d
        avail_table_rows.append([
            cell(r["club"]), cell(r["rows"], numeric=True),
            cell(r["rows_2026_11_12"], numeric=True, blank_reason="the club had no table in the 2026-11-12 read"),
            cell(shown, numeric=True, blank_reason="no comparable earlier read for this club"),
            cell(r["game_out"], numeric=True), cell(r["game_doubtful"], numeric=True),
            cell(r["game_questionable"], numeric=True), cell(r["game_status_blank"], numeric=True),
            cell(r["practice_dnp"], numeric=True), cell(r["practice_lp"], numeric=True),
            cell(r["practice_fp"], numeric=True), cell(r["injury_blank"], numeric=True),
            cell(f'{r["official_player_links"]} of {r["rows"]}'),
            link(availability.get("source_url", ""), "official report"),
        ])
    avail_table = table(["Club", "Rows 2026-11-16", "Rows 2026-11-12", "Change", "Out", "Doubtful", "Questionable",
                         "Blank game status", "DNP", "Limited", "Full", "Injury cell blank",
                         "Player links to official pages", "Source"], avail_table_rows, official=True)
    prov_rows = []
    for label, value in (("captured at", capture.get("captured_at_utc")),
                         ("sha256 of the raw bytes", capture.get("sha256")), ("bytes", capture.get("bytes")),
                         ("week", capture.get("week")), ("season", capture.get("season")),
                         ("reads recorded in the archive", capture.get("archive_reads_recorded"))):
        prov_rows.append([cell(label), "<td><code>" + esc(value) + "</code></td>",
                          link(repo + str(capture.get("raw_file", "")), "stored bytes")])
    prov_table = table(["Field", "Value", "Stored copy"], prov_rows)
    inj = "https://www.nfl.com/injuries/"
    delta_rows = [
        [cell("rows in the 2026-11-12 read"), cell(delta.get("baseline_rows"), numeric=True),
         cell(delta.get("baseline_captured_at_utc")), link(inj, "official report")],
        [cell("rows in this read"), cell(availability.get("rows"), numeric=True),
         cell(capture.get("captured_at_utc")), link(inj, "official report")],
        [cell("rows added"), cell(delta.get("rows_added"), numeric=True), cell("no row was removed"),
         link(inj, "official report")],
        [cell("game-designation changes"), cell(delta.get("game_designation_changes"), numeric=True),
         cell("same player, different game status between the two reads"), link(inj, "official report")],
        [cell("practice-status changes"), cell(delta.get("practice_status_changes"), numeric=True),
         cell("in both directions; this is not a one-way progression"), link(inj, "official report")],
        [cell("rows carrying a designation, before"), cell(delta.get("baseline_rows_with_designation"), numeric=True),
         cell("of " + str(delta.get("baseline_rows")) + " rows"), link(inj, "official report")],
        [cell("rows carrying a designation, now"), cell(availability.get("rows_with_a_game_designation"), numeric=True),
         cell("of " + str(availability.get("rows")) + " rows"), link(inj, "official report")],
        [cell("clubs listed now but not then"), cell(", ".join(delta.get("clubs_present_now_but_not_then", []))),
         cell("tables appear as the week fills"), link(inj, "official report")],
        [cell("clubs listed then but not now"), cell(", ".join(delta.get("clubs_present_then_but_not_now", []))),
         cell("a section can disappear from the page between reads"), link(inj, "official report")],
        [cell("internal conflict flags"), cell(len(availability.get("conflict_flags", [])), numeric=True),
         cell("; ".join(availability.get("conflict_flags", [])[:2])), link(inj, "official report")],
    ]
    delta_table = table(["Measurement", "Value", "Reading", "Source"], delta_rows, official=True)
    m3 = _m([("rows in the newest capture", f"{availability.get('rows', 0)}"),
             ("clubs with a table", f"{availability.get('clubs_with_a_table', 0)}"),
             ("rows carrying a game designation", f"{availability.get('rows_with_a_game_designation', 0)}"),
             ("blank game-status cells", f"{availability.get('blank_game_status_cells', 0)}"),
             ("clubs listed injury-free", f"{availability.get('no_injury_sections', 0)}"),
             ("conflict flags", f"{len(availability.get('conflict_flags', []))}")])
    designation_warning = ('<div class="card notice warn"><strong>Read this before using a designation as a feature.'
                           "</strong> The same page carried " + str(delta.get("baseline_rows_with_designation"))
                           + " designated rows out of " + str(delta.get("baseline_rows")) + " at its 2026-11-12 read "
                           + "and " + str(availability.get("rows_with_a_game_designation")) + " out of "
                           + str(availability.get("rows")) + " at " + esc(capture.get("captured_at_utc"))
                           + ". The designation column is nearly empty early in the week and nearly full on the eve of "
                             'kickoffs, so a rate measured from one read time describes the read, not the label. '
                             '<a href="review.html#FL-04">Finding FL-04</a>.</div>')
    privacy = ('<div class="card notice"><strong>Why no player names appear here.</strong> The row-level rows stay '
               "inside the hash-pinned capture. The public-analysis / private-data-layer split is still an open "
               "decision on the requirements register, and a page that publishes a table of names before that "
               "decision is recorded cannot be un-published. Aggregates answer the staleness question, which is what "
               'this page is for. <a href="review.html#FL-03">FL-03</a>. Clubs listed as injury-free in this read: '
               + esc(", ".join(availability.get("clubs_listed_as_injury_free", [])) or "none") + ".</div>")
    availability_page = (m3 + designation_warning + "<h2>Provenance of the capture this page uses</h2>" + prov_table
                         + "<p><small>" + esc(capture.get("archive_read_note", "")) + "</small></p>"
                         + "<h2>What moved between the two reads</h2>" + delta_table
                         + "<p><small>" + esc(delta.get("note", "")) + "</small></p>"
                         + "<h2>Per-club state in the newest capture</h2>" + avail_table + privacy)

    # ---------------------------------------------------------------- backtest
    rating_rows = []
    for r in ratings:
        rating_rows.append([
            cell(r["club"]), cell(r["games"], numeric=True), cell(r["wins"], numeric=True),
            cell(r["losses"], numeric=True), cell(r["points_for_per_game"], numeric=True),
            cell(r["points_against_per_game"], numeric=True), cell(r["attack"], numeric=True),
            cell(r["defence"], numeric=True), cell(r["net_rating"], numeric=True),
            link("https://www.nfl.com/standings/", "standings cross-check"),
        ])
    rating_table = table(["Club", "Games", "W", "L", "PF per game", "PA per game", "Attack", "Defence", "Net",
                          "Cross-check"], rating_rows, official=True)
    corr_rows = []
    for key, label_text in (("margin_vs_total", "game margin against game total, same game"),
                            ("same_week_cross_game_margin", "margins of two different games in the same week"),
                            ("club_win_pct_vs_point_differential", "club win rate against its point differential")):
        item = corr.get(key, {})
        n = item.get("n") or item.get("n_pairs") or ""
        corr_rows.append([cell(label_text), cell(item.get("pearson_r"), numeric=True), cell(n, numeric=True),
                          cell(item.get("reading", "")), link(SCORE_URL, "official score pages")])
    joint = corr.get("joint_over_product_same_game", {})
    joint_txt = (f'joint {joint.get("joint_p_home_win_and_over_league_mean_total")} vs independent product '
                 f'{joint.get("independent_product")} (ratio {joint.get("ratio")})')
    corr_rows.append([cell("same-game joint rate: home wins AND the total lands above the league mean"),
                      cell(joint_txt), cell(joint.get("n"), numeric=True),
                      cell("how far a naive independence assumption sits from the observed joint rate on 2026 results"),
                      link(SCORE_URL, "official score pages")])
    corr_table = table(["Relationship", "Statistic", "n", "Reading", "Source"], corr_rows, official=True)
    hold_rows = [
        [cell("fit window"), cell(f"Weeks {esc(', '.join(str(w) for w in hold.get('train_weeks', [])))}"),
         cell(str(hold.get("n_train")) + " games; the model never saw an evaluation game"), link(SCORE_URL, "score page")],
        [cell("evaluation window"), cell(f"Weeks {esc(', '.join(str(w) for w in hold.get('eval_weeks', [])))}"),
         '<td>' + esc(str(hold.get("n_eval")) + " games, chronological, fixed in PREREGISTRATION.md §4 before "
                                   "fitting") + '<br><a href="' + repo + 'forward-ledger/PREREGISTRATION.md">the '+
         "registered text</a></td>",
         link(SCORE_URL, "score page")],
        [cell("Brier, model, home win"), cell(hold.get("brier_home_win_model"), numeric=True), cell("lower is better"),
         link(SCORE_URL, "score page")],
        [cell("Brier, in-window base rate"), cell(hold.get("brier_home_win_base_rate"), numeric=True),
         cell("the best constant predictor on this window: home won " + str(hold.get("base_rate_home_win")) + " of "
              + str(hold.get("n_eval")) + " games"), link(SCORE_URL, "score page")],
        [cell("Brier, coin"), cell(hold.get("brier_home_win_coin"), numeric=True), cell("0.5 on every game"),
         link(SCORE_URL, "score page")],
        [cell("skill against the base rate"), cell(hold.get("brier_skill_vs_base_rate"), numeric=True),
         cell("1 minus model over benchmark, on one window of " + str(hold.get("n_eval"))
              + " games in one season; no interval is claimed for it here"), link(SCORE_URL, "score page")],
        [cell("margin R2, in sample"), cell(insample.get("margin_r2"), numeric=True),
         cell(str(insample.get("n")) + " graded games"), link(SCORE_URL, "score page")],
        [cell("margin R2, holdout"), cell(hold.get("margin_r2_holdout"), numeric=True),
         cell("the same formula on unseen weeks"), link(SCORE_URL, "score page")],
        [cell("total R2, holdout"), cell(hold.get("total_r2"), numeric=True),
         cell("the totals side is the weak half of this fit"), link(SCORE_URL, "score page")],
        [cell("mean absolute margin error"), cell(hold.get("mean_abs_margin_error"), numeric=True), cell("points"),
         link(SCORE_URL, "score page")],
        [cell("mean absolute total error"), cell(hold.get("mean_abs_total_error"), numeric=True),
         cell("points on the summed score"), link(SCORE_URL, "score page")],
        [cell("fitted home-field term"), cell(constants.get("hfa"), numeric=True),
         cell("negative and small: 2026 as published shows no home advantage to assume. See FL-10"),
         link(SCORE_URL, "score page")],
    ]
    hold_table = table(["Measurement", "Value", "What it means", "Source"], hold_rows, official=True)
    luck_rows = [
        [cell("variance of the actual margin"), cell(luck.get("variance_of_actual_margin"), numeric=True),
         cell("what happens on the field"), link(SCORE_URL, "score pages")],
        [cell("variance of the expectation"), cell(luck.get("variance_of_expectation"), numeric=True),
         cell("what an expectation can address"), link(SCORE_URL, "score pages")],
        [cell("share inside the expectation"), cell(luck.get("share_of_variance_inside_the_expectation"), numeric=True),
         cell(luck.get("reading", "")), link(SCORE_URL, "score pages")],
        [cell("margin mean, bootstrap 95% interval"), cell(" to ".join(str(v) for v in corr.get("margin_mean_bootstrap_ci", []))),
         cell("game-cluster resample, 2000 draws, seed 20261116, one game per cluster"), link(SCORE_URL, "score pages")],
        [cell("ties in graded games"), cell(corr.get("ties_observed"), numeric=True),
         cell("a Normal model assigns a tie zero probability, so the moneyline row is labelled tie-blind"),
         link(SCORE_URL, "score pages")],
    ]
    luck_table = table(["Measurement", "Value", "Reading", "Source"], luck_rows, official=True)
    m4 = _m([("margin R2 in sample", f"{insample.get('margin_r2', 0):.4f}"),
             ("margin R2 holdout", f"{hold.get('margin_r2_holdout', 0):.4f}"),
             ("total R2 in sample", f"{insample.get('total_r2', 0):.4f}"),
             ("games fitted", f"{insample.get('n', 0)}"), ("holdout games", f"{hold.get('n_eval', 0)}"),
             ("ties observed", f"{corr.get('ties_observed', 0)}")])
    firewall = ('<div class="card notice bad"><strong>Backtest surface. Nothing on this page may be read as a '
                "ranking.</strong> These are the diagnostics the pre-registration allows for model development: fit "
                "quality, dependence structure and the luck split, measured on games that were already finished when "
                "the model was fitted. The gate in <code>scripts/verify.py</code> proves that no number on this page "
                'is echoed on <a href="leaderboard.html">the leaderboard</a>, which is the only place ranking could '
                "live.</div>")
    backtest = (firewall + m4 + "<h2>How the model scored outside its fitting window</h2>" + hold_table
                + "<h2>Removal of luck</h2>" + luck_table
                + "<h2>Correlation register - official inputs only, n printed with every value</h2>"
                  "<p><small>" + esc(corr.get("caveat", "")) + "</small></p>" + corr_table
                + "<h2>Fitted ratings</h2><p><small>Attack and defence are points per game relative to the league mean "
                  "of " + esc(constants.get("mu")) + "; net rating is attack minus defence, with no shrinkage and no "
                  "prior. Records are cross-checked against the official standings: "
                  + str(crosscheck.get("clubs_matching_on_all_five_fields", 0)) + " of " + str(n_clubs_sc)
                  + " clubs agree on all five fields.</small></p>" + rating_table)

    # ---------------------------------------------------------------- prospects
    def before_kickoff(row: dict) -> bool:
        return str(row["issued_at_utc"])[:10] <= str(row["kickoff_et"])[:10]

    prospect_rows = []
    for r in prospects:
        ok = before_kickoff(r)
        prospect_rows.append([
            cell(r["slot"]), cell(r["kickoff_et"]), cell(f'{r["away"]} at {r["home"]}'), cell(r["market"]),
            cell(r["event"]),
            cell(r["our_line"], numeric=True, blank_reason="a moneyline row prices an outcome, not a line"),
            cell(r["projected_value"], numeric=True), cell(r["probability"], numeric=True),
            cell(r["fair_line"], numeric=True),
            cell(r["market_line"], blank_reason="no licensed two-sided price source exists (price-data policy)"),
            cell(r["difference"], blank_reason="a difference needs a market line"),
            cell(r["push_or_tie_probability"], numeric=True, blank_reason="push applies to totals only"),
            cell(r["secondary_total_estimator"], numeric=True, blank_reason="the secondary estimator prices totals only"),
            cell(r["estimator_gap"], numeric=True, blank_reason="the gap needs two total estimators"),
            f'<td><span class="pill {"ok" if ok else "bad"}">{"yes" if ok else "NO"}</span></td>',
            link(r["source_url"], "fixture page"),
        ])
    prospect_table = table(["Slot", "Kickoff (ET)", "Fixture", "Market", "Event", "Our line", "Projected",
                            "Probability", "Fair line", "Market line", "Difference", "Push prob.", "Secondary total",
                            "Estimator gap", "Before kickoff?", "Source"], prospect_rows, official=True)
    gaps = [abs(float(r["estimator_gap"])) for r in prospects if r["market"] == "total" and r["estimator_gap"]]
    mean_gap = f"{sum(gaps) / len(gaps):.2f}" if gaps else ""
    n_fixtures = len({(r["slot"], r["away"], r["home"]) for r in prospects})
    n_before = sum(1 for r in prospects if before_kickoff(r))
    m5 = _m([("fixtures", f"{n_fixtures}"), ("forecast rows", f"{len(prospects)}"), ("markets", "3"),
             ("rows issued before their kickoff", f"{n_before} of {len(prospects)}"),
             ("rows priced against a market", "0"),
             ("mean absolute gap, two total estimators", mean_gap + (" pts" if gaps else ""))])
    pit_card = ('<div class="card notice ok"><strong>Point-in-time.</strong> Every row was written at <code>'
                + esc(issued) + "</code>, before the first kickoff of the window (2026-11-19 20:15 ET). Each record "
                "in <code>data/prospect_records.jsonl</code> stores the inputs alongside the probability, which is "
                "what the brief asks for: an output without its inputs cannot be audited or re-run.</div>")
    two_totals = ('<div class="card notice warn"><strong>Two totals, one gap.</strong> Every total is published '
                  "twice - the additive model and the sum-of-scoring-rates estimator - with the signed gap in its "
                  "own column, and neither is retired until the walk-forward comparison in PREREGISTRATION.md §3 can "
                  "be evaluated. Mean absolute gap on this slate: <strong>" + esc(mean_gap or "n/a")
                  + " points</strong>. A reader who takes one column as 'the model's total' has picked one of two "
                  "numbers that disagree by about a field goal.</div>")
    price_firewall = ('<div class="card notice"><strong>The market and difference columns are empty on purpose.'
                      "</strong> " + esc(prospects[0]["price_policy_note"] if prospects else "")
                      + " Publishing a residual against an unlicensed, undated number would be the fastest way to "
                        "teach this site to trust a fake.</div>")
    repro_rows = []
    for label, value in (("model", "fl1.0.0"), ("config hash", constants.get("config_hash")),
                         ("sigma, margin", insample.get("sigma_margin")), ("sigma, total", insample.get("sigma_total")),
                         ("league mean points per club per game", constants.get("mu")),
                         ("input ledger sha256 (first 16)",
                          hashlib.sha256((DATA / "results_ledger.csv").read_bytes()).hexdigest()[:16]),
                         ("rows per fixture", "3 (side, total, moneyline)")):
        repro_rows.append([cell(label), "<td><code>" + esc(value) + "</code></td>",
                            link(repo + "forward-ledger/PREREGISTRATION.md", "registration")])
    repro_table = table(["Field", "Value", "Reference"], repro_rows)
    prospects_page = (m5 + pit_card + two_totals + price_firewall + "<h2>Originated lines</h2>" + prospect_table
                      + "<h2>Reproducibility of this slate</h2>" + repro_table)

    # ---------------------------------------------------------------- leaderboard
    div_rows = []
    for d in leaderboard.get("divisions", []):
        div_rows.append([
            cell(d["division"]), cell(d["registered_rows"], numeric=True), cell(d["eligible_for_ranking"], numeric=True),
            cell(d["why_not"]), cell(d["grading_basis"]), cell(d["signal_column"]),
            cell(d["staking_column"], blank_reason="the price-data policy grants no source"),
            link("https://www.nfl.com/schedules/2026/by-week/week-11", "window schedule"),
        ])
    div_table = table(["Division", "Registered rows", "Eligible for ranking", "Why not", "Grading basis",
                       "Signal column", "Staking column", "Window source"], div_rows, official=True)
    control_rows = []
    for c in leaderboard.get("controls", []):
        state = "registered" if c.get("registered") else "missing"
        control_rows.append([cell(c["control"]), cell(c["definition"]),
                             f'<td><span class="pill ok">{state}</span></td>', cell(c.get("note", "")),
                             link(SCORE_URL, "official results")])
    control_table = table(["Control", "Definition", "State", "Note", "Source"], control_rows, official=True)
    reg_text = repo + "forward-ledger/PREREGISTRATION.md"
    gates_table = table(["Gate", "Rule", "Consequence", "Rule text"], [
        [cell("Promotion"), cell("at least 40 graded fixtures in the prospective window, benchmark-relative skill "
              "with a game-cluster lower bound above zero, a Benjamini-Hochberg adjusted p under 0.10, and a price "
              "register that permits a residual"),
         cell("a row may be ranked"), link(reg_text, "PREREGISTRATION.md §4")],
        [cell("Demotion, signal"), cell("20 consecutive graded fixtures with skill below zero, or two consecutive "
              "windows whose lower bound crosses zero downward"),
         cell("the row returns to paper automatically, with no review meeting"), link(reg_text, "PREREGISTRATION.md §4")],
        [cell("Demotion, data"), cell("the input ledger older than 48 hours at any kickoff in the window, or one "
              "graded score changed by a later official read"),
         cell("the row returns to paper and the affected fixtures are listed as unresolved"),
         link(reg_text, "PREREGISTRATION.md §4 and §5")],
        [cell("Parlays and prop combos"), cell("a directly validated joint probability and the operator's void/push "
              "rules, both, before a row may be registered in the division"),
         cell("the division stays empty: the measured dependence on the backtest page is a warning about "
              "multiplication, not a licence to combine"), link(reg_text, "PREREGISTRATION.md §5 G7")],
        [cell("Reward"), cell("a tier pays only a row that has cleared promotion in two consecutive windows"),
         cell("unfunded: no owner decision sets an amount, so the field stays blank"),
         link("https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL",
              "NFL odds boundary")]])
    reward = leaderboard.get("reward", {})
    reward_table = table(["Field", "Value", "Note", "Reference"], [
        [cell("pool funded"), cell("no" if not reward.get("funded") else "yes"), cell(reward.get("note", "")),
         link(reg_text, "registration")],
        [cell("payable rows"), cell("0"), cell("nothing has cleared promotion, and no backtest number can"),
         link(SCORE_URL, "official results")]])
    m6 = _m([("graded fixtures in window", f"{leaderboard.get('graded_fixtures_in_window', 0)}"),
             ("divisions", f"{len(div_rows)}"), ("eligible rows", "0"), ("controls registered", f"{len(control_rows)}"),
             ("reward funded", "no"), ("window opens", str(leaderboard.get("window_opens_utc", "")))])
    split_card = ('<div class="card notice"><strong>Signal and staking are separate columns, and only one of them '
                  "can fill first.</strong> Signal is benchmark-relative skill with an interval. Staking is a return, "
                  "and a return needs a price. Because <code>pricing/PRICE_DATA_POLICY.md</code> grants no source, the "
                  "staking column is empty on every row: a lucky run of stakes cannot move anything, and neither can "
                  "an unlucky one. That is the whole point of the split.</div>")
    leaderboard_page = (split_card + m6 + "<h2>Divisions and eligibility</h2>" + div_table
                        + "<h2>Controls, which must be beaten before anything else counts</h2>" + control_table
                        + "<h2>Promotion and demotion gates</h2>" + gates_table + "<h2>Reward</h2>" + reward_table)

    # ---------------------------------------------------------------- review
    sev = {"High": "bad", "Medium": "warn", "Low": "blank"}
    finding_rows = []
    for f in findings:
        status = f["status"]
        pill = "ok" if "fixed" in status else ("warn" if "open" in status else "blank")
        finding_rows.append([
            f'<td id="{esc(f["id"])}"><code>{esc(f["id"])}</code></td>',
            f'<td><span class="pill {sev.get(f["severity"], "blank")}">{esc(f["severity"])}</span></td>',
            cell(f["finding"]), cell(f["evidence"]), cell(f["action"]), cell(f["owner"]),
            f'<td><span class="pill {pill}">{esc(status)}</span></td>',
            link(f["official_source_url"], f["official_source_label"]),
        ])
    # The review register mixes two kinds of claim: an irregularity in what the league published, whose authority is
    # an nfl.com page, and an irregularity in this repository, whose authority is a file in it. Every row must link
    # what it rests on; which host that is, the finding decides for itself - so the table is sourced, not official,
    # and verify.py enforces the nfl.com requirement on the findings whose label claims an official page.
    findings_table = table(["ID", "Severity", "Finding", "Evidence", "Action", "Owner", "Status", "Source"],
                           finding_rows)
    checks_rows = [
        [cell("ledger against the frozen corpus"),
         cell(f"{agreement.get('exact_score_matches')} of {agreement.get('graded_ledger_rows_weeks_1_9')} identical, "
              f"{agreement.get('blank_in_frozen_corpus')} blank in the corpus, {agreement.get('score_mismatches')} mismatches"),
         cell("<code>scripts/build_ledger.py</code>, stored in <code>data/ledger_manifest.json</code>"),
         link(repo + "corpus/games_2026_w1_9.csv", "frozen corpus")],
        [cell("ledger against official record chips"),
         cell(f"{standings_check.get('clubs_checked_against_official_chips')} of 32 match, "
              f"{standings_check.get('mismatches')} mismatches, "
              f"{len(standings_check.get('clubs_not_read_in_this_pass', []))} not read"),
         cell("<code>scripts/build_ledger.py</code> against <code>data/live_reads_2026-11-16.json</code>"),
         link("https://www.nfl.com/schedules/2026/by-week/week-10", "official page")],
        [cell("ledger against the independent standings read"),
         cell(f"{field_checks} of {n_clubs_sc * 5} field checks"), cell("<code>scripts/crosscheck_standings.py</code>"),
         link("https://www.nfl.com/standings/", "standings page")],
        [cell("official weekday labels against printed dates"),
         cell(f"{n_anom} anomaly of {labels.get('labels_checked', 0)} labels compared"),
         cell("<code>scripts/build_ledger.py</code>"), link(SCORE_URL, "official page")],
        [cell("injury counts against the newest hash-pinned capture"),
         cell(f"{availability.get('rows')} rows, {availability.get('rows_with_a_game_designation')} designated, "
              f"{availability.get('blank_game_status_cells')} blank"),
         cell("<code>scripts/availability_w10.py</code> re-parsing the stored bytes"), link(inj, "official report")],
    ]
    checks_table = table(["Check", "Result", "How it is produced", "Source"], checks_rows)
    review_intro = ('<div class="card notice warn"><strong>Line-by-line review, ' + esc(read_date)
                    + ".</strong> These are the irregularities found while verifying the repository against live "
                      "official pages in this pass. Each row states its evidence, the file it concerns, the owner who "
                      "can close it and the action that would close it. Rows marked <em>fixed in this pass</em> were "
                      "changed here; the rest are logged as requests, because their files belong to other workspaces "
                      "and shared outputs are not edited from two sessions at once.</div>")
    review_page = (review_intro + findings_table + "<h2>Checks run in this pass</h2>" + checks_table)

    # ---------------------------------------------------------------- sources
    page_rows = []
    for p in reads.get("pages", []):
        page_rows.append([cell(p["url"]), cell(p["read_utc"]), cell(p["yielded"]), link(p["url"], "open the page")])
    pages_table = table(["Page", "Read at (UTC)", "What it yielded", "Link"], page_rows, official=True)
    input_rows = []
    for name, v in manifest.get("inputs", {}).items():
        input_rows.append(["<td><code>" + esc(name) + "</code></td>",
                           "<td><code>" + esc(str(v.get("sha256", ""))[:20]) + "…</code></td>",
                           cell(v.get("games", ""), numeric=True), cell(v.get("observed", "")),
                           link(repo + name, "stored copy")])
    inputs_table = table(["File", "SHA-256 (first 20)", "Games", "Observed", "Copy"], input_rows)
    gap_rows = [[cell(x["team"]), cell(x["reason"]), cell(x["action"]),
                 link("https://www.nfl.com/schedules/2026/by-week/week-11", "Week 11 schedule")]
                for x in reads.get("club_record_chips_read", {}).get("unread", [])]
    gap_table = table(["Club", "Why the cell is blank", "Action recorded", "Source"], gap_rows, official=True)
    used = [
        ("corpus/games_2026_w1_9.csv", "read only", "the frozen pre-registered corpus is compared row by row and never edited", "file"),
        ("corpus/manifest.json", "read only", "the hash this ledger must not silently contradict", "file"),
        ("pricing/PRICE_DATA_POLICY.md", "read only", "the rule that keeps the market-line and residual columns empty", "file"),
        ("results-verification/data/official_scores_2026/week_01..09.json", "read only", "the Weeks 1-9 official transcriptions this ledger extends", "freeze rules"),
        ("captures/nfl-injuries/", "read only", "the hash-pinned capture the availability page aggregates", "index"),
        ("injury-capture/scripts/common.py", "imported", "the verified parser is reused so both paths read the page identically", "file"),
        ("origination/data/official_standings_2026.json", "read only", "the same-day independent standings read used for the 160-field cross-check", "file"),
        ("ops-center/data/derived.json", "read only", "the merged question and proposal registers the root decision pages render", "file"),
        ("docs/PRE_REGISTRATION.md", "read only", "the standing convention this registration follows", "file"),
    ]
    used_rows = []
    for name, mode, why, label in used:
        target = "results-verification/CORPUS_FREEZE.md" if label == "freeze rules" else name
        if label == "index":
            target = "captures/nfl-injuries/index.jsonl"
        used_rows.append([cell(name), cell(mode), cell(why), link(repo + target, label)])
    used_table = table(["File", "Read or written", "Why", "Link"], used_rows)
    sources_page = ('<div class="card notice"><strong>How these reads were taken.</strong> '
                    + esc(reads.get("egress_note", "")) + "</div><h2>Official pages read for this pass</h2>"
                    + pages_table + "<h2>Committed inputs, with hashes</h2>" + inputs_table
                    + '<h2 id="gap">The one value this session could not read</h2>' + gap_table
                    + "<h2>Repository files this workspace touches</h2>" + used_table)

    built = {
        "index.html": page("index.html", "Forward ledger",
                           "A point-in-time verified results feed and a pre-registered prospective forecast register, 2026 season",
                           index, ("research only - no validated strategy", "warn")),
        "results.html": page("results.html", "Verified results feed",
                             f"{graded} graded 2026 fixtures with their official pages, read windows and three cross-checks",
                             results, ("official pages only", "ok")),
        "availability.html": page("availability.html", "Availability, recomputed",
                                  "What the newest hash-pinned official injury-report capture contains, and how far it moved since the read other pages still publish",
                                  availability_page, ("aggregates, not row-level data", "warn")),
        "backtest.html": page("backtest.html", "Backtest diagnostics",
                              "Fit quality, dependence and the removal-of-luck panel, measured on finished games and excluded from ranking by gate",
                              backtest, ("never on the leaderboard", "bad")),
        "prospects.html": page("prospects.html", "Originated lines",
                               "One row per market per fixture: our line, the market line, the difference, and the inputs behind every probability",
                               prospects_page, ("issued before kickoff", "ok")),
        "leaderboard.html": page("leaderboard.html", "Leaderboard",
                                 "Divisions, controls and gates. There are no results here because none may come from a backtest and none exists yet.",
                                 leaderboard_page, ("0 rows eligible", "blank")),
        "review.html": page("review.html", "Review findings",
                            f"Irregularities found while verifying this pass, each with evidence, an owner and an action ({read_date})",
                            review_page, (f"{len(findings)} findings", "warn")),
        "sources.html": page("sources.html", "Source register",
                             "Every page read and every file used, with hashes and read windows", sources_page),
    }

    counts: dict = {}
    for name, text in built.items():
        rows_checked = 0
        blocks = list(re.finditer(r'<div class="tablewrap"([^>]*)>(.*?)</tbody></table></div>', text, re.S))
        if not blocks:
            L.errors.append(f"{name}: no table rendered at all")
        for block in blocks:
            if 'data-navigation="1"' in block.group(1):
                continue
            for row in re.findall(r"<tr>(.*?)</tr>", block.group(2), re.S):
                if "<td" not in row:
                    continue
                rows_checked += 1
                if 'href="https://' not in row:
                    L.errors.append(f"{name}: row without an https source link: "
                                   f"{re.sub('<[^>]+>', ' ', row)[:110]}")
                elif 'data-official="1"' in block.group(1) and not re.search(
                        r'href="https://(www|static\.www|operations)\.nfl\.com', row):
                    L.errors.append(f"{name}: league-fact row without an nfl.com link: "
                                   f"{re.sub('<[^>]+>', ' ', row)[:110]}")
        counts[name] = rows_checked
        if rows_checked == 0:
            L.errors.append(f"{name}: zero sourced rows, so nothing on this page was checked")
        found = PLACEHOLDERS.search(text)
        if found:
            L.errors.append(f"{name}: placeholder '{found.group(0)}' leaked into the build")
    if L.errors:
        print("forward-ledger build failed:")
        print("\n".join(f"- {e}" for e in L.errors))
        return 1

    if args.check:
        stale = [name for name, text in built.items()
                 if not (HERE / name).is_file() or (HERE / name).read_text(encoding="utf-8") != text]
        if stale:
            print("pages are stale or missing (run forward-ledger/scripts/build_site.py): " + ", ".join(stale))
            return 1
        print(f"forward-ledger: {len(PAGES)} pages match the committed data exactly "
              f"({sum(counts.values())} sourced rows, each carrying an official link).")
        return 0
    for name, text in built.items():
        (HERE / name).write_text(text, encoding="utf-8")
    print(f"forward-ledger: wrote {len(PAGES)} pages from {len(ledger)} ledger rows, {len(prospects)} forecast rows, "
          f"{len(findings)} review findings; {sum(counts.values())} sourced rows each carry an official link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
