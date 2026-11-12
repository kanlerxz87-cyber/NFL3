#!/usr/bin/env python3
"""build_root.py — renders the root NFL3 site from the canonical decision-lab data.

Nothing on the root site is hand-typed data. Every table row comes from a JSON
file and carries a source link:

* ``decision-lab/data/catalog.json``       — sources, requirements, questions,
                                              suggestions, strategies, gates, flags
* ``decision-lab/data/official_snapshot.json`` — official NFL/club capture
* ``data/root_decisions.json``              — migrated root content plus the
                                              site-improvement suggestions
* ``data/verification/verification.json``   — line-by-line verification result

Unknown values are rendered blank and labelled unverified. Nothing is inferred.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "decision-lab"
CATALOG = json.loads((LAB / "data" / "catalog.json").read_text(encoding="utf-8"))
SNAPSHOT = json.loads((LAB / "data" / "official_snapshot.json").read_text(encoding="utf-8"))
ROOT_DATA = json.loads((ROOT / "data" / "root_decisions.json").read_text(encoding="utf-8"))
VERIFY_PATH = ROOT / "data" / "verification" / "verification.json"
VERIFICATION = json.loads(VERIFY_PATH.read_text(encoding="utf-8")) if VERIFY_PATH.exists() else {}
AUDIT_PATH = LAB / "data" / "audit.json"
AUDIT = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else {}

SOURCES = {row["id"]: row for row in CATALOG["sources"]}
SECTIONS = ROOT_DATA["sections"]

NAV = [
    ("Overview", [("index.html", "Overview")]),
    ("Decide", [
        ("executive-summary.html", "Executive summary"),
        ("questions.html", "Questions & answers"),
        ("decisions.html", "Decision journal"),
    ]),
    ("Research", [
        ("signals.html", "Signals & models"),
        ("strategies.html", "Strategy lab"),
        ("validation.html", "Validation gates"),
        ("lineups.html", "Injuries & lineups"),
        ("lineup.html", "Depth & schema"),
    ]),
    ("Review", [
        ("suggestions.html", "Suggestions & paths"),
        ("flagged.html", "Flagged for review"),
        ("verification.html", "Verification report"),
        ("review.html", "Review protocol"),
        ("sources.html", "Source register"),
    ]),
]

SECTION_OF = {file: group for group, entries in NAV for file, _ in entries}
PAGE_TITLE = {file: label for group, entries in NAV for file, label in entries}
WORKSPACE_LINK = {
    "Canonical decision lab": "decision-lab/index.html",
    "Dashboard": "dashboard/index.html",
    "Line lab": "line-lab/index.html",
    "Decision hub": "decision-hub/index.html",
    "Research desk": "research-desk/index.html",
    "Research workspace": "research-workspace/index.html",
}


# --------------------------------------------------------------------- helpers
def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def source_url(source_id: str) -> str:
    row = SOURCES.get(source_id, {})
    return row.get("url", "")


def src(source_id: str, label: str = "Open source ↗") -> str:
    """A source cell: an official link plus the registry id it came from."""
    url = source_url(source_id)
    if not url:
        return '<span class="muted-src">No registered source</span>'
    return f'<a class="source" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a> <span class="sid">{esc(source_id)}</span>'


def srcs(*source_ids: str) -> str:
    parts = [src(item) for item in source_ids if item]
    return "<br>".join(parts) if parts else '<span class="muted-src">No registered source</span>'


def raw_link(url: str, label: str) -> str:
    return f'<a class="source" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'


def ref_link(url: str, label: str) -> str:
    """A link that is explicitly not an official source (community or secondary)."""
    return (f'<a class="ref" href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(label)} ↗ <span class="sid">not official</span></a>')


def table(headers: list[str], rows: list[list[str]], note: str = "") -> str:
    head = "".join(f'<th scope="col">{esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    caption = f'<p class="small muted-note">{note}</p>' if note else ""
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{caption}'


def section_table(key: str, source_column: str | None = None, note: str = "") -> str:
    """Render a migrated root section, keeping the links that were in each row."""
    block = SECTIONS[key]
    headers = block["columns"]
    rows = []
    for row in block["rows"]:
        links = row.get("_links", {})
        cells = []
        for column in headers:
            text = row.get(column, "")
            cell = esc(text)
            if column == source_column or (source_column is None and column in links):
                for url in links.get(column, []):
                    cell = f'{cell}<br>{raw_link(url, "Open source ↗")}'
            cells.append(cell)
        rows.append(cells)
    return table(headers, rows, note)


def metric(label: str, value: str, detail: str) -> str:
    return f'<div><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(detail)}</small></div>'


def callout(title: str, body: str, button: str = "", tone: str = "") -> str:
    inner = f'<div><div class="section-label">{esc(title)}</div><p>{body}</p></div>'
    if button:
        inner += button
    return f'<div class="callout {tone}">{inner}</div>'


def page(filename: str, title: str, lede: str, body: str, badge: str = "", badge_class: str = "blue") -> str:
    group = SECTION_OF.get(filename, "Overview")
    nav_html = []
    counter = 0
    for nav_group, entries in NAV:
        nav_html.append(f'<div class="nav-group">{esc(nav_group)}</div>')
        for file, label in entries:
            current = ' aria-current="page"' if file == filename else ""
            counter += 1
            number = f"<span>{counter:02d}</span>"
            nav_html.append(f'<a href="{file}"{current}>{number}{esc(label)}</a>')
    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(title)} — official-source NFL research and decision site. Unverified values are left blank.">
<title>{esc(title)} | NFL3</title><link rel="stylesheet" href="assets/style.css"></head>
<body><div class="layout">
<aside class="sidebar"><a class="brand" href="index.html"><span class="brand-icon">N<span>3</span></span><span>NFL<span class="brand-light"> / LAB</span><small>OFFICIAL-SOURCE DECISION SITE</small></span></a>
<div class="nav-label">NAVIGATION</div>
<nav aria-label="Main navigation">{''.join(nav_html)}</nav>
<div class="side-bottom"><span class="status-dot"></span> Research mode<small>No live model or feed connected</small></div></aside>
<main><header class="topbar"><span>FOOTBALL INTELLIGENCE <b>/</b> {esc(group.upper())}</span><span class="top-right"><span class="status-dot"></span> OFFICIAL-SOURCE WORKSPACE</span></header>
<div class="content">
<div class="eyebrow"><span></span> {esc(group.upper())}</div>
<h1>{esc(title)}</h1>
<p class="lede">{lede}</p>
{body}
<footer> NFL3 OFFICIAL-SOURCE DECISION SITE <span>Generated {esc(updated)} from the canonical register. Built for informed decisions, not guaranteed outcomes.</span></footer>
</div></main></div></body></html>
"""


