#!/usr/bin/env python3
"""Build injury-verification/index.html from report.json + the evidence TSV.

Deterministic: re-running produces the same page. Every table body row carries
an official https://www.nfl.com/ citation. Unverified values stay blank and are
listed on the page; nothing is inferred.

Run: python3 injury-verification/build_page.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VER = ROOT / "injury-verification"
REPORT = VER / "report.json"
EVIDENCE = VER / "evidence" / "live_injuries_2026_w10.tsv"
OUT = VER / "index.html"

SRC_REPORT = "https://www.nfl.com/injuries/"
SRC_SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_RAMS_ROSTER = "https://www.nfl.com/teams/los-angeles-rams/roster"
SRC_DARNOLD = ("https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-"
               "week-10-game-vs-raiders-drew-lock-expected-to-start-again")

STYLE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Independent line-by-line verification of the official NFL Week 10 2026 injury data">
<title>Verification report — Week 10 2026 injury data | NFL3</title>
<link rel="stylesheet" href="../assets/style.css">
<style>
.v-match{color:#0a7d33;font-weight:600}
.v-change{color:#b45309;font-weight:600}
.v-added{color:#1d4ed8;font-weight:600}
.content h1{margin-top:.5rem}
.code,code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em}
</style></head><body><div class="layout">
<main><header class="topbar"><span>VERIFICATION <b>/</b> INDEPENDENT LINE-BY-LINE PASS</span>
<span class="top-right"><span class="status-dot"></span> SESSION arena/e0b5058a-nfl3</span></header>
<div class="content">
<div class="eyebrow"><span></span> VERIFICATION DESK</div>
<h1>Independent verification — Week 10 2026 injury data</h1>
<p class="lede">Every row of the official Week 10 injury report, extracted independently and compared
field by field against the committed captures. Differences are reported, never reconciled by hand.
Blank stays blank.</p>
<p><a class="text-link" href="../index.html">← Back to the main NFL3 site</a></p>
"""

FOOTER = """
<footer> NFL3 VERIFICATION DESK <span>Reported, not inferred · official sources only · blank stays blank.</span></footer>
</div></main></div></body></html>
"""


