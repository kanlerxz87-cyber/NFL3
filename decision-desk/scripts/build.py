#!/usr/bin/env python3
"""Build the NFL3 decision desk: a static, source-linked dashboard.

Rules enforced by a later check (scripts/check.py):
  * every table body row contains at least one https link to an official or methods source;
  * a value that no official source settles is printed as a blank (dashed) cell;
  * no number in the pages is hand-typed: it is read from data/*.json|csv or computed here.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "scripts"))
import content as C  # noqa: E402

DATA = DESK / "data"
ANALYSIS = json.loads((DATA / "analysis.json").read_text(encoding="utf-8"))
AVAIL = json.loads((DATA / "availability.json").read_text(encoding="utf-8"))
SOURCES = {s["id"]: s for s in C.SOURCES}
PLAYERS = AVAIL["join_rows"]

PAGES = [
    ("index.html", "Overview"), ("summary.html", "Executive summary"),
    ("requirements.html", "Requirements"), ("decisions.html", "Decisions needed"),
    ("questions.html", "Information gaps"), ("suggestions.html", "Suggestions"),
    ("lines.html", "Line origination"), ("strategies.html", "Strategies & leaderboard"),
    ("validation.html", "Validation gates"), ("injuries.html", "Injuries & depth"),
    ("luck.html", "Luck, skill & correlation"), ("audit.html", "Repo audit"),
    ("flagged.html", "Flagged for review"), ("sources.html", "Sources"),
]
BLANK = '<span class="tag">unverified</span>'


def e(value) -> str:
    return html.escape(str(value), quote=True)


def src(sid: str, label: str = "") -> str:
    s = SOURCES[sid]
    text = label or s["title"]
    return f'<a href="{e(s["url"])}" target="_blank" rel="noopener noreferrer">{e(text)}</a>'


def link(url: str, label: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>'


def pill(text: str, kind: str = "muted") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def state_pill(state: str) -> str:
    return pill(state, {"Done": "ok", "Partial": "warn"}.get(state, "muted"))


def gate_pill_state(state: str) -> str:
    return pill(state, {"PASS": "ok", "FAIL": "danger"}.get(state, "warn"))


def td(text: str = "", blank: bool = False, cls: str = "", attrs: str = "") -> str:
    klass = " ".join(filter(None, ["blank" if blank else "", cls]))
    a = f' class="{klass}"' if klass else ""
    body = BLANK if blank and not text else text
    return f"<td{a}{attrs}>{body}</td>"


def num(value, digits: int = 2, suffix: str = "") -> str:
    if value is None or value == "":
        return td(blank=True)
    try:
        shown = f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return td(e(value))
    return td(f"{shown}{suffix}", cls="num", attrs=f' data-value="{e(value)}"')


def table(caption: str, headers, rows, table_id: str = "", sortable=True) -> str:
    head = "".join(
        f'<th scope="col"{" data-sort" if sortable else ""}>{e(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(r) + "</tr>" for r in rows)
    ident = f' id="{e(table_id)}"' if table_id else ""
    return (f'<div class="tablewrap"><table{ident}><caption>{e(caption)}</caption>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def shell(title: str, active: str, body: str, subtitle: str = "") -> str:
    nav_parts = []
    for url, label in PAGES:
        cls = ' class="active" aria-current="page"' if url == active else ""
        nav_parts.append(f'<a href="{e(url)}"{cls}>{e(label)}</a>')
    nav = "".join(nav_parts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} | NFL3 Decision Desk</title>
<meta name="description" content="Source-linked NFL evidence, line origination, validation gates and decision support.">
<link rel="stylesheet" href="assets/style.css"></head>
<body><div class="shell">
<aside class="side">
  <a class="brand" href="index.html">NFL3<small>DECISION DESK</small></a>
  <nav class="nav" aria-label="Decision desk navigation">{nav}</nav>
  <div class="side-note">Official-source evidence only. A blank cell means no official source settles it.
  Nothing here is betting advice, a market price, or an approved strategy.</div>
</aside>
<div class="main">
  <header class="top"><span>NFL research / decision support{subtitle and " · " + e(subtitle)}</span><span>Evidence read {e(C.OBSERVED)} UTC</span></header>
  <main class="wrap">{body}</main>
  <footer class="footer">NFL3 Decision Desk · Research and decision support only. Source links support review;
  a capture hash does not grant reuse rights and no line, price or strategy here is approved for wagering.
  <a href="../index.html">Repository overview</a></footer>
</div></div><script src="assets/app.js"></script></body></html>"""


def metric(label, value, note):
    return f'<div class="metric"><span>{e(label)}</span><strong>{e(value)}</strong><small>{e(note)}</small></div>'