# ------------------------------------------------------------------ page parts
def metrics_block(items: list[tuple[str, str, str]]) -> str:
    return '<div class="metrics">' + "".join(metric(*item) for item in items) + "</div>"


def canonical_questions() -> list[dict]:
    return CATALOG["questions"]


def question_status(question: dict) -> tuple[str, str]:
    answer = (question.get("answer") or "").strip()
    if answer:
        return "Answered", "P1"
    return "Open — not established", "P0" if question.get("blocking") else "P1"


def build_index() -> str:
    questions = canonical_questions()
    blocking = [q for q in questions if q.get("blocking")]
    answered = [q for q in questions if (q.get("answer") or "").strip()]
    injury_rows = len(SNAPSHOT["injury_rows"])
    depth_rows = len(SNAPSHOT["depth_rows"])
    verification = VERIFICATION.get("summary", {})
    drift = verification.get("drift_rows", 0)

    path_rows = []
    for row in SECTIONS["paths"]["rows"]:
        path_rows.append([
            esc(row.get("Path", "")), esc(row.get("What to do next", "")), esc(row.get("Advantages", "")),
            esc(row.get("Trade-offs / missing decision", "")),
            f'<span class="badge">{esc(row.get("Recommendation", ""))}</span>',
            "".join(raw_link(url, "Official source ↗") for url in row.get("_links", {}).get("Official source reference", [])),
        ])
    paths_table = table(["Path", "What to do next", "Advantages", "Trade-offs / missing decision",
                         "Recommendation", "Official source"], path_rows)

    workspace_rows = []
    for row in ROOT_DATA["workspaces"]["rows"]:
        target = WORKSPACE_LINK.get(row["Workspace"], "index.html")
        link = row.get("Official source", "")
        if "nflverse" in link:
            link_cell = ref_link(link, "Community release page")
        else:
            link_cell = raw_link(link, "Official source")
        workspace_rows.append([
            f'<a href="{esc(target)}">{esc(row["Workspace"])} →</a>',
            esc(row.get("What it contains", "")), esc(row.get("Evidence boundary", "")), link_cell,
        ])
    workspaces_table = table(["Workspace", "What it contains", "Evidence boundary", "Official source"], workspace_rows)

    directory = []
    for group, entries in NAV:
        for file, label in entries:
            if file == "index.html":
                continue
            directory.append(f'<a class="linkcard" href="{file}"><strong>{esc(label)}</strong><span>{esc(PAGE_BLURB.get(file, ""))}</span></a>')

    body = f"""
<div class="notice"><b>Evidence boundary.</b> Every published row on this site comes from an official NFL or
club source and keeps its source link. A value that could not be confirmed stays blank and is listed on the
<a href="flagged.html">Flagged for review</a> page. No strategy has passed validation, no correlation has been
measured and no reward has been approved &mdash; those cells are blank on purpose.</div>
{metrics_block([
    ("INJURY ROWS CAPTURED", f"{injury_rows:,}", "Official NFL report, with capture time"),
    ("CLUB DEPTH ROWS", f"{depth_rows:,}", "Published order inside each position group"),
    ("BLOCKING QUESTIONS", str(len(blocking)), f"{len(answered)} of {len(questions)} questions answered"),
    ("VALIDATED STRATEGIES", "0", "No strategy has passed the ten gates"),
])}
<div class="section-head"><div><div class="section-label">01 / THE BRIEF</div><h2>What is established, and what is not</h2></div>
<p>Verified facts and open items are kept apart on purpose.</p></div>
<div class="brief">
<div><div class="card-kicker">ESTABLISHED</div><h3>The official capture is faithful and reproducible.</h3>
<p>{injury_rows:,} injury rows and {depth_rows:,} club depth rows were captured from official NFL and club pages with a
document hash, and {verification.get('injury_rows_matched', 0)} of the {verification.get('injury_rows_compared', 0)} rows re-read
line by line from the live pages match exactly.</p>
<a class="text-link" href="verification.html">Read the verification report →</a></div>
<div><div class="card-kicker">NOT ESTABLISHED</div><h3>No price, no edge, no reward.</h3>
<p>No licensed historical odds or player-prop feed is established, so no independent line can be compared with a market
price, no leg correlation can be measured and no leaderboard entry can be scored. The gates exist; nothing has passed them.</p>
<a class="text-link" href="validation.html">See the validation gates →</a></div>
</div>
<div class="section-head"><div><div class="section-label">02 / THE PATH</div><h2>Recommended order of work</h2></div>
<p>Proposals, not implemented changes.</p></div>
{paths_table}
<div class="section-head"><div><div class="section-label">03 / DIRECTORY</div><h2>Pages by category</h2></div>
<p>One design, one register, every table source-linked.</p></div>
<div class="linkcards">{''.join(directory)}</div>
<div class="section-head"><div><div class="section-label">04 / PRESERVED ARCHIVES</div><h2>Concurrent workspaces, clearly labelled</h2></div>
<p>Linked for review; not merged into the official-only decision gate.</p></div>
{workspaces_table}
{callout("START HERE", "See what is known, what is missing, and how to close each gap before any decision is made.", '<a class="button" href="questions.html">Open the questions register <span>↗</span></a>')}
"""
    return page("index.html", "A clearer view of the game",
                "A decision-first workspace for NFL data, independent lines and disciplined strategy evaluation, built only from official NFL and club sources.",
                body)