def esc(text: object) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load_evidence() -> list[dict]:
    rows: list[dict] = []
    day = matchup = ""
    for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("# DAY:"):
            day = line[6:].strip()
        elif line.startswith("# MATCHUP:"):
            matchup = line[10:].strip()
        elif line.startswith("#") or not line.strip():
            continue
        else:
            team, player, position, injury, practice, game = line.split("\t")
            rows.append({"day": day, "matchup": matchup, "team": team,
                         "player": player, "position": position, "injury": injury,
                         "practice_status": practice, "game_status": game})
    return rows


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    evidence = load_evidence()

    pairs = report["pairs"]
    ab = pairs["A_vs_B"]
    bc = pairs["B_vs_C"]
    ac = pairs["A_vs_C"]

    # Status of every live row vs the committed snapshot
    snap_keys = {}
    for item in ab["only_in_a"]:
        snap_keys[tuple(item["key"])] = "added since capture"
    diff_keys = {tuple(item["key"]): item["diffs"] for item in ab["field_diffs"]}
    for r in evidence:
        k = (r["team"], r["player"], r["position"])
        r["_status"] = "field change" if k in diff_keys else snap_keys.get(k, "match")

    n_match = sum(1 for r in evidence if r["_status"] == "match")
    n_added = sum(1 for r in evidence if r["_status"] == "added since capture")
    n_change = sum(1 for r in evidence if r["_status"] == "field change")
    n_game = sum(1 for r in evidence if r["game_status"])

    added_by_team: dict[str, list[str]] = {}
    for item in ab["only_in_a"]:
        added_by_team.setdefault(item["key"][0], []).append(
            f"{item['key'][1]} ({item['key'][2]})")

    parts: list[str] = [STYLE]

    # Metrics
    parts.append(f"""
<div class="metrics">
<div><span>LIVE ROWS VERIFIED</span><strong>{len(evidence)}</strong><small>Fetched {esc(report['sources']['A_live']['observed_at'])}</small></div>
<div><span>COMMITTED CAPTURE ROWS</span><strong>{report['sources']['B_snapshot']['rows']}</strong><small>decision-lab snapshot</small></div>
<div><span>EXTRACTION AGREEMENT (B vs C)</span><strong>{bc['exact_matches']}/{bc['matched_keys']}</strong><small>zero field differences</small></div>
<div><span>DRIFT ITEMS SINCE CAPTURE</span><strong>{n_added + n_change}</strong><small>{n_added} added · {n_change} changed</small></div>
</div>""")

    # Method
    parts.append(f"""
<div class="section-head"><div><div class="section-label">01 / METHOD</div>
<h2>What was compared, and how</h2></div><p>Two independent extraction paths, three sources.</p></div>
<div class="brief">
<div><div class="card-kicker">SOURCE A — LIVE, THIS SESSION</div><h3>Official report, fetched independently</h3>
<p>The live <a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">official NFL Week 10 injury report ↗</a>
was fetched at {esc(report['sources']['A_live']['observed_at'])} through a markdown rendering path and transcribed
row by row ({len(evidence)} rows) — a different parser path than the repository's regex-on-HTML capture.
Evidence file: <code>injury-verification/evidence/live_injuries_2026_w10.tsv</code>.</p></div>
<div><div class="card-kicker">SOURCE B — COMMITTED CAPTURE</div><h3>decision-lab snapshot</h3>
<p><code>decision-lab/data/official_snapshot.json</code>, observed
{esc(report['sources']['B_snapshot']['observed_at'])} (16h before source A), {report['sources']['B_snapshot']['rows']} rows,
SHA-256 recorded per page. Same official URL as source A.</p></div>
<div><div class="card-kicker">SOURCE C — COMMITTED EXTRACT</div><h3>dashboard CSV</h3>
<p><code>dashboard/data/injuries_2026_w10.csv</code>, {report['sources']['C_dashboard']['rows']} rows, extracted by a
different session with its own parser. Same official URL as sources A and B.</p></div>
<div><div class="card-kicker">LIMITS</div><h3>What this does not prove</h3>
<p>One fetch, one day: this is not a link crawler, not a historical archive, and not proof the page will
stay unchanged. Field values were never inferred — where the page is blank, the row is blank. Game-status
columns fill in as game time approaches; timing effects are flagged below, not filled in. Related
verification workspaces cover other angles: <code>verification-lab/</code> re-checks published claims
claim by claim, and <code>decision-lab/verification.html</code> logs capture-time checks; this page adds
the three-way extractor comparison and its captured evidence file.</p></div>
</div>""")

    # Pairwise results
    parts.append("""
<div class="section-head"><div><div class="section-label">02 / PAIRWISE RESULTS</div>
<h2>Line-by-line comparison</h2></div><p>Matched on (team, player, position); then every field compared.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">Pair</th><th scope="col">Rows</th><th scope="col">Exact matches</th>
<th scope="col">Only in first</th><th scope="col">Only in second</th><th scope="col">Field differences</th>
<th scope="col">Source</th></tr></thead><tbody>""")
    for label, pair, src in (
        ("B snapshot vs C dashboard", bc, SRC_REPORT),
        ("A live vs B snapshot", ab, SRC_REPORT),
        ("A live vs C dashboard", ac, SRC_REPORT),
    ):
        parts.append(
            f"<tr><td>{esc(label)}</td><td>{pair['a_rows']} vs {pair['b_rows']}</td>"
            f"<td>{pair['exact_matches']} / {pair['matched_keys']}</td>"
            f"<td>{len(pair['only_in_a'])}</td><td>{len(pair['only_in_b'])}</td>"
            f"<td>{len(pair['field_diffs'])}</td>"
            f'<td><a href="{src}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append("</tbody></table></div>")

    # Findings: drift
    parts.append("""
<div class="section-head"><div><div class="section-label">03 / FINDINGS</div>
<h2>Drift since the committed capture</h2></div>
<p>The page changed between 06:32Z and 22:34Z on 2026-11-12. Reported as observed.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">ID</th><th scope="col">Finding</th><th scope="col">Rows</th><th scope="col">Detail</th>
<th scope="col">Handling</th><th scope="col">Source</th></tr></thead><tbody>""")
    parts.append(
        "<tr><td>V-D01</td><td>Seahawks table appeared</td><td>15</td>"
        "<td>The capture recorded Seahawks as “No Injuries Reported”; the live report now carries a "
        "15-row Seahawks table (Sam Darnold, Drew Lock, Jaxon Smith-Njigba and others).</td>"
        "<td>Recorded as page update; capture not overwritten</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append(
        "<tr><td>V-D02</td><td>Bengals table appeared</td><td>4</td>"
        "<td>The capture recorded Bengals as “No Injuries Reported”; the live report now carries a "
        "4-row Bengals table (Jonathan Allen, Kyle Dugger, Dylan Fairchild, DJ Turner II).</td>"
        "<td>Recorded as page update; capture not overwritten</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append(
        "<tr><td>V-D03</td><td>Six players added to existing team tables</td><td>6</td>"
        "<td>" + esc("; ".join(
            f"{team}: {', '.join(players)}" for team, players in sorted(added_by_team.items())
            if team not in {"Seahawks", "Bengals"})) + ".</td>"
        "<td>Recorded as page update; capture not overwritten</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    colts_bits = []
    for item in ab["field_diffs"]:
        team, player, _pos = item["key"]
        if team != "Colts":
            continue
        d = item["diffs"]["practice_status"]
        colts_bits.append(f"{player}: “{d['B_snapshot']}” → “{d['A_live']}”")
    parts.append(
        "<tr><td>V-D04</td><td>Four Colts practice-status changes</td><td>4</td>"
        f"<td>{esc('; '.join(colts_bits))} — Thursday practice report updated after the capture.</td>"
        "<td>Both values shown in the appendix; neither overwritten</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append("</tbody></table></div>")

    # Independent confirmation of flags another session already resolved
    parts.append("""
<div class="section-head"><div><div class="section-label">04 / INDEPENDENT CONFIRMATION</div>
<h2>Re-check of flags resolved by the second-pass session</h2></div>
<p>Dashboard Q09/Q10/Q11 were resolved by session 22802aed on 2026-11-12. This pass reached the same
answers from its own fetch, 4–9 minutes later — corroboration, not a new claim.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">Prior flag</th><th scope="col">Question</th><th scope="col">Answer found independently</th>
<th scope="col">Status</th><th scope="col">Source</th></tr></thead><tbody>""")
    parts.append(
        "<tr><td>Dashboard R-10 / Q11</td><td>Why are DEN, CHI, PHI and TB absent from the Week 10 injury page?</td>"
        "<td>They are on Week 10 bye. The official schedule’s “Teams on Bye” section lists exactly "
        "CHI, DEN, PHI, TB; the other 28 teams fill the 14 published matchups — matching the second-pass "
        "resolution against the same official page.</td>"
        "<td>Confirmed (resolved by 22802aed)</td>"
        f'<td><a href="{SRC_SCHEDULE}" target="_blank" rel="noopener noreferrer">Official Week 10 schedule ↗</a></td></tr>')
    parts.append(
        "<tr><td>Dashboard R-07 / Q10</td><td>Are Myles Garrett and Trent McDuffie really Rams — the injury "
        "report lists them under Los Angeles?</td>"
        "<td>Yes. The official Rams roster lists Myles Garrett (#95, LB, ACT) and Trent McDuffie (#22, CB, ACT) "
        "as 2026 Rams — matching the second-pass resolution against the same official roster.</td>"
        "<td>Confirmed (resolved by 22802aed)</td>"
        f'<td><a href="{SRC_RAMS_ROSTER}" target="_blank" rel="noopener noreferrer">Official Rams roster ↗</a></td></tr>')
    parts.append(
        "<tr><td>Dashboard R-06 / Q09</td><td>Seattle shows “No Injuries Reported” while a headline says "
        "Sam Darnold is ruled out.</td>"
        "<td>Confirmed the report lag is gone: at 22:34Z the live report carries a 15-row Seahawks table "
        "(Sam Darnold, DNP practice). The formal Game Status cell is still blank while the league’s own "
        "article says he will not play — tracked as new flag V-F01, not re-filled here.</td>"
        "<td>Confirmed, with residual V-F01</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append("</tbody></table></div>")

    # New flags
    parts.append("""
<div class="section-head"><div><div class="section-label">05 / FLAGGED FOR REVIEW</div>
<h2>New irregularities from this pass</h2></div>
<p>Published for review; not fixed by inference.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">ID</th><th scope="col">Irregularity</th><th scope="col">Why it matters</th>
<th scope="col">Handling</th><th scope="col">Sources</th></tr></thead><tbody>""")
    parts.append(
        "<tr><td>V-F01</td>"
        "<td>NFL-internal gap: an official article states Sam Darnold will not play Week 10 (coach statement), "
        "and his report row shows Did Not Participate in Practice — but the Game Status cell on that row is "
        "empty as of 2026-11-12T22:34Z.</td>"
        "<td>Practice status is consistent with the article; the formal game designation is missing from the "
        "table. A consumer keying on Game Status alone would read “unknown” while the league’s newsroom "
        "states he is out.</td>"
        "<td>Both recorded; the blank Game Status cell is left blank, not filled from the article.</td>"
        f'<td><a href="{SRC_DARNOLD}" target="_blank" rel="noopener noreferrer">Official article ↗</a> · '
        f'<a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append(
        "<tr><td>V-F02</td>"
        "<td>Point-in-time mutability: 16 hours between captures produced 25 added rows and 4 field "
        "changes on the same URL.</td>"
        "<td>Any single capture is a snapshot, not history. Decisions built on “the injury report” "
        "need timestamped storage to be reproducible.</td>"
        "<td>Both observations kept with their timestamps; no capture treated as permanent.</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append(
        "<tr><td>V-F03</td>"
        f"<td>As of the fetch, only {n_game} of {len(evidence)} rows carry a Game Status "
        "(the Thursday game and three Patriots rows); Sunday/Monday statuses are mostly still blank.</td>"
        "<td>Game-status-dependent gates cannot be evaluated mid-week from this page alone; the blank "
        "cells are timing, not data loss.</td>"
        "<td>Recorded as a timing limitation; blanks preserved.</td>"
        f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>')
    parts.append("</tbody></table></div>")

    # Full appendix
    parts.append(f"""
<div class="section-head"><div><div class="section-label">06 / FULL APPENDIX</div>
<h2>Every live row, line by line</h2></div>
<p>{len(evidence)} rows · {n_match} exact matches · {n_change} field changes · {n_added} added since capture.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">Day</th><th scope="col">Matchup</th><th scope="col">Team</th><th scope="col">Player</th>
<th scope="col">Pos</th><th scope="col">Injury</th><th scope="col">Practice status</th>
<th scope="col">Game status</th><th scope="col">Vs committed capture</th>
<th scope="col">Source</th></tr></thead><tbody>""")
    for r in evidence:
        status_cls = "match" if r["_status"] == "match" else (
            "change" if r["_status"] == "field change" else "added")
        status_text = {"match": "match", "change": "field change",
                       "added": "added since capture"}[status_cls]
        parts.append(
            f"<tr><td>{esc(r['day'])}</td><td>{esc(r['matchup'])}</td><td>{esc(r['team'])}</td>"
            f"<td>{esc(r['player'])}</td><td>{esc(r['position'])}</td><td>{esc(r['injury'])}</td>"
            f"<td>{esc(r['practice_status'])}</td><td>{esc(r['game_status'])}</td>"
            f'<td class="v-{status_cls}">{status_text}</td>'
            f'<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Report ↗</a></td></tr>')
    parts.append("</tbody></table></div>")

    # Recompute line (how to reproduce)
    parts.append(f"""
<div class="section-head"><div><div class="section-label">07 / REPRODUCE</div>
<h2>How to re-run this verification</h2></div><p>Deterministic from the committed evidence file.</p></div>
<div class="table-wrap"><table><thead><tr>
<th scope="col">Step</th><th scope="col">Command</th><th scope="col">Result</th>
<th scope="col">Source / context</th></tr></thead><tbody>
<tr><td>1. Compare all three sources</td><td><code>python3 injury-verification/verify.py</code></td>
<td>Writes <code>injury-verification/report.json</code>; prints every difference</td>
<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>
<tr><td>2. Rebuild this page</td><td><code>python3 injury-verification/build_page.py</code></td>
<td>Regenerates <code>injury-verification/index.html</code> from report.json + evidence</td>
<td><a href="{SRC_REPORT}" target="_blank" rel="noopener noreferrer">Official report ↗</a></td></tr>
<tr><td>3. Site-wide citation gate</td><td><code>python3 scripts/validate_site.py</code></td>
<td>Asserts every table row on this page carries an official source link</td>
<td><a href="https://www.nfl.com/" target="_blank" rel="noopener noreferrer">NFL.com ↗</a></td></tr>
</tbody></table></div>
""")

    parts.append(FOOTER)
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
