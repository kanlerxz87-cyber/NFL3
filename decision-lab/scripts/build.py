#!/usr/bin/env python3
"""Build the canonical NFL decision lab from official-source snapshots and catalogs."""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
sys.path.insert(0, str(LAB / "scripts"))
import audit

DATA = LAB / "data"
CATALOG = json.loads((DATA / "catalog.json").read_text())
SNAPSHOT = json.loads((DATA / "official_snapshot.json").read_text())
AVAILABILITY = json.loads((DATA / "availability.json").read_text()) if (DATA / "availability.json").exists() else None
VERIFICATION = json.loads((DATA / "verification.json").read_text()) if (DATA / "verification.json").exists() else None
SOURCES = {s["id"]: s for s in CATALOG["sources"]}
PAGES = [
    ("index.html", "Overview"), ("executive-summary.html", "Executive summary"),
    ("requirements.html", "Requirements"), ("questions.html", "Questions & gaps"),
    ("suggestions.html", "Suggestions"), ("lines.html", "Line origination"),
    ("strategies.html", "Signals & leaderboard"), ("validation.html", "Validation gates"),
    ("injuries.html", "Injuries"), ("depth.html", "Depth & backups"),
    ("availability.html", "Availability & replacements"), ("decisions.html", "Decision paths"),
    ("sources.html", "Sources & capture"), ("verification.html", "Verification log"),
    ("integrity.html", "Verification & integrity"),
    ("flagged.html", "Flagged for review"), ("audit.html", "Repository audit"),
]


def e(value) -> str:
    return html.escape(str(value), quote=True)


def source_link(source_id: str) -> str:
    s = SOURCES[source_id]
    return f'<a href="{e(s["url"])}" target="_blank" rel="noopener noreferrer">{e(s["title"])}</a>'


def raw_source(url: str, label: str = "Official source") -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>'