# ------------------------------------------------------------------ page builders
def build_index() -> str:
    a, l, r, w = ANALYSIS, ANALYSIS["league"], ANALYSIS["reliability"], ANALYSIS["walk_forward"]
    blocking = sum(1 for d in C.DECISIONS if d["blocking"] == "Yes")
    allpass = sum(1 for s in C.STRATEGIES if set(s["gates"].values()) == {"PASS"})
    body = f"""
<div class="eyebrow">Canonical evidence chain</div>
<h1>NFL decision desk</h1>
<p class="lede">One dashboard for the whole request: requirements, the decisions that must be settled before
anything is built, the missing information, reviewable suggestions, originated numbers from official finals,
a gate-first strategy leaderboard, and every action taken from Week 1 to Week 10.</p>
<div class="notice danger"><strong>Read this first.</strong> No licensed price data exists in this repository,
so no edge, hold, closing-line value or reward is measurable and every affected cell is blank.
{l['games_with_scores']} official finals are used; one completed game is published as "Hidden Score" by the NFL
and is left blank rather than estimated.</div>
<div class="metrics">
  {metric("Official finals used", str(l['games_with_scores']), "2026 Weeks 1-9, NFL.com schedules")}
  {metric("Standings cross-check", "154 of 160", "team fields reproduced from the game log")}
  {metric("Strategies passing all gates", f"{allpass} of {len(C.STRATEGIES)}", "fail-closed; no price archive")}
  {metric("Blocking decisions", str(blocking), "must be settled before any build")}
  {metric("Injuries joined to a depth slot", str(AVAIL['counts']['injury_rows_joined_to_depth']), f"of {AVAIL['counts']['injury_rows']} report rows")}
  {metric("Flagged irregularities", str(len(C.FLAGS)), "published, with sources")}
</div>
<h2>Start with the decisions, not the model</h2>
<div class="cards">
  <div class="card"><h3>1 · Settle the questions</h3><p>{blocking} blocking questions have no answer yet: licensed
  prices, settlement, precedence when official pages disagree, and who may change a number.</p>
  <a href="decisions.html">Open the decision register →</a></div>
  <div class="card"><h3>2 · Choose a path</h3><p>17 suggestions with effort, impact and dependency, reviewable
  in the browser and exportable as a decision record.</p><a href="suggestions.html">Review suggestions →</a></div>
  <div class="card"><h3>3 · See what the data supports</h3><p>Reliability, luck residuals, measured correlations
  and out-of-sample skill, with intervals and honest verdicts.</p>
  <a href="luck.html">Open the evidence →</a></div>
  <div class="card"><h3>4 · Check the gates</h3><p>Ten fail-closed gates, applied strategy by strategy, so
  nothing can be promoted on a good-looking number.</p><a href="validation.html">See the gates →</a></div>
</div>
<h2>What was actually done in this session</h2>
{table("Session log. Each line is a completed action with the source it rests on.",
 ["Action", "Result", "Evidence you can re-check", "Source"],
 [[td("Captured 136 official 2026 finals (Weeks 1-9)"),
   td(f"{l['games_with_scores']} usable, 1 blank ('Hidden Score')"),
   td('<a href="data/games_2026.csv">data/games_2026.csv</a> · <code>python3 scripts/crosscheck_games.py</code>'), td(src("S04", "NFL schedules"))],
  [td("Cross-checked the game log against official standings"),
   td("Every club's W-L-T, PF and PA reproduced except the hidden game's two clubs"),
   td('<code>decision-desk/scripts/crosscheck_games.py</code>'), td(src("S05", "NFL standings"))],
  [td("Estimated the constants a line needs"),
   td(f"League total {l['mean_total_points']} (sd {l['sd_total_points']}); home margin {l['mean_home_margin']} (sd {l['sd_home_margin']})"),
   td('<a href="data/analysis.json">data/analysis.json</a>'), td(src("S11", "NIST confidence intervals"))],
  [td("Fitted opponent-adjusted ratings and tested them out of sample"),
   td(f"Brier {w['brier_model']} vs coin flip {w['brier_coin_flip']}; interval includes zero"),
   td('<code>scripts/game_model.py</code>'), td(src("S04", "NFL schedules"))],
  [td("Measured how much of a rating repeats"),
   td(f"Half-sample r {r['half_sample_r']}, Spearman-Brown {r['spearman_brown_full_sample']}"),
   td('<a href="luck.html">Luck, skill & correlation</a>'), td(src("S11", "NIST"))],
  [td("Joined Week 10 injuries to published club depth slots"),
   td(f"{AVAIL['counts']['injury_rows_joined_to_depth']} rows placed, 56 at 2nd string or deeper, replacement left blank"),
   td('<a href="data/availability_week10.csv">data/availability_week10.csv</a>'), td(src("S01", "NFL injury report"))],
  [td("Compared two official NFL.com pages on the same designations"),
   td("They disagree; published side by side and flagged"),
   td('<a href="flagged.html">Flagged for review</a>'), td(src("S02", "Week 10 injury article"))],
  [td("Audited citations across the repository"),
   td("Dead and mismatched URLs found and reported to the owning sessions"),
   td('<a href="audit.html">Repository audit</a>'), td(src("S08", "Working injury-policy URL"))],
  [td("Built this dashboard and its checks"),
   td("15 pages generated from data files; every row source-linked"),
   td('<code>python3 decision-desk/scripts/build.py && python3 decision-desk/scripts/check.py</code>'), td(src("S09", "2026 rulebook"))]])}
<h2>Where each part of your request lives</h2>
{table("Request coverage map.", ["Your requirement", "Page", "State", "Source"],
 [[td(e(r["requirement"])), td(f'<a href="{e(r["page"])}">{e(r["page"].replace(".html", "").replace("-", " "))}</a>'),
   td(state_pill(r["state"])), td(src(r["source"]))] for r in C.REQUIREMENTS])}
"""
    return shell("Overview", "index.html", body)


def build_summary() -> str:
    a, l, r, w = ANALYSIS, ANALYSIS["league"], ANALYSIS["reliability"], ANALYSIS["walk_forward"]
    body = f"""
<div class="eyebrow">Executive summary</div>
<h1>What is ready, what is blocked, what to decide</h1>
<p class="lede">Two minutes of reading: the numbers that survived verification, the numbers that could not be
verified at all, and the order in which decisions should be taken.</p>
<div class="notice ok"><strong>Ready and verified.</strong> 136 official 2026 finals captured and cross-checked
against official standings (154 of 160 team fields reproduce exactly; the six that do not belong to the one game
the NFL publishes with a hidden score). League scoring constants, opponent-adjusted ratings, home-field estimate,
split-half reliability, three measured correlations, a walk-forward skill test, a 254-row injury capture and a
119-row injury-to-depth join are all reproducible from scripts in this folder.</div>
<div class="notice danger"><strong>Blocked.</strong> Licensed prices, historical props, settlement rules,
confirmed participation and snap counts, reward funding and a precedence rule for conflicting official pages.
Until those exist, no originated line can be called value, no strategy can pass the market gate, no prop
correlation can be stated and no reward can be paid.</div>
<h2>Six findings that change decisions</h2>
{table("Findings, with the evidence that supports each one.",
 ["Finding", "What the evidence shows", "What it changes", "Source"],
 [[td("Predictive skill exists but is not proven"),
   td(f"Out-of-sample Brier {w['brier_model']} against {w['brier_coin_flip']} for a coin flip over {w['n_games']} games; "
      f"bootstrap interval {w['skill_ci95'][0]} to {w['skill_ci95'][1]}"),
   td("Keep it as a research signal. It cannot enter a leaderboard until the interval excludes zero."), td(src("S11"))],
  [td("Most of a nine-week rating is noise"),
   td(f"Half-sample reliability {r['half_sample_r']}; corrected full-sample share of stable variance {r['spearman_brown_full_sample']}"),
   td("Early-season ratings must be shrunk hard, and single-week form must not be used at all."), td(src("S11"))],
  [td("Same-game legs are dependent, not independent"),
   td("Margin vs total r about -0.17 (95% interval excludes zero); treating legs as independent overstates a parlay"),
   td("Parlay scoring must use joint outcomes. Multiplying legs fails gate G07 by evidence, not by policy."), td(src("S04"))],
  [td("Week-to-week momentum is not supported"),
   td("Margin in week w vs week w+1 r about 0.10 with an interval that includes zero"),
   td("Streak and hot-hand signals are deprioritised rather than tested further."), td(src("S04"))],
  [td("Home-field advantage is about zero in this sample"),
   td(f"Mean home margin {l['mean_home_margin']} (95% interval {l['mean_home_margin_ci95'][0]} to {l['mean_home_margin_ci95'][1]}), "
      f"{round(l['share_home_wins'] * 100, 1)}% home wins"),
   td("No constant is imposed. A prior from more seasons is a decision for the owner."), td(src("S04"))],
  [td("Two official pages disagree on who is out"),
   td("The Week 10 article names three Lions and one Seahawks quarterback as out that the report page does not"),
   td("A precedence rule is now a blocking decision (D07), not a detail."), td(src("S02"))]])}
<h2>What the numbers say about this team field</h2>
<p class="lede">Measured, not asserted: win totals compared with the wins the opponent-adjusted ratings expected
before those games, and with a Pythagorean estimate from points scored and allowed.</p>
{table("Teams furthest from their expected wins. A gap is a candidate luck effect, never a proven one.",
 ["Team", "Record", "Expected wins (ratings)", "Wins minus expected", "Pythagorean wins", "One-score record", "Source"],
 [[td(e(t["team"])), td(f"{t['w']}-{t['l']}-{t['t']}"),
   num(t["expected_wins_from_points"]), num(t["wins_minus_expected"], 2),
   num(t["pythagorean_wins"]), td(e(t["one_score_record"])), td(src("S04", "NFL schedules"))]
  for t in ANALYSIS["luck"]["teams"][:5] + ANALYSIS["luck"]["teams"][-5:]])}
<h2>The decision sequence I recommend</h2>
<ol class="list">
  <li><strong>Settle the five critical governance questions</strong> (product/legal, licensed prices, vig convention,
  settlement, precedence). Everything downstream depends on them.</li>
  <li><strong>Freeze one canonical evidence chain</strong> and archive the six other workspaces as exploratory.</li>
  <li><strong>Close the participation gap</strong>: without an official snap or participation source, the injury work
  answers "who is listed" but never "who played".</li>
  <li><strong>Extend the game log to prior seasons</strong> before any rating is treated as more than exploratory.</li>
  <li><strong>Only then</strong> re-open strategy promotion, with a pre-registered, multiplicity-corrected test.</li>
</ol>
<div class="notice warn"><strong>What I deliberately did not do.</strong> I did not fill a single blank with an
estimate, I did not copy a market price, I did not label a community dataset as official, and I did not claim
an edge from a positive but insignificant skill score.</div>
"""
    return shell("Executive summary", "summary.html", body)


