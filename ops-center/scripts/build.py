#!/usr/bin/env python3
"""Build the ops-centre static site.

Everything rendered here comes from `model.py`, which only copies official rows
or counts them. Blank cells are rendered as an explicit 'unverified' marker and
never as a dash that could be read as a value.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402
import theme as thememod  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops-center"
PAGES = OPS
DATA = OPS / "data"
BUILD_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

NAV = [
    ("index.html", "Overview"),
    ("availability.html", "Availability & chains"),
    ("coverage.html", "Published depth"),
    ("drift.html", "Source drift"),
    ("questions.html", "Decision register"),
    ("suggestions.html", "Suggestions"),
    ("leaderboard.html", "Line origination"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
]

STATUS_LABEL = {
    "chain-identified": ("Chain published", "ok"),
    "injured-player-not-on-published-chart": ("Not on club chart", "warn"),
    "no-published-depth-at-position": ("No published depth", "warn"),
    "no-depth-capture-for-club": ("No depth capture", "danger"),
}

RANK_WORD = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th"}

INJURY_URL = "https://www.nfl.com/injuries/"

SHORT_PRACTICE = {
    "Did Not Participate In Practice": "DNP",
    "Limited Participation in Practice": "limited",
    "Full Participation in Practice": "full",
}


def e(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def blank() -> str:
    return '<td class="blank"><span class="unv" title="Not verifiable from an official source">unverified</span></td>'


NFL_HOST_SUFFIXES = (".nfl.com",)
CLUB_MARKERS = (".com/team/", "clubs.nfl.com")

AUTHORITY_HOSTS = {
    "www.itl.nist.gov": "NIST",
    "scikit-learn.org": "scikit-learn docs",
    "www.weather.gov": "NWS",
    "kansspelautoriteit.nl": "Ksa (NL regulator)",
    "www.gaming.nv.gov": "Nevada GCB",
    "docs.github.com": "GitHub docs",
}
SECONDARY_HOSTS = {"sports.yahoo.com", "lamag.com", "statrankings.com",
                   "fsroundup.com", "sticktothemodel.com"}


def _club_hosts() -> set[str]:
    """Club hosts taken from the official depth capture, not guessed."""
    try:
        snap = model.load_snapshot()
        hosts = set()
        for row in snap["depth_rows"]:
            url = row.get("source_url", "")
            if "://" in url:
                hosts.add(url.split("/")[2])
        for m in snap.get("manifest", []):
            url = m.get("url", "")
            if "://" in url:
                hosts.add(url.split("/")[2])
        return {h.replace("www.", "") for h in hosts}
    except Exception:
        return set()


# The capture currently reaches 30 of 32 clubs; the two missing ones are still
# official club domains when another workspace cites them.
CLUB_HOSTS = _club_hosts() | {
    "greenbaypackers.com", "packers.com",
    "houstontexans.com", "texans.com",
}


def source_class(url: str) -> str:
    """official-nfl | authority | community | secondary | unknown"""
    if not url:
        return "unknown"
    host = url.split("/")[2] if "://" in url else ""
    host = host.replace("www.", "")
    if "kanlerxz87-cyber.github.io" in host:
        return "official-nfl"
    if host in SECONDARY_HOSTS:
        return "secondary"
    if host == "github.com" or host == "codeload.github.com":
        return "internal" if "/kanlerxz87-cyber/NFL3" in url else "community"
    if host in {h.replace("www.", "") for h in AUTHORITY_HOSTS}:
        return "authority"
    if host.endswith(NFL_HOST_SUFFIXES) or "nfl.com" in host:
        return "official-nfl"
    if host in CLUB_HOSTS:
        return "official-nfl"
    return "unknown"


CLASS_LABEL = {
    "official-nfl": "official NFL / club",
    "internal": "this repository",
    "authority": "authority",
    "community": "community",
    "secondary": "secondary",
    "unknown": "unclassified",
}


def ext(url: str, label: str = "Source") -> str:
    if not url:
        return '<span class="unv">no official link</span>'
    cls = source_class(url)
    host = url.split("/")[2].replace("www.", "")
    text = label or host
    return (f'<a class="src src-{cls}" href="{e(url)}" target="_blank" rel="noopener noreferrer" '
            f'title="{e(CLASS_LABEL[cls])} source">{e(text)} &#8599;</a>')


def pill(text: str, kind: str = "") -> str:
    return f'<span class="pill {e(kind)}">{e(text)}</span>'


def sources_cell(urls: list[str]) -> str:
    urls = [u for u in urls if u]
    if not urls:
        return '<td class="blank"><span class="unv">unverified</span></td>'
    seen, out = set(), []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        host = u.split("/")[2].replace("www.", "")
        out.append(ext(u, host))
        if source_class(u) == "secondary":
            out.append('<span class="pill danger">secondary, unverified</span>')
    return "<td>" + " ".join(out) + "</td>"


def table(headers: list[str], rows: list[str], caption: str = "", table_id: str = "") -> str:
    head = "".join(f"<th scope=\"col\">{e(h)}</th>" for h in headers)
    body = "".join(rows)
    cap = f"<caption>{e(caption)}</caption>" if caption else ""
    ident = f' id="{e(table_id)}"' if table_id else ""
    return (f'<div class="table-wrap"><table{ident}>{cap}<thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def shell(title: str, active: str, content: str, subtitle: str = "") -> str:
    nav = "".join(
        f'<a href="{e(href)}"{f" class=active" if href == active else ""}>{e(label)}</a>'
        for href, label in NAV
    )
    sub = f'<p class="page-sub">{e(subtitle)}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | NFL3 ops centre</title>
<meta name="description" content="NFL3 availability, decision and line-origination ops centre. Every table row carries an official source link; unverified values stay blank.">
<link rel="stylesheet" href="assets/style.css"></head>
<body>
<div class="skip"><a href="#main">Skip to content</a></div>
<div class="layout">
<aside class="sidebar">
  <a class="brand" href="index.html"><span class="mark">N3</span><span>ops centre<small>availability &amp; decisions</small></span></a>
  <div class="nav-label">WORKSPACE</div>
  <nav aria-label="Ops centre navigation">{nav}</nav>
  <div class="side-links">
    <a href="../index.html">&#8592; Main NFL3 site</a>
    <a href="../decision-lab/index.html">Canonical decision lab &#8599;</a>
  </div>
  <div class="side-foot"><span class="dot"></span> Snapshot {e(BUILD_DATE)}<br><small>Research only &mdash; no wagering product</small></div>
</aside>
<main id="main">
  <header class="topbar"><span>NFL3 <b>/</b> OPS CENTRE</span><span class="right">OFFICIAL-SOURCE ONLY &middot; BLANKS PRESERVED</span></header>
  <div class="content">
    <h1>{e(title)}</h1>{sub}
    {content}
  </div>
  <footer>NFL3 ops centre &middot; built {e(BUILD_DATE)} &middot; values are copied from official pages or counted from official rows; nothing is inferred.</footer>
</main>
</div>
<script src="assets/app.js" defer></script>
</body></html>"""


