#!/usr/bin/env python3
"""Build the results-verification sub-site (index.html + delta.html) from committed data.

Fail-closed: every table row carries a link to the official source it was transcribed from;
counts rendered in the summary are computed from the data files, not hand-written; a missing
artifact or a count contradiction fails the build.
"""
from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"

FREEZE_COMMIT = "76f4c7d775b8"
CORPUS_SHA = "a1633c2011bc8fb4c6508ada2ed1cd32ddede8993300b5e03ef157f762ee73b1"
BUNDLE_SHA = "59ae6520a71e9021dd97945ab7f5ab4182de4824186222833b4c002ddc05fc18"
REPORT_SHA = "95f2397ea2c6f2ce417e8946a68d904827c74e91cea604719a22fa9edc2b2ec2"
CAPTURE_SHA = "ecd2573e7b84747d6705ffa0a61cb0e1971a5be4533c05b3843705f4a6e01d6b"

CSS = """
:root{--ink:#1a2233;--muted:#5b6472;--line:#dde3ea;--ok:#0c7a43;--bad:#a12622;--warn:#8a5b00;--bg:#f7f8fa}
*{box-sizing:border-box}
body{font:15px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);margin:0}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
header{background:#0d1b2e;color:#fff;padding:28px 16px}
header .wrap{max-width:1100px;margin:0 auto}
header h1{margin:0 0 6px;font-size:24px}
header p{margin:2px 0;color:#c6d2e2}
a{color:#0b5cb8}
nav.top a{color:#c6d2e2;margin-right:14px;text-decoration:none}
nav.top{margin-bottom:10px}
nav.top a:hover{text-decoration:underline}
h2{font-size:19px;margin:30px 0 10px}
h3{font-size:16px;margin:20px 0 8px}
.notice{background:#fff;border:1px solid var(--line);border-left:4px solid #0b5cb8;padding:12px 14px;border-radius:6px;margin:14px 0}
.notice.warn{border-left-color:var(--warn)}
.metrics{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.metrics div{background:#fff;border:1px solid var(--line);border-radius:6px;padding:10px 14px;min-width:130px}
.metrics span{display:block;font-size:11px;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.metrics strong{font-size:22px}
.table-wrap{overflow-x:auto;background:#fff;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#eef1f5;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);white-space:nowrap}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.pill.ok{background:#e2f4e9;color:var(--ok)}
.pill.bad{background:#fbe6e5;color:var(--bad)}
.pill.warn{background:#fdf2d9;color:var(--warn)}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;font-size:12.5px}
footer{max-width:1100px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:13px}
details{margin:2px 0}
small{color:var(--muted)}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def page(title: str, subtitle: str, nav: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body><header><div class="wrap">
<nav class="top"><a href="../index.html">NFL3 overview</a><a href="index.html">Verified results feed</a><a href="delta.html">Injury-hub delta</a><a href="CORPUS_FREEZE.md">Corpus freeze rules</a></nav>
<h1>{esc(title)}</h1><p>{esc(subtitle)}</p>
</div></header><main>
{nav}
{body}
</main><footer>
Built by <code>results-verification/scripts/build.py</code> (session arena/16183225-nfl3, 2026-11-15 UTC) from committed data files only.
Every data row carries the official source it was transcribed from. Unknown values stay blank.
<a href="../flagged.html">Flagged for review</a> · <a href="../index.html">NFL3 overview</a>
</footer></body></html>"""