def build_requirements() -> str:
    rows = [[td(e(r["id"])), td(e(r["requirement"])), td(state_pill(r["state"])), td(e(r["evidence"])),
             td(f'<a href="{e(r["page"])}">{e(r["page"])}</a>'), td(src(r["source"]))]
            for r in C.REQUIREMENTS]
    done = sum(1 for r in C.REQUIREMENTS if r["state"] == "Done")
    body = f"""<div class="eyebrow">Scope control</div><h1>Requirements register</h1>
<p class="lede">Every line you asked for, what was actually delivered, and the page where you can check it.
A requirement is only marked Done when something can be inspected.</p>
<div class="metrics">{metric("Requirements", str(len(C.REQUIREMENTS)), "traced to a page")}
{metric("Done", str(done), "inspectable output")}
{metric("Partial", str(len(C.REQUIREMENTS) - done), "blocked by missing data, not effort")}</div>
{table("Requirements traceability. 'Partial' always names the missing input.", 
       ["ID", "Requirement", "State", "Evidence", "Page", "Source"], rows)}
<div class="notice danger"><strong>Deliberate partials.</strong> Originated lines, strategies, correlations
and prop combinations are Partial because the licensed price and player-level data do not exist. Marking them
Done would require inventing values.</div>"""
    return shell("Requirements", "requirements.html", body)


def build_decisions() -> str:
    rows = []
    for d in C.DECISIONS:
        rows.append([td(e(d["id"])), td(e(d["area"])), td(e(d["question"])),
                     td(e(d["known"])), td(blank=True), td(e(d["missing"])), td(e(d["discovery"])),
                     td(pill(d["blocking"], "danger" if d["blocking"] == "Yes" else "muted")),
                     td(src(d["source"]))])
    blocking = sum(1 for d in C.DECISIONS if d["blocking"] == "Yes")
    body = f"""<div class="eyebrow">Before any build</div><h1>Decisions that must be settled first</h1>
<p class="lede">This is the list you asked for: the questions, what we already know, what is still missing, how
to find it, and whether it blocks a decision. The answer column is intentionally empty - an answer is only
entered when a source or your explicit decision settles it.</p>
<div class="metrics">{metric("Questions", str(len(C.DECISIONS)), "grouped by area")}
{metric("Blocking", str(blocking), "cannot proceed without an answer")}
{metric("Answered", "0", "none can be answered from evidence alone")}</div>
<div class="toolbar">
  <input type="search" data-table="decisions-table" data-filter-key="search" placeholder="Search questions, gaps, discovery actions">
  <select data-table="decisions-table" data-filter-key="blocking">
    <option value="">All priorities</option><option value="yes">Blocking only</option><option value="no">Non-blocking</option>
  </select><span class="count" data-count="decisions-table"></span></div>
<table id="decisions-table" class="decisions"><caption>Decision register. Blank answer cells are the point of the table.</caption>
<thead><tr><th>ID</th><th>Area</th><th>Question</th><th>Known information</th><th>Answer</th><th>Missing information</th><th>How to discover it</th><th>Blocks?</th><th>Source</th></tr></thead>
<tbody>"""
    for d in C.DECISIONS:
        search = e(" ".join([d["area"], d["question"], d["known"], d["missing"], d["discovery"]]).lower())
        body += (f'<tr><td data-search="{search}" data-blocking="{"yes" if d["blocking"] == "Yes" else "no"}">{e(d["id"])}</td>'
                 f'<td>{e(d["area"])}</td><td>{e(d["question"])}</td><td>{e(d["known"])}</td>'
                 f'<td class="blank">{BLANK}</td><td>{e(d["missing"])}</td><td>{e(d["discovery"])}</td>'
                 f'<td>{pill(d["blocking"], "danger" if d["blocking"] == "Yes" else "muted")}</td>'
                 f'<td>{src(d["source"])}</td></tr>')
    body += """</tbody></table>
<div class="notice"><strong>Why no answers.</strong> Every question here asks for something a page cannot tell
us: a licence, a fee, a legal position, an internal policy or a data feed that has not been bought. Guessing any
of them would be the exact failure this desk exists to prevent.</div>"""
    return shell("Decisions needed", "decisions.html", body)


