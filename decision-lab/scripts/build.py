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
SOURCES = {s["id"]: s for s in CATALOG["sources"]}
PAGES = [
    ("index.html", "Overview"), ("executive-summary.html", "Executive summary"),
    ("requirements.html", "Requirements"), ("questions.html", "Questions & gaps"),
    ("suggestions.html", "Suggestions"), ("lines.html", "Line origination"),
    ("strategies.html", "Signals & leaderboard"), ("validation.html", "Validation gates"),
    ("injuries.html", "Injuries"), ("depth.html", "Depth & backups"),
    ("sources.html", "Sources & capture"), ("flagged.html", "Flagged for review"),
    ("audit.html", "Repository audit"),
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
<div class="metrics">{metric("Official injury rows", str(SNAPSHOT["coverage"]["injury_rows"]), "NFL.com Week 10 capture")}{metric("Club depth rows", str(SNAPSHOT["coverage"]["depth_rows"]), f'{len(SNAPSHOT["coverage"]["depth_teams"])} club labels captured')}{metric("Validated strategies", "0", "No eligible verified ledger")}{metric("Open blocking answers", str(critical), "Blank until evidence exists")}{metric("Review flags", str(len(CATALOG["flags"])), "Source-linked irregularities")}</div>
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
    [td("Community data was labeled official in an existing workspace"), td("Digest matching proves bytes, not NFL authorship or factual accuracy"), td("Use canonical official-only tables; treat research-desk as exploratory"), td(source_link("S12"))],
    [td("Injury status is not depth or workload"), td("Questionable/Out cannot identify a 2nd/3rd/4th-string replacement by itself"), td("Join dated club depth, inactive and participation evidence; blank missing fields"), td(source_link("S03"))],
    [td("Club depth charts can be unofficial or stale"), td("Published rank is guidance, not confirmed snaps"), td("Store authority and timestamp; flag conflicts"), td(source_link("S08"))],
    [td("Luck cannot be removed"), td("Residual variance is not pure luck; hot streaks are not skill"), td("Proper scores, game-cluster uncertainty, ablations, multiplicity and shadow records"), td(source_link("S13"))],
    [td("Parlays require joint evidence"), td("Marginal multiplication fails under dependence"), td("Validate direct joint probability and payout rules before combo signals"), td(source_link("S15"))],
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
    rows = [[td(e(f["id"])), td(pill(f["severity"], "danger" if f["severity"] == "Critical" else "warn")), td(e(f["title"])), td(e(f["finding"])), td(e(f["action"])), td(source_link(f["source"]))] for f in CATALOG["flags"]]
    content = '<div class="eyebrow">Published irregularities</div><h1>Flagged for review</h1><p class="lede">These items do not block site publication, but they block affected decisions. Each flag includes an official review link and a discovery/remediation action.</p>'
    content += table("Flagged review register.", ["ID", "Severity", "Issue", "Finding", "Action", "Source"], rows)
    return shell("Flagged for review", "flagged.html", content)


def build_audit(audit_doc: dict) -> str:
    findings = audit_doc["findings"]
    rows = [[td(e(f["id"])), td(pill(f["severity"], "danger" if f["severity"] == "Critical" else "warn")), td(e(f["title"])), td(e(f["detail"])), td(e(", ".join(f.get("files", [])[:8]))), td(source_link(f["source"]))] for f in findings]
    if not rows:
        rows = [[td("None"), td(pill("OK", "ok")), td("No audit findings"), td("Canonical lab gate passed; repository scan found no flagged source/link issues."), td(""), td(source_link("S16"))]]
    summary = [[td("HTML pages scanned"), td(str(audit_doc["html_pages"])), td(source_link("S16"))], [td("Table rows scanned"), td(str(audit_doc["table_rows"])), td(source_link("S16"))], [td("Rows missing official source"), td(str(audit_doc["rows_missing_official_source"])), td(source_link("S12"))], [td("Community-only rows"), td(str(audit_doc["rows_community_only"])), td(source_link("S12"))], [td("Canonical lab gate"), td(pill("PASS" if audit_doc["lab_gate_passed"] else "FAIL", "ok" if audit_doc["lab_gate_passed"] else "danger")), td(source_link("S16"))]]
    content = '<div class="eyebrow">Independent verification</div><h1>Repository audit</h1><p class="lede">This audit scans published workspaces for source authority, table citations, local links and conflict markers. It does not overwrite other sessions’ work; findings are routed to review.</p><div class="notice warn"><strong>Key boundary:</strong> GitHub release digests verify transport integrity. They do not make community nflverse data official NFL data.</div>'
    content += table("Audit summary.", ["Measure", "Value", "Source"], summary)
    content += table("Audit findings.", ["ID", "Severity", "Finding", "Detail", "Example files", "Source"], rows)
    return shell("Repository audit", "audit.html", content)


def main() -> int:
    builders = {
        "index.html": build_index, "executive-summary.html": build_summary,
        "requirements.html": build_requirements, "questions.html": build_questions,
        "suggestions.html": build_suggestions, "lines.html": build_lines,
        "strategies.html": build_strategies, "validation.html": build_validation,
        "injuries.html": build_injuries, "depth.html": build_depth,
        "sources.html": build_sources, "flagged.html": build_flagged,
    }
    for name, builder in builders.items():
        (LAB / name).write_text(builder(), encoding="utf-8")
    placeholder = {"html_pages": 0, "table_rows": 0, "rows_missing_official_source": 0,
                   "rows_community_only": 0, "findings": [], "lab_gate_passed": True, "lab_gate_errors": []}
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