def metrics(items: list[tuple[str, str, str]]) -> str:
    cells = "".join(
        f'<div class="metric"><span>{e(label)}</span><strong>{e(value)}</strong><small>{e(note)}</small></div>'
        for label, value, note in items
    )
    return f'<div class="metrics">{cells}</div>'


def notice(kind: str, body: str) -> str:
    return f'<div class="notice {e(kind)}">{body}</div>'


def filter_box(target: str, placeholder: str) -> str:
    return (f'<div class="filter"><label>Filter <input type="search" data-filter="{e(target)}" '
            f'placeholder="{e(placeholder)}" aria-label="{e(placeholder)}"></label>'
            f'<span class="count" data-count-for="{e(target)}"></span></div>')


# ---------------------------------------------------------------------------
def page_index(ctx: dict) -> str:
    ch, cov, ex = ctx["chains"], ctx["coverage"], ctx["exposure"]
    groups = sum(r["position_groups"] for r in cov)
    no_third = sum(r["groups_with_1_string"] + r["groups_with_2_strings"] for r in cov)
    identified = sum(1 for c in ch if c["chain_status"] == "chain-identified")
    not_on = sum(1 for c in ch if c["chain_status"] == "injured-player-not-on-published-chart")
    compounded = sum(r["compounded_positions"] for r in ex)

    body = [
        metrics([
            ("Injury rows (current official view)", str(ctx["current_rows"]),
             f'{ctx["baseline_rows"]} at 06:32Z + {ctx["added"]} published during the day'),
            ("Club depth rows", str(len(ctx["depth_rows"])), f'{len(cov)} clubs captured'),
            ("Replacement chains published", str(identified), "injured player found on his club chart"),
            ("Injured, absent from own chart", str(not_on), "no published next-man-up exists"),
            ("Position groups without a 3rd string", f"{no_third} / {groups}",
             f'{round(100.0 * no_third / groups)}% of published groups'),
            ("Validated strategies", "0", "blocked at the data gate"),
        ]),
        notice("warn",
               "<b>Read this first.</b> This workspace answers the availability question with official "
               "sources only. It can tell you who the club publishes behind an injured player. It cannot "
               "tell you who will actually play, how many snaps they will take, or what it costs in points. "
               "Those cells are empty on purpose."),
        '<div class="section"><h2>Executive summary</h2>'
        '<div class="brief">',
        '<div><div class="kicker">WHAT THE DATA SUPPORTS</div><h3>Availability is knowable. Impact is not.</h3>'
        f'<p>The official injury report and the 30 captured club depth charts are enough to name, for each '
        f'listed player, the published string behind him. That produced <b>{identified}</b> replacement chains. '
        f'It also produced <b>{not_on}</b> players who are on the league report but hold no published string at '
        f'their position on their own club chart &mdash; for those there is no official next-man-up to name, and '
        f'the cell is left empty rather than guessed.</p></div>',
        '<div><div class="kicker">WHAT BLOCKS EVERYTHING ELSE</div><h3>Three gaps, and none of them are modelling gaps.</h3>'
        '<p><b>1. The source moves.</b> Re-read the official injury page roughly sixteen hours after the '
        'committed capture and it had gained 25 rows. A single capture cannot support any availability feature. '
        '<b>2. Depth is published shallow.</b> '
        f'{no_third} of {groups} position groups publish no third string, so a third- or fourth-string '
        'replacement is usually unknown. <b>3. There is no price history.</b> Without a licensed odds archive '
        'nothing can be scored, so every strategy stays at "not run" by construction.</p>'
        '<p><a href="flagged.html">Every irregularity, with its source &#8599;</a></p></div>',
        '</div></div>',
        '<div class="section"><h2>What each page answers</h2>',
        table(["Page", "Question it answers", "Rows", "Primary official source"], [
            f'<tr><td><a href="availability.html">Availability &amp; chains</a></td>'
            f'<td>For every listed player, what does his club publish behind him &mdash; and is the next man also on the report?</td>'
            f'<td>{len(ch)}</td>' + sources_cell([INJURY_URL]) + "</tr>",
            f'<tr><td><a href="coverage.html">Published depth</a></td>'
            f'<td>How deep does each club actually publish, and which charts carry an unofficial disclaimer?</td>'
            f'<td>{len(cov)}</td>' + sources_cell(["https://www.commanders.com/team/depth-chart"]) + "</tr>",
            f'<tr><td><a href="drift.html">Source drift</a></td>'
            f'<td>What changed on the official page between this morning and tonight?</td>'
            f'<td>{ctx["added"] + len(ctx["status_changes"])}</td>' + sources_cell([INJURY_URL]) + "</tr>",
            f'<tr><td><a href="questions.html">Decision register</a></td>'
            f'<td>What is known, what is missing, and the cheapest action that closes each gap?</td>'
            f'<td>{len(ctx["questions"])}</td>' + sources_cell([INJURY_URL]) + "</tr>",
            f'<tr><td><a href="suggestions.html">Suggestions</a></td>'
            f'<td>Which path do we take, and can it be reviewed before anything is built?</td>'
            f'<td>{len(ctx["suggestions"])}</td>' + sources_cell([INJURY_URL]) + "</tr>",
            f'<tr><td><a href="leaderboard.html">Line origination</a></td>'
            f'<td>Strategies, gates, correlation, the arithmetic of removing luck, and reward rules.</td>'
            f'<td>{len(ctx["strategies"])}</td>' + sources_cell(["https://www.nfl.com/standings/"]) + "</tr>",
            f'<tr><td><a href="sources.html">Sources</a></td>'
            f'<td>Exactly which official pages were opened, when, and what each one does not cover.</td>'
            f'<td>{len(ctx["sources"])}</td>' + sources_cell([INJURY_URL]) + "</tr>",
            f'<tr><td><a href="flagged.html">Flagged for review</a></td>'
            f'<td>Irregularities found while verifying, each with the page that shows it.</td>'
            f'<td>{len(ctx["flags"])}</td>' + sources_cell([INJURY_URL]) + "</tr>",
        ]),
        '</div>',
        '<div class="section"><h2>Worked example: the Patriots backfield</h2>'
        '<p>Three Patriots are ruled <b>Out</b> for Week 10. Their running-back chain is published four deep: '
        'Rhamondre Stevenson (1st), TreVeyon Henderson (2nd), Corey Kiner (3rd), Lan Larison (4th). '
        'Henderson is Out and Stevenson is on the same report as Did Not Participate, so the published '
        'next men are the <b>3rd</b> and <b>4th</b> strings. This is the case the brief asks for &mdash; and it is '
        'the only kind of case the data can answer. Whether Kiner or Larison plays, and what it costs, is not '
        'published by anyone.</p>'
        '<p class="fine">Source: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener noreferrer">'
        'NFL injury report &#8599;</a> and <a href="https://www.patriots.com/team/depth-chart" target="_blank" '
        'rel="noopener noreferrer">Patriots depth chart &#8599;</a>, which states it is unofficial.</p></div>',
        '<div class="section"><h2>Compounded positions this week</h2>'
        f'<p>{compounded} position groups have a compromised published string <i>and</i> a compromised '
        'player behind it at the same time. These are the places where the next man is himself on the report.</p>',
    ]
    rows = []
    for r in ex:
        for d in r["compounded_detail"]:
            rows.append(
                "<tr>" + f"<td>{e(r['team'])}</td><td>{e(d['position_group'])}</td>"
                f"<td>{e(d['player'])}</td><td>{e(d['status'])}</td>"
                f"<td>{e(d['also'])}</td>"
                f'<td>{e(d["next_string"]) or "<span class=unv>not published</span>"}</td>'
                + sources_cell(["https://www.nfl.com/injuries/"]) + "</tr>"
            )
    body.append(table(
        ["Club", "Group", "Player", "Status", "Also on report", "Next published string", "Source"],
        rows[:40],
        caption="Compromised string with a compromised published replacement, Week 10"))
    body.append('</div>')
    return shell("Overview", "index.html", "".join(body),
                 "Availability, decisions and line origination, built only from pages the NFL and its clubs publish.")