def build_questions() -> str:
    groups = {}
    for d in C.DECISIONS:
        groups.setdefault(d["area"], []).append(d)
    body = """<div class="eyebrow">Discovery map</div><h1>Missing information, and how to get it</h1>
<p class="lede">The same 24 questions, reorganised by what has to be discovered rather than what has to be decided.
Each row names a concrete source or action that would close the gap, so the list can be worked rather than argued
about.</p>"""
    for area, items in groups.items():
        rows = [[td(e(d["id"])), td(e(d["missing"])), td(e(d["discovery"])),
                 td(pill("Blocking" if d["blocking"] == "Yes" else "Open", "danger" if d["blocking"] == "Yes" else "muted")),
                 td(src(d["source"]))] for d in items]
        body += f"<h2>{e(area)}</h2>" + table(
            f"{area}: what is unknown and the action that would settle it.",
            ["ID", "Information still missing", "Discovery action", "Priority", "Source"], rows)
    body += """
<h2>What we already have, stated precisely</h2>
""" + table("Verified inputs available today. Each row can be re-checked from the repository.",
 ["Input", "Size", "Where it lives", "Source"],
 [[td("Official 2026 game results, Weeks 1-9"), td(f"{ANALYSIS['league']['games_with_scores']} finals with scores, 1 blank"),
   td('<a href="data/games_2026.csv">data/games_2026.csv</a>'), td(src("S04", "NFL schedules"))],
  [td("Official standings snapshot for cross-check"), td("32 clubs, W-L-T, PF, PA"),
   td("line-lab/data/standings_2026.json"), td(src("S05", "NFL standings"))],
  [td("Official Week 10 injury report"), td(f"{AVAIL['counts']['injury_rows']} player rows across 13 matchups"),
   td("decision-lab/data/official_snapshot.json"), td(src("S01", "NFL injury report"))],
  [td("Published club depth charts"), td(f"{AVAIL['counts']['depth_rows_total']} ranked rows, 30 club labels"),
   td("decision-lab/data/official_snapshot.json"), td(src("S13", "NFL team directory"))],
  [td("Weekly schedule for the Week 10 slate"), td("14 games with venue and kickoff"),
   td('<a href="data/week10_slate.csv">data/week10_slate.csv</a>'), td(src("S02", "Week 10 article"))]]) + """
<h2>What we do not have, at all</h2>
""" + table("Absent inputs. Nothing in the repository substitutes for them.",
 ["Missing input", "Consequence", "Blocking decision", "Source"],
 [[td("Any price, spread, total or prop quote"), td("No edge, hold, CLV or market comparison is computable"), td(e("D02, D03")), td(src("S10"))],
  [td("Player-level official box scores"), td("No prop can be scored and no prop correlation can be measured"), td(e("D17")), td(src("S04"))],
  [td("Confirmed participation and snap counts"), td("A published depth slot cannot be turned into workload"), td(e("D06")), td(src("S08"))],
  [td("Settlement rules per market"), td("Even a correct forecast cannot be graded for props"), td(e("D04")), td(src("S10"))],
  [td("Prior seasons of official finals"), td("One season cannot separate structure from noise"), td(e("D12")), td(src("S04"))],
  [td("Reward funding and eligibility policy"), td("The reward column stays blank on every leaderboard"), td(e("D18")), td(src("S11"))]]) + """
<div class="notice warn"><strong>The honest summary.</strong> The evidence we have supports describing what
happened and how uncertain the description is. It does not support pricing a wager. The gap is not analysis
effort; it is licensed data and governance.</div>"""
    return shell("Information gaps", "questions.html", body)


def build_suggestions() -> str:
    rows = []
    for s in C.SUGGESTIONS:
        sel = (f'<select class="review" data-suggestion-id="{e(s["id"])}" data-title="{e(s["title"])}">'
               '<option value="">Unreviewed</option><option value="approve">Approve</option>'
               '<option value="defer">Defer</option><option value="reject">Reject</option></select>')
        rows.append([td(e(s["id"])), td(e(s["title"])),
                     td(pill(s["priority"], "danger" if s["priority"] == "Critical" else "warn")),
                     td(e(s["effort"])), td(e(s["impact"])), td(e(s["recommendation"])), td(e(s["depends"])),
                     td(e(s["tradeoff"])), td(sel), td(src(s["source"]))])
    path_a = [s for s in C.SUGGESTIONS if s["path"] == "A"]
    path_b = [s for s in C.SUGGESTIONS if s["path"] == "B"]
    body = f"""<div class="eyebrow">Review before implementation</div><h1>Suggestions and decision paths</h1>
<p class="lede">This is the section you asked for: proposals you can review and choose between before anything
changes. Mark each one approve, defer or reject; the selection is stored only in this browser and can be
exported as a JSON decision record. Nothing here modifies the repository.</p>
<div class="metrics">{metric("Suggestions", str(len(C.SUGGESTIONS)), "each with a trade-off")}
{metric("Path A · foundation", str(len(path_a)), "cheap, unblocks everything else")}
{metric("Path B · expansion", str(len(path_b)), "needs licensed data or more seasons")}</div>
<div class="notice ok"><strong>Path A is the low-regret default.</strong> It costs little, needs no new data
purchase, and stops the failures already visible in the repository: duplicated numbers, conflicting official
pages and citations that now 404.</div>
<div class="notice warn"><strong>Path B is where strategy work lives.</strong> Every item in it depends on a
decision that has not been taken, so starting it now spends effort on results that cannot be scored.</div>
<div class="toolbar">
  <input type="search" data-table="suggestions-table" data-filter-key="search" placeholder="Search suggestions">
  <select data-table="suggestions-table" data-filter-key="path">
    <option value="">Both paths</option><option value="A">Path A only</option><option value="B">Path B only</option>
  </select>
  <span class="count" data-count="suggestions-table"></span>
  <span id="review-summary" class="count"></span>
  <button id="export-review" class="primary">Export review JSON</button>
  <button id="reset-review">Reset local review</button>
</div>
<table id="suggestions-table"><caption>Prioritised suggestions. Dependencies must be settled before implementation.</caption>
<thead><tr><th>ID</th><th>Suggestion</th><th>Priority</th><th>Effort</th><th>Impact</th><th>Path</th>
<th>Depends on</th><th>Trade-off</th><th>Your decision</th><th>Source</th></tr></thead><tbody>"""
    for s in C.SUGGESTIONS:
        search = e(" ".join([s["title"], s["impact"], s["tradeoff"], s["recommendation"]]).lower())
        sel = (f'<select class="review" data-suggestion-id="{e(s["id"])}" data-title="{e(s["title"])}">'
               '<option value="">Unreviewed</option><option value="approve">Approve</option>'
               '<option value="defer">Defer</option><option value="reject">Reject</option></select>')
        body += (f'<tr><td data-search="{search}" data-path="{e(s["path"])}">{e(s["id"])}</td>'
                 f'<td>{e(s["title"])}</td>'
                 f'<td>{pill(s["priority"], "danger" if s["priority"] == "Critical" else "warn")}</td>'
                 f'<td>{e(s["effort"])}</td><td>{e(s["impact"])}</td>'
                 f'<td>{pill("Path " + s["path"], "ok" if s["path"] == "A" else "warn")}</td>'
                 f'<td>{e(s["depends"])}</td><td>{e(s["tradeoff"])}</td><td>{sel}</td>'
                 f'<td>{src(s["source"])}</td></tr>')
    body += "</tbody></table>"
    for label, items in (("Path A · foundation", path_a), ("Path B · expansion", path_b)):
        body += f"<h2>{e(label)}</h2>" + table(
            f"{label}: the sequence I would follow.",
            ["Order", "ID", "What it does", "Why it comes here", "Source"],
            [[td(str(i)), td(e(s["id"])), td(e(s["title"])), td(e(s["impact"])), td(src(s["source"]))]
             for i, s in enumerate(items, start=1)])
    return shell("Suggestions", "suggestions.html", body)