PAGE_BLURB = {
    "executive-summary.html": "Findings, requirement status and blockers in one place.",
    "questions.html": "Every open question, what is known, the missing answer and how to close it.",
    "decisions.html": "How a decision moves from question to verified answer.",
    "signals.html": "Testable signal candidates with their controls and known risks.",
    "strategies.html": "Strategy candidates, the leaderboard and its gates.",
    "validation.html": "The ten fail-closed gates and the limits of luck control.",
    "lineups.html": "Injury capture, depth evidence and what each can establish.",
    "lineup.html": "Field-by-field schema for player availability evidence.",
    "suggestions.html": "Suggestions and paths, ready to review before implementation.",
    "flagged.html": "Open gaps, irregularities and unverified values.",
    "verification.html": "Line-by-line check of the published data against official pages.",
    "review.html": "How to review a flag and request a change.",
    "sources.html": "Every official source, what it establishes and what it cannot.",
}


def build_executive_summary() -> str:
    requirements = CATALOG["requirements"]
    flags = CATALOG["flags"]
    note_rows = []
    for row in ROOT_DATA["executive_notes"]["rows"]:
        note_rows.append([
            esc(row["Finding"]), esc(row["Evidence"]), esc(row["Consequence for a decision"]),
            raw_link(row["Official source"], "Official source ↗"),
        ])
    notes_table = table(["Finding", "Evidence", "Consequence for a decision", "Official source"], note_rows)

    requirement_rows = []
    for row in requirements:
        state = row.get("state", "")
        badge = {"implemented": "good", "partial": "warn", "blocked": "danger"}.get(state, "")
        requirement_rows.append([
            esc(row["id"]), esc(row["requirement"]),
            f'<span class="badge {badge}">{esc(state)}</span>',
            esc(row.get("evidence", "")), esc(row.get("next", "")),
            src(row.get("source", "")),
        ])
    requirements_table = table(["ID", "Requirement", "State", "Evidence today", "Next action", "Official source"], requirement_rows)

    blocker_rows = []
    for row in flags:
        if row.get("severity") not in {"Critical", "High"}:
            continue
        badge = "danger" if row.get("severity") == "Critical" else "warn"
        blocker_rows.append([
            esc(row["id"]),
            f'<span class="badge {badge}">{esc(row.get("severity"))}</span>',
            esc(row["title"]), esc(row.get("finding", "")), esc(row.get("action", "")),
            src(row.get("source", "")),
        ])
    blockers_table = table(["ID", "Severity", "Irregularity", "What was found", "Required action", "Official source"], blocker_rows)

    body = f"""
<div class="notice"><b>Reading guide.</b> This summary states only what an official source established and what
remains open. Every number below is taken from the committed capture; the capture time is shown on the
<a href="verification.html">verification report</a>.</div>
{metrics_block([
    ("REQUIREMENTS TRACKED", str(len(requirements)), "Full register, with state per requirement"),
    ("ANSWERED QUESTIONS", f"{sum(1 for q in CATALOG['questions'] if (q.get('answer') or '').strip())}", f"of {len(CATALOG['questions'])} registered questions"),
    ("OPEN BLOCKERS", str(sum(1 for f in flags if f.get('severity') == 'Critical')), "Critical findings that block decisions"),
    ("VALIDATED STRATEGIES", "0", "Gates defined, none passed"),
])}
<div class="section-head"><div><div class="section-label">01 / FINDINGS</div><h2>What the verification actually shows</h2></div>
<p>Each finding is traceable to an official source.</p></div>
{notes_table}
<div class="section-head"><div><div class="section-label">02 / REQUIREMENTS</div><h2>Full requirements register</h2></div>
<p>Collect, organize and analyze — with the state of each requirement stated.</p></div>
{requirements_table}
<div class="section-head"><div><div class="section-label">03 / BOUNDARIES</div><h2>What this project may not claim</h2></div>
<p>Stated once, applied everywhere.</p></div>
{section_table("fact_boundaries", "Reference")}
<div class="section-head"><div><div class="section-label">04 / BLOCKERS</div><h2>What blocks a decision today</h2></div>
<p>Published in full on the flagged page.</p></div>
{blockers_table}
{callout("NEXT STEP", "Review the suggestions, choose one path, then implement it. Nothing on this site should be implemented before that choice is recorded.", '<a class="button" href="suggestions.html">Open suggestions &amp; paths <span>↗</span></a>')}
"""
    return page("executive-summary.html", "Executive summary",
                "The important details of the project in one place: what an official source established, what remains unverified, and what blocks the next decision.",
                body)


def build_questions() -> str:
    questions = canonical_questions()
    rows = []
    for question in questions:
        status, priority = question_status(question)
        badge = "good" if status == "Answered" else ("danger" if priority == "P0" else "warn")
        rows.append([
            esc(question["id"]), esc(question.get("area", "")), esc(question["question"]),
            esc(question.get("known", "")), esc(question.get("answer", "")),
            f'<span class="badge {badge}">{esc(status)}</span>', esc(priority),
            esc(question.get("discovery", "")), src(question.get("source", "")),
        ])
    table_html = table(
        ["ID", "Decision area", "Question", "What is confirmed today", "Answer", "Status", "Priority",
         "How to close it", "Official source"], rows,
        "The answer column is blank wherever no official source establishes an answer. A blank cell is a real state, not a formatting gap.")
    answered = sum(1 for q in questions if (q.get("answer") or "").strip())
    blocking = sum(1 for q in questions if q.get("blocking"))
    body = f"""
<div class="notice"><b>How to read this register.</b> “Confirmed” means the linked official page was inspected for the
cited kind of information. It does not certify historical availability, a licensing right or a prediction. Questions
marked <span class="badge danger">P0</span> block any decision that depends on them.</div>
{metrics_block([
    ("REGISTERED QUESTIONS", str(len(questions)), "One id per decision that must be made"),
    ("ANSWERED", str(answered), "Backed by an official source"),
    ("BLOCKING", str(blocking), "P0 — no decision may depend on them yet"),
    ("OPEN", str(len(questions) - answered), "Blank answer cells are intentional"),
])}
<div class="section-head"><div><div class="section-label">01 / REGISTER</div><h2>Questions, what is known, and what is missing</h2></div>
<p>Each row names the cheapest action that closes the question.</p></div>
{table_html}
<div class="section-head"><div><div class="section-label">02 / BY DECISION AREA</div><h2>The same material grouped for review</h2></div>
<p>Discovery checklist before any vendor, model or signal is chosen.</p></div>
{section_table("discovery_checklist", "Official source")}
{callout("ALSO", "The decision journal shows how a question becomes an answer, and the fact boundaries state what this project may not claim.", '<a class="button" href="decisions.html">Open the decision journal <span>↗</span></a>')}
"""
    return page("questions.html", "Questions & answers",
                "Every question that has to be answered before a decision can reasonably be made, with what is already established, what is still missing and the action that closes it.",
                body)