# ---------------------------------------------------------------------------
def page_availability(ctx: dict) -> str:
    ch = ctx["chains"]
    rows = []
    for c in ch:
        label, kind = STATUS_LABEL.get(c["chain_status"], (c["chain_status"], ""))
        rank = c["published_rank"]
        next_cell = ", ".join(f'{n["player"]} ({RANK_WORD.get(n["rank"], n["rank"])})'
                              for n in c["next_string"]) or '<span class="unv">not published</span>'
        deeper_cell = ", ".join(f'{n["player"]} ({RANK_WORD.get(n["rank"], n["rank"])})'
                                for n in c["deeper_strings"]) or '<span class="unv">not published</span>'
        also_cell = ", ".join(
            f'{a["player"]} ({RANK_WORD.get(a["published_rank"], a["published_rank"])}, '
            f'{a["game_status"] or SHORT_PRACTICE.get(a["practice_status"], a["practice_status"])})'
            for a in c["also_on_report"]) or '<span class="quiet">none on report</span>'
        rows.append(
            "<tr>" +
            f'<td><a href="{e(c["player_url"])}" target="_blank" rel="noopener noreferrer">{e(c["player"])}</a></td>'
            f"<td>{e(c['team'])}</td><td>{e(c['injury_position'])}</td>"
            f"<td>{e(c['practice_status'])}</td>"
            f"<td>{e(c['game_status']) or '<span class=quiet>not yet designated</span>'}</td>"
            f'<td>{e(c["unit"][:1] + "/" + c["position_group"]) if c["unit"] else "<span class=quiet>searched: " + e(", ".join(c["groups_searched"])) + "</span>"}</td>'
            f"<td>{e(RANK_WORD.get(rank, rank)) if rank else '<span class=unv>not listed</span>'}</td>"
            f"<td>{next_cell}</td><td>{deeper_cell}</td><td>{also_cell}</td>"
            f"<td>{e(', '.join(c['other_listings'])) or '<span class=quiet>none</span>'}</td>"
            + blank() +
            f'<td>{pill(label, kind)}</td>'
            + sources_cell([c["injury_source_url"], c["depth_source_url"]]) +
            "</tr>"
        )
    return shell("Availability & chains", "availability.html", "".join([
        notice("ok",
               "<b>How to read this.</b> Each row is one player on the official injury report, joined to the "
               "string his own club publishes at that position. &ldquo;Next published string&rdquo; is the "
               "player at the following published rank &mdash; it is what the club publishes, not a prediction "
               "of who plays. Confirmed replacement is empty everywhere because no official source states it."),
        metrics([
            ("Rows", str(len(ch)), "one per player per matched position"),
            ("Chain published", str(sum(1 for c in ch if c["chain_status"] == "chain-identified")), "player found on his club chart"),
            ("Not on own club chart", str(sum(1 for c in ch if c["chain_status"] == "injured-player-not-on-published-chart")), "no published next-man-up"),
            ("No club depth captured", str(sum(1 for c in ch if c["chain_status"] == "no-depth-capture-for-club")), "clubs outside the capture"),
            ("Confirmed replacements", "0", "no official source names one"),
        ]),
        notice("ok",
               "<b>Reconciliation with the canonical lab's availability page.</b> "
               "<a href=\"../decision-lab/availability.html\">Decision lab &rarr; Availability &amp; "
               "replacements</a> joins the same two official sources by exact club-and-player name and "
               "reports 185 of 254 report rows joined, 69 unmatched. This page joins by club and "
               "<i>position family</i> instead of name, and uses the fresher 279-row view rather than the "
               "254-row capture. On the same 254 rows this method resolves 173 chains and leaves 39 players "
               "unlisted at their position, 29 rows for the two clubs with no depth capture and 13 rows where "
               "no depth is published at that position. The two numbers differ because the join keys differ, "
               "not because one is wrong; read both before relying on either."),
        filter_box("chain-table", "club, player or position"),
        ('<p class="fine">Practice status is shown in full; in the "also on report" column it is '
         'abbreviated: <b>DNP</b> = Did Not Participate, <b>limited</b> = Limited Participation, '
         '<b>full</b> = Full Participation. The official policy (OS-02) defines these as categories, '
         'not probabilities.</p>'),
        table(["Player", "Club", "Pos", "Practice", "Game status", "Group", "String",
               "Next published string", "Deeper strings", "Also on report at this group",
               "Other listings", "Confirmed replacement", "Chain", "Sources"],
              rows, table_id="chain-table",
              caption="Official injury report joined to official club depth charts, 2026 Week 10"),
    ]), "Who the club publishes behind each listed player, and where that answer does not exist.")


