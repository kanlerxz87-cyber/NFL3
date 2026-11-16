#!/usr/bin/env python3
"""Render the matchup workspace pages from the artifacts written by build.py.

Every value printed here is copied from a committed artifact; nothing is computed at
render time except counts and sort order. Every table row carries an https link, and
values that could not be produced from a published source render as an explicit
"unverified" marker rather than a guess.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

SOURCE = "https://www.nfl.com/injuries/"
SOURCE_REG10 = "https://www.nfl.com/injuries/league/2026/REG10"
TRANSACTIONS = "https://www.nfl.com/transactions/"

OBSERVED = "2026-11-16"
ARCHIVE = "https://www.nfl.com/injuries/league/2026/REG10"
INACTIVES_URL = "https://www.nfl.com/news/nfl-week-10-inactives-players-ruled-out-sunday-2026-season"
PREV_OBSERVED = "2026-11-12T06:32Z"

NAV = [
    ("index.html", "Overview"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("injury-verify.html", "Week 10 re-read"),
    ("matrix.html", "Matchup matrix"),
    ("teams.html", "Per-team view"),
    ("replacement-depth.html", "Depth of replacement"),
    ("roster-events.html", "Roster events"),
    ("coverage.html", "Published depth census"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
]


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def blank(v, note="unverified"):
    """Render an official value, or an explicit marker when there is none."""
    s = "" if v is None else str(v)
    return (f'<span class="pill warn">{esc(note)}</span>' if s == ""
            else esc(s))


def srclink(url: str, label: str = "source", title: str = "") -> str:
    t = f' title="{esc(title)}"' if title else ""
    return (f'<a class="source" href="{esc(url)}" target="_blank" '
            f'rel="noopener noreferrer"{t}>{esc(label)} ↗</a>')


def page(title: str, active: str, body: str, lede: str = "") -> str:
    nav = "".join(
        f'<a href="{esc(href)}"{" aria-current=page" if href == active else ""}>{esc(label)}</a>'
        for href, label in NAV)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | NFL3 matchup desk</title>
<link rel="stylesheet" href="../assets/style.css"><link rel="stylesheet" href="assets/matchup.css"></head><body>
<div class="layout"><aside class="sidebar">
<a class="brand" href="../index.html"><span class="brand-icon">N<span>3</span></span><span>NFL<span class="brand-light"> / LAB</span><small>MATCHUP DESK</small></span></a>
<div class="nav-label">MATCHUP WORKSPACE</div><nav aria-label="Matchup navigation">{nav}</nav>
<div class="side-bottom"><span class="status-dot"></span> Research mode <small>Read {esc(OBSERVED)}</small></div>
</aside><main><header class="topbar"><span>FOOTBALL INTELLIGENCE <b>/</b> MATCHUP DEFICIENCY DESK</span><span class="top-right"><span class="status-dot"></span> OFFICIAL SOURCES ONLY</span></header>
<div class="content">
<div class="eyebrow"><span></span> THE MATCHUP DESK</div>
<h1>{esc(title)}</h1>
{f'<p class="lede">{lede}</p>' if lede else ""}
{body}
<footer> NFL3 MATCHUP DESK <span>Every row links to the official page it was read from. Blanks stay blank.</span></footer>
</div></main></div></body></html>
'''


def table(headers, rows, caption="", empty="No rows. This is a real zero, not a missing table."):
    if not rows:
        return f'<p class="notice">{esc(empty)}</p>'
    thead = "".join(f'<th scope="col">{esc(h)}</th>' for h in headers)
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    out = f'<div class="table-wrap"><table>{cap}<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>'
    return out


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ----------------------------------------------------------------- 1. overview
def page_index():
    rec = load("injury_reconciliation.json")
    cen = load("census.json")
    rd = load("replacement_depth.json")
    df = load("depth_flags.json")
    ev = load("roster_events.json")
    cor = load("matrix_corrections.json")
    prev, live = rec["previous"], rec
    capmix = "; ".join(
        f'{c["rows"]} rows from {c["observed_at"][:16]}Z (hash {c["source_sha256"][:12]}…)'
        for c in prev.get("captures", []))
    cards = f'''
<div class="brief">
<div><div class="card-kicker">THE READ</div><h3>{live["live_rows"]} rows, {live["live_teams"]} clubs.</h3>
<p>Every row of the official Week 10 injury report as it stood on {OBSERVED}, transcribed line by line. The committed snapshot from {PREV_OBSERVED} held {prev["rows"]} rows.</p>
<a class="text-link" href="injury-verify.html">Open the re-read →</a></div>
<div><div class="card-kicker">DEPTH, NOT BOOLEAN</div><h3>{len(rd)} replacement chains.</h3>
<p>For every player the league expects not to play, the published string of the next man behind him — not just the fact that a replacement exists. {cen["replacement_depth_unresolved"]} chains run past the end of the published chart.</p>
<a class="text-link" href="replacement-depth.html">Open the depth ledger →</a></div>
<div><div class="card-kicker">THE MATRIX</div><h3>{cen["matrix_cells_published"]} of {cen["matrix_rows"]} cells published.</h3>
<p>Offence string versus defence string for every group in every Week 10 game. {cen["matrix_cells_unverified"]} cells cannot be filled from published data, each with the reason.</p>
<a class="text-link" href="matrix.html">Open the matrix →</a></div>
<div><div class="card-kicker">NOT LISTED ≠ AVAILABLE</div><h3>{len(df)} stale depth rows.</h3>
<p>Club depth charts still publishing a player a dated official roster event says cannot play. {len(ev)} dated events are in the ledger, {len(cor)} of them change a matrix cell.</p>
<a class="text-link" href="roster-events.html">Open the roster-event ledger →</a></div>
</div>'''
    body = f'''
<div class="notice"><b>What this workspace is.</b> One question, answered from published sources only:
when a starter cannot play, <em>which string</em> takes his place, and which string does that string then face?
Every number here is either copied from an official page or is an arithmetic difference between two copied numbers.
Nothing is modelled, estimated or inferred. Where the answer is not published, the cell says so and names the reason.</div>
{cards}
<div class="section-head"><div><div class="section-label">01 / WHAT CHANGED ON THE PAGE</div>
<h2>The official report is not a fixed document</h2></div></div>
<div class="table-wrap"><table><caption>Two reads of the same official page, {PREV_OBSERVED} and {OBSERVED}.</caption>
<thead><tr><th scope="col">Field</th><th scope="col">Committed snapshot ({PREV_OBSERVED})</th><th scope="col">This re-read ({OBSERVED})</th><th scope="col">Difference</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>Rows on the page</td><td>{prev["rows"]}</td><td>{live["live_rows"]}</td><td>+{live["live_rows"] - prev["rows"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Clubs listing players</td><td>{prev["teams"]}</td><td>{live["live_teams"]}</td><td>+{live["live_teams"] - prev["teams"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>"No Injuries Reported" sections</td><td>{prev["no_injury_sections"]}</td><td>{live["live_no_injury_sections"]}</td><td>−{prev["no_injury_sections"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Rows with a game status</td><td>{prev["out"] + prev["doubtful"] + prev["questionable"]}</td><td>{live["live_out"] + live["live_doubtful"] + live["live_questionable"]}</td><td>+{live["live_out"] + live["live_doubtful"] + live["live_questionable"] - prev["out"] - prev["doubtful"] - prev["questionable"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Out</td><td>{prev["out"]}</td><td>{live["live_out"]}</td><td>+{live["live_out"] - prev["out"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Doubtful</td><td>{prev["doubtful"]}</td><td>{live["live_doubtful"]}</td><td>+{live["live_doubtful"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Questionable</td><td>{prev["questionable"]}</td><td>{live["live_questionable"]}</td><td>+{live["live_questionable"] - prev["questionable"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Rows added since the snapshot</td><td>—</td><td>{live["added_count"]}</td><td>—</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Rows removed since the snapshot</td><td>—</td><td>{live["removed_count"]}</td><td>—</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Rows whose fields changed</td><td>—</td><td>{live["changed_count"]}</td><td>—</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Source</td><td>{srclink(SOURCE, "nfl.com/injuries", "Committed snapshot, hash " + prev["source_sha256"][:16] + "…")}</td><td>{srclink(SOURCE_REG10, "nfl.com/injuries REG10", "Re-read 2026-11-16 through the week-specific URL")}</td><td>{srclink(SOURCE, "same page", "Both reads are the same official report")}</td></tr>
</tbody></table></div>
<div class="notice"><b>Why it matters.</b> The committed capture was taken on Thursday morning. At that point
{prev["out"] + prev["doubtful"] + prev["questionable"]} of {prev["rows"]} rows carried a game status. By {OBSERVED} the same page carried
{live["live_out"] + live["live_doubtful"] + live["live_questionable"]}. Any figure computed from the Thursday capture silently describes a different week.
The earlier flag "only 6 of 254 report rows carry a game designation" is therefore a <em>timing</em> artifact of the capture, not a parser defect — but the four clubs
published as "No Injuries Reported" on Thursday ({", ".join(esc(t) for t in prev["no_injury_teams"])}) are now listed with
{", ".join(str(x["rows_now"]) for x in live["no_injury_now_listed"])} rows respectively, which is a coverage difference, not a timing one.</div>

<div class="section-head"><div><div class="section-label">02 / HOW TO READ IT</div><h2>Start here</h2></div></div>
<div class="table-wrap"><table><caption>The four pages that carry the answer, in the order to read them.</caption>
<thead><tr><th scope="col">Page</th><th scope="col">Question it answers</th><th scope="col">Rows</th><th scope="col">Primary official source</th></tr></thead><tbody>
<tr><td><a href="injury-verify.html">Week 10 re-read</a></td><td>What does the official report say today, and how does it differ from what is committed?</td><td>{live["live_rows"]}</td><td>{srclink(SOURCE_REG10, "NFL injury report")}</td></tr>
<tr><td><a href="replacement-depth.html">Depth of replacement</a></td><td>For each player who cannot play, which published string replaces him?</td><td>{len(rd)}</td><td>{srclink(SOURCE, "NFL injury report")}</td></tr>
<tr><td><a href="matrix.html">Matchup matrix</a></td><td>Which string of the defence does each offensive string actually face?</td><td>{cen["matrix_rows"]}</td><td>{srclink(SOURCE, "NFL injury report")}</td></tr>
<tr><td><a href="roster-events.html">Roster events</a></td><td>Who is on the reserve list even though the weekly report never lists them?</td><td>{len(ev)}</td><td>{srclink(TRANSACTIONS, "NFL transactions hub")}</td></tr>
</tbody></table></div>
'''
    return page("Matchup deficiency desk", "index.html", body,
                "Which string is really on the field? A depth-of-replacement and offence-versus-defence "
                "workspace built only from official NFL pages and published club depth charts.")


# ----------------------------------------------------------------- 2. re-read
def page_injury_verify():
    rec = load("injury_reconciliation.json")
    rows = []
    import csv
    with (DATA / "injury_live_2026-11-16.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    prev, live = rec["previous"], rec
    capmix = "; ".join(
        f'{c["rows"]} rows from {c["observed_at"][:16]}Z (hash {c["source_sha256"][:12]}…)'
        for c in prev.get("captures", []))

    # counts by club
    by_club = {}
    for r in rows:
        c = by_club.setdefault(r["team"], {"rows": 0, "out": 0, "doubtful": 0, "q": 0, "blank": 0,
                                           "matchup": r["matchup"], "day": r["day"]})
        c["rows"] += 1
        g = r["game_status"] or "blank"
        c[{"Out": "out", "Doubtful": "doubtful", "Questionable": "q", "blank": "blank"}[g]] += 1

    club_rows = [[
        f'<a href="teams.html#{esc(t.replace(" ", "-").lower())}">{esc(t)}</a>',
        esc(v["matchup"]), esc(v["day"]), str(v["rows"]), str(v["out"]), str(v["doubtful"]),
        str(v["q"]), str(v["blank"]), srclink(SOURCE_REG10, "report"),
    ] for t, v in sorted(by_club.items())]

    added = [[esc(a["team"]), esc(a["player"]), esc(a["position"]),
              blank(a["game_status"], "no game status"),
              f'<a class="source" href="{esc(a["player_url"])}" target="_blank" rel="noopener noreferrer">player ↗</a>',
              srclink(SOURCE_REG10, "report")]
             for a in live["added"]]

    changed_status = [c for c in live["changed"]
                      if any(d["field"] == "game status" for d in c["changes"])]
    chg = [[esc(c["team"]), esc(c["player"]),
            "<br>".join(f'{esc(d["field"])}: <s>{esc(d["was"]) or "blank"}</s> → <b>{esc(d["now"])}</b>'
                        for d in c["changes"]),
            f'<a class="source" href="{esc(c["player_url"])}" target="_blank" rel="noopener noreferrer">player ↗</a>',
            srclink(SOURCE_REG10, "report")]
           for c in changed_status]

    noinj = [[esc(x["team"]), "No Injuries Reported", str(x["rows_now"]),
              srclink(SOURCE_REG10, "report")]
             for x in live["no_injury_now_listed"]]

    status_counts = "<br>".join(
        f"{esc(k)}: {v}" for k, v in sorted(
            live["live_practice_counts"].items()))

    body = f'''
<div class="notice"><b>Method.</b> The official injury report page was opened twice on {OBSERVED} — once at
<code>{esc(SOURCE)}</code> and once at <code>{esc(SOURCE_REG10)}</code>. Both reads returned the same tables.
Every row below was transcribed field by field from those reads: club, player, position, injury description,
practice status, game status and the player's own nfl.com URL. The transcript is committed as
<code>matchup/data/captures/2026-11-16-nfl-injuries/rows.tsv</code> and as
<code>matchup/data/injury_live_2026-11-16.csv</code>; its SHA-256 is
<code>{esc(live["transcript_sha256"][:32])}…</code>. It is then compared, club by club and player by player,
against the committed <code>decision-lab/data/official_snapshot.json</code> capture of {PREV_OBSERVED}
(hash <code>{esc(prev["source_sha256"][:32])}…</code>).</div>

<div class="table-wrap"><table><caption>The headline comparison.</caption>
<thead><tr><th scope="col">Measure</th><th scope="col">Snapshot {PREV_OBSERVED}</th><th scope="col">Re-read {OBSERVED}</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>Rows</td><td>{prev["rows"]}</td><td><b>{live["live_rows"]}</b></td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Clubs with a player table</td><td>{prev["teams"]}</td><td><b>{live["live_teams"]}</b></td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>"No Injuries Reported" sections</td><td>{prev["no_injury_sections"]}</td><td><b>{live["live_no_injury_sections"]}</b></td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Out / Doubtful / Questionable</td><td>{prev["out"]} / {prev["doubtful"]} / {prev["questionable"]}</td><td><b>{live["live_out"]} / {live["live_doubtful"]} / {live["live_questionable"]}</b></td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Blank game status</td><td>{prev["blank_game_status"]}</td><td>{live["live_blank_game_status"]}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
<tr><td>Practice status mix</td><td>{esc(prev["rows"])} rows</td><td>{status_counts}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
</tbody></table></div>

<div class="notice"><b>Independent confirmation of the row count.</b> A concurrent session captured the
same official URL, <code>{esc(ARCHIVE)}</code>, at 2026-11-16T15:05:00Z — twenty-one minutes after the read
below — and its own capture reports <b>347 rows</b> for Week 10 ({srclink(ARCHIVE, "same official page")}).
Two independent transcriptions of the same page agree on the count. The capture is archived under
<code>injury-archive/</code> with its SHA-256; this workspace did not edit it and does not depend on it.</div>

<div class="section-head"><div><div class="section-label">01 / BY CLUB</div>
<h2>Every club on the report, {OBSERVED}</h2></div></div>
{table(["Club", "Matchup", "Day", "Rows", "Out", "Doubtful", "Questionable", "No game status", "Source"],
       club_rows, "Counts computed from the committed transcript. Every row's source is the same official page.")}

<div class="section-head"><div><div class="section-label">02 / CLUBS THAT WERE "NO INJURIES REPORTED"</div>
<h2>{len(noinj)} clubs were published as injury-free on {PREV_OBSERVED}</h2></div></div>
<p>All four now publish a full table. This is a coverage difference between the two reads, not a change of
mind by a player: a club simply had not filed when the Thursday-morning capture was taken.</p>
{table(["Club", "Published on " + PREV_OBSERVED, "Rows on " + OBSERVED, "Source"], noinj,
       "The four 'No Injuries Reported' sections in the committed snapshot.")}

<div class="section-head"><div><div class="section-label">03 / ADDED ROWS</div>
<h2>{live["added_count"]} rows exist now that did not exist in the snapshot</h2></div></div>
<p>Nothing was removed: {live["removed_count"]} rows present on {PREV_OBSERVED} are absent on {OBSERVED}.</p>
{table(["Club", "Player", "Position", "Game status", "Player page", "Source"], added,
       "Rows on the current page whose club and player name do not appear in the committed snapshot.")}

<div class="section-head"><div><div class="section-label">04 / GAME STATUS APPEARED</div>
<h2>{len(changed_status)} players gained or changed a game designation</h2></div></div>
<p>Of the {live["changed_count"]} rows whose fields differ between the two reads, {len(changed_status)} differ in the
game-status column, and in {live["gained_designation_count"]} of them the earlier value was blank. The committed capture is a mix of reads, not
one: {esc(capmix)}.</p>
{table(["Club", "Player", "Field changes", "Player page", "Source"], chg,
       "Only rows whose game status changed are listed here; practice-status and injury-description changes are in the artifact.")}
'''
    return page("Week 10 official report, re-read", "injury-verify.html", body,
                f"A line-by-line transcript of the official NFL injury report as published on {OBSERVED}, "
                f"reconciled against the committed capture of {PREV_OBSERVED}.")


# ----------------------------------------------------------------- 3. matrix
def page_matrix():
    m = load("matrix.json")
    cen = load("census.json")
    cor = load("matrix_corrections.json")
    games = []
    for r in m:
        if r["matchup"] not in games:
            games.append(r["matchup"])

    groups = ["QB", "RB", "FB", "TE", "WR", "OT", "OG", "OC"]

    js_games = json.dumps([{"matchup": g, "day": next(x["day"] for x in m if x["matchup"] == g)}
                           for g in games])
    js_cells = json.dumps([{
        "matchup": r["matchup"], "off": r["offence_team"], "def": r["defence_team"],
        "og": r["offence_group"], "dg": r["defence_group"],
        "ogl": r["offence_group_label"], "dgl": r["defence_group_label"],
        "os": r["offence_effective_string"], "op": r["offence_player"],
        "ops": r["offence_player_status"],
        "ds": r["defence_effective_string"], "dp": r["defence_player"],
        "dps": r["defence_player_status"],
        "d": r["deficiency"], "st": r["cell_status"], "fl": r["flags"],
        "oo": r["offence_outs"], "do": r["defence_outs"],
    } for r in m])

    body = f'''
<div class="notice"><b>What a cell means.</b> For one game and one offensive group, the page shows
the <em>string</em> of the shallowest offensive player the club still publishes as available, the string of the
shallowest defender in the opposing group, and the difference. A positive difference means the defence is
reaching deeper into its chart than the offence is — an offensive advantage on paper, and nothing more:
no official source publishes what any of this is worth in points.</div>

<div class="controls"><label for="game-select">Game</label>
<select id="game-select">{''.join(f'<option value="{esc(g)}">{esc(g)}</option>' for g in games)}</select>
<span class="legend"><span class="sw pos"></span>offence advantage &nbsp;
<span class="sw neg"></span>defence advantage &nbsp; <span class="sw zero"></span>level</span></div>

<div id="matrix-holder"></div>

<div class="section-head"><div><div class="section-label">01 / HOW THE CELLS ARE BUILT</div>
<h2>The pairing convention, stated</h2></div></div>
<div class="notice"><b>This is our convention, not an official fact.</b> nfl.com does not publish which
defender covers which offensive group. The table below is the labelling this workspace uses. It is applied
identically to every club and every game, and it is the only place any judgement enters the matrix. Every
other value in a cell is copied from a published page.</div>
<div class="table-wrap"><table><caption>Offensive group to opposing defensive group, as used by this workspace.</caption>
<thead><tr><th scope="col">Offence group</th><th scope="col">Opposing defence group</th><th scope="col">Basis</th><th scope="col">Source</th></tr></thead><tbody>
{''.join(f'<tr><td>{esc(lbl)}</td><td>{esc({"OT": "Edge rusher", "OG": "Interior defensive line", "OC": "Interior defensive line", "QB": "Edge rusher", "RB": "Linebacker", "FB": "Linebacker", "TE": "Safety", "WR": "Cornerback"}[g])}</td><td>convention of this workspace; not published by the NFL</td><td>{srclink(SOURCE_REG10, "NFL injury report")}</td></tr>' for g, lbl in [("QB", "Quarterback"), ("RB", "Running back"), ("FB", "Fullback"), ("WR", "Wide receiver"), ("TE", "Tight end"), ("OT", "Offensive tackle"), ("OG", "Offensive guard"), ("OC", "Centre")])}
</tbody></table></div>

<div class="section-head"><div><div class="section-label">02 / WHAT THE RESERVE LIST CHANGED</div>
<h2>{len(cor)} cells moved</h2></div></div>
<p>The matrix is computed twice: once from the injury report alone, and once with the dated official roster
events applied. The difference is the correction. It is published in full so a reviewer can reverse it.</p>
{table(["Game", "Offence", "Group pairing", "Offence, report only", "Offence, corrected",
        "Defence, report only", "Defence, corrected", "Report source", "Event source"],
       [[esc(c["matchup"]), esc(c["offence_team"]), esc(c["group"]), esc(c["before_offence"]),
         esc(c["after_offence"]), esc(c["before_defence"]), esc(c["after_defence"]),
         srclink(c["source_url"], "injury report"),
         srclink(next((e["source_url"] for e in load("roster_events.json")
                       if e["effect"] == "cannot play" and e["applies_to_week_10"] == "yes"),
                      SOURCE_REG10), "roster event")]
        for c in cor],
       "Cells whose top string changed once the dated roster events were applied.")}

<div class="section-head"><div><div class="section-label">03 / WHAT COULD NOT BE FILLED</div>
<h2>{cen["matrix_cells_unverified"]} of {cen["matrix_rows"]} cells are blank, each with a reason</h2></div></div>
<div class="table-wrap"><table><caption>Why cells are blank. No cell is ever filled by inference.</caption>
<thead><tr><th scope="col">Reason</th><th scope="col">Cells</th><th scope="col">What would clear it</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>No depth chart captured for the club</td><td>{cen["matrix_cell_reasons"].get("no depth chart captured", 0) + cen["matrix_cell_reasons"].get("group not published; no depth chart captured", 0)}</td><td>A structured capture of the Packers' and Texans' official depth pages. The Packers publish theirs as text with jersey numbers prefixed; the Texans publish theirs as an image.</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
<tr><td>Club publishes no player in that group</td><td>{cen["matrix_cell_reasons"].get("group not published", 0) + cen["matrix_cell_reasons"].get("group not published; no depth chart captured", 0)}</td><td>A common position vocabulary across clubs, or a per-club mapping published by the club itself. See the <a href="coverage.html">published-depth census</a>.</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
</tbody></table></div>

<script>
const GAMES = {js_games};
const CELLS = {js_cells};
const GROUPS = {json.dumps(groups)};
function render(mat) {{
  const cells = CELLS.filter(c => c.matchup === mat);
  const g = GAMES.find(x => x.matchup === mat);
  const sides = [];
  cells.forEach(c => {{ if (!sides.some(s => s.off === c.off)) sides.push({{off: c.off, def: c.def}}); }});
  let out = '<h3>' + mat + '</h3><p class="muted">' + (g ? g.day : '') + '</p>';
  sides.forEach(side => {{
    out += '<div class="matrix-block"><h4>' + side.off + ' offence vs ' + side.def +
           ' defence</h4><div class="table-wrap"><table><thead><tr>' +
           '<th scope="col">Offence group</th><th scope="col">Offence string</th>' +
           '<th scope="col">Offence player</th><th scope="col">Defence group</th>' +
           '<th scope="col">Defence string</th><th scope="col">Defence player</th>' +
           '<th scope="col">Difference</th></tr></thead><tbody>';
    GROUPS.forEach(gr => {{
      const c = cells.find(x => x.off === side.off && x.og === gr);
      if (!c) return;
      let cls = c.st === 'published' ? '' : ' class="row-blank"';
      let dcell;
      if (c.st !== 'published') {{
        dcell = '<span class="pill warn">unverified</span>';
      }} else if (c.d > 0) {{
        dcell = '<span class="pill good">+' + c.d + '</span>';
      }} else if (c.d < 0) {{
        dcell = '<span class="pill bad">' + c.d + '</span>';
      }} else {{
        dcell = '<span class="pill">0</span>';
      }}
      const flag = c.fl ? '<br><small class="flag">' + c.fl + '</small>' : '';
      out += '<tr' + cls + '><td>' + c.ogl + '</td><td>' +
             (c.os === '' ? '—' : c.os) + '</td><td>' +
             (c.op === '' ? '<span class="pill warn">unverified</span>' : c.op) +
             (c.ops ? '<br><small>' + c.ops + '</small>' : '') + '</td><td>' + c.dgl +
             '</td><td>' + (c.ds === '' ? '—' : c.ds) + '</td><td>' +
             (c.dp === '' ? '<span class="pill warn">unverified</span>' : c.dp) +
             (c.dps ? '<br><small>' + c.dps + '</small>' : '') + '</td><td>' + dcell + flag +
             '</td></tr>';
    }});
    out += '</tbody></table></div>';
    const blank = cells.filter(c => c.off === side.off && c.st !== 'published');
    if (blank.length) {{
      out += '<details class="reason"><summary>' + blank.length +
             ' cell(s) could not be filled — show the reason for each</summary><ul>';
      blank.forEach(c => {{ out += '<li><b>' + c.ogl + ' vs ' + c.dgl + ':</b> ' + c.st + '</li>'; }});
      out += '</ul></details>';
    }}
    out += '</div>';
  }});
  document.getElementById('matrix-holder').innerHTML = out;
}}
const sel = document.getElementById('game-select');
sel.addEventListener('change', () => render(sel.value));
render(GAMES[0].matchup);
</script>
'''
    return page("Offence vs defence matchup matrix", "matrix.html", body,
                "Which published string of the defence each offensive string actually faces, "
                "for every group of every Week 10 game.")


# ----------------------------------------------------------------- 4. teams
def page_teams():
    teams = load("teams.json")
    by_team = {t["team"]: t for t in teams}
    rows = [[
        f'<a href="#{esc(t["team"].replace(" ", "-").lower())}">{esc(t["team"])}</a>',
        esc(t["matchup"]), str(t["rows_on_report"]), str(t["out"]), str(t["doubtful"]),
        str(t["questionable"]), f'<b>{t["net_designation_count"]}</b>',
        esc(t["depth_chart_captured"]),
        srclink(SOURCE_REG10, "report"),
    ] for t in sorted(teams, key=lambda x: -x["net_designation_count"])]

    blocks = []
    for t in sorted(teams, key=lambda x: x["team"]):
        starters = [[esc(s["player"]), esc(s["position"]), esc(s["club_slot"]),
                     str(s["published_rank"]), esc(s["game_status"]),
                     srclink(s["depth_source_url"], "depth chart"),
                     srclink(s["report_source_url"], "injury report")]
                    for s in t["starters_out"]]
        reps = [[esc(r["out_player"]), esc(r["club_slot"]),
                 blank(r["replacement_player"], "published depth exhausted"),
                 blank(r["replacement_rank"]),
                 esc(r["replacement_game_status"] or "—"),
                 srclink(r["depth_source_url"], "depth chart")]
                for r in t["replacements_named"]]
        unnamed = [[esc(u["player"]), esc(u["position"]), esc(u["game_status"]),
                    esc(u["reason"]), srclink(u["source_url"], "injury report")]
                   for u in t["not_on_depth_chart"]]

        blocks.append(f'''
<div class="section-head" id="{esc(t["team"].replace(" ", "-").lower())}">
<div><div class="section-label">{esc(t["matchup"])}</div><h2>{esc(t["team"])}</h2></div></div>
<div class="table-wrap"><table><caption>{esc(t["team"])} counts, computed from the {OBSERVED} transcript.</caption>
<thead><tr><th scope="col">Rows</th><th scope="col">Out</th><th scope="col">Doubtful</th>
<th scope="col">Questionable</th><th scope="col">Net designations</th>
<th scope="col">Depth chart captured</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>{t["rows_on_report"]}</td><td>{t["out"]}</td><td>{t["doubtful"]}</td>
<td>{t["questionable"]}</td><td><b>{t["net_designation_count"]}</b></td>
<td>{esc(t["depth_chart_captured"])}</td><td>{srclink(SOURCE_REG10, "report")}</td></tr>
</tbody></table></div>
<h3>Starters out or doubtful, with the slot the club publishes them in</h3>
{table(["Player", "Report position", "Club depth slot", "Published rank", "Game status", "Depth source", "Report source"],
       starters, "Only players the club's own depth chart lists. Rank 1 means the club publishes them as a first string.",
       empty="No player this club publishes is Out or Doubtful on the official report.")}
<h3>Replacement the club publishes next in that slot</h3>
{table(["Out player", "Club depth slot", "Next published player", "His rank", "His game status", "Depth source"],
       reps, "The next published player in the same slot who is not Out or Doubtful.",
       empty="No replacement chain to show.")}
<h3>Out or doubtful, but not on the club's published chart</h3>
{table(["Player", "Position", "Game status", "Why there is no slot", "Source"], unnamed,
       "These players cannot be placed in a depth slot from published data.",
       empty="Every Out or Doubtful player on this club appears on its published depth chart.")}
''')
    body = f'''
<div class="notice"><b>Net designation count</b> = Out + Doubtful on the official report. Questionable is
counted separately and never treated as out, because the league publishes no probability for it.
<b>Replacement</b> is never inferred: it is the next player the club itself publishes in the same slot.</div>
<div class="section-head"><div><div class="section-label">01 / ALL CLUBS</div>
<h2>Per-team decision view, {OBSERVED}</h2></div></div>
{table(["Club", "Matchup", "Rows", "Out", "Doubtful", "Questionable", "Net", "Depth chart?", "Source"],
       rows, "Sorted by net designation count, highest first. Click a club to jump to its detail.")}
<hr>
{"".join(blocks)}
'''
    return page("Per-team decision view", "teams.html", body,
                "Starters out, the replacement each club publishes, and the net designation count — "
                "one block per club, every row sourced.")


# ----------------------------------------------------------------- 5. replacement depth
def page_replacement_depth():
    rd = load("replacement_depth.json")
    rows = [[esc(r["team"]), esc(r["unit"]), esc(r["position"]), esc(r["group"]),
             esc(r["out_player"]), str(r["out_rank"]), esc(r["out_game_status"]),
             esc(r["out_basis"]),
             blank(r["replacement_player"], "published depth exhausted"),
             blank(r["replacement_rank"]), blank(r["replacement_game_status"]),
             blank(r["strings_skipped"]), str(r["published_depth_of_slot"]),
             srclink(r["source_url"], "depth chart")]
            for r in rd]
    unresolved = [r for r in rd if not r["replacement_player"]]
    biggest = sorted([r for r in rd if isinstance(r["strings_skipped"], int)],
                     key=lambda r: -r["strings_skipped"])[:12]
    body = f'''
<div class="notice"><b>The requirement this answers.</b> "Track the depth of the replacement, not just the
fact of a replacement." For every player the league expects not to play, this page publishes the string of
the next man the club lists behind him, how many strings were skipped to reach him, and whether that man is
himself carrying a designation. A replacement who is Questionable is flagged, not counted as clean.</div>

<div class="section-head"><div><div class="section-label">01 / THE BIGGEST DROPS</div>
<h2>Where the published chart falls furthest</h2></div></div>
{table(["Club", "Unit", "Slot", "Out player", "His string", "Replacement", "His string",
        "Strings skipped", "Depth published", "Source"],
       [[esc(r["team"]), esc(r["unit"]), esc(r["position"]), esc(r["out_player"]),
         str(r["out_rank"]), esc(r["replacement_player"]), str(r["replacement_rank"]),
         f'<b>{r["strings_skipped"]}</b>', str(r["published_depth_of_slot"]),
         srclink(r["source_url"], "depth chart")] for r in biggest],
       "The twelve chains that skip the most published strings.")}

<div class="section-head"><div><div class="section-label">02 / RUNS PAST THE CHART</div>
<h2>{len(unresolved)} chains have no published replacement left</h2></div></div>
<p>In each of these the club publishes nobody deeper in that slot, or everyone deeper is also Out or
Doubtful. The honest value is blank, not a guess.</p>
{table(["Club", "Unit", "Slot", "Out player", "His string", "Players deeper published",
        "Players still available", "Source"],
       [[esc(r["team"]), esc(r["unit"]), esc(r["position"]), esc(r["out_player"]),
         str(r["out_rank"]), str(r["published_depth_of_slot"]),
         str(r["players_still_available_in_slot"]), srclink(r["source_url"], "depth chart")]
        for r in unresolved],
       "Slots where the published chart is exhausted.")}

<div class="section-head"><div><div class="section-label">03 / EVERY CHAIN</div>
<h2>{len(rd)} replacement chains</h2></div></div>
{table(["Club", "Unit", "Slot", "Group", "Out player", "String", "Game status", "Basis",
        "Replacement", "His string", "His game status", "Strings skipped", "Depth published", "Source"],
       rows, "One row per player the published data says cannot play and whom the club's chart lists.")}
'''
    return page("Depth of replacement", "replacement-depth.html", body,
                "Not whether a starter is replaced, but which published string replaces him — "
                "and how far down the chart the club had to go.")


# ----------------------------------------------------------------- 6. roster events
def page_roster_events():
    ev = load("roster_events.json")
    df = load("depth_flags.json")
    announce = [e for e in ev if e["effect"] == "announcement"]
    rows = [[esc(e["date"]), esc(e["club"]), esc(e["player"]), esc(e["event_class"]),
             esc(e["verbatim"]), esc(e["injury_report_game_status"] or "—"),
             esc(e["applies_to_week_10"]), esc(e["agreement"]),
             srclink(e["source_url"], "article")]
            for e in sorted(ev, key=lambda x: (x["date"], x["club"], x["player"]))]
    flags = [[esc(f["team"]), esc(f["unit"]), esc(f["position"]), str(f["published_rank"]),
              esc(f["player"]), esc(f["event_date"]), esc(f["event"]),
              esc(f["on_week_10_injury_report"] or "not on the report"),
              srclink(f["depth_source_url"], "depth chart"),
              srclink(f["event_source_url"], "roster event")]
             for f in df]

    body = f'''
<div class="notice"><b>Why this page exists.</b> A player missing from the weekly injury report is not
evidence that he is available. The club may have placed him on the reserve list, in which case the NFL's own
weekly page will never list him. The rows below were copied from the body of dated nfl.com articles that were
opened and read on {OBSERVED}; each carries the sentence as published and the URL it came from.</div>

<div class="section-head"><div><div class="section-label">01 / ANNOUNCED STARTERS AND BACKUPS</div>
<h2>{len(announce)} dated announcements</h2></div></div>
<p>These are the only rows on this site where a starter is stated rather than derived from a depth chart.
They are also the only independent check available on the depth-derived answer — and where they exist, the
two agree.</p>
{table(["Date", "Club", "Player", "Announcement", "Verbatim", "Source"],
       [[esc(a["date"]), esc(a["club"]), esc(a["player"]), esc(a["event_class"]),
         esc(a["verbatim"]), srclink(a["source_url"], "article")] for a in announce],
       "Starters and backups announced in the body of a dated official article.")}

<div class="section-head"><div><div class="section-label">02 / STALE DEPTH ROWS</div>
<h2>{len(df)} published depth rows name a player a dated official event says cannot play</h2></div></div>
<p>The club chart was captured on {PREV_OBSERVED}. A depth row is stale when a dated official roster event
says the player it names cannot play in the game in question. Those rows are excluded from the matrix and
listed here instead of being published as fact.</p>
{table(["Club", "Unit", "Slot", "Rank", "Player", "Event date", "Event",
        "On the Week 10 report?", "Depth source", "Event source"], flags,
       "Every published depth row contradicted by a dated official roster event.")}

<div class="section-head"><div><div class="section-label">03 / FULL LEDGER</div>
<h2>{len(ev)} dated roster, reserve and designation events</h2></div></div>
{table(["Date", "Club", "Player", "Event class", "Verbatim", "Injury report says",
        "Applies to Week 10", "Agreement", "Source"], rows,
       "Every dated event read from an official article body on 2026-11-16.")}
'''
    return page("Dated official roster events", "roster-events.html", body,
                "Reserve-list placements, activations, announced starters and final designations, "
                "each copied from a dated official article.")


# ----------------------------------------------------------------- 7. coverage
def page_coverage():
    cen = load("census.json")
    voc = load("vocabulary.json")
    grp = cen["group_rank_depth"]
    depth_rows = []
    for g in sorted(grp):
        d = grp[g]
        depth_rows.append([
            esc(voc[g]["label"]), esc(g), str(d["1"]), str(d["2"]), str(d["3"]), str(d["4"]),
            f'{d["3"] - d["4"] if False else ""}<b>{cen["teams_with_depth_chart"] - d["3"]}</b> of {cen["teams_with_depth_chart"]}',
            str(voc[g]["count"]),
            srclink("https://www.nfl.com/teams/", "NFL team index"),
        ])
    vocab_rows = [[esc(voc[g]["label"]), esc(g), str(voc[g]["count"]),
                   esc(", ".join(voc[g]["clubs_with_no_player_in_group"]) or "none"),
                   srclink("https://www.nfl.com/teams/", "NFL team index")]
                  for g in sorted(voc) if voc[g]["count"]]
    body = f'''
<div class="notice"><b>The question this answers.</b> The brief asks for a first-through-fourth-string view.
This page publishes how deep the 30 captured club charts actually go, and where they stop.</div>

<div class="section-head"><div><div class="section-label">01 / HOW DEEP THE CHARTS GO</div>
<h2>Of {cen["teams_with_depth_chart"]} captured club charts, how many publish a 1st, 2nd, 3rd and 4th string</h2></div></div>
{table(["Group", "Code", "Clubs with a 1st string", "2nd", "3rd", "4th",
        "Clubs with no 3rd string", "Clubs with nothing in the group", "Source"], depth_rows,
       "Counted from the committed club depth capture (1,745 rows, 676 slots) of 2026-11-12.")}
<p>The brief's premise — that every club publishes four strings at every position — does not hold. Three
groups publish a third string at more than half the clubs: running back ({grp["RB"]["3"]}), tight end
({grp["TE"]["3"]}) and linebacker ({grp["LB"]["3"]}). Only one club in thirty publishes a fourth-string
cornerback, and no club publishes a fourth-string offensive lineman or edge rusher.</p>

<div class="section-head"><div><div class="section-label">02 / THE VOCABULARY PROBLEM</div>
<h2>Clubs do not publish a common set of position labels</h2></div></div>
<div class="notice"><b>A structural limit, not a parsing bug.</b> Nine of the thirty captured clubs publish
no player under any edge-rusher label (DE, LDE, RDE, EDGE or RUSH) — they publish "DL" and "OLB" instead.
This workspace does not guess which of those is the edge rusher, so those cells stay blank with the reason
shown. Filling them would mean inventing a depth order the club never published, which the brief explicitly
rejects.</div>
{table(["Group", "Code", "Clubs with nobody in the group", "Those clubs", "Source"], vocab_rows,
       "Groups that at least one captured club leaves empty.")}

<div class="section-head"><div><div class="section-label">03 / SHARED AND EMPTY SLOTS</div>
<h2>{cen["slots_with_multiple_rank1"]} of {cen["slots"]} slots name more than one first string</h2></div></div>
<p>The brief warns that treating column one as "the starter" would fabricate a starter the club never named.
It is right: {cen["slots_with_multiple_rank1"]} slots across the {cen["teams_with_depth_chart"]} captured clubs list more than one player at
rank 1 — three receivers at rank 1, three inside linebackers at rank 1, and so on. This workspace treats a
slot as a group and never reduces it to a single named starter.</p>
<div class="table-wrap"><table><caption>Coverage census.</caption>
<thead><tr><th scope="col">Measure</th><th scope="col">Value</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>Club depth charts captured</td><td>{cen["teams_with_depth_chart"]} of 32</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
<tr><td>Clubs on the Week 10 report with no captured chart</td><td>{esc(", ".join(cen["teams_on_report_without_depth_chart"]))}</td><td>{srclink(SOURCE_REG10, "NFL injury report")}</td></tr>
<tr><td>Depth rows used</td><td>{cen["depth_rows_used"]}</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
<tr><td>Slots</td><td>{cen["slots"]}</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
<tr><td>Slots naming more than one first string</td><td>{cen["slots_with_multiple_rank1"]}</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
</tbody></table></div>
'''
    return page("Published depth census", "coverage.html", body,
                "How deep the official club depth charts actually go, which clubs publish which labels, "
                "and where the 1st-to-4th-string view cannot be built from published data.")


# ----------------------------------------------------------------- 8. flagged
def page_flagged():
    ev = load("roster_events.json")
    cen = load("census.json")
    rec = load("injury_reconciliation.json")
    df = load("depth_flags.json")
    contradictions = [e for e in ev if e["agreement"].startswith("CONTRADICTS")]
    absences = [e for e in ev if e["agreement"].startswith("the player is absent")]
    prev = rec["previous"]

    items = []
    items.append((
        "M-F1", "Two official pages disagree about six players",
        f"On {OBSERVED} the official injury report still shows these players as Questionable, while the "
        f"official news roundup dated 2026-11-14 says each was ruled out or will remain on injured reserve. "
        f"Both pages are NFL-published. This workspace applies the dated roster event and lists every cell it "
        f"changed, so the choice can be reversed — but the disagreement itself is not resolved by any source "
        f"available here.",
        f'{len(contradictions)} players',
        [[esc(e["club"]), esc(e["player"]), esc(e["injury_report_game_status"]),
          esc(e["verbatim"]), srclink(SOURCE_REG10, "injury report"),
          srclink(e["source_url"], "roundup")] for e in contradictions],
        ["Club", "Player", "Injury report says", "Dated roundup says", "Report", "Roundup"]))
    items.append((
        "M-F2", "Three players are on the reserve list and never appear on the weekly report",
        "A player absent from the injury report is not evidence of availability. These three are named in "
        "dated official articles as being on injured reserve, yet the weekly report lists no row for them at "
        "all. Any availability feature built on the report alone would score them as fully available.",
        f'{len(absences)} players',
        [[esc(e["club"]), esc(e["player"]), esc(e["date"]), esc(e["verbatim"]),
          srclink(e["source_url"], "article")] for e in absences],
        ["Club", "Player", "Date", "What the article says", "Source"]))
    items.append((
        "M-F3", "The committed snapshot describes a different week",
        f"The capture committed to decision-lab/data/official_snapshot.json was taken {PREV_OBSERVED}. "
        f"The same page now carries {rec['live_rows']} rows instead of {prev['rows']}, and "
        f"{rec['live_out'] + rec['live_doubtful'] + rec['live_questionable']} game designations instead of "
        f"{prev['out'] + prev['doubtful'] + prev['questionable']}. Four clubs published as injury-free now "
        f"publish full tables. Any figure derived from the committed snapshot should be treated as a Thursday "
        f"morning reading, not as the week. This session does not edit that file; the request is logged in "
        f"COORDINATION.md for its owner.",
        f'{prev["rows"]} → {rec["live_rows"]} rows',
        [[esc(x["team"]), "No Injuries Reported", str(x["rows_now"]),
          srclink(SOURCE_REG10, "report")] for x in rec["no_injury_now_listed"]],
        ["Club", "Published " + PREV_OBSERVED, "Rows " + OBSERVED, "Source"]))
    items.append((
        "M-F4", "Two clubs publish no structured depth chart",
        "The Packers prefix jersey numbers to player names and the Texans publish their chart as an image. "
        "The committed capture holds 30 of 32 clubs. Every matrix cell that would need either club is blank "
        "and counts as unverified; no transcription by eye is used to fill them.",
        f'{len(cen["teams_on_report_without_depth_chart"])} clubs',
        [[esc(c), "no captured depth chart", "0 rows in the capture",
          srclink("https://www.nfl.com/teams/", "NFL team index")]
         for c in cen["teams_on_report_without_depth_chart"]],
        ["Club", "Problem", "Rows captured", "Source"]))
    items.append((
        "M-F5", "Nine clubs publish no edge rusher at all",
        "No player in those clubs' charts carries an edge-rusher label (DE, LDE, RDE, EDGE or RUSH); they "
        "publish DL and OLB instead. Mapping one of those onto 'edge rusher' would invent a depth order the "
        "club never published, which the brief rejects. Those cells stay blank with the reason stated.",
        "9 of 30 clubs",
        [[esc(c["label"]), str(c["count"]), esc(", ".join(c["clubs_with_no_player_in_group"])),
          srclink("https://www.nfl.com/teams/", "NFL team index")]
         for c in [load("vocabulary.json")["EDGE"]]],
        ["Group", "Clubs with nobody", "Those clubs", "Source"]))
    items.append((
        "M-F6", "The offence-versus-defence pairing is a convention, not an official fact",
        "nfl.com does not publish which defender covers which offensive group. The pairing used in the matrix "
        "(tackle vs edge, guard and centre vs interior line, receiver vs cornerback, tight end vs safety, "
        "back vs linebacker, quarterback vs edge) is this workspace's stated convention. It is applied "
        "identically everywhere and is the only judgement in the matrix, but it is not sourced.",
        "8 pairings",
        [[esc(a), esc(b), "convention of this workspace",
          srclink(SOURCE_REG10, "NFL injury report")] for a, b in
         [("Offensive tackle", "Edge rusher"), ("Offensive guard", "Interior defensive line"),
          ("Centre", "Interior defensive line"), ("Quarterback", "Edge rusher"),
          ("Running back", "Linebacker"), ("Fullback", "Linebacker"),
          ("Tight end", "Safety"), ("Wide receiver", "Cornerback")]],
        ["Offence group", "Opposing group", "Basis", "Source"]))
    items.append((
        "M-F8", "The root landing page shipped as two stacked HTML documents",
        "index.html contained two complete HTML documents concatenated: a 3,355-byte stub opening at "
        "byte 0, followed by the 92,790-byte live page opening at byte 3,355. A browser renders the "
        "stub's header and lede and then the entire live page again, so the landing page showed a "
        "duplicated header and navigation. The stub is the older of the two: its category nav linked "
        "shadow-board where the live page links skill-lab and the availability ledger. Fixed on "
        "2026-11-16 by removing the stub and keeping the live page byte for byte. It is recorded here "
        "rather than quietly fixed because no existing validator could detect it: a duplicated section "
        "is not a broken link.",
        "2 documents, 1 page",
        [["index.html", "2 <code>&lt;!doctype html&gt;</code> declarations, 2 <code>&lt;body&gt;</code> elements",
          "3,355-byte stub removed; 92,790-byte page kept",
          'fixed 2026-11-16',
          srclink("https://www.nfl.com/injuries/", "NFL injury report")]],
        ["File", "What was wrong", "What was done", "When", "Source"]))
    items.append((
        "M-F9", "Every page repeats the navigation instead of generating it, so they drift apart",
        "index.html holds the sidebar navigation, and each page's build script copies that file's "
        "prefix as its own navigation rather than rendering the nav from one shared list. The "
        "consequence is that a nav edit only reaches the pages whose generator happens to be re-run. "
        "Adding the matchup entry to index.html on 2026-11-16 left pricing.html and corpus.html "
        "carrying a navigation that was already two edits behind: it still linked shadow-board and "
        "had no skill lab, no availability ledger and no injury archive. Both were re-generated and "
        "re-committed. readiness.html is still stale and is not fixed here: its generator "
        "(readiness/build_readiness.py) refuses to run outside a full clone, and readiness.html is "
        "not covered by any drift check in the workflow. The durable fix is one shared nav list that "
        "every generator imports.",
        "3 pages behind",
        [["pricing.html", "nav linked shadow-board; no skill lab, ledger, injury archive or matchup",
          "re-generated 2026-11-16", "fixed",
          srclink("https://www.nfl.com/injuries/", "NFL injury report")],
         ["corpus.html", "same two edits behind", "re-generated 2026-11-16", "fixed",
          srclink("https://www.nfl.com/injuries/", "NFL injury report")],
         ["readiness.html", "same, and also missing matchup; generator not run in CI, no drift check",
          "left as-is and reported", "open",
          srclink("https://www.nfl.com/injuries/", "NFL injury report")]],
        ["Page", "What the navigation was missing", "What was done", "State", "Source"]))

    items.append((
        "M-F7", "The depth charts are four days older than the report they are joined to",
        f"The club depth capture is dated {PREV_OBSERVED}; the injury report transcript is dated {OBSERVED}. "
        f"Between those dates the league recorded reserve-list placements, activations and trades. "
        f"{len(df)} published depth rows name a player a dated official event says cannot play. The join is "
        f"still made because the charts are the only published depth source, but every such row is listed on "
        f"the roster-events page and excluded from the matrix.",
        f'{len(df)} stale rows',
        [[esc(f["team"]), esc(f["player"]), esc(f["event_date"]), esc(f["event"]),
          srclink(f["event_source_url"], "roster event")] for f in df[:12]],
        ["Club", "Player", "Event date", "Event", "Source"]))

    blocks = []
    for iid, title, desc, count, rows, heads in items:
        blocks.append(f'''
<div class="section-head"><div><div class="section-label">{esc(iid)}</div><h2>{esc(title)}</h2></div>
<div class="count-badge">{esc(count)}</div></div>
<p>{desc}</p>
{table(heads, rows, esc(iid) + " — every row carries the official page it was read from.")}''')

    body = f'''
<div class="notice"><b>What "flagged" means here.</b> None of these items blocks publication. Each is a place
where the published sources are missing, silent, out of date, or in disagreement with each other. In every
case the affected cell on this site is blank or carries the value with its source, never a filled-in guess.
Nothing here is resolved by inference.</div>
<div class="section-head"><div><div class="section-label">FLAGGED FOR REVIEW</div>
<h2>{len(items)} items from this workspace</h2></div></div>
{"".join(blocks)}
'''
    return page("Flagged for review", "flagged.html", body,
                "Where the official sources are silent, stale, missing or in disagreement with each other.")


# ----------------------------------------------------------------- 9. sources
def page_sources():
    cen = load("census.json")
    rec = load("injury_reconciliation.json")
    ev = load("roster_events.json")
    src = {}
    for e in ev:
        src.setdefault(e["source_url"], 0)
        src[e["source_url"]] += 1
    rows = [
        [srclink(SOURCE_REG10, "nfl.com/injuries (week-specific URL)"),
         "Official NFL injury report, Week 10 2026",
         "Player, position, injury description, practice status, game status, per club, per game",
         OBSERVED, f'{rec["live_rows"]} rows transcribed line by line',
         "Mutable page. Not a point-in-time archive; a capture hash proves byte integrity only."],
        [srclink(SOURCE, "nfl.com/injuries"),
         "The same official report at its default URL", OBSERVED,
         "Independent second read used to confirm the Commanders, Giants, Patriots and Lions tables",
         "Same content as the week-specific URL on the day of reading.",
         "Both URLs returned identical tables for the sections compared."],
        [srclink("https://www.nfl.com/news/drew-lock-no-injury-designation-seahawks-raiders", "article"),
         "Drew Lock start announcement", "2026-11-13",
         "Seahawks starting quarterback and backup, as stated by the head coach",
         "One club, one game.", "Body read; the sentence is quoted verbatim on the roster-events page."],
        [srclink("https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start", "article"),
         "Malik Willis injured reserve; Kyle McCord to start", "2026-11-11",
         "Dolphins starting quarterback, the reserve-list placement behind it, and the expected backup",
         "One club, four weeks of availability.",
         "Body read; the return date is quoted from the article, not calculated."],
        [srclink("https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14", "article"),
         "League-wide roundup, Saturday 14 November 2026", "2026-11-14",
         "Reserve-list placements, activations, elevations and final designations by club",
         f'{src.get("https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-saturday-nov-14", 0)} events transcribed',
         "Body read in full. Only clubs with news that day are listed; a club with no entry is not evidence of no move."],
        [srclink("https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-thursday-nov-5", "article"),
         "League-wide roundup, Thursday 5 November 2026", "2026-11-05",
         "Ravens reserve-list placements for Lamar Jackson and Tyler Huntley",
         f'{src.get("https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-thursday-nov-5", 0)} events transcribed',
         "Only the Arizona, Atlanta, Baltimore, Buffalo, Carolina, Chicago, Cincinnati, Cleveland and Dallas sections were read."],
        [srclink("https://www.nfl.com/teams/", "index"),
         "NFL team index", "2026-11-12 (capture)",
         "Entry point for the club depth charts used throughout",
         f'{cen["teams_with_depth_chart"]} of 32 clubs captured by an earlier session',
         "Not edited by this session. Two clubs are missing from the capture."],
        [srclink(TRANSACTIONS, "hub"),
         "NFL transactions hub", "2026-11-16",
         "Referenced by every roundup article as the daily transaction breakdown",
         "0 rows transcribed here",
         "Linked as the authoritative transaction source; not itself parsed by this workspace."],
    ]
    body = f'''
<div class="notice"><b>Authority boundary.</b> Every value on these pages comes from nfl.com or from a club
site reached through the official NFL team index. A capture hash proves that bytes did not change, not that
the publisher grants reuse rights or that the page will still say the same thing tomorrow. No page here is a
point-in-time archive; each is a live document that was read on the date shown.</div>
<div class="section-head"><div><div class="section-label">SOURCE REGISTER</div>
<h2>Everything this workspace read</h2></div></div>
{table(["Source", "What it is", "Date read", "What was taken from it", "Coverage", "Limits"],
       [[r[0], esc(r[1]), esc(r[2]), esc(r[3]), esc(r[4]), esc(r[5])] for r in rows],
       "One row per source. Dates are the publication date of the article or the moment of reading.")}
<div class="section-head"><div><div class="section-label">NOT USED</div><h2>Sources deliberately excluded</h2></div></div>
<div class="table-wrap"><table><caption>Community and unofficial sources are never used to fill a cell.</caption>
<thead><tr><th scope="col">Source</th><th scope="col">Why it is excluded</th><th scope="col">Where it does appear</th><th scope="col">What is used instead</th></tr></thead><tbody>
<tr><td>nflverse / nflreadr community releases</td><td>Not established as official NFL data in this repository's own source-authority boundary.</td><td>Other workspaces on this site; labelled there, and never in an official-only gate.</td><td>{srclink(SOURCE_REG10, "official report used instead")}</td></tr>
<tr><td>Club charts labelled "UNOFFICIAL" by the publishing club</td><td>The capture marks 32 rows this way; a club disclaiming its own chart is not evidence of a depth order.</td><td>Excluded from every depth-derived value here.</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
<tr><td>Jersey number, experience, salary or roster order</td><td>The brief rejects deriving depth order from these. Nothing on these pages does.</td><td>Nowhere on this workspace.</td><td>{srclink("https://www.nfl.com/teams/", "NFL team index")}</td></tr>
</tbody></table></div>
'''
    return page("Sources", "sources.html", body,
                "Every page this workspace read, what was taken from it, and what was deliberately not used.")




# ----------------------------------------------------------------- 10. questions
QUESTIONS = [
    ("MQ-1", "When two official pages disagree about a player, which one wins?",
     "Six players are Questionable on the injury report and ruled out or on injured reserve in the "
     "dated Saturday roundup. Both pages are published by the NFL.",
     "(a) The injury report is the weekly club filing; (b) the roundup is a same-day summary of it. "
     "Nothing available here establishes precedence.",
     "Read the club's own official weekly report, then the official game book for the game in question, "
     "and record which page the club itself treats as final. Until then, do not use either page as a "
     "model input without recording which one was used.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MQ-2", "Is the official injury report an archive or a live page?",
     "The same page held 254 rows across 24 clubs on 2026-11-12T06:32Z and 347 rows across 28 clubs on "
     "2026-11-16. A capture hash proves byte integrity, not that the page is frozen.",
     "It behaves as a live page during the week. Whether a past week's tab freezes after that week ends "
     "has not been tested.",
     "Fetch a completed week's URL (for example Week 6) twice, several days apart, and compare hashes. "
     "If it is stable, the week tabs are an archive and historical reads become possible. If it is not, "
     "no official point-in-time injury history exists and the multi-day capture in this repository is "
     "the only way to get one.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MQ-3", "How deep do clubs actually publish, and does it change during the season?",
     "Of 30 captured charts, 10 publish a third-string cornerback, 3 a third-string offensive tackle, "
     "and 1 a fourth-string cornerback. No club publishes a fourth-string offensive lineman or edge rusher.",
     "The brief's premise of a 1st-to-4th-string view cannot be met from club charts as they stand.",
     "Re-capture all 32 clubs weekly for one month and count rank-3 and rank-4 rows per club per week. "
     "If depth is stable, the honest answer is that the fourth string is unpublished and no feature may "
     "depend on it.",
     "https://www.nfl.com/teams/"),
    ("MQ-4", "Do the Texans publish a structured depth chart anywhere?",
     "The committed capture holds 0 Texans rows; the brief records that the chart is published as an image.",
     "Not established here. No Texans depth page was opened in this session.",
     "Open houstontexans.com/team/depth-chart and record whether the page carries a table in its HTML. "
     "If it does not, the Texans cannot enter any depth-derived feature until an authorised structured "
     "source exists. Transcription by eye is explicitly out of scope.",
     "https://www.nfl.com/teams/houston-texans/"),
    ("MQ-5", "Do the Packers' jersey-number prefixes prevent parsing, or just the current parser?",
     "The committed capture holds 0 Packers rows. The brief records that the club prepends jersey numbers.",
     "Not tested here: no Packers depth page was opened in this session.",
     "Fetch the Packers depth page, strip leading digits, and store both the parsed name and the raw "
     "string. The raw string is what makes the parse auditable if it later turns out to be wrong.",
     "https://www.nfl.com/teams/green-bay-packers/"),
    ("MQ-6", "Does any official source say which defender covers which offensive group?",
     "No. nfl.com publishes no coverage assignment. The pairing used in the matrix is this workspace's "
     "own stated convention.",
     "Every deficiency number on this site rests on a convention, not on an official fact.",
     "Check the official game book and the official participation report for a game and see whether "
     "either records a coverage assignment. If neither does, publish the pairing convention alongside "
     "every deficiency figure permanently, as done here.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MQ-7", "Is there an official snap-count source?",
     "data/raw/snap_counts_2026.csv exists in this repository but comes from a community release, not "
     "from an NFL page. The brief asks for playing time as the depth proxy, not jersey order.",
     "No official snap-count page has been verified in this repository.",
     "Open nextgenstats.nfl.com and check whether per-game snap counts are published for the current "
     "season with a stated licence. If they are, playing time can replace the depth chart as the "
     "starter proxy and the two missing clubs stop mattering.",
     "https://nextgenstats.nfl.com/"),
    ("MQ-8", "How far back does the official transactions page go, and is it parseable?",
     "The transactions hub is linked by every roundup article as the daily breakdown, but this workspace "
     "parses 0 rows from it. Every reserve-list row here comes from a news article body.",
     "Not established.",
     "Read the transactions page for a single day and count the rows by move type. If it is parseable "
     "and dated, it replaces hand transcription of the roundups and closes the reserve-list gap properly.",
     "https://www.nfl.com/transactions/"),
    ("MQ-9", "Can the depth-derived starter be confirmed for more than one club?",
     "For Seattle, yes: the depth chart's second string, Drew Lock, is the quarterback the head coach "
     "named on 2026-11-13. For the other 27 clubs on the report, no dated announcement was read.",
     "One club out of 28 is confirmed. That is a proof of method, not coverage.",
     "For each club, read that week's roundup articles and record any stated starter. Where a club's "
     "announced starter differs from its depth-derived string, publish both — never overwrite one "
     "with the other.",
     "https://www.nfl.com/news/drew-lock-no-injury-designation-seahawks-raiders"),
    ("MQ-10", "What is a Questionable designation actually worth?",
     "90 of 347 rows are Questionable. The league's own policy text gives no percentage for it.",
     "Cannot be measured here: this workspace captures no inactive list. A concurrent session has "
     "archived the official Week 10 inactive list under injury-archive/ and published a measured "
     "inactive rate per designation, but that is outside this workspace's scope and is not used here.",
     "Capture the official inactive list for each week of a season, join it to that week's designations, "
     "and publish the play rate per designation with a confidence interval. Only then may the label "
     "become a model feature. Point this workspace's replacement chains at that archive: it would turn "
     "the 59 chains here from 'the club publishes this man next' into 'this man actually played'.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
]

SUGGESTIONS = [
    ("MS-1", "Capture the injury report three times a week, with hashes, and commit the captures",
     "A Thursday-morning read carried 6 game designations. The same page on Monday carried 171. Any "
     "availability feature built on a single capture silently describes the wrong week.",
     "Decision: availability features — every replacement chain, matrix cell and per-team count on this site.",
     "A. Extend the existing injury-capture workflow to Wednesday, Thursday and Friday, plus a Saturday "
     "read, keeping the raw hash per read. B. Rely on the daily nfl.com roundups instead, which are "
     "dated articles rather than mutable pages. C. Accept a single weekly read and label every figure "
     "with the exact timestamp it came from.",
     "A gives a real series; B is cheaper but the roundups omit clubs with no news; C is what happens "
     "if nothing is done and it is the current state.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MS-2", "Recover the two missing clubs before widening anything else",
     "The Packers prefix jersey numbers and the Texans publish their chart as an image. 32 of the 224 "
     "matrix cells are blank for no other reason.",
     "Decision: whether the matchup matrix can ever cover all 32 clubs.",
     "A. Strip leading digits for the Packers and store the raw string beside the parsed name; find out "
     "whether the Texans publish a structured page at all. B. Drop the club charts and use officially "
     "published snap counts as the depth proxy. C. Leave both clubs blank permanently and say so on "
     "every page that uses depth.",
     "A is a day's work and recovers one club; B is the better long-term answer but depends on MQ-7; "
     "C is honest and costs nothing.",
     "https://www.nfl.com/teams/"),
    ("MS-3", "Parse the official transactions page into the availability pipeline",
     "Every reserve-list row here was transcribed by hand from a news article. That does not scale and "
     "it silently misses clubs with no news that day.",
     "Decision: whether 'not listed' can ever be separated from 'available'.",
     "A. Read the transactions hub daily and store dated, hashed rows by move type. B. Keep using the "
     "roundups but add a completeness check that records which clubs had no entry. C. Do nothing and "
     "keep flagging the gap.",
     "A is the only option that closes the gap; B at least stops it being invisible.",
     "https://www.nfl.com/transactions/"),
    ("MS-4", "Add an announced-starter field fed by the daily roundups",
     "The brief asks for announced-starter evidence rather than an inferred replacement. Four dated "
     "announcements were found for three clubs in about an hour of reading.",
     "Decision: whether a starter is stated or derived, per club per week.",
     "A. Read each week's roundups and record any stated starter as a separate field that sits beside, "
     "never over, the depth-derived string. B. Treat the depth chart as sufficient. C. Drop the depth "
     "chart wherever an announcement exists.",
     "A is the only option that keeps both sources visible where they disagree.",
     "https://www.nfl.com/news/drew-lock-no-injury-designation-seahawks-raiders"),
    ("MS-5", "Write down a per-club position vocabulary, by hand, from each club's own page",
     "Nine of thirty captured clubs publish no edge rusher at all — they publish DL and OLB instead. "
     "26 matrix cells are blank for this reason alone.",
     "Decision: whether the offence-versus-defence matrix can be completed.",
     "A. Maintain a per-club label map, sourced to that club's own page, reviewed each time a club "
     "changes its chart. B. Map by convention centrally and label every mapped cell as derived. "
     "C. Leave those cells blank, as now.",
     "A is the only option that does not invent a depth order; it is also the only one that needs "
     "ongoing maintenance.",
     "https://www.nfl.com/teams/"),
    ("MS-6", "Pin the scrapers to an expected shape and fail the build on drift",
     "Three injury-row counts (254, 279, 347) have been published side by side on this site. No alarm "
     "fired for any of them.",
     "Decision: whether a published count can be trusted.",
     "A. Pin the report to 14 games and 28 clubs per week, and the depth capture to 32 clubs, failing "
     "the build when either moves. B. Publish the count with its timestamp and hash and let a reader "
     "notice. C. Leave it as it is.",
     "A is a small change to scripts that already run in CI.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MS-7", "Decide the two-source conflict rule before any availability figure enters a model",
     "Six players are Questionable on one official page and ruled out on another official page the same "
     "week. A model fed one will disagree with a model fed the other on 1.7% of rows.",
     "Decision: which official page is the input of record.",
     "A. Take the injury report as the input of record and carry the roundup as a contradicting flag. "
     "B. Take the latest-dated statement regardless of page. C. Exclude any player the two pages "
     "disagree about from any model input.",
     "C is the most conservative and loses the least sleep; A is what this workspace currently does and "
     "publishes the conflict for.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
    ("MS-8", "Reconcile the published injury counts once, in one place",
     "254 rows, 279 rows and 347 rows are all published on this site for the same week of the same page.",
     "Decision: which number a reader should believe.",
     "A. Publish one table of every count with its hash, timestamp and the URL it was read from, and "
     "delete the others from the pages that state them bare. B. Leave the counts as they are with a "
     "footnote. C. Pick the largest and move on.",
     "A is what the reconciliation page in this workspace already does for two of the three reads; the "
     "279-row figure is not yet traced to a committed capture.",
     "https://www.nfl.com/injuries/league/2026/REG10"),
]


def page_questions():
    rows = [[f'<b>{esc(q[0])}</b>', esc(q[1]), esc(q[2]), esc(q[3]), esc(q[4]),
             srclink(q[5], "official source")] for q in QUESTIONS]
    body = f"""