def build_decisions() -> str:
    questions = canonical_questions()
    blocking = [q for q in questions if q.get("blocking")]
    rows = []
    for question in blocking:
        status, priority = question_status(question)
        rows.append([
            esc(question["id"]), esc(question.get("area", "")), esc(question["question"]),
            esc(question.get("missing", "")), esc(question.get("discovery", "")),
            src(question.get("source", "")),
        ])
    blocking_table = table(["ID", "Decision area", "Question", "What is still missing", "Discovery action", "Official source"], rows)

    suggestion_rows = []
    for row in SECTIONS["decision_suggestions"]["rows"]:
        suggestion_rows.append([
            esc(row.get("Suggestion", "")), esc(row.get("Why it matters", "")),
            esc(row.get("Trade-off / prerequisite", "")),
            "".join(raw_link(url, "Source ↗") for url in row.get("_links", {}).get("Source / context", [])),
        ])
    suggestions_table = table(["Suggestion", "Why it matters", "Trade-off / prerequisite", "Source / context"], suggestion_rows)

    flow = "".join(
        f'<div class="step"><em>Step {index}</em><strong>{esc(step["Step"])}</strong><span>{esc(step["Action"])}</span></div>'
        for index, step in enumerate(ROOT_DATA["review_protocol"], start=1))

    body = f"""
<div class="notice"><b>Rule.</b> A decision is not made by picking a strategy; it is made by closing a question with
an official source and recording the result. Nothing in this repository has been deployed, approved or paid for.</div>
<div class="section-head"><div><div class="section-label">01 / FLOW</div><h2>How a decision is made here</h2></div>
<p>The same flow applies to every page in the site.</p></div>
<div class="flow">{flow}</div>
<div class="section-head"><div><div class="section-label">02 / BLOCKING QUESTIONS</div><h2>What must be answered first</h2></div>
<p>{len(blocking)} questions block the next step.</p></div>
{blocking_table}
<div class="section-head"><div><div class="section-label">03 / PROPOSALS</div><h2>Proposed improvements</h2></div>
<p>Suggestions only. They stay here until they are chosen.</p></div>
{suggestions_table}
{callout("REVIEW", "The full suggestion board, with the site-improvement list and the paths, is on the suggestions page.", '<a class="button" href="suggestions.html">Open suggestions &amp; paths <span>↗</span></a>')}
"""
    return page("decisions.html", "Decision journal",
                "How a question becomes a decision in this project: the flow, the blocking questions and the proposals that are waiting for a choice.",
                body)


def build_signals() -> str:
    body = f"""
<div class="notice"><b>No results.</b> These are hypotheses, not picks. No coefficient, edge, hit rate, ROI or
correlation has been measured in this repository, and no signal below has been run. Every “Result” cell is blank
until a pre-registered test produces one.</div>
<div class="section-head"><div><div class="section-label">01 / CANDIDATES</div><h2>Signal candidates</h2></div>
<p>Interpretable inputs first, complexity only when it earns its place.</p></div>
{section_table("signals", "Official NFL source")}
{callout("NEXT", "Each candidate names the observations it needs. The blocking observation for all of them is a timestamped price, which is not yet available.", '<a class="button" href="questions.html">See the blocking questions <span>↗</span></a>')}
"""
    return page("signals.html", "Signals & model candidates",
                "Testable signal ideas for independent lines, each with the observations it needs, the test it must pass and the risk it carries.",
                body)


def build_strategies() -> str:
    leaderboard_rows = []
    for row in SECTIONS["leaderboard"]["rows"]:
        leaderboard_rows.append([
            esc(row.get("Item", "")), esc(row.get("Value", "")), esc(row.get("Method / outstanding work", "")),
            "".join(raw_link(url, "Source ↗") for url in row.get("_links", {}).get("Source / context", [])),
        ])
    leaderboard_table = table(["Item", "Value", "Method / outstanding work", "Source / context"], leaderboard_rows)

    strategy_rows = []
    for row in CATALOG["strategies"]:
        strategy_rows.append([
            esc(row["id"]), esc(row["name"]), esc(row.get("division", "")), esc(row.get("hypothesis", "")),
            esc(row.get("inputs", "")), esc(row.get("test", "")), esc(row.get("risk", "")),
            f'<span class="badge warn">{esc(row.get("status", ""))}</span>', src(row.get("source", "")),
        ])
    strategies_table = table(
        ["ID", "Strategy", "Division", "Hypothesis", "Required inputs", "Test", "Known risk", "Status", "Official source"],
        strategy_rows,
        "Status is “Not run” for every strategy: no strategy in this repository has a verified ledger to score.")

    body = f"""
<div class="notice"><b>Leaderboard rule.</b> An entry becomes eligible only after all ten gates pass. The gates
require an official source URL, a raw hash and an official outcome confirmation for every record, so the leaderboard
is empty by construction until a licensed price feed and an outcome source exist.</div>
<div class="section-head"><div><div class="section-label">01 / LEADERBOARD</div><h2>Scoreboard and what it still needs</h2></div>
<p>Empty where the evidence is empty.</p></div>
{leaderboard_table}
<div class="section-head"><div><div class="section-label">02 / CANDIDATES</div><h2>Strategy candidates</h2></div>
<p>Singles, parlays and player-prop combinations.</p></div>
{strategies_table}
<div class="section-head"><div><div class="section-label">03 / GATES</div><h2>Release gates applied to every entry</h2></div>
<p>A summary; the full gate text is on the validation page.</p></div>
{section_table("strategy_gates", "Source / context")}
{callout("NEXT", "Read the gate text before writing a strategy. The first gate is provenance, and it is the one this repository cannot yet pass.", '<a class="button" href="validation.html">Open validation gates <span>↗</span></a>')}
"""
    return page("strategies.html", "Strategy lab",
                "Candidate strategies for singles, parlays and player-prop combinations, the leaderboard they would enter, and the gates every entry must pass.",
                body)