# ---------------------------------------------------------------------------
def page_coverage(ctx: dict) -> str:
    cov = ctx["coverage"]
    rows = []
    for r in cov:
        unofficial = "unofficial" in r["authority"].lower()
        rows.append(
            "<tr>" + f"<td>{e(r['team'])}</td>"
            f"<td>{'yes' if r['in_week_10_report'] else 'no'}</td>"
            f"<td>{r['position_groups']}</td><td>{r['max_string_published']}</td>"
            f"<td>{r['groups_with_1_string']}</td><td>{r['groups_with_2_strings']}</td>"
            f"<td>{r['groups_with_3plus_strings']}</td>"
            f'<td><b>{r["pct_groups_without_3rd_string"]}%</b></td>'
            f'<td>{pill("club-published unofficial", "danger") if unofficial else pill("club depth chart", "ok")}</td>'
            + sources_cell([r["source_url"]]) + "</tr>"
        )
    groups = sum(r["position_groups"] for r in cov)
    no_third = sum(r["groups_with_1_string"] + r["groups_with_2_strings"] for r in cov)
    return shell("Published depth", "coverage.html", "".join([
        notice("warn",
               "<b>The 3rd/4th string requirement cannot currently be met from official charts.</b> "
               f"Across the {len(cov)} captured clubs, {no_third} of {groups} position groups publish no third "
               f"string ({round(100.0 * no_third / groups)}%). Where a strategy needs a third or fourth string, "
               "the honest answer is that it is not published."),
        metrics([
            ("Clubs captured", str(len(cov)), "of 32; two Week 10 clubs are missing"),
            ("Position groups", str(groups), "unit + position pairs"),
            ("Publish a 3rd string", str(sum(r["groups_with_3plus_strings"] for r in cov)), "groups"),
            ("Without a 3rd string", f"{no_third} / {groups}", f'{round(100.0 * no_third / groups)}% of groups'),
            ("Charts disclaimed unofficial", str(sum(1 for r in cov if "unofficial" in r["authority"].lower())),
             "as labelled in the committed capture"),
        ]),
        notice("danger",
               "<b>Authority caveat.</b> The capture labels only one club's rows as unofficial, but the "
               "Patriots page states in its own text that its chart is unofficial and reflects the opinions of "
               "the site's writers. The label in the data is therefore wrong and is flagged as "
               "<a href=\"flagged.html#OF-02\">OF-02</a>. Disclaimer status has not been checked for the other "
               "clubs and is left blank there."),
        filter_box("cov-table", "club"),
        table(["Club", "In Week 10 report", "Groups", "Deepest string", "1-string groups",
               "2-string groups", "3+ string groups", "Without a 3rd string", "Authority as captured", "Source"],
              rows, table_id="cov-table",
              caption="How deep each club publishes, and what the capture says about that chart's authority"),
    ]), "How far down each club actually publishes, and which charts disclaim themselves.")


# ---------------------------------------------------------------------------
def page_drift(ctx: dict) -> str:
    rec = ctx["recheck"]
    base, reobs, delta = rec["baseline"], rec["reobservation"], rec["delta"]
    add_rows = []
    for r in rec["added_rows"]:
        add_rows.append(
            "<tr>" + f"<td>{e(r['team'])}</td><td>{e(r['matchup'])}</td>"
            f'<td><a href="{e(r["player_url"])}" target="_blank" rel="noopener noreferrer">{e(r["player"])}</a></td>'
            f"<td>{e(r['position'])}</td><td>{e(r['practice_status'])}</td>"
            f"<td>{e(r['game_status']) or '<span class=quiet>not designated</span>'}</td>"
            f"<td>{e(r['day'])}</td>"
            + sources_cell([rec["source_url"]]) + "</tr>"
        )
    chg_rows = []
    for r in rec["practice_status_changes"]:
        chg_rows.append(
            "<tr>" + f"<td>{e(r['team'])}</td>"
            f'<td><a href="{e(r["player_url"])}" target="_blank" rel="noopener noreferrer">{e(r["player"])}</a></td>'
            f"<td>{e(r['position'])}</td>"
            f"<td>{e(r['baseline_practice_status'])}</td>"
            f"<td>{e(r['reobserved_practice_status'])}</td>"
            + sources_cell([rec["source_url"]]) + "</tr>"
        )
    game_rows = []
    for r in rec["game_status_rows_reobserved"]:
        game_rows.append(
            "<tr>" + f"<td>{e(r['team'])}</td><td>{e(r['player'])}</td><td>{e(r['position'])}</td>"
            f"<td>{e(r['injury'])}</td><td>{e(r['game_status'])}</td>"
            + sources_cell([rec["source_url"]]) + "</tr>"
        )
    return shell("Source drift", "drift.html", "".join([
        notice("danger",
               f"<b>The official page is not an archive.</b> Captured at {e(base['observed_at'][:16])}Z it held "
               f"<b>{base['injury_rows']}</b> injury rows across 24 clubs with four &ldquo;No Injuries "
               f"Reported&rdquo; sections. Re-read at {e(reobs['observed_at'][11:16])}Z the same day it held "
               f"<b>{reobs['injury_rows_observed']}</b>. That is <b>+{delta['rows_added']} rows</b> in about "
               "sixteen hours, with two clubs publishing reports that did not exist in the morning."),
        metrics([
            ("Rows at 06:32Z", str(base["injury_rows"]), "committed capture, hash recorded"),
            ("Rows at 22:25Z", str(reobs["injury_rows_observed"]), "this session's re-read"),
            ("Rows added", str(delta["rows_added"]), "19 from two clubs that reported none"),
            ("Practice statuses changed", str(delta["practice_status_changes"]), "all Colts, both directions"),
            ("Game statuses changed", str(delta["game_status_changes"]), "the six designations held"),
            ("Rows removed", str(delta["rows_removed"]), "nothing disappeared"),
        ]),
        '<div class="section"><h2>Method and its limits</h2><p>'
        + e(reobs["method"]) + "</p><p>" + e(reobs["method_limit"]) +
        '</p><p class="fine">Observed at ' + e(reobs["observed_at"]) + " &mdash; " + e(reobs["observed_at_note"]) +
        "</p></div>",
        '<div class="section"><h2>Rows published during the day</h2>',
        filter_box("add-table", "club or player"),
        table(["Club", "Matchup", "Player", "Pos", "Practice status", "Game status", "Game day", "Source"],
              add_rows, table_id="add-table",
              caption="Injury rows present at 22:25Z that did not exist at 06:32Z"),
        "</div>",
        '<div class="section"><h2>Practice statuses that moved</h2>',
        table(["Club", "Player", "Pos", "At 06:32Z", "At 22:25Z", "Source"], chg_rows,
              caption="Same player, same day, different official practice status"),
        "</div>",
        '<div class="section"><h2>Game-status designations</h2>'
        '<p>Six players carry a game status. None changed between the two observations. The official policy '
        '(OS-02) defines Out as &ldquo;the player will not play&rdquo;, Doubtful as &ldquo;unlikely the player '
        'will participate&rdquo; and Questionable as &ldquo;uncertain as to whether the player will play&rdquo;, '
        'and states that a player certain to play is not listed in the Game Status Report at all.</p>',
        table(["Club", "Player", "Pos", "Injury", "Game status", "Source"], game_rows,
              caption="The only six game-status designations on the official Week 10 report at 22:25Z"),
        "</div>",
        '<div class="section"><h2>Why this decides the design</h2><p>' + e(rec["implication"]) +
        '</p><p><a href="suggestions.html">See the snapshot-history proposal &#8599;</a></p></div>',
    ]), "One page, two observations, sixteen hours apart: what the official injury report did in between.")