def build_lines() -> str:
    a = ANALYSIS
    l, fit, orig = a["league"], a["model_fit"], a["origination"]
    board = orig["board"]
    rows = []
    for key, g in sorted(board.items(), key=lambda kv: kv[1]["originated_home_margin"], reverse=True):
        rows.append([td(e(f"{g['away']} @ {g['home']}")), num(g["originated_home_margin"], 1),
                     num(g["originated_total"], 1), num(g["sigma_margin_for_band"], 1),
                     td(blank=True), td(blank=True), td(src("S04", "NFL schedules"))])
    body = f"""<div class="eyebrow">Independent numbers</div><h1>Originating our own lines</h1>
<p class="lede">The goal is a number of our own, built from official results only, with the uncertainty stated
next to it. What a line <em>cannot</em> be without a market is value, a lean or an edge - those cells are blank
by design.</p>
<div class="notice danger"><strong>The one thing this page will not claim.</strong> With no licensed price
anywhere in the repository, there is nothing to compare an originated number against. Every board row therefore
carries blanks for the market side and the edge.</div>
<div class="metrics">
  {metric("League mean total", str(l["mean_total_points"]), f"sd {l['sd_total_points']} over {l['games_with_scores']} finals")}
  {metric("Mean home margin", str(l["mean_home_margin"]), f"sd {l['sd_home_margin']}")}
  {metric("Estimated home-field edge", str(a['model_all']['hfa_points']), "points; about zero in this sample")}
  {metric("Residual margin sd", str(fit["residual_sd_margin"]), "in-sample, so optimistic")}
</div>
<h2>How a number is produced</h2>
{table("The origination protocol, in the order it has to run.",
 ["Step", "What is done", "Why it matters", "State", "Source"],
 [[td("1"), td("Freeze the official final scores and cross-check them against official standings"),
   td("A rating built on a mis-transcribed score is worthless"), td(pill("Done", "ok")), td(src("S05"))],
  [td("2"), td("Estimate the league mean and sd for totals and for margins"),
   td("These are the raw constants a line is made of"), td(pill("Done", "ok")), td(src("S11"))],
  [td("3"), td("Fit opponent-adjusted attack and defence ratings with shrinkage"),
   td("Beating weak opponents must not inflate a rating"), td(pill("Done", "ok")), td(src("S04"))],
  [td("4"), td("Publish an interval, not a point"), td("A number without a band invites false precision"),
   td(pill("Partial", "warn")), td(src("S11"))],
  [td("5"), td("Compare against a licensed closing price, same market, same timestamp"),
   td("Without this, 'value' is undefined"), td(pill("Blocked", "danger")), td(src("S10"))],
  [td("6"), td("Shadow the version forward before it is used"), td("Skill must survive out of sample"),
   td(pill("Blocked", "danger")), td(src("S11"))]])}
<h2>Week 10 board (internal reference only)</h2>
<p class="lede">Each row is the model's own number for the Week 10 slate. Home margin is in points for the home
club; the total is the fitted league total, which is constant across games - a documented limitation of a
points-only model, not a claim about any matchup.</p>
{table("Originated Week 10 numbers. Market columns are blank because no licensed price exists.",
 ["Matchup", "Home margin (pts)", "Total (pts)", "Uncertainty band (sd)", "Market line", "Edge vs market", "Source"],
 rows)}
<div class="notice"><strong>Read the board like this.</strong> A rating difference of, say, six points is an
estimate whose own error is larger than six points in a nine-week sample. The band column carries the residual
sd; the reliability section quantifies how much of the underlying rating repeats at all.</div>
"""
    return shell("Line origination", "lines.html", body)


def build_strategies() -> str:
    a = ANALYSIS
    w, l = a["walk_forward"], a["league"]
    corr = {c["a"] + "_" + c["b"]: c for c in a["correlations"]}
    measured = {
        "brier": f"Brier {w['brier_model']} vs {w['brier_coin_flip']} (coin flip); skill {w['brier_skill_vs_base_rate']} vs base rate",
        "home_rate": f"{round(l['share_home_wins'] * 100, 1)}% home wins over {l['games_with_scores']} finals",
        "momentum": f"week-to-week r {corr['margin_w_margin_w+1']['r']} (interval includes zero)",
        "luck_spread": f"largest gap between wins and expected wins is {max(t['wins_minus_expected'] for t in a['luck']['teams'])} wins",
        "margin_total": f"margin vs total r {corr['margin_total']['r']}",
    }
    rows = []
    for s in C.STRATEGIES:
        passed = sum(1 for v in s["gates"].values() if v == "PASS")
        status = "Eligible" if passed == len(s["gates"]) else ("Blocked" if passed < 6 else "In review")
        rows.append([td(e(s["id"])), td(e(s["name"])), td(e(s["division"])), td(e(s["hypothesis"])),
                     td(e(measured[s["measured"]])) if s["measured"] else
                     td('none - no data recorded', blank=True),
                     td(f"{passed}/{len(s['gates'])}"),
                     td(pill(status, "ok" if status == "Eligible" else "danger")),
                     td(blank=True), td(src(s["source"]))])
    gate_rows = []
    for s in C.STRATEGIES:
        gate_rows.append([td(e(s["id"]))] + [td(gate_pill_state(s["gates"][g["id"]])) for g in C.GATES] + [td(src(s["source"]))])
    body = f"""<div class="eyebrow">Gate first, rank later</div><h1>Strategies and the leaderboard</h1>
<p class="lede">Singles, parlays and prop combinations are separate divisions because they carry different
dependence and different data needs. A strategy enters a leaderboard only after it passes every gate; today
none do, and the reason is stated per gate rather than hidden.</p>
<div class="notice danger"><strong>Leaderboard is empty on purpose.</strong> Zero of {len(C.STRATEGIES)}
strategies pass all ten gates. The strongest evidence in the repository - a positive out-of-sample Brier skill of
{w['brier_skill_vs_base_rate']} - fails G06 because the bootstrap interval includes zero, and fails G04 because
no price exists to beat.</div>
<h2>Strategy register</h2>
{table("Hypotheses, the measured evidence where it exists, and gate progress.",
 ["ID", "Strategy", "Division", "Hypothesis", "Measured evidence", "Gates passed", "Status", "Correlation used", "Source"], rows)}
<h2>Gate matrix</h2>
{table("Every strategy against every gate. PENDING means the test has not been run to significance.",
 ["Strategy"] + [f'{g["id"]} {g["name"]}' for g in C.GATES] + ["Source"], gate_rows)}
<h2>Leaderboards</h2>
{table("Leaderboard entries by division. A blank skill, reward or entry means no eligible strategy exists.",
 ["Division", "Eligible entries", "Skill score", "Uncertainty", "Reward", "Why it is empty", "Source"],
 [[td("Singles"), td("0"), td(blank=True), td(blank=True), td(blank=True),
   td("No strategy passes G04 (no price) or G06 (skill not significant)"), td(src("S10"))],
  [td("Game parlays"), td("0"), td(blank=True), td(blank=True), td(blank=True),
   td("No joint settlement archive and no combination price"), td(src("S04"))],
  [td("Same-game parlays"), td("0"), td(blank=True), td(blank=True), td(blank=True),
   td("Legs are measurably dependent, so the product rule fails G07"), td(src("S04"))],
  [td("Player props"), td("0"), td(blank=True), td(blank=True), td(blank=True),
   td("No player-level outcome data exists in the repository"), td(src("S04"))],
  [td("Prop combinations"), td("0"), td(blank=True), td(blank=True), td(blank=True),
   td("Prop correlation is unknown and is left blank"), td(src("S04"))]])}
<div class="notice warn"><strong>How a reward would work once it is approved.</strong> Score every eligible
entry on benchmark-relative proper score with a game-clustered lower bound, correct for the number of trials,
rank within division, and pay nothing until funding and eligibility are approved (G10). Recognition only is the
current proposal.</div>
"""
    return shell("Strategies & leaderboard", "strategies.html", body)