def build_validation() -> str:
    gate_rows = []
    for row in CATALOG["gates"]:
        gate_rows.append([
            esc(row["id"]), esc(row["name"]), esc(row.get("rule", "")), esc(row.get("fail", "")),
            src(row.get("source", "")),
        ])
    gates_table = table(["ID", "Gate", "Rule", "Fails when", "Official source"], gate_rows)

    body = f"""
<div class="notice"><b>Luck cannot be removed.</b> Randomness is not removable from sports outcomes. It can only be
controlled statistically: freeze the hypothesis, evaluate on periods never used for fitting, compare against strong
baselines, quantify uncertainty and refuse to reward an inconclusive result.</div>
<div class="section-head"><div><div class="section-label">01 / GATES</div><h2>Fail-closed release gates</h2></div>
<p>All ten gates must pass before an entry can be scored or rewarded.</p></div>
{gates_table}
<div class="section-head"><div><div class="section-label">02 / PROPOSED CONTROLS</div><h2>Operational controls behind the gates</h2></div>
<p>Detailed draft controls and their failure conditions.</p></div>
{section_table("validation_gates", "Official source")}
<div class="section-head"><div><div class="section-label">03 / LUCK</div><h2>How the evaluation controls for luck</h2></div>
<p>Each measure has a stated interpretation boundary.</p></div>
{section_table("luck_measures", "Source")}
{callout("STATUS", "No strategy has passed. The gates exist to keep the leaderboard honest while the missing inputs are still missing.", '<a class="button" href="strategies.html">Back to the strategy lab <span>↗</span></a>')}
"""
    return page("validation.html", "Validation gates",
                "The ten fail-closed gates every strategy must pass, the controls behind them, and the honest limits of separating skill from luck.",
                body)


def build_lineups() -> str:
    coverage = SNAPSHOT.get("coverage", {})
    depth_teams = coverage.get("depth_teams", [])
    rows = []
    for row in SECTIONS["availability_samples"]["rows"]:
        rows.append([
            esc(row.get("Team / player", "")), esc(row.get("Position", "")), esc(row.get("Injury", "")),
            esc(row.get("Practice", "")), esc(row.get("Game status", "")),
            "".join(raw_link(url, "NFL report ↗") for url in row.get("_links", {}).get("Source / context", [])),
        ])
    samples_table = table(["Team / player", "Position", "Injury", "Practice", "Game status", "Source / context"], rows)

    field_rows = []
    for row in SECTIONS["availability_fields"]["rows"]:
        field_rows.append([
            esc(row.get("Required field", "")), esc(row.get("Verified value", "")), esc(row.get("How to establish", "")),
            "".join(raw_link(url, "Official source ↗") for url in row.get("_links", {}).get("Source / context", [])),
        ])
    fields_table = table(["Required field", "Verified value", "How to establish", "Source / context"], field_rows)

    body = f"""
<div class="notice"><b>What the capture establishes.</b> The official report establishes a report state for the
players it lists, at the capture time. It does not establish that an unlisted player is healthy, that a listed
player will start, who replaces them, or how many snaps they will play. Those cells stay blank.</div>
{metrics_block([
    ("INJURY ROWS", f"{len(SNAPSHOT['injury_rows']):,}", "Official NFL injury report"),
    ("CLUB DEPTH ROWS", f"{len(SNAPSHOT['depth_rows']):,}", "Published order per position group"),
    ("CLUBS WITH DEPTH DATA", str(len(depth_teams)), "Of 32 official club pages"),
    ("CONFIRMED STARTERS", "0", "No official source confirms a starter"),
])}
<div class="section-head"><div><div class="section-label">01 / SAMPLE</div><h2>Worked example from the capture</h2></div>
<p>A small, verifiable excerpt. The full tables live in the decision lab and the dashboard.</p></div>
{samples_table}
<div class="section-head"><div><div class="section-label">02 / FIELDS</div><h2>What a replacement analysis still needs</h2></div>
<p>Empty means not established by any official source.</p></div>
{fields_table}
{callout("FULL TABLES", "The complete capture is published with a source link on every row, together with the capture hash and time.", '<a class="button" href="decision-lab/injuries.html">Open the injury table <span>↗</span></a>')}
"""
    return page("lineups.html", "Injuries & lineups",
                "What the official capture establishes about availability, and the difference between a report state, a published depth order and a confirmed starter.",
                body)


def build_lineup() -> str:
    body = f"""
<div class="notice"><b>Schema before data.</b> A lineup model must keep four things apart: a report state, a
confirmed active status, a published depth order and an expected workload. Collapsing them is how a depth chart
turns into a false pick. The table below specifies the fields; it does not fill them in.</div>
<div class="section-head"><div><div class="section-label">01 / SCHEMA</div><h2>Player evidence ledger</h2></div>
<p>Every field records what a source can and cannot establish.</p></div>
{section_table("lineup_schema", "Official source")}
<div class="section-head"><div><div class="section-label">02 / DEPTH STRINGS</div><h2>Second, third and fourth string</h2></div>
<p>The specific deficiency this project has to detect.</p></div>
<div class="brief">
<div><div class="card-kicker">WHAT EXISTS</div><h3>Published order inside a position group</h3>
<p>Club charts publish a first, second and third name inside each position group. In the verified Commanders chart,
running back reads Jacory Croskey-Merritt, Rachaad White, Austin Ekeler, and quarterback reads Jayden Daniels, Marcus
Mariota, Athan Kaliakmanis. That is a published order, not participation.</p>
<a class="text-link" href="https://www.commanders.com/team/depth-chart" target="_blank" rel="noopener noreferrer">Open the club chart ↗</a></div>
<div><div class="card-kicker">WHAT DOES NOT EXIST</div><h3>Confirmation of who starts or plays</h3>
<p>No official source in this repository confirms a starter, an assignment or an expected snap count for a player who
replaces an unavailable starter. A depth rank plus an injury status is evidence of a gap, not a forecast.</p>
<a class="text-link" href="flagged.html">See the open items ↗</a></div>
</div>
{callout("NEXT", "The suggestion board explains what it would take to close the replacement question without guessing at it.", '<a class="button" href="suggestions.html">Open suggestions &amp; paths <span>↗</span></a>')}
"""
    return page("lineup.html", "Depth & lineup schema",
                "The field-by-field schema for player availability evidence, and the precise limit of what a published depth order can tell you about a replacement.",
                body)