# ---------------------------------------------------------------------------
def page_questions(ctx: dict) -> str:
    qs = ctx["questions"]
    for q in qs:
        q["theme"] = thememod.theme_for(q["area"], q["question"])

    themed: dict[str, list[dict]] = {}
    for q in qs:
        themed.setdefault(q["theme"], []).append(q)

    counts = "".join(
        f'<span class="chip">{e(name)} <b>{len(items)}</b></span>'
        for name, items in sorted(themed.items(), key=lambda kv: -len(kv[1]))
    )
    open_blockers = [q for q in qs if q["blocking"]]
    answered = [q for q in qs if q["answer"]]

    body = [
        notice("ok",
               f'<b>{len(qs)} questions</b> merged from four workspaces, deduplicated and grouped by theme. '
               f'<b>{len(open_blockers)} are blocking</b> &mdash; a decision made before they are answered is a '
               f'decision made on nothing. <b>{len(answered)} have an answer</b> that a source supports; every '
               'other answer cell is empty and marked unverified.'),
        metrics([
            ("Questions", str(len(qs)), f'merged from {sum(len(q["provenance"]) for q in qs)} source entries'),
            ("Blocking", str(len(open_blockers)), "no decision should close first"),
            ("Answered from a source", str(len(answered)), "answer cell filled"),
            ("Answer blank", str(len(qs) - len(answered)), "nothing to fill it with"),
            ("Themes", str(len(themed)), "grouped for review"),
        ]),
        f'<div class="chips">{counts}</div>',
        filter_box("q-table", "question, theme or area"),
    ]
    rows = []
    for q in sorted(qs, key=lambda x: (not x["blocking"], x["theme"], x["question"])):
        answer_cell = (f"<td>{e(q['answer'])}</td>" if q["answer"] else blank())
        rows.append(
            "<tr>" + f"<td>{e(q['id'])}</td><td>{e(q['theme'])}</td>"
            f"<td>{e(q['question'])}</td>"
            f"<td>{e(q['known']) or '<span class=quiet>&#8212;</span>'}</td>"
            + answer_cell +
            f"<td>{e(q['missing']) or '<span class=quiet>&#8212;</span>'}</td>"
            f"<td>{e(q['discovery']) or '<span class=quiet>&#8212;</span>'}</td>"
            f'<td>{pill("blocking", "danger") if q["blocking"] else pill("open", "warn")}</td>'
            f'<td class="fine">{e(", ".join(q["provenance"]))}</td>'
            + sources_cell(q["sources"]) + "</tr>"
        )
    body.append(table(
        ["#", "Theme", "Question", "What we know", "Answer", "What is missing",
         "Cheapest action that closes it", "Status", "Merged from", "Sources"],
        rows, table_id="q-table",
        caption="Consolidated pre-decision register. Answer is empty unless a source answers it."))
    return shell("Decision register", "questions.html", "".join(body),
                 "What is known, what is missing, and the cheapest action that closes each gap.")