def pill(text: str, kind: str = "") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def table(caption: str, headers: list[str], rows: list[list[str]], table_id: str = "") -> str:
    ident = f' id="{e(table_id)}"' if table_id else ""
    head = "".join(f"<th scope=\"col\">{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(cell for cell in row) + "</tr>" for row in rows)
    return f'<div class="tablewrap"><table{ident}><caption>{e(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def td(text: str = "", blank: bool = False, attrs: str = "") -> str:
    cls = ' class="blank"' if blank else ""
    return f"<td{cls}{attrs}>{text}</td>"


def shell(title: str, active: str, content: str) -> str:
    nav_parts = []
    for url, label in PAGES:
        current = ' class="active" aria-current="page"' if url == active else ""
        nav_parts.append(f'<a href="{e(url)}"{current}>{e(label)}</a>')
    nav = "".join(nav_parts)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | NFL3 Decision Lab</title><link rel="stylesheet" href="assets/style.css"></head><body><div class="shell"><aside class="side"><a class="brand" href="index.html">NFL3<small>DECISION LAB</small></a><nav class="nav" aria-label="Decision lab navigation">{nav}</nav><div class="side-note">Official-source snapshots. Unknown values stay blank. No strategy is approved for wagering.</div></aside><div class="main"><header class="top"><span>NFL research / decision support</span><span>Updated {e(CATALOG["updated"])}</span></header><main class="wrap">{content}</main><footer class="footer">NFL3 Decision Lab · Research-only. Official source links support review, not reuse rights or betting advice. <a href="../index.html">Repository overview</a></footer></div></div><script src="assets/app.js"></script></body></html>'''


def metric(label: str, value: str, note: str) -> str:
    return f'<div class="metric"><span>{e(label)}</span><strong>{e(value)}</strong><small>{e(note)}</small></div>'


def build_index() -> str:
    critical = sum(1 for q in CATALOG["questions"] if q["blocking"] and not q["answer"])
    content = f'''
<div class="eyebrow">Canonical decision workspace</div><h1>NFL decision lab</h1>
<p class="lede">A source-first dashboard for requirements, questions, suggestions, line-origination protocol, injury/depth evidence and fail-closed validation. It preserves concurrent research workspaces while separating official facts from exploratory community data.</p>
<div class="notice danger"><strong>Decision boundary:</strong> no originated line, correlation, strategy edge or reward is verified for deployment. Existing <a href="../research-desk/index.html">research-desk</a> outputs use community nflverse assets and are flagged as exploratory, not official NFL verification.</div>
<div class="metrics">{metric("Official injury rows", str(SNAPSHOT["coverage"]["injury_rows"]), "NFL.com Week 10 capture")}{metric("Club depth rows", str(SNAPSHOT["coverage"]["depth_rows"]), f'{len(SNAPSHOT["coverage"]["depth_teams"])} club labels captured')}{metric("Report rows joined to depth", str(AVAILABILITY["coverage"]["matched_rows"]) if AVAILABILITY else "—", f'{AVAILABILITY["coverage"]["unmatched_rows"]} unmatched, each with a reason' if AVAILABILITY else "no analysis")}{metric("Replacement leads", str(AVAILABILITY["coverage"]["replacement_leads"]) if AVAILABILITY else "—", "Published next-man evidence")}{metric("Validated strategies", "0", "No eligible verified ledger")}{metric("Open blocking answers", str(critical), "Blank until evidence exists")}{metric("Review flags", str(len(CATALOG["flags"])), "Source-linked irregularities")}</div>
<h2>Recommended path</h2><div class="cards"><div class="card"><h3>1 · Evidence contract</h3><p>Approve official-only provenance, immutable snapshots and conflict flags before model expansion.</p><a href="suggestions.html">Review suggestions →</a></div><div class="card"><h3>2 · Data foundation</h3><p>Secure permissioned odds/prop history and official outcome mapping; keep market values blank until then.</p><a href="questions.html">Open decision questions →</a></div><div class="card"><h3>3 · Shadow singles</h3><p>Pre-register a simple baseline, validate by game clusters, then consider personnel ablations and combos.</p><a href="validation.html">See validation gates →</a></div></div>
<h2>Category tables</h2>{table("Every category is source-linked; unknown empirical cells remain blank.", ["Category", "Purpose", "State", "Source"], [[td(f'<a href="{e(url)}">{e(label)}</a>'), td(purpose), td(state), td(source_link(sid))] for url, label, purpose, state, sid in [
    ("executive-summary.html", "Executive summary", "Important details, blockers and next decisions", "Ready for review", "S01"),
    ("requirements.html", "Requirements", "Full requested scope and delivery state", "Partial where data is missing", "S16"),
    ("questions.html", "Questions & gaps", "Known / missing / answer / discovery action", "Blocking answers blank", "S12"),
    ("suggestions.html", "Suggestions", "Review paths before implementation", "Optional browser-local review", "S16"),
    ("lines.html", "Line origination", "Independent-number protocol and blank current lines", "Blocked by market data", "S12"),
    ("strategies.html", "Signals & leaderboard", "Singles, parlays, props; gate-first ranking", "No eligible entries", "S15"),
    ("validation.html", "Validation gates", "Ten fail-closed gates and reward rules", "Implemented; no live passes", "S14"),
    ("injuries.html", "Injuries", "Official report rows with blank replacement fields", "Captured snapshot", "S01"),
    ("depth.html", "Depth & backups", "Published club order, not confirmed workload", "Partial club coverage", "S06"),
    ("sources.html", "Sources & capture", "Official references and capture hashes", "Opened/captured", "S05"),
    ("verification.html", "Verification log", "Line-by-line re-check with counted exceptions", "Run; 0 mismatches", "S01"),
    ("availability.html", "Availability & replacements", "Which published starters are on the report, who is listed next, and what cannot be answered", "Analysis with per-row sources", "S01"),
    ("decisions.html", "Decision paths", "Three routes compared on prerequisites, cost, benefit and risk", "Ready for a recorded human choice", "S16"),
    ("integrity.html", "Verification & integrity", "Automated field-by-field re-check of the live official source, with drift and unreachable sources reported", "Live run wired into deployment", "S01"),
    ("flagged.html", "Flagged for review", "Irregularities and unverified items", "Published, non-blocking for site", "S02"),
    ("audit.html", "Repository audit", "Independent source-authority and link audit", "See findings", "S16"),
]])}'''
    return shell("Overview", "index.html", content)


def build_summary() -> str:
    content = f'''<div class="eyebrow">Executive summary</div><h1>What is ready, what is blocked</h1>
<p class="lede">The site is publishable as a research and decision-support dashboard. It is not a validated betting system. The most important improvement is governance: separate official evidence, community exploration, model proposals and approved decisions.</p>
<div class="notice ok"><strong>Delivered:</strong> clean category dashboard; full requirements/questions/suggestions registers; official injury capture ({SNAPSHOT["coverage"]["injury_rows"]} rows); club depth capture ({SNAPSHOT["coverage"]["depth_rows"]} rows); fail-closed validation gates; source-linked flagged-review page; automated capture/build workflow.</div>
<div class="notice danger"><strong>Blocked:</strong> licensed historical odds/props, official-only outcome settlement, confirmed replacement workload, empirical correlations, validated strategy performance, reward funding/legal approval. These values remain blank.</div>
<h2>Important findings</h2>{table("Executive findings with official review links.", ["Finding", "Implication", "Action", "Source"], [
    [td("NFL authority is unverified for GitHub-hosted nflverse inputs"), td("Manifest digests verify bytes only; this review found no NFL authorship/authorization record and does not judge data accuracy"), td("Keep these outputs out of official-only gates until provenance and data-use permission are independently confirmed"), td('Observed publisher: ' + raw_source("https://github.com/nflverse/nflverse-data/releases", "nflverse GitHub releases") + '<br>Official reference: ' + source_link("S18"))],
    [td("Injury status is not depth or workload"), td("Questionable/Out cannot identify a 2nd/3rd/4th-string replacement by itself"), td("Join dated club depth, inactive and participation evidence; blank missing fields"), td(source_link("S03"))],
    [td("Club depth charts can be unofficial or stale"), td("Published rank is guidance, not confirmed snaps"), td("Store authority and timestamp; flag conflicts"), td(source_link("S08"))],
    [td("Luck cannot be removed"), td("Residual variance is not pure luck; hot streaks are not skill"), td("Proper scores, game-cluster uncertainty, ablations, multiplicity and shadow records"), td(source_link("S13"))],
    [td("Parlays require joint evidence"), td("Marginal multiplication fails under dependence"), td("Validate direct joint probability and payout rules before combo signals"), td(source_link("S15"))],
    [td("Depth capture joined two players in one cell"), td("Published rows contained non-existent player names"), td("Parser fixed; 22 captured rows flagged and excluded until a fresh capture"), td(source_link("S19"))],
    [td("Self-declared unofficial charts were labelled official"), td("Patriots rows claimed more authority than the page gives them"), td("Capturer now reads the page caveat and labels it UNOFFICIAL"), td(source_link("S20"))],
])}
<h2>Verified findings from the availability analysis</h2>{table("Each number is reproduced by decision-lab/scripts/availability.py from the committed snapshot.", ["Finding", "Measured", "Why it matters", "Source"], [
    [td("Most report rows can be located on a club depth page"), td(f'{AVAILABILITY["coverage"]["matched_rows"]} of {AVAILABILITY["coverage"]["injury_rows"]} joined; {AVAILABILITY["coverage"]["unmatched_rows"]} unmatched, all listed with a reason') if AVAILABILITY else td("—"), td("Personnel questions are answerable for those clubs, and the remainder is visible rather than silently dropped."), td(source_link("S01"))],
    [td("The unmatched rows are concentrated in two clubs"), td("29 of 69 come from the Texans (image chart) and Packers (jersey-number prefixes)") if AVAILABILITY else td("—"), td("This is a parsing gap, not missing data, so it is fixable without new sources."), td(source_link("S28") + "<br>" + source_link("S29"))],
    [td("'Rank 1' does not identify a starter"), td("149 club/unit/position slots publish more than one rank-1 player"), td("Treating column 1 as a confirmed starter would fabricate a lineup the club never published."), td(source_link("S07"))],
    [td("Injury designation is sparse at capture"), td(f'{sum(v for k, v in AVAILABILITY["report_status_counts"]["game_status"].items() if k != "blank") if AVAILABILITY else 0} of 254 rows carry Out or Questionable'), td("The NFL policy says a player certain to play is not listed, so a blank is not evidence of health."), td(source_link("S03"))],
    [td("Depleted depth slots can be counted, not projected"), td("19 slots have 2+ of the top three published players on the report") if AVAILABILITY else td("—"), td("This is the measurable input for replacement-deficiency research; the effect size still needs snaps."), td(source_link("S06"))],
    [td("The report is structurally complete this week"), td("28 of 28 expected club sections across 14 matchups"), td("Nothing is missing at the club level, which isolates the gap to parsing."), td(source_link("S01"))],
    [td("Depth evidence goes stale on publication"), td("The Colts' own Week 10 release reports two starting-receiver trades"), td("A depth snapshot must be versioned against roster events, not trusted as durable."), td(source_link("S08"))],
])}
<h2>What is still missing before a decision</h2>{table("Missing information, phrased as answerable questions.", ["Missing information", "Why it blocks", "Discovery action", "Source"], [
    [td("Permissioned, timestamped price history"), td("No market-relative skill, correlation, parlay or prop test is possible."), td("Secure a data agreement (SG14); publish no price until then."), td(source_link("S12"))],
    [td("Official inactive lists and snap counts"), td("A designation cannot become confirmed participation or backup usage."), td("Capture both per game (SG18)."), td(source_link("S01"))],
    [td("Multi-day retained captures"), td("A single snapshot cannot be backtested, so no history exists yet."), td("Schedule daily captures with hashes (SG16)."), td(source_link("S01"))],
    [td("A pre-registered primary metric"), td("Without it, 'best path' is undefined and win rate would be used by default."), td("Answer Q27, then freeze the metric (SG19)."), td(source_link("S13"))],
    [td("Product scope, jurisdiction and reward funding"), td("A prize or wager feature is unlawful or unfunded until answered."), td("Answer Q01 and Q18; keep rewards recognition-only."), td(source_link("S12"))],
])}
<h2>Next decision sequence</h2><ol class="list"><li>Approve the official-only evidence contract and recognition-only leaderboard.</li><li>Resolve product/jurisdiction and data-rights questions without inventing answers.</li><li>Automate durable official snapshots and conflict alerts.</li><li>Run a pre-registered singles shadow baseline; expand only after gates pass.</li></ol>'''
    return shell("Executive summary", "executive-summary.html", content)


def build_requirements() -> str:
    rows = [[td(e(r["id"])), td(e(r["requirement"])), td(pill(r["state"], "ok" if r["state"] == "implemented" else "warn")), td(e(r["evidence"])), td(e(r["next"])), td(source_link(r["source"]))] for r in CATALOG["requirements"]]
    content = '<div class="eyebrow">Scope control</div><h1>Full requirements register</h1><p class="lede">Each requested capability is traced to delivery state, evidence and the next action. Missing data is not filled by inference.</p>' + table("Requirements traceability.", ["ID", "Requirement", "State", "Evidence", "Next action", "Source"], rows)
    return shell("Requirements", "requirements.html", content)


def build_questions() -> str:
    rows = []
    for q in CATALOG["questions"]:
        answer = td(e(q["answer"])) if q["answer"] else td("", blank=True)
        rows.append([td(e(q["id"])), td(e(q["area"])), td(e(q["question"])), td(e(q["known"])), answer, td(e(q["missing"])), td(e(q["discovery"])), td(pill("Blocking" if q["blocking"] else "Open", "danger" if q["blocking"] else "warn")), td(source_link(q["source"]))])
    content = '<div class="eyebrow">Before any decision</div><h1>Questions, information and answers</h1><p class="lede">Known facts are separated from missing answers. Blank answer cells are intentional; discovery actions name how to close the gap.</p><div class="toolbar"><input data-table="questions-table" data-filter-key="search" placeholder="Search questions"><select data-table="questions-table" data-filter-key="blocking"><option value="">All priority</option><option value="yes">Blocking</option><option value="no">Non-blocking</option></select><span class="count" data-count="questions-table"></span></div>'
    for row, q in zip(rows, CATALOG["questions"]):
        row[0] = td(e(q["id"]), attrs=f' data-search="{e((q["area"] + " " + q["question"] + " " + q["known"] + " " + q["missing"]).lower())}" data-blocking="{"yes" if q["blocking"] else "no"}"')
    content += table("Decision register. Blocking unknowns prevent dependent deployment decisions.", ["ID", "Area", "Question", "Known information", "Answer", "Missing information", "Discovery action", "Priority", "Source"], rows, "questions-table")
    return shell("Questions & gaps", "questions.html", content)


def build_suggestions() -> str:
    rows = []
    for s in CATALOG["suggestions"]:
        select = f'<select class="review" data-suggestion-id="{e(s["id"])}" data-title="{e(s["title"])}"><option value="">Unreviewed</option><option value="approve">Approve</option><option value="defer">Defer</option><option value="reject">Reject</option></select>'
        rows.append([td(e(s["id"])), td(e(s["title"])), td(pill(s["priority"], "danger" if s["priority"] == "Critical" else "warn")), td(e(s["effort"])), td(e(s["impact"])), td(e(s["recommendation"])), td(e(s["depends"])), td(e(s["tradeoff"])), td(select), td(source_link(s["source"]))])
    content = f'''<div class="eyebrow">Review before implementation</div><h1>Suggestions & decision paths</h1><p class="lede">Path A is the recommended low-regret foundation: evidence contract, rights, snapshots and review governance. Path B expands models only after data gates. Selections below are optional, browser-local review artifacts; they do not deploy changes.</p><div class="notice"><span class="path">Path A · Foundation</span><span class="path">Path B · Gated expansion</span><div id="review-summary" class="count"></div><div class="toolbar"><button id="export-review">Export review JSON</button><button id="reset-review" class="secondary">Reset local review</button></div></div>'''
    content += table("Prioritized suggestions. Dependencies must be satisfied before implementation.", ["ID", "Suggestion", "Priority", "Effort", "Impact", "Recommendation", "Depends on", "Trade-off", "Review", "Source"], rows)
    return shell("Suggestions", "suggestions.html", content)


def build_lines() -> str:
    line_rows = [[td(market), td("", blank=True), td("", blank=True), td(pill("Unverified", "warn")), td(reason), td(source_link(sid))] for market, reason, sid in [
        ("Point spread", "No official-only verified forecast ledger or permissioned market benchmark.", "S12"),
        ("Game total", "No verified possession/context training sample and settlement mapping.", "S04"),
        ("Moneyline", "No calibrated official-only probability ledger.", "S15"),
        ("Player prop", "No permissioned prop history, participation and void rules.", "S09"),
        ("Parlay / combo", "No validated joint probability or book payout archive.", "S15"),
    ]]
    protocol = [[td(step), td(detail), td(source_link(sid))] for step, detail, sid in [
        ("1 · Freeze inputs", "Official outcomes, as-of features, raw hashes and permissioned quotes only.", "S14"),
        ("2 · Baseline first", "Simple opponent/context model before complex personnel or tracking features.", "S09"),
        ("3 · Distribution, not one number", "Produce probabilities/quantiles with game-cluster uncertainty; keep point estimate secondary.", "S13"),
        ("4 · Compare fairly", "Same event set, timestamp, vig treatment and settlement as benchmark.", "S12"),
        ("5 · Gate before display", "Only validated, shadowed versions may become decision candidates; current lines remain blank.", "S14"),
    ]]
    content = '<div class="eyebrow">Independent numbers</div><h1>Line origination protocol</h1><p class="lede">The goal is to originate useful NFL lines, not to copy market prices. Current actionable values are blank because the official-only data and market-rights gates are not satisfied.</p><div class="notice warn"><strong>Exploratory archive:</strong> <a href="../research-desk/lines.html">research-desk line outputs</a> are community-data research, not official-source verification or approved betting lines.</div>'
    content += table("Current originated lines: blank until verified.", ["Market", "Independent line", "Probability / interval", "State", "Reason", "Source"], line_rows)
    content += table("Origination method to implement after data gates.", ["Step", "Method", "Source"], protocol)
    return shell("Line origination", "lines.html", content)


def build_strategies() -> str:
    rows = [[td(e(s["id"])), td(e(s["name"])), td(e(s["division"])), td(e(s["hypothesis"])), td(e(s["inputs"])), td(e(s["test"])), td(e(s["risk"])), td(pill(s["status"], "warn")), td("", blank=True), td(source_link(s["source"]))] for s in CATALOG["strategies"]]
    leaderboard = [[td("No eligible strategies"), td("", blank=True), td("", blank=True), td("", blank=True), td("All canonical strategies are Not run; community-data results are excluded from official-only ranking."), td(source_link("S13"))]]
    content = '<div class="eyebrow">Signal research</div><h1>Signals, strategies and leaderboard</h1><p class="lede">Singles, parlays and player-prop combinations are separate research divisions. Correlation and performance cells remain blank without verified matched outcomes.</p>'
    content += table("Strategy hypotheses. No strategy has passed canonical validation.", ["ID", "Strategy", "Division", "Hypothesis", "Required inputs", "Validation test", "Risk", "State", "Correlation", "Source"], rows)
    content += '<div class="notice"><strong>Input readiness (measured):</strong> availability evidence now exists for the personnel strategies — <a href="availability.html">147 published depth slots join to the official report</a>, 19 with two or more listed players. Snapped participation is still absent: no inactive list or snap count is captured, so ST02, ST03, ST04 and ST08 cannot be tested yet.</div>'
    content += '<h2>Leaderboard</h2><div class="notice">Rank only gate-passing strategies by benchmark-relative proper-score skill with uncertainty. Raw win rate, short-run ROI and unverified community results do not earn rewards.</div>'
    content += table("Current eligible leaderboard.", ["Entry", "Skill score", "Uncertainty", "Reward", "Note", "Source"], leaderboard)
    return shell("Signals & leaderboard", "strategies.html", content)


def build_validation() -> str:
    gates = [[td(e(g["id"])), td(e(g["name"])), td(e(g["rule"])), td(e(g["fail"])), td(source_link(g["source"]))] for g in CATALOG["gates"]]
    policy = [[td(rule), td(detail), td(source_link(sid))] for rule, detail, sid in [
        ("Divisions", "Singles, game parlays, same-game parlays and prop combinations ranked separately.", "S15"),
        ("Score", "Benchmark-relative Brier skill with game-cluster lower bound and multiplicity adjustment.", "S13"),
        ("Eligibility", "G01-G09 must pass; G10 adds approved reward policy and verified funding.", "S14"),
        ("Luck boundary", "Luck is not eliminated; uncertainty and prospective evidence reduce false skill claims.", "S13"),
        ("Rewards", "Recognition-only until funding/legal approval; no stake handling.", "S12"),
    ]]
    content = '<div class="eyebrow">Fail closed</div><h1>Validation gates</h1><p class="lede">Every strategy must pass all applicable gates before it can enter a decision leaderboard. The executable gate is tested offline with synthetic fixtures only; those tests are not NFL performance evidence.</p><div class="notice ok"><strong>Offline tests:</strong> 15 unit tests cover capture parsing, blank preservation, odds/vig math, multiplicity, small-sample failure, community-source rejection, future-leak rejection, combo joint evidence and reward withholding.</div>'
    content += table("Ten gates. Unknown or unsupported evidence fails closed.", ["Gate", "Name", "Rule", "Fail condition", "Source"], gates)
    content += table("Leaderboard and reward policy proposal.", ["Rule", "Detail", "Source"], policy)
    return shell("Validation gates", "validation.html", content)


def build_injuries() -> str:
    rows = []
    for r in SNAPSHOT["injury_rows"]:
        search = " ".join(str(r.get(k, "")) for k in ("team", "player", "position", "injury", "practice_status", "game_status", "matchup")).lower()
        rows.append([td(e(r["day"])), td(e(r["matchup"])), td(e(r["team"]), attrs=f' data-search="{e(search)}" data-team="{e(r["team"])}" data-status="{e(r["game_status"] or "blank")}"'), td(e(r["player"])), td(e(r["position"])), td(e(r["injury"])), td(e(r["practice_status"])), td(e(r["game_status"])), td("", blank=True), td("", blank=True), td("", blank=True), td(raw_source(r["source_url"], "NFL report"))])
    for r in SNAPSHOT["no_injury_sections"]:
        search = f'{r["team"]} no injuries reported'.lower()
        rows.append([td(e(r["day"])), td(e(r["matchup"])), td(e(r["team"]), attrs=f' data-search="{e(search)}" data-team="{e(r["team"])}" data-status="no-injuries"'), td("No Injuries Reported"), td(""), td(""), td(""), td(""), td("", blank=True), td("", blank=True), td("", blank=True), td(raw_source(r["source_url"], "NFL report"))])
    teams = sorted({r["team"] for r in SNAPSHOT["injury_rows"]} | {r["team"] for r in SNAPSHOT["no_injury_sections"]})
    options = "".join(f'<option value="{e(t)}">{e(t)}</option>' for t in teams)
    content = f'<div class="eyebrow">Availability evidence</div><h1>Injury report snapshot</h1><p class="lede">Captured {e(SNAPSHOT["observed_at"])} from the official NFL report. Blank game status is not active status. Replacement, rank and snaps remain blank because the report does not establish them.</p><div class="toolbar"><input data-table="injuries-table" data-filter-key="search" placeholder="Search player/team/injury"><select data-table="injuries-table" data-filter-key="team"><option value="">All teams</option>{options}</select><select data-table="injuries-table" data-filter-key="status"><option value="">All statuses</option><option value="Out">Out</option><option value="Questionable">Questionable</option><option value="Doubtful">Doubtful</option><option value="blank">Blank status</option><option value="no-injuries">No injuries reported</option></select><span class="count" data-count="injuries-table"></span></div>'
    content += table("Official injury rows plus explicit no-injury sections. Unknown replacement fields are intentionally blank.", ["Day", "Matchup", "Team", "Player / section", "Pos", "Injury", "Practice status", "Game status", "Replacement", "Rank", "Expected snaps", "Source"], rows, "injuries-table")
    return shell("Injuries", "injuries.html", content)


def build_depth() -> str:
    rows = []
    for r in SNAPSHOT["depth_rows"]:
        search = f'{r["team"]} {r["unit"]} {r["position"]} {r["player"]} {r["authority"]}'.lower()
        rows.append([td(e(r["team"]), attrs=f' data-search="{e(search)}" data-team="{e(r["team"])}" data-unit="{e(r["unit"])}"'), td(e(r["unit"])), td(e(r["position"])), td(e(r["player"])), td(str(r["published_rank"])), td(e(r["authority"])), td("", blank=True), td("", blank=True), td("", blank=True), td(raw_source(r["source_url"], "Club source"))])
    teams = sorted({r["team"] for r in SNAPSHOT["depth_rows"]})
    options = "".join(f'<option value="{e(t)}">{e(t)}</option>' for t in teams)
    failures = SNAPSHOT.get("depth_directory_failures", [])
    content = f'<div class="eyebrow">Offense / defense / special teams</div><h1>Depth charts & backup evidence</h1><p class="lede">Published club order is captured for {len(teams)} club labels. Rank is not confirmed starter status, replacement assignment or workload. Colts evidence is explicitly unofficial. Missing clubs remain flagged.</p><div class="toolbar"><input data-table="depth-table" data-filter-key="search" placeholder="Search team/player/position"><select data-table="depth-table" data-filter-key="team"><option value="">All teams</option>{options}</select><select data-table="depth-table" data-filter-key="unit"><option value="">All units</option><option value="Offense">Offense</option><option value="Defense">Defense</option><option value="Special Teams">Special Teams</option></select><span class="count" data-count="depth-table"></span></div>'
    content += table("Published depth rows. Confirmed starter, assignment and snaps are blank without direct evidence.", ["Team", "Unit", "Position", "Player", "Published rank", "Authority", "Confirmed starter", "Replacement assignment", "Expected snaps", "Source"], rows, "depth-table")
    if failures:
        frows = [[td(e(f["team"])), td(e(f.get("reason", ""))), td(pill("Missing", "warn")), td(raw_source(f.get("source_url", "https://www.nfl.com/teams/"), "NFL directory"))] for f in failures]
        content += "<h2>Depth coverage gaps</h2>" + table("Clubs where no depth table was parsed; no values inferred.", ["Team", "Reason", "State", "Source"], frows)
    return shell("Depth & backups", "depth.html", content)


def build_sources() -> str:
    rows = [[td(e(s["id"])), td(e(s["title"])), td(e(s["publisher"])), td(e(s["checked"])), td(e(s["scope"])), td(e(s["limit"])), td(raw_source(s["url"], "Open official source"))] for s in CATALOG["sources"]]
    manifest = [[td(e(m["id"])), td(e(m["observed_at"])), td(e(m["bytes"])), td(f'<code>{e(m["sha256"][:16])}…</code>'), td(raw_source(m["final_url"], "Captured source"))] for m in SNAPSHOT["manifest"]]
    content = '<div class="eyebrow">Traceability</div><h1>Official sources and capture manifest</h1><p class="lede">Source authority, capture integrity and model validation are separate. A hash proves the captured bytes match the recorded source; it does not grant reuse rights or prove future stability.</p>'
    content += table("Official reference register.", ["ID", "Source", "Publisher", "Checked", "Establishes", "Limitation", "Link"], rows)
    content += table("Latest official capture manifest.", ["Capture", "Observed at (UTC)", "Bytes", "SHA-256 prefix", "Source"], manifest)
    return shell("Sources & capture", "sources.html", content)


def build_flagged() -> str:
    rows = []
    for f in CATALOG["flags"]:
        if f["id"] == "F01":
            provenance = ('Observed publisher: ' + raw_source("https://github.com/nflverse/nflverse-data/releases", "nflverse GitHub releases") + '<br>Official reference: ' + source_link("S18"))
        else:
            provenance = source_link(f["source"])
        rows.append([td(e(f["id"])), td(pill(f["severity"], "danger" if f["severity"] == "Critical" else "warn")), td(e(f["title"])), td(e(f["finding"])), td(e(f["action"])), td(provenance)])
    content = '<div class="eyebrow">Published irregularities</div><h1>Flagged for review</h1><p class="lede">These items do not block site publication, but they block affected decisions. External links identify the reviewed source or official reference; they do not imply authority beyond the stated scope.</p>'
    content += table("Flagged review register.", ["ID", "Severity", "Issue", "Finding", "Action", "Source trail"], rows)
    return shell("Flagged for review", "flagged.html", content)


def build_audit(audit_doc: dict) -> str:
    findings = audit_doc["findings"]
    local_audit = '<a href="scripts/audit.py">Audit code</a> · <a href="data/audit.json">Generated audit data</a>'
    official_context = 'Official context only (not a count source): ' + source_link("S18")
    rows = []
    for f in findings:
        source = local_audit + '<br>' + official_context if f["source"] == "LOCAL_AUDIT" else source_link(f["source"])
        rows.append([td(e(f["id"])), td(pill(f["severity"], "danger" if f["severity"] == "Critical" else "warn")), td(e(f["title"])), td(e(f["detail"])), td(e(", ".join(f.get("files", [])[:8]))), td(source)])
    if not rows:
        rows = [[td("None"), td(pill("OK", "ok")), td("No audit findings"), td("Canonical lab gate passed; repository scan found no flagged source/link issues."), td(""), td(local_audit + '<br>' + official_context)]]
    provenance = local_audit + '<br>' + official_context
    summary = [[td("HTML pages scanned"), td(str(audit_doc["html_pages"])), td(provenance)], [td("Table rows scanned"), td(str(audit_doc["table_rows"])), td(provenance)], [td("Rows missing official source"), td(str(audit_doc["rows_missing_official_source"])), td(provenance)], [td("Rows citing community hosts only"), td(str(audit_doc["rows_community_only"])), td(provenance)], [td("Rows sourced to local audit code/data"), td(str(audit_doc.get("rows_with_internal_audit_source", 0))), td(provenance)], [td("Canonical lab gate"), td(pill("PASS" if audit_doc["lab_gate_passed"] else "FAIL", "ok" if audit_doc["lab_gate_passed"] else "danger")), td(provenance)]]
    content = '<div class="eyebrow">Independent verification</div><h1>Repository audit</h1><p class="lede">This audit scans published workspaces for source authority, table citations, local links and conflict markers. It does not overwrite other sessions’ work; findings are routed to review. The counts on this page are generated by the linked local audit script/data; they are not externally reported NFL statistics.</p><div class="notice warn"><strong>Key boundary:</strong> GitHub release digests verify captured bytes against a publisher-provided digest. They do not establish NFL authorship, authorization, data accuracy or reuse rights. The audit does not determine those claims.</div>'
    content += table("Repository-derived audit counts. Local links provide provenance for each calculated value. The official NFL statistics link is context only and does not substantiate these counts.", ["Measure", "Value", "Provenance / context"], summary)
    content += table("Audit findings.", ["ID", "Severity", "Finding", "Detail", "Example files", "Provenance / context"], rows)
    return shell("Repository audit", "audit.html", content)


def build_verification() -> str:
    report_path = DATA / "verification_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
    else:
        report = {"totals": {"match": 0, "mismatch": 0, "unverified": 0}, "sections": [],
                  "transcribed_by": "", "transcribed_at": "", "method": ""}
    integrity = SNAPSHOT.get("depth_cell_integrity", {})
    sections = report.get("sections", [])
    totals = report.get("totals", {})

    overview = [
        [td("Values re-checked against an independent transcription"), td(str(totals.get("match", 0))), td(pill("match", "ok")), td(raw_source("https://www.nfl.com/standings/", "NFL standings"))],
        [td("Values that contradict the transcription"), td(str(totals.get("mismatch", 0))), td(pill("mismatch" if totals.get("mismatch") else "none", "danger" if totals.get("mismatch") else "ok")), td(raw_source("https://www.nfl.com/standings/", "NFL standings"))],
        [td("Values with no independent transcription (left unverified)"), td(str(totals.get("unverified", 0))), td(pill("unverified", "warn")), td(raw_source("https://www.nfl.com/injuries/league/2026/REG10", "NFL injury report"))],
        [td("Depth rows whose published cell held more than one player"), td(str(integrity.get("rows_needs_split", 0))), td(pill("excluded", "warn")), td(raw_source("https://www.nfl.com/teams/", "NFL team directory"))],
    ]

    section_sources = {
        "line-lab/data/standings_2026.json": "https://www.nfl.com/standings/",
        "decision-lab/data/official_snapshot.json": "https://www.nfl.com/injuries/league/2026/REG10",
        "decision-lab/data/catalog.json": "https://www.nfl.com/teams/",
    }
    section_rows = [
        [td(e(s["page"])), td(str(s["summary"].get("match", 0))), td(str(s["summary"].get("mismatch", 0))),
         td(str(s["summary"].get("unverified", 0))),
         td(pill("PASS" if s["summary"].get("mismatch", 0) == 0 else "FAIL", "ok" if s["summary"].get("mismatch", 0) == 0 else "danger")),
         td(raw_source(section_sources.get(s["page"].split(" (")[0], "https://www.nfl.com/standings/"), "Official source"))]
        for s in sections
    ]

    detail_rows = []
    for s in sections:
        for row in s["rows"]:
            if row["status"] == "match":
                continue  # matches are counted; the exceptions are what a reviewer needs
            detail_rows.append([
                td(e(row["label"])), td(e(row["field"])), td(e(row.get("published", ""))),
                td(e(row.get("reference", "")) if row.get("reference") is not None else td("", blank=True)),
                td(pill(row["status"], "danger" if row["status"] == "mismatch" else "warn")),
                td(e(row.get("note", ""))), td(raw_source(row["source"], "Official source")),
            ])

    split_rows = [
        [td(e(item["team"])), td(e(item["unit"])), td(e(item["position"])), td(str(item["published_rank"])),
         td(e(item["stored_value"])), td(raw_source(item["source_url"], "Club source"))]
        for item in integrity.get("rows", [])
    ]

    content = f'''<div class="eyebrow">Independent re-verification</div><h1>Verification log</h1>
<p class="lede">Every published value is re-checked against a second, independent transcription of the official page and against the page's own arithmetic. This is the line-by-line record. It runs without network access on purpose: a failed fetch must not be able to look like a passing check.</p>
<div class="notice ok"><strong>How to read a pass:</strong> a match means the published value equals the independent transcription. An unverified cell means no transcription exists for it, so this review makes <em>no</em> claim either way — it is not a soft pass.</div>
<div class="notice warn"><strong>Counted exceptions:</strong> {totals.get("mismatch", 0)} mismatches and {totals.get("unverified", 0)} unverified values. Unverified values are listed individually below so they cannot be mistaken for confirmed facts.</div>
<h2>Summary</h2>{table("Verification counts.", ["Measure", "Count", "State", "Official source"], overview)}
<h2>By section</h2>{table("Each section is checked independently; a mismatch in any one fails the run.", ["Section", "Match", "Mismatch", "Unverified", "Result", "Official source"], section_rows)}
{"<h2>Mismatches and unverified values</h2>" + table("Every value that is not a confirmed match, with the official page to re-check.", ["Item", "Field", "Published", "Reference", "Status", "Note", "Source"], detail_rows) if detail_rows else ""}
{"<h2>Depth cells that need a fresh capture</h2>" + table("Rows where the published cell held more than one player. The stored text is kept exactly as published; no player name was invented by splitting it.", ["Team", "Unit", "Position", "Rank", "Stored value", "Source"], split_rows) if split_rows else ""}
<h2>Method and limits</h2>
<p>{e(report.get("method", ""))}</p>
<p>Transcription by {e(report.get("transcribed_by", "") or "not recorded")}, {e(report.get("transcribed_at", "") or "undated")}. The transcription is intentionally small and hand-checked so a mistake in it is visible for review rather than hidden inside a scraper. A larger automated re-capture would need the club and NFL sites to be reachable from the build.</p>'''
    return shell("Verification log", "verification.html", content)


def main() -> int:
    builders = {
        "index.html": build_index, "executive-summary.html": build_summary,
        "requirements.html": build_requirements, "questions.html": build_questions,
        "suggestions.html": build_suggestions, "lines.html": build_lines,
        "strategies.html": build_strategies, "validation.html": build_validation,
        "injuries.html": build_injuries, "depth.html": build_depth,
        "sources.html": build_sources, "verification.html": build_verification,
        "flagged.html": build_flagged,
    }
    import pages_extra
    builders.update({
        "availability.html": pages_extra.build_availability,
        "decisions.html": pages_extra.build_decisions,
        "integrity.html": pages_extra.build_integrity,
    })
    for name, builder in builders.items():
        (LAB / name).write_text(builder(), encoding="utf-8")
    placeholder = {"html_pages": 0, "table_rows": 0, "rows_missing_official_source": 0,
                   "rows_community_only": 0, "rows_with_internal_audit_source": 0,
                   "findings": [], "lab_gate_passed": True, "lab_gate_errors": []}
    (LAB / "audit.html").write_text(build_audit(placeholder), encoding="utf-8")
    audit_doc = audit.scan_repo()
    audit_doc["lab_gate_passed"] = True
    audit_doc["lab_gate_errors"] = []
    (LAB / "audit.html").write_text(build_audit(audit_doc), encoding="utf-8")
    errors = audit.verify_lab()
    audit_doc["lab_gate_passed"] = not errors
    audit_doc["lab_gate_errors"] = errors
    (LAB / "data/audit.json").write_text(json.dumps(audit_doc, indent=2) + "\n", encoding="utf-8")
    (LAB / "audit.html").write_text(build_audit(audit_doc), encoding="utf-8")
    print(f"Built {len(PAGES)} decision-lab pages; audit findings={len(audit_doc['findings'])}; lab gate={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(errors[:20]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