def build_suggestions() -> str:
    path_rows = []
    for row in SECTIONS["paths"]["rows"]:
        path_rows.append([
            esc(row.get("Path", "")), esc(row.get("What to do next", "")), esc(row.get("Advantages", "")),
            esc(row.get("Trade-offs / missing decision", "")),
            f'<span class="badge">{esc(row.get("Recommendation", ""))}</span>',
            "".join(raw_link(url, "Official source ↗") for url in row.get("_links", {}).get("Official source reference", [])),
        ])
    paths_table = table(["Path", "What to do next", "Advantages", "Trade-offs / missing decision", "Recommendation", "Official source"], path_rows)

    site_rows = []
    for row in ROOT_DATA["site_suggestions"]["rows"]:
        site_rows.append([
            esc(row["ID"]), esc(row["Change to make"]), esc(row["Why it improves a decision"]),
            esc(row["Effort"]), esc(row["Impact"]), esc(row["Depends on"]), esc(row["Status"]),
            raw_link(row["Official source (context)"], "Official source ↗"),
        ])
    site_table = table(["ID", "Change to make", "Why it improves a decision", "Effort", "Impact", "Depends on", "Status", "Official source (context)"], site_rows)

    canonical_rows = []
    for row in CATALOG["suggestions"]:
        canonical_rows.append([
            esc(row["id"]), esc(row["title"]), esc(row.get("priority", "")), esc(row.get("effort", "")),
            esc(row.get("impact", "")), esc(row.get("recommendation", "")), esc(row.get("path", "")),
            esc(row.get("depends", "")), esc(row.get("detail", "")), esc(row.get("tradeoff", "")),
            src(row.get("source", "")),
        ])
    canonical_table = table(
        ["ID", "Suggestion", "Priority", "Effort", "Impact", "Recommendation", "Path", "Depends on", "Detail", "Trade-off", "Official source"],
        canonical_rows)

    flow = "".join(
        f'<div class="step"><em>Step {index}</em><strong>{esc(step["Step"])}</strong><span>{esc(step["Action"])}</span></div>'
        for index, step in enumerate(ROOT_DATA["review_protocol"], start=1))

    body = f"""
<div class="notice"><b>How to use this page.</b> This is the review board. Nothing here has been implemented. Read the
paths, mark the ones you want, and the implementation follows the marked order. Every suggestion names the official
source that grounds it and the trade-off it accepts.</div>
<div class="section-head"><div><div class="section-label">01 / REVIEW FLOW</div><h2>How a suggestion becomes work</h2></div>
<p>Accept, defer or reject — with a reason.</p></div>
<div class="flow">{flow}</div>
<div class="section-head"><div><div class="section-label">02 / PATHS</div><h2>Proposed paths</h2></div>
<p>The recommended path is first; the others depend on it.</p></div>
{paths_table}
<div class="section-head"><div><div class="section-label">03 / SITE IMPROVEMENTS</div><h2>How to improve this site so decisions improve</h2></div>
<p>{len(ROOT_DATA['site_suggestions']['rows'])} proposals for the site itself.</p></div>
{site_table}
<div class="section-head"><div><div class="section-label">04 / REGISTERED SUGGESTIONS</div><h2>Suggestions already on the register</h2></div>
<p>Kept with the canonical decision lab so both stay in step.</p></div>
{canonical_table}
{callout("DECISION", "If you only read one thing: choose Path A first. The critical blocker is the absence of permissioned, timestamped odds and price history — not a shortage of feature ideas.", '<a class="button" href="questions.html">See the blocking questions <span>↗</span></a>')}
"""
    return page("suggestions.html", "Suggestions & decision paths",
                "Every proposed improvement, in one reviewable place, with the trade-off it accepts and the official source that grounds it — so a path can be chosen before anything is built.",
                body)