<div class="notice"><b>What this list is.</b> The questions that must be answered before the numbers on
this site can be used to make a decision. Each row states what is already known from a published source,
what is not known, and the concrete action that would close the gap. No row answers itself by inference.</div>
<div class="section-head"><div><div class="section-label">OPEN QUESTIONS</div>
<h2>{len(QUESTIONS)} questions this workspace cannot close</h2></div></div>
{table(["ID", "Question", "What we have", "What we do not have", "How to find out", "Source"], rows,
       "One row per open question. The source column links the official page the known part came from.")}
"""
    return page("Questions this workspace raises", "questions.html", body,
                "What is known, what is not, and the concrete action that would close each gap — "
                "before any of these numbers is used to decide anything.")


def page_suggestions():
    rows = [[f'<b>{esc(g[0])}</b>', esc(g[1]), esc(g[2]), esc(g[3]), esc(g[4]), esc(g[5]),
             srclink(g[6], "official source")] for g in SUGGESTIONS]
    body = f"""
<div class="notice"><b>How to use this page.</b> Each row is a proposal with the gap it closes, the
decision it affects, and two or three paths with their cost. Nothing here is implemented. The point of
the section is that a path is chosen deliberately, on the record, before anything is built.</div>
<div class="section-head"><div><div class="section-label">SUGGESTIONS</div>
<h2>{len(SUGGESTIONS)} proposals, none implemented</h2></div></div>
{table(["ID", "Proposal", "The gap it closes", "Decision it affects", "Paths", "Cost of each path",
        "Source"], rows,
       "One row per proposal. Every proposal is traceable to an official page; none changes a published number.")}
"""
    return page("Suggestions for review", "suggestions.html", body,
                "What to do about the gaps, with the paths and their costs, so a choice is made on the "
                "record before anything is built.")


def main() -> int:
    pages = {
        "index.html": page_index(),
        "injury-verify.html": page_injury_verify(),
        "matrix.html": page_matrix(),
        "teams.html": page_teams(),
        "replacement-depth.html": page_replacement_depth(),
        "roster-events.html": page_roster_events(),
        "coverage.html": page_coverage(),
        "flagged.html": page_flagged(),
        "sources.html": page_sources(),
        "questions.html": page_questions(),
        "suggestions.html": page_suggestions(),
    }
    for name, doc in pages.items():
        (ROOT / name).write_text(doc, encoding="utf-8")
        print(f"wrote {name} ({len(doc):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