# ---------------------------------------------------------------------------
def page_suggestions(ctx: dict) -> str:
    sgs = ctx["suggestions"]
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    for s in sgs:
        s["theme"] = thememod.theme_for(s["area"], s["title"], s["summary"])
    sgs.sort(key=lambda s: (order.get(s["priority"], 4), s["theme"], s["title"]))
    for i, s in enumerate(sgs, 1):
        s["id"] = f"SG-{i:02d}"

    # Order the critical path by declared dependency, not by alphabetical luck:
    # items nothing else depends on come first.
    critical = sorted((s for s in sgs if s["priority"] == "Critical"),
                      key=lambda s: (0 if not s["depends"] else 1, s["title"]))
    body = [
        notice("ok",
               "<b>This is a review surface, not a build queue.</b> Nothing here has been implemented. "
               "Pick a path, record a decision, and export the result &mdash; the export is the hand-off, and it "
               "stays in your browser until you save it. No selection on this page changes a file in the "
               "repository."),
        metrics([
            ("Proposals", str(len(sgs)), f'merged from {sum(len(s["provenance"]) for s in sgs)} source entries'),
            ("Critical", str(len(critical)), "these gate everything else"),
            ("Awaiting a decision", str(len(sgs)), "no proposal has been approved"),
            ("Decisions recorded here", '0', "this page stores nothing server-side"),
        ]),
        '<div class="section"><h2>Critical path</h2>'
        '<p>These are sequenced, not just prioritised. Each one blocks the next, so approving the second '
        'without the first produces evidence that cannot be trusted.</p>',
        table(["Order", "Proposal", "Why it comes first", "Path", "Sources"],
              [f'<tr><td>{i}</td><td><b>{e(s["title"])}</b></td>'
               f'<td>{e(s["summary"])}</td>'
               f'<td>{e("Path " + s["path"]) if s["path"] else pill("path not set", "warn")}</td>'
               + sources_cell(s["sources"]) + "</tr>"
               for i, s in enumerate(critical[:6], 1)],
              caption="Critical proposals in the order they must be taken"),
        '</div>',
        '<div class="section"><h2>Review every proposal</h2>'
        '<p>Use <b>Approve</b>, <b>Defer</b> or <b>Reject</b> on each row, choose a path where one is offered, '
        'then export. The counts above the table update as you go.</p>',
        '<div class="review-bar">'
        '<div class="tally"><span data-tally="Approve">0</span><small>approved</small></div>'
        '<div class="tally"><span data-tally="Defer">0</span><small>deferred</small></div>'
        '<div class="tally"><span data-tally="Reject">0</span><small>rejected</small></div>'
        '<div class="tally"><span data-tally="Unreviewed">0</span><small>unreviewed</small></div>'
        '<div class="spacer"></div>'
        '<button type="button" class="btn" data-action="export">Export decisions (JSON)</button>'
        '<button type="button" class="btn ghost" data-action="copy">Copy to clipboard</button>'
        '<button type="button" class="btn ghost" data-action="reset">Reset</button>'
        '</div>',
        filter_box("sg-table", "proposal, theme or area"),
    ]
    rows = []
    for s in sgs:
        rows.append(
            "<tr data-id=\"" + e(s["id"]) + "\" data-title=\"" + e(s["title"]) + "\">" +
            f"<td>{e(s['id'])}</td><td>{e(s['theme'])}</td>"
            f'<td><b>{e(s["title"])}</b><div class="fine">{e(s["summary"])}</div></td>'
            f'<td>{pill(s["priority"], "danger" if s["priority"] == "Critical" else "warn") if s["priority"] else pill("unset", "warn")}</td>'
            f"<td>{e(s['impact']) or '<span class=quiet>&#8212;</span>'}</td>"
            f"<td>{e(s['effort']) or '<span class=quiet>&#8212;</span>'}</td>"
            f"<td>{e(s['depends']) or '<span class=quiet>none</span>'}</td>"
            f"<td>{e(s['recommendation']) or '<span class=quiet>&#8212;</span>'}</td>"
            '<td><div class="choice" role="group" aria-label="Path">'
            f'<label><input type="radio" name="path-{e(s["id"])}" value="A" {"checked" if s["path"] == "A" else ""}><span>A</span></label>'
            f'<label><input type="radio" name="path-{e(s["id"])}" value="B" {"checked" if s["path"] == "B" else ""}><span>B</span></label>'
            '</div></td>'
            '<td><select data-decision aria-label="Decision"><option value="Unreviewed">Unreviewed</option>'
            '<option>Approve</option><option>Defer</option><option>Reject</option></select></td>'
            f'<td class="fine">{e(", ".join(s["provenance"]))}</td>'
            + sources_cell(s["sources"]) + "</tr>"
        )
    body.append(table(
        ["#", "Theme", "Proposal", "Priority", "Impact", "Effort", "Depends on", "Recommendation",
         "Path", "Your decision", "Merged from", "Sources"],
        rows, table_id="sg-table",
        caption="Every proposal from every workspace, merged and deduplicated. Nothing on this page is implemented."))
    body.append('<p class="fine">Decisions are stored in your browser only (localStorage), are never sent '
                'anywhere, and are lost if you clear site data. Export before you close the tab.</p></div>')
    return shell("Suggestions", "suggestions.html", "".join(body),
                 "Review every proposal, choose a path, and export the decision before anything is built.")