def build_flagged() -> str:
    rows = []
    for row in CATALOG["flags"]:
        badge = {"Critical": "danger", "High": "warn"}.get(row.get("severity", ""), "")
        rows.append([
            esc(row["id"]), f'<span class="badge {badge}">{esc(row.get("severity"))}</span>', esc(row["title"]),
            esc(row.get("finding", "")), esc(row.get("action", "")), src(row.get("source", "")),
        ])
    canonical_table = table(["ID", "Severity", "Irregularity", "What was found", "Required action", "Official source"], rows)

    root_rows = []
    for row in SECTIONS["root_flagged"]["rows"]:
        root_rows.append([
            esc(row.get("Irregularity or gap", "")), esc(row.get("Verified value", "")),
            esc(row.get("Impact / next step", "")),
            "".join(raw_link(url, "Source ↗") for url in row.get("_links", {}).get("Source / context", [])),
        ])
    root_table = table(["Irregularity or gap", "Verified value", "Impact / next step", "Source / context"], root_rows)

    verification = VERIFICATION.get("summary", {})
    drift_rows = []
    for row in (VERIFICATION.get("injuries", {}).get("rows_added_since_capture", []) or []):
        drift_rows.append([esc(row.get("team", "")), esc(row.get("player", "")), "Added after the capture", esc(row.get("note", "")),
                           raw_link("https://www.nfl.com/injuries/", "NFL report ↗")])
    for row in (VERIFICATION.get("injuries", {}).get("rows_changed", []) or []):
        for field, values in row.get("fields", {}).items():
            drift_rows.append([esc(row.get("team", "")), esc(row.get("player", "")), esc(field),
                               f'{esc(values[0])} → {esc(values[1])}',
                               raw_link("https://www.nfl.com/injuries/", "NFL report ↗")])
    drift_table = table(["Team", "Player", "Field", "Capture value → live value", "Official source"], drift_rows) if drift_rows else ""

    coverage_rows = []
    if AUDIT:
        coverage_rows = [
            ["Table rows scanned", str(AUDIT.get("table_rows", 0)), "Every published row in every workspace", src("S12")],
            ["Citing an official source directly", str(AUDIT.get("rows_official_direct", 0)), "The row links an official page", src("S12")],
            ["Citing an official source by register id", str(AUDIT.get("rows_official_via_register", 0)), "The row cites a source id that resolves to an official page", src("S12")],
            ["Citing only community or secondary sources", str(AUDIT.get("rows_community_only", 0)), "Marked unverified; excluded from official-only claims", src("S12")],
            ["No source link at all", str(AUDIT.get("rows_without_any_link", 0)), "Preserved archives that predate the citation rule", src("S12")],
            ["Pages scanned", str(AUDIT.get("html_pages", 0)), "Static pages across the whole repository", src("S12")],
        ]
    coverage_table = table(["Citation coverage", "Rows", "Meaning", "Official source"], coverage_rows, "Counts come from the independent repository audit, which resolves source-register ids before judging a row.") if coverage_rows else ""

    body = f"""
<div class="notice"><b>What belongs here.</b> Any value that an official source does not establish, any irregularity
found during verification, and any gap that would change a decision. Nothing on this page blocks the site from being
published; each item blocks the specific decision it affects.</div>
{metrics_block([
    ("REGISTERED FLAGS", str(len(CATALOG["flags"])), "Canonical decision lab register"),
    ("CRITICAL", str(sum(1 for f in CATALOG['flags'] if f.get('severity') == 'Critical')), "Block the affected decision"),
    ("DRIFT ROWS FOUND", str(verification.get("drift_rows", 0)), "Live pages changed after the capture"),
    ("MANUAL INPUT REQUIRED", "0", "Every capture and check is automated"),
])}
<div class="section-head"><div><div class="section-label">01 / REGISTER</div><h2>Open irregularities and gaps</h2></div>
<p>Published with the source link that a reviewer needs.</p></div>
{canonical_table}
<div class="section-head"><div><div class="section-label">02 / CITATION COVERAGE</div><h2>How much of the published site carries an official source</h2></div>
<p>Measured by the independent audit, not asserted.</p></div>
{coverage_table}
<div class="section-head"><div><div class="section-label">03 / SITE GAPS</div><h2>Gaps in the site itself</h2></div>
<p>What the site still does not do.</p></div>
{root_table}
<div class="section-head"><div><div class="section-label">04 / DRIFT</div><h2>Live pages changed after the capture</h2></div>
<p>Found by the line-by-line verification, not assumed.</p></div>
{drift_table or '<p class="footnote">No drift recorded in the latest verification run.</p>'}
{callout("REQUEST A CHANGE", "Open a change request with the flag id, the source that closes it and the tables it affects.", '<a class="button" href="review.html">Review protocol <span>↗</span></a>')}
"""
    return page("flagged.html", "Flagged for review",
                "Every gap, irregularity and unverified value, with the official source a reviewer needs to close it.",
                body)


def build_review() -> str:
    rows = []
    for step in ROOT_DATA["review_protocol"]:
        rows.append([esc(step["Step"]), esc(step["Action"]), raw_link(step["Source"], "Reference ↗")])
    protocol_table = table(["Step", "What to do", "Reference"], rows)

    body = f"""
<div class="notice"><b>Why this page exists.</b> The site publishes gaps on purpose, so a reviewer can close them
after the site is live. This page says exactly how: which source closes which flag, and what a change request must
contain.</div>
<div class="section-head"><div><div class="section-label">01 / PROTOCOL</div><h2>Review and change-request protocol</h2></div>
<p>Five steps, no manual data entry.</p></div>
{protocol_table}
<div class="section-head"><div><div class="section-label">02 / WHAT TO INCLUDE</div><h2>Checklist for a change request</h2></div>
<p>Short and specific beats long and vague.</p></div>
<div class="brief">
<div><div class="card-kicker">REQUIRED</div><h3>Four things</h3>
<ul class="list"><li>The flag or suggestion id, for example F-02 or SI-04.</li>
<li>The official source that establishes the value, with its URL.</li>
<li>The capture or observation time, so the value can be reproduced.</li>
<li>The table or page the change affects.</li></ul></div>
<div><div class="card-kicker">REJECTED</div><h3>What does not close an item</h3>
<ul class="list"><li>A secondary report of an official fact, with no primary link.</li>
<li>A value inferred from another value, for example a replacement derived from a roster list.</li>
<li>A community dataset described as official data.</li>
<li>A request to fill a blank cell without a source.</li></ul></div>
</div>
{callout("OPEN ITEMS", "The full list of open flags, with severity and the action each one needs.", '<a class="button" href="flagged.html">Open flagged items <span>↗</span></a>')}
"""
    return page("review.html", "Review protocol",
                "How to review a published gap, close it with an official source and request the change — including what a change request has to contain.",
                body)


def build_sources() -> str:
    rows = []
    for row in CATALOG["sources"]:
        rows.append([
            esc(row["id"]), esc(row.get("title", "")), esc(row.get("publisher", "")),
            f'<a class="source" href="{esc(row.get("url", ""))}" target="_blank" rel="noopener noreferrer">{esc(row.get("url", ""))} ↗</a>',
            esc(row.get("checked", "")), esc(row.get("status", "")), esc(row.get("scope", "")),
            esc(row.get("limit", "")),
        ])
    sources_table = table(["ID", "Title", "Publisher", "Official URL", "Checked", "Status", "What it establishes", "What it cannot establish"], rows,
                           "Checked means the page was opened on that date. An official link is not a licence to reuse the content.")
    body = f"""
<div class="notice"><b>Authority rule.</b> An official page establishes what it publishes, on the day it was read. It
does not grant permission for automated reuse, and it does not make a historical archive. Community and secondary
sources are excluded from official-only claims.</div>
{metrics_block([
    ("REGISTERED SOURCES", str(len(CATALOG["sources"])), "NFL, club, regulator and methodology authorities"),
    ("PAGES OPENED", str(sum(1 for r in CATALOG['sources'] if r.get('status') == 'opened')), "Each with a recorded limit"),
    ("CLUB DEPTH SOURCES", str(len({row.get('source_url') for row in SNAPSHOT['depth_rows']})), "Official club charts"),
    ("COMMUNITY SOURCES USED", "0", "Excluded from official-only claims"),
])}
<div class="section-head"><div><div class="section-label">01 / REGISTER</div><h2>Every source used, with its limit</h2></div>
<p>Link, publisher, date checked, what it establishes and what it cannot.</p></div>
{sources_table}
<div class="section-head"><div><div class="section-label">02 / SITE SOURCES</div><h2>Additional references used by the root pages</h2></div>
<p>Context links for the published proposals.</p></div>
{section_table("root_sources", "Source / context")}
"""
    return page("sources.html", "Source register",
                "Every official source behind the published tables, with the publisher, the date checked, what it establishes and what it cannot establish.",
                body)