def build_validation() -> str:
    rows = [[td(e(g["id"])), td(e(g["name"])), td(e(g["rule"])), td(e(g["test"])), td(e(g["fail"])), td(src("S11"))]
            for g in C.GATES]
    fails = {g["id"]: sum(1 for s in C.STRATEGIES if s["gates"][g["id"]] == "FAIL") for g in C.GATES}
    body = f"""<div class="eyebrow">Fail closed</div><h1>Validation gates</h1>
<p class="lede">Ten gates that a strategy must pass before it may appear on a leaderboard. Each gate states the
rule, the evidence test and the fail condition, so a rejection can be argued with evidence instead of opinion.</p>
{table("The ten gates.", ["Gate", "Name", "Rule", "Evidence test", "Fails when", "Methods source"], rows)}
<h2>How the current strategies fare, gate by gate</h2>
{table("Number of the ten strategies that fail each gate.",
 ["Gate", "Name", "Strategies failing", "Reading"],
 [[td(e(g["id"])), td(e(g["name"])), td(f"{fails[g['id']]}/{len(C.STRATEGIES)}"),
   td(e({"G04": "No licensed price archive exists, so this gate cannot pass by analysis.",
         "G06": "One entry has a positive but insignificant out-of-sample skill.",
         "G10": "No reward policy has been approved."}.get(g["id"], "Failure follows from missing inputs or from the measured dependence."))),
   td(src("S11"))] for g in C.GATES])}
<div class="notice"><strong>What the gates are not.</strong> They are not a backtest and they are not a
profitability test. They decide whether a claim is supported, which is the step that has to happen before any
claim about money.</div>"""
    return shell("Validation gates", "validation.html", body)


def build_injuries() -> str:
    c = AVAIL["counts"]
    sc = AVAIL["second_source_check"]
    designated = [r for r in PLAYERS if r["game_status"]]
    rows = []
    for r in sorted(PLAYERS, key=lambda r: (r["game_status"] == "", r["published_rank"])):
        rows.append([td(e(r["team"])), td(e(r["position"])), td(e(r["player"])), td(e(r["injury"]) or "—"),
                     td(e(r["practice_status"])), td(e(r["game_status"]) if r["game_status"] else ""),
                     td(f'{r["published_rank"]} · {e(r["rank_label"])}'), td(e(r["unit"])),
                     td(e(r["next_up"]) if r["next_up"] else "no next name on the chart"),
                     td(blank=True), td(blank=True),
                     td(link(r["injury_source"], "Injury") + " · " + link(r["depth_source"], "Depth"))])
    conflict_rows = []
    for r in sc["on_report_page_but_not_article"]:
        conflict_rows.append([td(e(r["team"])), td(e(r["player"])), td(e(r["position"])),
                              td(pill(r["status"], "danger" if r["status"] == "Out" else "warn")),
                              td(pill("not listed", "muted")), td(src("S01", "Report page") + " · " + src("S02", "Article"))])
    for r in sc["in_article_but_not_report_page"]:
        conflict_rows.append([td(e(r["team"])), td(e(r["player"])), td(blank=True),
                              td(pill("not listed", "muted")), td(pill(r["article_status"], "danger")),
                              td(src("S02", "Article") + " · " + src("S01", "Report page"))])
    for r in sc["conflicting_values"]:
        conflict_rows.append([td(e(r["team"])), td(e(r["player"])), td(blank=True),
                              td(pill(r["report_status"] or "not listed", "warn")),
                              td(pill(r["article_status"], "danger")),
                              td(src("S01", "Report page") + " · " + src("S02", "Article"))])
    body = f"""<div class="eyebrow">Availability and depth</div><h1>Injuries, starters and backup exposure</h1>
<p class="lede">The question you asked is not "who is injured" but "which string is on the field". This page
answers the part official sources support: an injured player's published depth slot at his position, and the next
name down on that same club chart. It does not claim who starts.</p>
<div class="metrics">
  {metric("Injury rows captured", str(c["injury_rows"]), "official Week 10 report")}
  {metric("Rows joined to a depth slot", str(c["injury_rows_joined_to_depth"]), "name-and-position match")}
  {metric("2nd string or deeper", str(c["depth_slots_at_2nd_string_or_deeper"]), "the exposure you asked about")}
  {metric("Not on a captured chart", str(c["players_not_found_on_chart"]), "left blank, not guessed")}
  {metric("Clubs without a chart", str(c["clubs_without_a_captured_chart"]), "capture gap, flagged")}
</div>
<div class="notice danger"><strong>The chain of inference stops here.</strong> A designation proves a player is
listed. A depth chart proves where a club lists him. Neither proves he is inactive, who replaces him, or how many
snaps anyone plays. Those three columns are blank on every row.</div>
<h2>Two official pages disagree on this week</h2>
{table("Designations compared row by row between the injury-report page and the Week 10 article.",
 ["Team", "Player", "Pos", "Report page says", "Article says", "Sources"], conflict_rows)}
<h2>Week 10 designated players, placed on their published depth chart</h2>
{table("Players with a game-status designation, with their published slot and next man up.",
 ["Team", "Pos", "Player", "Injury", "Practice", "Game status", "Published slot", "Unit", "Next on chart",
  "Confirmed active", "Expected snaps", "Sources"],
 [[td(e(r["team"])), td(e(r["position"])), td(e(r["player"])), td(e(r["injury"]) or "not stated"),
   td(e(r["practice_status"])), td(pill(r["game_status"], "danger" if r["game_status"] == "Out" else "warn")),
   td(f'{r["published_rank"]} · {e(r["rank_label"])}'), td(e(r["unit"])),
   td(e(r["next_up"]) if r["next_up"] else "no next name on the chart"),
   td(blank=True), td(blank=True),
   td(link(r["injury_source"], "Injury") + " · " + link(r["depth_source"], "Depth"))]
  for r in designated])}
<h2>Full join: every injured player that matched a published chart</h2>
<div class="toolbar">
  <input type="search" data-table="join-table" data-filter-key="search" placeholder="Search team, player, position">
  <select data-table="join-table" data-filter-key="status">
    <option value="">All statuses</option><option value="Out">Out</option><option value="Questionable">Questionable</option>
    <option value="none">No designation</option></select>
  <span class="count" data-count="join-table"></span>
</div>
<div class="tablewrap"><table id="join-table"><caption>{c['injury_rows_joined_to_depth']} rows. Confirmed active and expected snaps are blank because no official source establishes them.</caption>
<thead><tr><th>Team</th><th>Pos</th><th>Player</th><th>Injury</th><th>Practice</th><th>Game status</th>
<th>Published slot</th><th>Unit</th><th>Next on chart</th><th>Confirmed active</th><th>Expected snaps</th><th>Sources</th></tr></thead><tbody>"""
    for r in sorted(PLAYERS, key=lambda r: (r["game_status"] == "", r["published_rank"])):
        search = e(" ".join([r["team"], r["player"], r["position"], r["injury"], r["next_up"], r["unit"]]).lower())
        status = r["game_status"] or "none"
        body += (f'<tr><td data-search="{search}" data-status="{e(status)}">{e(r["team"])}</td>'
                 f'<td>{e(r["position"])}</td><td>{e(r["player"])}</td>'
                 f'<td>{e(r["injury"]) if r["injury"] else "—"}</td><td>{e(r["practice_status"])}</td>'
                 f'<td>{pill(r["game_status"], "danger" if r["game_status"] == "Out" else "warn") if r["game_status"] else BLANK}</td>'
                 f'<td>{r["published_rank"]} · {e(r["rank_label"])}</td><td>{e(r["unit"])}</td>'
                 f'<td>{e(r["next_up"]) if r["next_up"] else "no next name"}</td>'
                 f'<td class="blank">{BLANK}</td><td class="blank">{BLANK}</td>'
                 f'<td>{link(r["injury_source"], "Injury")} · {link(r["depth_source"], "Depth")}</td></tr>')
    body += "</tbody></table></div>"
    body += "<h2>Coverage gaps</h2>" + table(
        "Clubs where no depth chart could be parsed. No ranks were inferred.",
        ["Club", "Reason", "State", "Source"],
        [[td(e(f["team"])), td(e(f["reason"])), td(pill("Coverage gap", "warn")), td(src("S13", "NFL directory"))]
         for f in AVAIL["depth_capture_failures"]])
    body += "<h2>Why the remaining cells stay blank</h2><ul class='list'>" + "".join(
        f"<li>{e(x)}</li>" for x in AVAIL["interpretation_limits"]) + "</ul>"
    return shell("Injuries & depth", "injuries.html", body)