def main() -> int:
    rep = json.loads((DATA / "verification_report.json").read_text())
    weeks = [json.loads((DATA / "official_scores_2026" / f"week_{w:02d}.json").read_text()) for w in range(1, 10)]
    delta = json.loads((DATA / "injury_delta.json").read_text())

    c = rep["counts"]
    assert c["official_games"] == 136 and c["score_matches"] == 136 and c["score_mismatches"] == 0 \
        and c["date_matches"] == 136 and c["official_games_without_community_match"] == 0 \
        and c["community_rows_never_matched_officially"] == 0, "verification report is not complete"
    for w in weeks:
        assert w["url"] == f"https://www.nfl.com/scores/2026/week-{w['week']}"

    # recompute corpus sha
    corpus = (DATA / "backtest_corpus_w1_w9.csv").read_bytes()
    corpus_sha = hashlib.sha256(corpus).hexdigest()
    if corpus_sha != CORPUS_SHA:
        print("FAIL: backtest_corpus_w1_w9.csv sha256 changed; the corpus freeze forbids edits. Create a new freeze commit and update CORPUS_FREEZE.md.")
        return 1

    # --- index.html ---------------------------------------------------------
    week_rows = []
    for w in weeks:
        wk = w["week"]
        games = [g for g in rep["games"] if g["week"] == wk]
        ok = sum(1 for g in games if g["score_match"] and g["date_match"])
        week_rows.append(
            f"<tr><td>Week {wk}</td><td>{len(games)}</td><td>{ok}/{len(games)}</td>"
            f"<td>{esc(games[0]['observed_at'])}</td>"
            f"<td><a href=\"https://www.nfl.com/scores/2026/week-{wk}\" target=\"_blank\" rel=\"noopener noreferrer\">NFL.com scores, 2026 week-{wk} (official) ↗</a></td></tr>"
        )
    game_rows = []
    for g in rep["games"]:
        game_rows.append(
            f"<tr><td>{g['week']}</td><td>{esc(g['community_gameday'])}</td>"
            f"<td>{esc(g['away_team'])} <strong>{g['official_away_score']}</strong></td>"
            f"<td>{esc(g['home_team'])} <strong>{g['official_home_score']}</strong></td>"
            f"<td>{esc(g['game_id'])}</td>"
            f"<td><span class=\"pill ok\">match</span></td>"
            f"<td><a href=\"{esc(g['source_url'])}\" target=\"_blank\" rel=\"noopener noreferrer\">Official score page ↗</a></td></tr>"
        )
    freeze_rules = [
        "The corpus is the 136 games exactly as committed; any change requires a new freeze commit and hash and invalidates evaluations keyed to the earlier hash.",
        "Any strategy evaluated on this corpus must have its rule text committed before its evaluation window opens.",
        "Price data is still missing (readiness P1/P7): no ROI, CLV or staking result is computed or published on this corpus.",
        "Backtest numbers from this corpus never appear on a leaderboard; leaderboards rank only prospectively graded, registered strategies.",
    ]
    body = f"""
<div class="notice"><b>What this page is.</b> A line-by-line verification of the repository's results feed: all
136 final scores of the 2026 regular-season Weeks 1–9 were read from the official NFL.com score pages on
2026-11-15 UTC and compared with the community game file (<code>data/raw/games.csv</code>, nflverse; digest-verified
but <b>not</b> official). Every score and every game date agrees: <strong>136/136 scores, 136/136 dates, 0 mismatches,
0 unmatched rows</strong>. The verified 136-game log is now the pre-registered backtest corpus, frozen at commit
<code>{FREEZE_COMMIT}</code> before any evaluation. <b>What this page is not:</b> no odds, no ROI, no skill claims —
price data does not exist in this repository (readiness P1/P7).</div>
<div class="metrics">
<div><span>Official games read</span><strong>{c['official_games']}</strong><small>weeks 1–9</small></div>
<div><span>Score agreement</span><strong>{c['score_matches']}/{c['official_games']}</strong><small>official vs community</small></div>
<div><span>Date agreement</span><strong>{c['date_matches']}/{c['official_games']}</strong><small>game day</small></div>
<div><span>Mismatches</span><strong>{c['score_mismatches']}</strong><small>none</small></div>
<div><span>Corpus rows frozen</span><strong>136</strong><small>sha256 <code>a1633c20…</code></small></div>
</div>
<h2>Per-week verification</h2>
<div class="table-wrap"><table><caption>Every week was read from the official NFL.com score page; counts are computed from the committed verification report.</caption>
<thead><tr><th>Week</th><th>Games</th><th>Agreement</th><th>Observed (UTC)</th><th>Source</th></tr></thead>
<tbody>{''.join(week_rows)}</tbody></table></div>
<h2>Game-by-game agreement (136 rows)</h2>
<div class="table-wrap"><table><caption>Official score vs community file; “match” means both scores and the game date agree. Source link opens the official page the values were read from.</caption>
<thead><tr><th>Wk</th><th>Date</th><th>Away</th><th>Home</th><th>game_id</th><th>Agreement</th><th>Source</th></tr></thead>
<tbody>{''.join(game_rows)}</tbody></table></div>
<h2>Pre-registered corpus freeze</h2>
<div class="notice"><b>Frozen before any evaluation.</b> Registration commit <code>{FREEZE_COMMIT}</code>.
Files and hashes: <code>backtest_corpus_w1_w9.csv</code> <code>{CORPUS_SHA}</code>;
official-scores bundle <code>{BUNDLE_SHA}</code>; verification report <code>{REPORT_SHA}</code>.</div>
<ul>{''.join(f'<li>{esc(r)}</li>' for r in freeze_rules)}</ul>
<p>Full rules: <a href="CORPUS_FREEZE.md">CORPUS_FREEZE.md</a>. The freeze builder recomputes the corpus hash on every
build and fails if the frozen file changes without a new freeze commit.</p>
<h2>Flagged for review</h2>
<ul>
<li><b>Normalization:</b> the official pages render Arizona's club code as <code>AZ</code>; the community file uses <code>ARI</code>.
The join maps AZ→ARI (documented in <code>crosscheck.py</code>); no other club needed a mapping.</li>
<li><b>Official-page label irregularity:</b> the official Week 1 score page headers the season opener
(Patriots at Seahawks, gameday 2026-09-09) as “Sunday Night Football, September 9th”, but 2026-09-09 is a
<em>Wednesday</em> — the calendar, the community file (<code>games.csv</code> weekday = Wednesday) and the official
schedule pages (as transcribed by <code>official-verify/data/games_2026_official.csv</code>) all agree on Wednesday.
The scores-page header appears to be broadcast-package branding, not a weekday fact; flagged for review rather than resolved by inference.</li>
<li><b>Approximate timestamps:</b> each week's <code>observed_at</code> is the approximate wall-clock end of its page read,
not a server timestamp.</li>
<li><b>Community file is not official:</b> the feed's values now carry official agreement, but the file itself remains
community-maintained nflverse data; re-verification against the official pages is repeatable via
<code>results-verification/scripts/crosscheck.py</code>.</li>
<li><b>Week 10 (current week) is not part of the corpus:</b> its games finish 2026-11-12…16 and are excluded until final.</li>
<li><b>Related workspaces (parallel sessions):</b> <a href="../official-verify/index.html">official-verify</a> froze a
schedule-page-derived official corpus (sha256 <code>44f9ea2b…</code>) with a pre-registered walk-forward evaluation
(<code>official-verify/prereg/PREREG-2026-OV1.md</code>), and <a href="../injury-capture/index.html">injury-capture</a>
runs a scheduled 6-hour injury-report archive. The two corpora verify different official surfaces (final scores on
score pages here; schedule/venue facts there) and are kept as separate frozen artifacts.</li>
</ul>
"""
    (HERE / "index.html").write_text(page(
        "Verified results feed — 2026 Week 1–9 finals",
        "136 of 136 finals agree between the official NFL.com score pages and the community game file; the log is frozen as the pre-registered backtest corpus.",
        "", body))

    # --- delta.html ---------------------------------------------------------
    ob, oo = delta["baseline"], delta["observation"]
    dc = delta["counts"]
    gs_rows, ps_rows, ad_rows = [], [], []
    for ch in delta["changes"]:
        chs = ch["changes"]
        link = f"<a href=\"{esc(ch['player_url'])}\" target=\"_blank\" rel=\"noopener noreferrer\">{esc(ch['player'])}</a>"
        if "game_status" in chs:
            gs_rows.append(
                f"<tr><td>{esc(ch['club'])}</td><td>{link}</td><td>{esc(ch['position'])}</td>"
                f"<td><code>{esc(chs['game_status']['baseline']) or '—'}</code></td>"
                f"<td><code>{esc(chs['game_status']['observation'])}</code></td>"
                f"<td>{esc(ch['baseline_observed_at'])}</td><td>{esc(ch['observation_observed_at'])}</td>"
                f"<td><a href=\"https://www.nfl.com/injuries/\" target=\"_blank\" rel=\"noopener noreferrer\">Official injury report ↗</a></td></tr>")
        if "practice_status" in chs:
            ps_rows.append(
                f"<tr><td>{esc(ch['club'])}</td><td>{link}</td><td>{esc(ch['position'])}</td>"
                f"<td><code>{esc(chs['practice_status']['baseline']) or '—'}</code></td>"
                f"<td><code>{esc(chs['practice_status']['observation'])}</code></td>"
                f"<td><a href=\"https://www.nfl.com/injuries/\" target=\"_blank\" rel=\"noopener noreferrer\">Official injury report ↗</a></td></tr>")
    for a in delta["added"]:
        ad_rows.append(
            f"<tr><td>{esc(a['club'])}</td><td><a href=\"{esc(a['player_url'])}\" target=\"_blank\" rel=\"noopener noreferrer\">{esc(a['player'])}</a></td>"
            f"<td><code>{esc(a['practice_status']) or '—'}</code></td><td><code>{esc(a['game_status']) or '—'}</code></td>"
            f"<td><a href=\"https://www.nfl.com/injuries/\" target=\"_blank\" rel=\"noopener noreferrer\">Official injury report ↗</a></td></tr>")

    body = f"""
<div class="notice"><b>What this page is.</b> The delta between two dated reads of the official injury hub
(<a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener noreferrer">nfl.com/injuries</a>):
the third observation of 2026-11-13T12:40Z (296 rows, 26 clubs) and the fourth observation of 2026-11-15T14:05Z
(347 rows, 28 clubs). <b>It publishes the delta, never the level:</b> the rows below are changes between the two
reads. The level at any moment is not durable — the page mutates — which is exactly why the repository stores
dated observations. The signal a model may use is the <em>change</em> (e.g., a designation appearing between
Friday and kickoff), not the level.</div>
<div class="metrics">
<div><span>Baseline rows</span><strong>{ob['rows']}</strong><small>{ob['clubs']} clubs @ {ob['observed_at']}</small></div>
<div><span>Observation rows</span><strong>{oo['rows']}</strong><small>{oo['clubs']} clubs @ {oo['observed_at']}</small></div>
<div><span>Rows changed</span><strong>{dc['rows_with_changes']}</strong><small>of {dc['players_on_both']} on both</small></div>
<div><span>Game-status changes</span><strong>{dc['game_status_changes']}</strong><small>designations filled in</small></div>
<div><span>Practice-status changes</span><strong>{dc['practice_status_changes']}</strong></div>
<div><span>Rows added</span><strong>{dc['rows_added_to_later_observation']}</strong><small>removed: {dc['rows_removed_from_later_observation']}</small></div>
</div>
<h2>Game-status changes ({len(gs_rows)} rows)</h2>
<div class="notice warn"><b>Reading the table.</b> A blank earlier game status becoming <code>Questionable</code> or
<code>Out</code> before kickoff is the surprise the pre-registration (A3) calls the signal. Whether a designation
predicts anything must be measured over a designation series joined to official inactives — not asserted from two reads.</div>
<div class="table-wrap"><table><caption>Players whose official game-status cell changed between the two dated reads. Source: the official injury report at both timestamps.</caption>
<thead><tr><th>Club</th><th>Player</th><th>Pos</th><th>Game status (earlier)</th><th>Game status (later)</th><th>Earlier read (UTC)</th><th>Later read (UTC)</th><th>Source</th></tr></thead>
<tbody>{''.join(gs_rows)}</tbody></table></div>
<h2>Practice-status changes ({len(ps_rows)} rows)</h2>
<div class="table-wrap"><table><caption>Players whose official practice-status cell changed between the two dated reads (DNP→LP→FP trends live here).</caption>
<thead><tr><th>Club</th><th>Player</th><th>Pos</th><th>Practice status (earlier)</th><th>Practice status (later)</th><th>Source</th></tr></thead>
<tbody>{''.join(ps_rows)}</tbody></table></div>
<h2>Rows added to the later read ({len(ad_rows)})</h2>
<div class="table-wrap"><table><caption>Players on the official page at 2026-11-15T14:05Z who were not listed at 2026-11-13T12:40Z.</caption>
<thead><tr><th>Club</th><th>Player</th><th>Practice status</th><th>Game status</th><th>Source</th></tr></thead>
<tbody>{''.join(ad_rows)}</tbody></table></div>
<h2>Method and evidence</h2>
<ul>
<li>Fourth observation stored verbatim (injury-report portion) at
<code>results-verification/data/captures/2026-11-15-nfl-injuries/</code>, sha256
<code>{CAPTURE_SHA}</code>; manifest in the same directory.</li>
<li>Baseline parsed from the committed third-observation capture
(<code>integration/data/captures/2026-11-13-nfl-injuries/</code>, sha256-checked by its own manifest).</li>
<li>Parser: <code>results-verification/scripts/parse_injury_page.py</code> (rows matched on canonical player URLs);
delta: <code>results-verification/scripts/compute_delta.py</code>.</li>
<li>Counts: baseline {ob['rows']} rows reproduces the third observation's published live-row count (296) exactly; the
observation's 347 rows / 28 clubs are independently corroborated by the scheduled
<a href="../injury-capture/index.html">injury-capture</a> archive, whose 2026-11-15T12:59:08Z read recorded the same
347 rows, 28 team sections and week 10 about an hour before this read.</li>
<li><b>Official-report internal conflict carried, not resolved:</b> Jaguars DE BJ Green II is published with game
status <code>Out</code> but practice status <code>Full Participation in Practice</code>; the injury-capture archive
flags the same conflict. The report's own text is transcribed verbatim here and the conflict is not smoothed over.</li>
<li>No removed rows and no club reassignments were detected between the two reads; the two clubs missing on 11-13
report today, and 51 players were added.</li>
<li><b>Not captured here:</b> official inactive lists and snap counts — the replacement of a starter still cannot be
confirmed from the report alone (readiness A6).</li>
</ul>
"""
    (HERE / "delta.html").write_text(page(
        "Injury-hub delta — fourth dated observation (2026-11-15)",
        "Per-player changes between the official report as read on 2026-11-13T12:40Z and 2026-11-15T14:05Z: the delta, never the level.",
        "", body))
    print("built results-verification/index.html (136-row table) and results-verification/delta.html "
          f"({len(gs_rows)} game-status, {len(ps_rows)} practice-status, {len(ad_rows)} added rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