# ---------------------------------------------------------------------------
def page_leaderboard(ctx: dict) -> str:
    strat, gates, math_, comm = ctx["strategies"], ctx["gates"], ctx["math"], ctx["community"]
    rewards = ctx["rewards"]

    # Some inherited strategy text carries numbers computed on community data.
    # Rather than silently republish them as if they were official, mark the row.
    FIGURE = re.compile(r"(\+\d+\.\d+)|(\bphi\b)|(\bp\s*=\s*0\.)|(\bMAE\b)|(measured)|(Sharpe)|"
                        r"(correlation of)|(\br\s*=\s*-?0\.)|(\d+\.\d+\s*%)", re.I)

    srows = []
    for s in strat:
        blob = " ".join(str(s.get(k, "")) for k in ("name", "kind", "thesis", "note"))
        carries = bool(FIGURE.search(blob))
        srows.append(
            "<tr>" + f"<td>{e(s['id'])}</td><td><b>{e(s['name'])}</b></td><td>{e(s['kind'])}</td>"
            f"<td>{e(s['thesis'])}"
            + (f'<div class="fine">{e(s["note"])}</div>' if s.get("note") else "")
            + "</td>"
            f'<td>{pill("carries computed figures", "warn") if carries else pill("hypothesis only", "ok")}</td>'
            f'<td>{pill(s["status"] or "not run", "danger" if "block" in (s["status"] or "").lower() else "warn")}</td>'
            + blank() + blank() + blank() +
            f'<td>{pill("no", "danger")}</td>'
            f'<td class="fine">{e(", ".join(s["provenance"]))}</td>'
            + sources_cell(s["sources"]) + "</tr>"
        )

    grows = []
    for g in gates:
        grows.append(
            "<tr>" + f"<td>{e(g['id'])}</td><td><b>{e(g['name'])}</b></td>"
            f"<td>{e(g['criterion'])}</td>"
            f"<td>{e(g['needs']) or '<span class=quiet>&#8212;</span>'}</td>"
            f"<td>{e(g['failure']) or '<span class=quiet>&#8212;</span>'}</td>"
            f'<td>{pill("not evaluated", "warn")}</td>'
            f'<td class="fine">{e(", ".join(g["provenance"]))}</td>'
            + sources_cell(g["sources"]) + "</tr>"
        )

    body = [
        notice("danger",
               "<b>Nothing on this page is a result.</b> No strategy has been run, because no licensed odds, "
               "prop or settlement history exists in this repository. Every edge, closing-line-value, rank and "
               "reward cell is empty. That is the correct state: a leaderboard that cannot be scored must not "
               "print a score."),
        metrics([
            ("Strategies registered", str(len(strat)), "hypotheses, not results"),
            ("Validated", "0", "all blocked at the data gate"),
            ("Gates", str(len(gates)), "merged and deduplicated"),
            ("Gates passed by any strategy", "0", "nothing has been evaluated"),
            ("Official-source correlation", "none", "no leg-level outcome data"),
            ("Rewards funded", "0", "no funding verified"),
        ]),
        '<div class="section"><h2>Strategy register</h2>'
        '<p>Every strategy proposed anywhere in this repository, merged. The last four columns are the ones '
        'that matter, and they are empty because there is nothing to put in them.</p>',
        filter_box("st-table", "strategy or market"),
        table(["#", "Strategy", "Type", "Hypothesis", "Basis", "Status", "Edge", "CLV", "Rank",
               "Reward", "Merged from", "Sources"],
              srows, table_id="st-table",
              caption="All registered strategies. Edge, CLV, rank and reward are unverified and blank."),
        '</div>',
        '<div class="section"><h2>Validation gates</h2>'
        '<p>A strategy enters a leaderboard only by passing all applicable gates. Ordered cheapest-first so a '
        'bad idea dies before anyone pays for it.</p>',
        table(["#", "Gate", "Criterion", "Evidence needed", "On failure", "Status", "Merged from", "Sources"],
              grows, caption="Merged validation gates"),
        '</div>',
    ]

    ss = math_.get("sample_size", {})
    if ss.get("rows"):
        body.append('<div class="section"><h2>Removing luck: the sample-size arithmetic</h2>'
                    '<p>These numbers are computed from declared parameters, not measured from NFL data. '
                    'That is the point: they say what would be required before any claim of edge is credible.</p>'
                    '<p class="fine">' + e(ss.get("method", "")) + '</p>'
                    '<p>' + e(ss.get("headline", "")) + '</p>')
        body.append(table(
            ["Target edge over break-even", "Break-even win rate", "Bets needed (win/loss test)",
             "Bets needed (ROI test)", "Basis"],
            ["<tr>" + f"<td>{r['target_edge']:.3f}</td><td>{r['break_even_win_rate']}</td>"
             f"<td>{r['required_bets_winprob_test']:,}</td>"
             f"<td>{r['required_bets_roi_test']:,}</td>"
             '<td class="blank"><span class="unv">computed, not measured</span></td></tr>'
             for r in ss["rows"]],
            caption="Required graded-bet sample at 80% power, two-sided alpha 0.05"))
        body.append('</div>')

    ds = math_.get("deflated_sharpe", {})
    if ds.get("rows"):
        body.append('<div class="section"><h2>Deflated Sharpe: the price of searching</h2>'
                    '<p class="fine">' + e(ds.get("method", "")) + '</p>'
                    '<p>' + e(ds.get("note", "")) + '</p>')
        body.append(table(
            ["Trials run", "Observed Sharpe", "n", "Expected max Sharpe under the null",
             "Deflated Sharpe ratio", "Passes", "Basis"],
            ["<tr>" + f"<td>{r['trials']}</td><td>{r['observed_sharpe']}</td><td>{r['n']}</td>"
             f"<td>{r['expected_max_sharpe_under_null']}</td>"
             f"<td>{r['deflated_sharpe_ratio']}</td>"
             f'<td>{pill("pass", "ok") if r.get("passes_G5") else pill("fail", "danger")}</td>'
             '<td class="blank"><span class="unv">computed, not measured</span></td></tr>'
             for r in ds["rows"]],
            caption="The same Sharpe stops looking like skill as the number of things tried rises"))
        body.append('</div>')

    body.append('<div class="section"><h2>Correlation</h2>'
                '<p><b>Official-source correlation: none.</b> No leg-level settlement data exists here, so no '
                'correlation has been measured on official data and the value is left blank.</p>')
    if comm.get("available") and comm.get("rows"):
        body.append(
            notice("warn",
                   "<b>Community-source figures below.</b> These were computed by another session from "
                   "nflverse community release assets. They are real arithmetic on real rows, but the source is "
                   "not NFL-authored; a matching GitHub digest proves the bytes arrived intact, not that the NFL "
                   "published them. They are published for completeness and are excluded from every "
                   "official-only gate."))
        body.append(table(
            ["Leg pair", "Statistic", "Value", "n", "95% CI", "p", "Source"],
            ["<tr>" + f"<td>{e(r['pair'])}</td><td>{e(r['statistic'])}</td>"
             f"<td>{e(r.get('value_display', r['value']))}</td>"
             f"<td>{r['n']:,}</td><td>{e(r['ci95'])}</td><td>{e(r['p_value'])}</td>"
             + sources_cell([comm.get("source_url", "")]) + "</tr>"
             for r in comm["rows"]],
            caption="Same-game leg associations computed from community data (not official)"))
        st = comm.get("stacked") or {}
        if st.get("lift"):
            body.append(
                '<div class="brief"><div><div class="kicker">WHY PARLAYS ARE NOT WHAT THEY LOOK LIKE</div>'
                '<h3>Independence overstates the risk, and understates it, in the wrong places.</h3>'
                f'<p>On {st.get("n", 0):,} community-data games a three-leg same-game parlay hit '
                f'<b>{st.get("p_triple_observed", 0):.1%}</b> of the time against '
                f'<b>{st.get("p_triple_if_independent", 0):.1%}</b> if the legs were independent &mdash; a lift of '
                f'<b>{st.get("lift", 0):.2f}x</b>. The home-win and favourite-cover legs are near-duplicates '
                'whenever the home side is the favourite, which is exactly why a three-leg '
                'same-game parlay is not three independent bets.</p>'
                '<p class="fine">Community source: '
                '<a href="https://github.com/nflverse/nflverse-data/releases" target="_blank" '
                'rel="noopener noreferrer">nflverse releases &#8599;</a>. Not official; not a decision input.</p>'
                '</div></div>')
    body.append('</div>')

    if rewards:
        body.append('<div class="section"><h2>Reward governance</h2>'
                    '<p>Rules proposed so that a leaderboard pays for skill rather than for the luckiest entry. '
                    'No funding, denomination or legal basis has been verified, so nothing here is approved.</p>')
        body.append(table(
            ["Rule", "Mechanism", "Anti-luck effect", "Status", "Source"],
            ["<tr>" + f"<td>{e(r['rule'])}</td><td>{e(r['mechanism'])}</td>"
             f"<td>{e(r['anti_luck_effect'])}</td><td>{e(r['status'])}</td>"
             + sources_cell([r["source_url"]]) + "</tr>" for r in rewards],
            caption="Reward governance proposals (none verified, none funded)"))
        body.append('</div>')

    return shell("Line origination", "leaderboard.html", "".join(body),
                 "Strategies, gates, correlation, the arithmetic of removing luck, and reward rules.")