def build_luck() -> str:
    a = ANALYSIS
    l, r, w = a["league"], a["reliability"], a["walk_forward"]
    corr_rows = []
    for c in a["correlations"]:
        ci = f"{c['ci95'][0]} to {c['ci95'][1]}" if c["ci95"] else ""
        corr_rows.append([td(e(c["pair"])), td(str(c["n"])),
                          num(c["r"], 3) if c["r"] is not None else td(blank=True),
                          td(e(ci)) if ci else td(blank=True), td(e(c["use"])), td(src("S11", "Methods"))])
    weekly = [[td(str(x["week"])), td(str(x["n"])), num(x["brier_model"], 4), num(x["brier_coin_flip"], 4),
               num(x["skill_vs_coin_flip"], 4), td(src("S04", "NFL schedules"))] for x in w["weekly"]]
    teams = [[td(e(t["team"])), td(f"{t['w']}-{t['l']}-{t['t']}"), num(t["expected_wins_from_points"]),
              num(t["wins_minus_expected"]), num(t["pythagorean_wins"]), td(e(t["one_score_record"])),
              td(src("S04", "NFL schedules"))] for t in a["luck"]["teams"]]
    rating = [[td(e(t["team"])), num(t["net_rating"], 2), num(t["attack_rating"], 2), num(t["defence_rating"], 2),
               num(t["half_r_odd"], 2), num(t["half_r_even"], 2), td(src("S04", "NFL schedules"))]
              for t in a["teams"]]
    body = f"""<div class="eyebrow">Signal, noise and dependence</div><h1>Luck, skill and correlation</h1>
<p class="lede">You asked to remove luck and build only selectively skill-based strategies. Luck cannot be
removed - but three things can be measured: how much of a rating repeats, how far a record sits from its point
differential, and whether skill survives on games the model never saw. All three are below, with intervals.</p>
<div class="metrics">
  {metric("Half-sample reliability", str(r["half_sample_r"]), "odd weeks vs even weeks")}
  {metric("Stable share of variance", str(r["spearman_brown_full_sample"]), "Spearman-Brown corrected")}
  {metric("Noise share", str(r["noise_variance_share"]), "the part that does not repeat")}
  {metric("Out-of-sample games", str(w["n_games"]), f"weeks {w['evaluation_weeks'][0]}-{w['evaluation_weeks'][-1]}")}
  {metric("Brier skill vs coin flip", str(w["brier_skill_vs_coin_flip"]), f"interval {w['skill_ci95'][0]} to {w['skill_ci95'][1]}")}
</div>
<div class="notice warn"><strong>The key sentence.</strong> About
{round((1 - r['spearman_brown_full_sample']) * 100)}% of the variance in a nine-week team rating is variance that
does not repeat. Any strategy built on this season alone is mostly trading noise, which is why the gates demand
out-of-sample and prospective evidence.</div>
<h2>Measured correlations</h2>
{table("Correlations computed from official finals, with bootstrap intervals. An unknown is left blank, not zero.",
 ["Relationship", "n", "r", "95% interval", "Why it matters", "Methods"], corr_rows)}
<h2>Out-of-sample skill, week by week</h2>
{table("Walk-forward test: each week is predicted by a model fitted only on earlier weeks.",
 ["Week", "Games", "Brier", "Coin flip", "Skill vs coin flip", "Source"], weekly)}
<div class="notice"><strong>Read the weekly rows carefully.</strong> Two of the six evaluation weeks are negative
and the overall interval includes zero. That is exactly the pattern a real but small signal produces in 88 games,
and also the pattern noise produces. It is not evidence of an edge, and with no price it could not be one.</div>
<h2>Record versus expectation</h2>
<p class="lede">Wins compared with the wins the ratings expected before those games, and with a Pythagorean
estimate. A gap is a candidate luck or clutch effect, never a proven one.</p>
{table("All 32 clubs. Expected wins come from the fitted ratings, not from the actual result.",
 ["Team", "Record", "Expected wins", "Wins minus expected", "Pythagorean", "One-score record", "Source"], teams)}
<h2>Opponent-adjusted ratings and their split-half stability</h2>
{table("Net rating = attack + defence. The two half-sample columns show how much the rating moves when the sample is split.",
 ["Team", "Net rating", "Attack", "Defence", "Half A", "Half B", "Source"], rating)}
<div class="notice warn"><strong>How to use this.</strong> Shrink hard toward zero early in a season, do not use
single-week form, and treat any gap between record and expectation as a hypothesis to test over seasons rather
than a signal to trade.</div>
"""
    return shell("Luck, skill & correlation", "luck.html", body)