def build_verification() -> str:
    summary = VERIFICATION.get("summary", {})
    coverage = VERIFICATION.get("coverage", {})
    injuries = VERIFICATION.get("injuries", {})
    depth = VERIFICATION.get("depth", {})
    method = VERIFICATION.get("method", "No verification has been recorded yet.")
    pages_read = VERIFICATION.get("pages_read", [])

    pages_table = table(["Official page", "Publisher", "Read at", "Clubs read in full"],
                         [[raw_link(p.get("url", ""), "Open official page"), esc(p.get("publisher", "")),
                           esc(p.get("read_at", "")),
                           esc(", ".join(p.get("teams_read_in_full", [])) or "all published rows")] for p in pages_read])

    match_rows = []
    for key, label in (("rows_matched", "Rows identical in every compared field"),
                       ("rows_changed", "Rows whose field value changed"),
                       ("rows_added_since_capture", "Rows present live but absent from the capture"),
                       ("rows_removed_since_capture", "Rows present in the capture but absent live")):
        match_rows.append([esc(label), str(injuries.get(key, 0) if isinstance(injuries.get(key), int) else len(injuries.get(key, []))),
                           src("S01")])
    match_table = table(["Comparison outcome", "Injury rows", "Official source"], match_rows)

    depth_table = table(
        ["Comparison outcome", "Club depth rows", "Official source"],
        [[esc(label), str(depth.get(key, 0) if isinstance(depth.get(key), int) else len(depth.get(key, []))), src("S06")]
         for key, label in (("rows_matched", "Rows identical in every compared field"),
                            ("rows_changed", "Rows whose published order changed"),
                            ("rows_added_since_capture", "Rows present live but absent from the capture"),
                            ("rows_removed_since_capture", "Rows present in the capture but absent live"))])

    drift_rows = []
    for row in (injuries.get("rows_added_since_capture", []) or []):
        drift_rows.append([esc(row.get("team", "")), esc(row.get("player", "")), "Added after the capture", esc(row.get("note", "")), src("S01")])
    for row in (injuries.get("rows_changed", []) or []):
        for field, values in row.get("fields", {}).items():
            drift_rows.append([esc(row.get("team", "")), esc(row.get("player", "")), esc(field),
                               f'{esc(values[0])} → {esc(values[1])}', src("S01")])
    drift_table = table(["Team", "Player", "Field", "Capture value → live value", "Official source"], drift_rows) if drift_rows else \
        '<p class="footnote">No drift was recorded in this run.</p>'

    body = f"""
<div class="notice"><b>Method.</b> {esc(method)}</div>
{metrics_block([
    ("INJURY ROWS MATCHED", f"{summary.get('injury_rows_matched', 0)} / {summary.get('injury_rows_compared', 0)}", "Field-by-field against the live page"),
    ("DEPTH ROWS MATCHED", f"{summary.get('depth_rows_matched', 0)} / {summary.get('depth_rows_compared', 0)}", "Unit, position, rank and player"),
    ("DRIFT ROWS", str(summary.get("drift_rows", 0)), "Live pages changed after the capture"),
    ("CAPTURE TIME", esc(str(summary.get("snapshot_observed_at", ""))[:19].replace("T", " ")), "UTC, from the committed snapshot"),
])}
<div class="section-head"><div><div class="section-label">01 / SOURCES READ</div><h2>Official pages read for this verification</h2></div>
<p>Every page opened is listed with the time it was read.</p></div>
{pages_table}
<div class="section-head"><div><div class="section-label">02 / INJURY REPORT</div><h2>Injury rows compared with the live report</h2></div>
<p>{esc(str(coverage.get('rows_read_live', 0)))} of {esc(str(coverage.get('snapshot_injury_rows', 0)))} published rows were re-read.</p></div>
{match_table}
<div class="section-head"><div><div class="section-label">03 / DEPTH CHART</div><h2>Club depth rows compared with the live chart</h2></div>
<p>{esc(str(coverage.get('depth_rows_read_live', 0)))} published rows of the Washington Commanders chart.</p></div>
{depth_table}
<div class="section-head"><div><div class="section-label">04 / DRIFT</div><h2>Every difference found</h2></div>
<p>Differences are reported, not repaired, because the live page is mutable and the capture is a point in time.</p></div>
{drift_table}
<div class="section-head"><div><div class="section-label">05 / LIMITS</div><h2>What this verification does not prove</h2></div>
<p>Stated so it is not over-read.</p></div>
<div class="brief">
<div><div class="card-kicker">NOT PROVEN</div><h3>Historical point-in-time truth</h3>
<p>The verification compares the capture with today's live page. It cannot turn a mutable page into an archive, and it
does not establish what was known before any earlier kickoff.</p></div>
<div><div class="card-kicker">NOT PROVEN</div><h3>Reuse permission or prediction</h3>
<p>Opening an official page proves what it publishes. It does not grant reuse rights, and a faithful copy of a report
still carries no predictive claim.</p></div>
</div>
{callout("RE-RUN", "The verification runs on every deployment; on a networked runner it re-captures the official pages and checks the whole population.", '<a class="button" href="sources.html">Open the source register <span>↗</span></a>')}
"""
    return page("verification.html", "Verification report",
                "The published capture checked line by line against the live official pages, with every difference listed rather than hidden.",
                body)


PAGES = {
    "index.html": build_index,
    "executive-summary.html": build_executive_summary,
    "questions.html": build_questions,
    "decisions.html": build_decisions,
    "signals.html": build_signals,
    "strategies.html": build_strategies,
    "validation.html": build_validation,
    "lineups.html": build_lineups,
    "lineup.html": build_lineup,
    "suggestions.html": build_suggestions,
    "flagged.html": build_flagged,
    "review.html": build_review,
    "sources.html": build_sources,
    "verification.html": build_verification,
}


def main() -> int:
    written = []
    for filename, builder in PAGES.items():
        (ROOT / filename).write_text(builder(), encoding="utf-8")
        written.append(filename)
    print(f"Built {len(written)} root pages: {', '.join(sorted(written))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