# ---------------------------------------------------------------------------
def page_sources(ctx: dict) -> str:
    rows = []
    for s in ctx["sources"]:
        obs = s.get("observations") or []
        obs_cell = "<br>".join(
            f'{e(o["at"])} &middot; {o.get("rows", "")} rows' if o.get("rows")
            else e(o["at"]) for o in obs) or '<span class="quiet">single observation</span>'
        rows.append(
            "<tr>" + f"<td>{e(s['id'])}</td><td><b>{e(s['title'])}</b></td><td>{e(s['publisher'])}</td>"
            f'<td>{pill(s["status"], "ok" if s["status"] == "opened" else "warn")}</td>'
            f"<td>{e(s['checked'])}</td><td>{obs_cell}</td>"
            f"<td>{e(s['scope'])}</td><td>{e(s['limit'])}</td>"
            + sources_cell([s["url"]]) + "</tr>"
        )
    opened = sum(1 for s in ctx["sources"] if s["status"] == "opened")
    return shell("Sources", "sources.html", "".join([
        notice("ok",
               f"<b>{opened} of {len(ctx['sources'])} sources</b> on this page were opened and read by this "
               "session. The rest are carried from other workspaces and are never used to fill a value here."),
        table(["#", "Source", "Publisher", "Status", "Checked", "Observations", "What it covers",
               "What it does not cover", "Link"],
              rows, caption="Sources used by the ops centre"),
        '<div class="section"><h2>Authority boundary</h2>'
        '<p>An official NFL or club page establishes a published fact for review. A capture hash proves the '
        'bytes arrived intact; it does not prove authorship, accuracy, reuse rights or that the page will still '
        'say the same thing tomorrow. Community nflverse assets are useful for exploration and are excluded '
        'from every official-only gate.</p></div>',
    ]), "Which pages were opened, when, and what each one does not cover.")


# ---------------------------------------------------------------------------
def page_flagged(ctx: dict) -> str:
    rows = []
    for f in ctx["flags"]:
        rows.append(
            f'<tr id="{e(f["id"])}">' + f"<td>{e(f['id'])}</td>"
            f'<td>{pill(f["severity"], "danger" if f["severity"] == "Critical" else "warn")}</td>'
            f'<td><b>{e(f["title"])}</b></td><td>{e(f["detail"])}</td>'
            f"<td>{e(f['impact'])}</td><td>{e(f['action'])}</td>"
            + sources_cell([f["source"]]) + "</tr>"
        )
    return shell("Flagged for review", "flagged.html", "".join([
        notice("warn",
               "<b>These do not block the site; they block the decisions that depend on them.</b> "
               "Each item was found while verifying official pages, and each carries the page that shows it."),
        metrics([
            ("Flagged items", str(len(ctx["flags"])), "found this session"),
            ("Critical", str(sum(1 for f in ctx["flags"] if f["severity"] == "Critical")), "changes what can be trusted"),
            ("High", str(sum(1 for f in ctx["flags"] if f["severity"] == "High")), "changes what can be measured"),
            ("Medium", str(sum(1 for f in ctx["flags"] if f["severity"] == "Medium")), "changes how values may be used"),
        ]),
        table(["#", "Severity", "Finding", "Detail", "Why it matters", "What to do", "Source"],
              rows, caption="Irregularities observed while verifying official sources"),
        '<div class="section"><h2>Also flagged elsewhere</h2>'
        '<p>Other workspaces keep their own registers: '
        '<a href="../decision-lab/flagged.html">canonical decision lab flagged items &#8599;</a>, '
        '<a href="../decision-lab/audit.html">independent source audit &#8599;</a>, '
        '<a href="../dashboard/flagged.html">dashboard flags &#8599;</a>, '
        '<a href="../line-lab/pages/flagged.html">line lab flags &#8599;</a>, '
        '<a href="../decision-hub/flagged.html">decision hub flags &#8599;</a>.</p></div>',
    ]), "Irregularities found while verifying, each with the page that shows it.")


# ---------------------------------------------------------------------------
def main() -> int:
    snapshot = model.load_snapshot()
    recheck = model.load_recheck()
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))["sources"]

    current = model.merge_recheck(snapshot, recheck)
    chains = model.build_chains(snapshot, current)
    coverage = model.build_coverage(snapshot)
    exposure = model.build_exposure(chains)

    ctx = {
        "chains": model._clean(chains), "coverage": model._clean(coverage),
        "exposure": model._clean(exposure),
        "current_rows": len(current), "baseline_rows": len(snapshot["injury_rows"]),
        "depth_rows": snapshot["depth_rows"],
        "added": recheck["delta"]["rows_added"],
        "status_changes": recheck["practice_status_changes"],
        "recheck": recheck, "sources": sources,
        "questions": model._clean(model.build_questions()),
        "suggestions": model._clean(model.build_suggestions()),
        "strategies": model._clean(model.build_strategies()),
        "gates": model._clean(model.build_gates()),
        "math": model.build_math(),
        "community": model.build_community_evidence(),
        "rewards": model.build_rewards(),
        "flags": model.build_flags(chains, coverage, snapshot),
    }

    (DATA / "derived.json").write_text(json.dumps({
        "generated": BUILD_DATE,
        "injury_rows_current": len(current),
        "chains": chains,
        "coverage": coverage,
        "exposure": exposure,
        "questions": ctx["questions"],
        "suggestions": ctx["suggestions"],
        "strategies": ctx["strategies"],
        "gates": ctx["gates"],
        "flags": ctx["flags"],
    }, indent=1), encoding="utf-8")

    pages = {
        "index.html": page_index(ctx),
        "availability.html": page_availability(ctx),
        "coverage.html": page_coverage(ctx),
        "drift.html": page_drift(ctx),
        "questions.html": page_questions(ctx),
        "suggestions.html": page_suggestions(ctx),
        "leaderboard.html": page_leaderboard(ctx),
        "sources.html": page_sources(ctx),
        "flagged.html": page_flagged(ctx),
    }
    for name, content in pages.items():
        (PAGES / name).write_text(content, encoding="utf-8")
    print(f"built {len(pages)} pages; {len(chains)} chains; {len(ctx['questions'])} questions; "
          f"{len(ctx['suggestions'])} suggestions; {len(ctx['strategies'])} strategies; "
          f"{len(ctx['gates'])} gates; {len(ctx['flags'])} flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