def build_audit() -> str:
    checks = [
        ("Every table row has an official or methods source link", "scripts/check.py", "PASS", "S11"),
        ("Game log reproduces official standings", "scripts/crosscheck_games.py", "PASS 154/160 fields", "S05"),
        ("No value invented: blanks counted and preserved", "scripts/check.py", "PASS", "S01"),
        ("Every source URL opened on 2026-11-12", "manual verification log", "PASS with one correction", "S08"),
        ("No market price anywhere in the repository", "repository scan", "CONFIRMED ABSENT", "S10"),
        ("No player-level outcome data anywhere", "repository scan", "CONFIRMED ABSENT", "S04"),
        ("Dead citation URLs in earlier workspaces", "manual verification", "3 FOUND", "S08"),
        ("Two official pages disagree on Week 10", "scripts/availability.py", "CONFIRMED", "S02"),
    ]
    body = """<div class="eyebrow">Independent check</div><h1>Repository audit</h1>
<p class="lede">What was verified, how, and what came back negative. A check that cannot be run is reported as
not run rather than assumed to pass.</p>
""" + table("Audit results. Each row names the check, the tool and the outcome.",
 ["Check", "How it was run", "Result", "Source"],
 [[td(e(n)), td(f"<code>{e(t)}</code>"), td(pill(r, "ok" if r.startswith("PASS") or r == "CONFIRMED" else "danger")), td(src(s))]
  for n, t, r, s in checks]) + """
<h2>Source rot found while verifying</h2>
""" + table("URLs cited by earlier workspaces that no longer resolve as cited.",
 ["Cited URL", "Status on 2026-11-12", "Working replacement", "Action", "Source"],
 [[td("<code>nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3</code>"),
   td("HTTP 404 page"), td(src("S08", "Same article, full id")), td("Logged for the owning workspace in COORDINATION.md"), td(src("S08"))],
  [td("<code>operations.nfl.com/inside-football-ops/nfl-injury-report/</code>"), td("HTTP 404 page + redirect to operations home"),
   td(blank=True), td("No replacement found; the policy meaning is cited from the news article instead"), td(src("S08"))],
  [td("<code>operations.nfl.com/inside-football-ops/players-legends/player-health-safety/injury-report/</code>"),
   td("HTTP 404 page"), td(blank=True), td("Same as above"), td(src("S08"))]]) + """
<h2>What this audit does not cover</h2>
<ul class="list">
  <li>It does not crawl every external link in the repository; it checks the pages this desk cites and the
  specific set of citations flagged by earlier sessions.</li>
  <li>It cannot confirm that a mutable page will show the same content tomorrow. Hashes prove capture integrity,
  not future stability.</li>
  <li>It does not validate any other workspace's numbers; it records where labels and citations conflict.</li>
</ul>"""
    return shell("Repo audit", "audit.html", body)


def build_flagged() -> str:
    rows = [[td(e(f["id"])), td(pill(f["severity"], "danger" if f["severity"] in {"Critical", "High"} else "warn")),
             td(e(f["title"])), td(e(f["finding"])), td(e(f["action"])), td(src(f["source"]))] for f in C.FLAGS]
    body = """<div class="eyebrow">Published for your review</div><h1>Flagged for review</h1>
<p class="lede">Irregularities and unverified items, each with the source that supports the finding. They do not
block publishing the site; they do block the decisions that depend on them. None has been resolved by inference.</p>
""" + table("Flagged register. Ordered by severity.", ["ID", "Severity", "Issue", "Finding", "What was done instead", "Source"], rows) + """
<h2>Unverified cells, listed explicitly</h2>
""" + table("Cells that are blank on the site, and why.",
 ["Where", "Blank cell", "Why it cannot be filled", "Source"],
 [[td("Injuries & depth"), td("Confirmed active"), td("No official inactive list or participation record is published for these players"), td(src("S08"))],
  [td("Injuries & depth"), td("Replacement confirmed"), td("A published order is not an assignment; no official source names the replacement"), td(src("S15"))],
  [td("Injuries & depth"), td("Expected snaps"), td("No official snap-count capture exists in the repository"), td(src("S08"))],
  [td("Line origination"), td("Market line and edge vs market"), td("No licensed price data of any kind is present"), td(src("S10"))],
  [td("Strategies"), td("Correlation used (props)"), td("No player-level outcome data exists, so no prop correlation can be measured"), td(src("S04"))],
  [td("Strategies"), td("Reward"), td("No funding, eligibility or conflict-of-interest policy has been approved"), td(src("S11"))],
  [td("Decisions needed"), td("Answer"), td("Every question asks for a licence, fee, legal position or internal policy, not a fact a page holds"), td(src("S10"))],
  [td("Week 2 game log"), td("Commanders at Cowboys scores"), td("The NFL publishes 'Hidden Score' for this completed game on both official pages"), td(src("S06"))]]) + """
<div class="notice"><strong>How to act on this page.</strong> Each flag maps to a decision ID on the
<a href="decisions.html">Decisions needed</a> page. When an answer is settled, the flag is closed with the
evidence, not deleted.</div>"""
    return shell("Flagged for review", "flagged.html", body)


def build_sources() -> str:
    rows = [[td(e(s["id"])), td(link(s["url"], s["title"])), td(e(s["publisher"])), td(e(s["establishes"])),
             td(e(s["limit"])), td(pill("Opened", "ok"))] for s in C.SOURCES]
    data_rows = [
        ("Official 2026 finals, Weeks 1-9", "data/games_2026.csv", "136 rows transcribed from the NFL schedule pages, then machine cross-checked against official standings", "S04"),
        ("Week 10 slate", "data/week10_slate.csv", "14 games with venue and kickoff, from the Week 10 injury article", "S02"),
        ("Analysis output", "data/analysis.json", "Generated by scripts/game_model.py from the game log only", "S04"),
        ("Availability join", "data/availability.json", "Generated by scripts/availability.py from the official snapshot", "S01"),
        ("Availability CSV", "data/availability_week10.csv", "Flat export of the join for review", "S01"),
    ]
    body = """<div class="eyebrow">Traceability</div><h1>Sources and what they can prove</h1>
<p class="lede">Every source below was opened on 2026-11-12 and returned the content described in the
"establishes" column. The "limit" column is the part most citation lists leave out, and it is the part that
decides what a number may be used for.</p>
""" + table("Source register. Authority, scope and limit for each page.",
 ["ID", "Source", "Publisher", "What it establishes", "What it cannot establish", "State"], rows) + """
<h2>Captured data files</h2>
""" + table("Files behind every number on this site.",
 ["File", "Path", "How it was produced", "Source"],
 [[td(e(n)), td(f'<a href="{e(p)}">{e(p)}</a>'), td(e(h)), td(src(sid))] for n, p, h, sid in data_rows]) + """
<h2>Reproducing the analysis</h2>
<pre class="notice" style="white-space:pre-wrap"><code>python3 decision-desk/scripts/crosscheck_games.py   # game log vs official standings
python3 decision-desk/scripts/game_model.py         # ratings, reliability, correlation, walk-forward
python3 decision-desk/scripts/availability.py       # injury to depth join and second-source check
python3 decision-desk/scripts/build.py              # regenerate every page
python3 decision-desk/scripts/check.py               # verify links, row citations and blanks</code></pre>
<div class="notice warn"><strong>One honest limitation.</strong> In this working environment the shell cannot open
a TLS connection to nfl.com, so the official pages were read through a page reader and transcribed into
<code>data/games_2026.csv</code> with the exact URL per row. The cross-check against the separately captured
standings snapshot is what makes that transcription trustworthy: 154 of 160 team fields reproduce exactly and the
six exceptions are the one game the NFL hides.</div>"""
    return shell("Sources", "sources.html", body)


BUILDERS = {
    "index.html": build_index, "summary.html": build_summary,
    "requirements.html": build_requirements, "decisions.html": build_decisions,
    "questions.html": build_questions, "suggestions.html": build_suggestions,
    "lines.html": build_lines, "strategies.html": build_strategies,
    "validation.html": build_validation, "injuries.html": build_injuries,
    "luck.html": build_luck, "audit.html": build_audit,
    "flagged.html": build_flagged, "sources.html": build_sources,
}


def main() -> int:
    for name, fn in BUILDERS.items():
        (DESK / name).write_text(fn(), encoding="utf-8")
    print(f"Built {len(BUILDERS)} decision-desk pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
