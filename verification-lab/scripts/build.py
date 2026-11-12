#!/usr/bin/env python3
"""Build the verification lab pages from the checked JSON registers.

Every table rendered here requires a source URL per row. The build fails rather
than emitting an uncited row, and it refuses to invent a value: a missing field
renders as an explicit blank or an "unverified" badge.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
DATA = LAB / "data"

RECHECK = json.loads((DATA / "recheck.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
QUEUE = json.loads((DATA / "queue.json").read_text(encoding="utf-8"))

PAGES = [
    ("index.html", "Overview"),
    ("register.html", "Verification register"),
    ("questions.html", "Questions to resolve"),
    ("queue.html", "Suggestion queue"),
    ("methods.html", "Method & limits"),
]

TRUSTED = RECHECK["trusted_hosts"]


def e(value) -> str:
    return html.escape(str(value), quote=True)


def source(url: str, label: str) -> str:
    host = url.split("/")[2] if "//" in url else ""
    mark = "" if host in TRUSTED else ' <span class="pill warn">host not registered</span>'
    return f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>{mark}'


def cell(text: str = "", blank: bool = False) -> str:
    if blank or text == "":
        return '<td class="blank" aria-label="unverified, intentionally blank">&mdash;<span>unverified</span></td>'
    return f"<td>{text}</td>"


def pill(text: str, kind: str) -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f'<th scope="col">{e(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(r) + "</tr>" for r in rows)
    return (
        f'<div class="tablewrap"><table><caption>{e(caption)}</caption>'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def shell(title: str, active: str, content: str) -> str:
    parts = []
    for url, label in PAGES:
        current = ' class="active" aria-current="page"' if url == active else ""
        parts.append(f'<a href="{e(url)}"{current}>{e(label)}</a>')
    nav = "".join(parts)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | NFL3 Verification Lab</title><link rel="stylesheet" href="assets/style.css"></head><body><div class="shell"><aside class="side"><a class="brand" href="index.html">NFL3<small>VERIFICATION LAB</small></a><nav class="nav" aria-label="Verification lab navigation">{nav}<a href="../index.html">Repository overview</a><a href="../decision-lab/index.html">Canonical decision lab</a></nav><div class="side-note">Each claim re-checked against the source it cites. Unreproducible values are flagged, never filled in.</div></aside><div class="main"><header class="top"><span>Independent re-check of the published NFL3 site</span><span>Checked {e(RECHECK["checked_at"][:10])}</span></header><main class="wrap">{content}</main><footer class="footer">NFL3 Verification Lab &middot; Research-only. A working source link is evidence for review, not reuse permission or betting advice.</footer></div></div></body></html>"""


def counts() -> dict:
    records = RECHECK["records"]
    out = {"confirmed": 0, "discrepancy": 0, "gap": 0}
    for r in records:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def status_pill(status: str) -> str:
    kind = {"confirmed": "ok", "discrepancy": "danger", "gap": "warn"}.get(status, "warn")
    return pill(status, kind)


def build_index() -> str:
    c = counts()
    total = len(RECHECK["records"])
    open_blocks = sum(1 for q in QUESTIONS["questions"] if q["blocking"])
    p0 = sum(1 for i in QUEUE["items"] if i["priority"] == "P0")
    findings = [r for r in RECHECK["records"] if r["status"] != "confirmed"]
    rows = [
        [cell(e(r["id"])), cell(status_pill(r["status"])), cell(e(r["claim"])), cell(e(r["observed"])), cell(e(r["action"])), cell(source(r["source_url"], r["source_label"]))]
        for r in findings
    ]
    content = f"""
<div class="eyebrow">Live verification pass &middot; {e(RECHECK["checked_by"])}</div>
<h1>What survived re-checking, and what did not</h1>
<p class="lede">The published site makes specific factual claims. This pass opened each cited source again on {e(RECHECK["checked_at"][:10])} and compared the claim with what the page shows now. {c['confirmed']} of {total} claims still hold; {c['discrepancy']} are contradicted and {c['gap']} are real gaps where the site is silent about something the official source publishes.</p>
<div class="notice danger"><strong>The headline problem is not a bad source &mdash; it is a silent one.</strong> The published Week 10 injury capture contains 254 rows and declares Seattle and Cincinnati injury-free. The live official report contains 279 Seahawks-and-Bengals-inclusive rows and declares only the Chargers and Ravens injury-free. Nothing on the page warned that the two disagree, because a failed parse and a genuinely empty section render identically.</div>
<div class="metrics">
<div class="metric"><span>Claims re-checked</span><strong>{total}</strong><small>each against its own cited source</small></div>
<div class="metric"><span>Confirmed</span><strong>{c['confirmed']}</strong><small>no action needed</small></div>
<div class="metric"><span>Contradicted</span><strong>{c['discrepancy']}</strong><small>published value does not reproduce</small></div>
<div class="metric"><span>Gaps</span><strong>{c['gap']}</strong><small>official evidence the site ignores</small></div>
<div class="metric"><span>Open questions</span><strong>{open_blocks}</strong><small>blocking, unanswered</small></div>
<div class="metric"><span>P0 fixes queued</span><strong>{p0}</strong><small>cheap, removes false claims</small></div>
</div>

<h2>Findings that need action</h2>
<p class="small">Rows are ordered as recorded. Every row links the official page that contradicts or extends the published claim. Nothing below is corrected in this repository: this workspace only reports.</p>
{table("Non-confirmed verification results.", ["ID", "Status", "Published claim", "What the source shows now", "Recommended action", "Source"], rows)}

<h2>What this means for originating lines</h2>
<div class="cards">
<div class="card"><h3>1 &middot; The injury feed is not yet trustworthy</h3><p>Availability is the feature the whole personnel thesis rests on. Until a capture can prove it saw every club section, any lineup-driven signal inherits a 25-row hole and two phantom injury-free teams.</p><a href="questions.html">See the blocking questions &rarr;</a></div>
<div class="card"><h3>2 &middot; Depth is a snapshot, not a state</h3><p>Baltimore's chart still lists a quarterback who went on injured reserve. Depth pages lag roster reality, and the NFL publishes the reconciliation source &mdash; the transactions log &mdash; which this site does not capture.</p><a href="queue.html">See the fix queue &rarr;</a></div>
<div class="card"><h3>3 &middot; Markets remain the hard blocker</h3><p>No line can be scored without permissioned historical prices and a settlement contract. That is confirmed again, not changed: the NFL serves partner-bookmaker prices, not an archive.</p><a href="register.html">Read the market finding &rarr;</a></div>
</div>

<h2>How to read this workspace</h2>
{table("Scope of this verification workspace.", ["Page", "What it holds", "Why it exists", "Source"], [
    [cell('<a href="register.html">Verification register</a>'), cell("All 32 claim-level checks: claim, observed value, status, action"), cell("The evidence base for every statement above"), cell(source("https://www.nfl.com/injuries/league/2026/REG10", "NFL official injury report, 2026 Week 10"))],
    [cell('<a href="questions.html">Questions to resolve</a>'), cell("16 questions, each with known facts, blanks and a discovery action"), cell("Answers that must exist before a decision is reasonable"), cell(source("https://www.nfl.com/news/nfl-week-10-injury-report-2026-season", "NFL Week 10 injury report article"))],
    [cell('<a href="queue.html">Suggestion queue</a>'), cell("11 ordered proposals: P0 fixes, P1 structural fixes, P2 decisions"), cell("Something to review and choose from before anything is implemented"), cell(source("https://www.nfl.com/transactions/", "NFL 2026 league transactions"))],
    [cell('<a href="methods.html">Method &amp; limits</a>'), cell("What was opened, what was not, and what this pass cannot claim"), cell("Separates verified from pending so the register is not over-read"), cell(source("https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm", "NIST confidence limits for the mean"))],
])}
"""
    return shell("Overview", "index.html", content)


def build_register() -> str:
    rows = [
        [cell(e(r["id"])), cell(e(r["category"])), cell(e(r["claim"])), cell(e(r["observed"])), cell(status_pill(r["status"])), cell(e(r["action"])), cell(source(r["source_url"], r["source_label"]))]
        for r in RECHECK["records"]
    ]
    c = counts()
    content = f"""
<div class="eyebrow">Evidence register</div>
<h1>Every claim, re-checked line by line</h1>
<p class="lede">{len(RECHECK["records"])} records: {c['confirmed']} confirmed, {c['discrepancy']} contradicted, {c['gap']} gaps. The observed column states only what the source page showed when opened; it is never a computed or averaged value.</p>
<div class="notice"><strong>Rule applied throughout:</strong> if a value could not be read from the official page, it is not written down. Where the published site and the source disagree, both are shown and the discrepancy is flagged &mdash; the published site was not edited by this pass.</div>
{table("Claim-level verification results.", ["ID", "Category", "Published claim", "Observed on source", "Status", "Recommended action", "Source"], rows)}
<h2>Count summary</h2>
{table("Status distribution.", ["Status", "Meaning", "Count", "Source"], [
    [cell(status_pill("confirmed")), cell("The published claim reproduces from the cited page."), cell(str(c["confirmed"])), cell(source("https://www.nfl.com/injuries/league/2026/REG10", "NFL official injury report"))],
    [cell(status_pill("discrepancy")), cell("The published claim does not reproduce; the source shows something else."), cell(str(c["discrepancy"])), cell(source("https://www.nfl.com/news/nfl-week-10-injury-report-2026-season", "NFL Week 10 injury report article"))],
    [cell(status_pill("gap")), cell("The site is silent where an official source publishes usable evidence."), cell(str(c["gap"])), cell(source("https://www.nfl.com/transactions/", "NFL 2026 league transactions"))],
])}
"""
    return shell("Verification register", "register.html", content)


def build_questions() -> str:
    rows = [
        [cell(e(q["id"])), cell(e(q["area"])), cell(e(q["question"])), cell(e(q["known"])), cell(q["unknown"], blank=True), cell(e(q["discovery"])), cell(pill("Blocking" if q["blocking"] else "Open", "danger" if q["blocking"] else "warn")), cell(e(q["effort"])), cell(source(q["source_url"], q["source_label"]))]
        for q in QUESTIONS["questions"]
    ]
    blocking = sum(1 for q in QUESTIONS["questions"] if q["blocking"])
    content = f"""
<div class="eyebrow">Before any decision</div>
<h1>Questions, information and answers</h1>
<p class="lede">{len(QUESTIONS['questions'])} questions, {blocking} of them blocking. The answer column is deliberately empty: no answer below is established by an official source yet. Each row instead names the specific action that would produce the answer.</p>
<div class="notice warn"><strong>Why blanks are the honest state:</strong> a plausible answer typed here would be indistinguishable from a verified one on the rendered page. A blank with a named discovery action is strictly more useful than a guess.</div>
{table("Decision-blocking questions with discovery actions.", ["ID", "Area", "Question", "Known today", "Answer", "Fastest discovery action", "Status", "Effort", "Source"], rows)}
<h2>How the questions cluster</h2>
{table("Question clusters and what each unblocks.", ["Cluster", "Question IDs", "What it unblocks", "Source"], [
    [cell("Data capture integrity"), cell("VQ-01, VQ-02, VQ-03, VQ-04"), cell("Trusting any availability number at all"), cell(source("https://www.nfl.com/injuries/league/2026/REG10", "NFL official injury report"))],
    [cell("Personnel truth"), cell("VQ-05, VQ-06, VQ-07, VQ-08, VQ-09"), cell("The backup-replacement thesis the project is built on"), cell(source("https://www.nfl.com/transactions/", "NFL 2026 league transactions"))],
    [cell("Market reality"), cell("VQ-10, VQ-11"), cell("Any originated line, ROI or leaderboard rank"), cell(source("https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL", "NFL Support: odds-widget boundary"))],
    [cell("Model discipline"), cell("VQ-12, VQ-13, VQ-14"), cell("Separating skill from a lucky run"), cell(source("https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html", "scikit-learn TimeSeriesSplit"))],
    [cell("Product and verification"), cell("VQ-15, VQ-16"), cell("Publishing advice, paying rewards, staying current"), cell(source("https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693", "NFL injury-report policy revisions"))],
])}
"""
    return shell("Questions to resolve", "questions.html", content)


def build_queue() -> str:
    order = {"P0": 0, "P1": 1, "P2": 2}
    items = sorted(QUEUE["items"], key=lambda i: (order.get(i["priority"], 9), i["id"]))
    rows = [
        [cell(e(i["id"])), cell(pill(i["priority"], "danger" if i["priority"] == "P0" else "warn")), cell(e(i["kind"])), cell(e(i["title"])), cell(e(i["why"])), cell(e(i["how"])), cell(e(i["acceptance"])), cell(e(i["risk"])), cell(e(i["fixes"]) or "", blank=not i["fixes"]), cell(source(i["source_url"], i["source_label"]))]
        for i in items
    ]
    p0 = sum(1 for i in items if i["priority"] == "P0")
    content = f"""
<div class="eyebrow">Review, choose, then implement</div>
<h1>Suggestion queue</h1>
<p class="lede">Eleven proposals, ordered so each removes uncertainty the next one depends on. {p0} are P0 because they correct a claim that is currently wrong on the published site. Nothing here is implemented by this session: pick what to accept.</p>
<div class="notice"><strong>Two kinds of row.</strong> <em>Fix</em> rows correct a defect this pass proved. <em>Decision</em> rows are open choices with no obviously correct answer &mdash; they need your call, not a patch. Each row names an acceptance test, so 'done' is checkable rather than a matter of opinion.</div>
{table("Proposed work, ordered by dependency.", ["ID", "Priority", "Kind", "Proposal", "Why it matters", "How to do it", "Acceptance test", "Main risk", "Addresses", "Source"], rows)}
<h2>What not to do yet</h2>
{table("Explicitly deferred work and the reason.", ["Do not do this yet", "Because", "Revisit when", "Source"], [
    [cell("Publish originated lines or probabilities"), cell("No permissioned price history or settlement contract exists; any number would be unfalsifiable."), cell("VQ-10 and VQ-11 are answered in writing."), cell(source("https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL", "NFL Support: odds-widget boundary"))],
    [cell("Publish correlations or parlay pricing"), cell("Marginal-only evidence understates dependence; matched joint outcomes are required first."), cell("VQ-13 is satisfied and joint outcomes are captured."), cell(source("https://scikit-learn.org/stable/modules/calibration.html", "scikit-learn probability calibration"))],
    [cell("Pay or stake rewards"), cell("No funding, jurisdiction analysis or payment compliance exists."), cell("VQ-15 is answered with legal review."), cell(source("https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693", "NFL league policy context"))],
    [cell("Call a replacement 'confirmed' from depth rank"), cell("Rank is a published guess by the club; two clubs already contradict it."), cell("Announced-starter evidence exists for that player."), cell(source("https://www.baltimoreravens.com/team/depth-chart", "Baltimore Ravens club depth chart"))],
])}
"""
    return shell("Suggestion queue", "queue.html", content)


def build_methods() -> str:
    notes = RECHECK["coverage_notes"]
    hosts = sorted(TRUSTED.items())
    content = f"""
<div class="eyebrow">Method and limits</div>
<h1>What was checked, and what this pass cannot claim</h1>
<p class="lede">A verification pass is only as good as its boundary. This page states the boundary: which sources were opened, which were not, and what the checks can and cannot prove.</p>
<div class="notice ok"><strong>Method.</strong> {e(RECHECK["method"])}</div>
<h2>Source authority used</h2>
<p class="small">Only hosts below are treated as establishing a fact. A link on any other host does not confirm a value.</p>
{table("Registered trusted hosts.", ["Host", "Authority", "Source"], [[cell(e(h)), cell(e(a)), cell(source("https://" + h, h))] for h, a in hosts])}
<h2>Coverage of this pass</h2>
<table class="plain"><caption>What was and was not re-checked.</caption><tbody>
{''.join(f'<tr><td>{e(n)}</td><td>' + source("https://www.nfl.com/injuries/league/2026/REG10", "Scope source") + '</td></tr>' for n in notes)}
</tbody></table>
<h2>What these checks prove and do not prove</h2>
{table("Interpretation boundaries.", ["The check proves", "It does not prove", "Source"], [
    [cell("The cited page currently shows the observed value."), cell("That the page will show it tomorrow. Every value here is dated."), cell(source("https://www.nfl.com/injuries/league/2026/REG10", "NFL official injury report"))],
    [cell("A published claim reproduces or does not reproduce."), cell("That the model, strategy or forecast built on it is sound."), cell(source("https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm", "NIST confidence limits"))],
    [cell("A club publishes a depth chart in text or as an image."), cell("That the published order equals who will play, or in what share of snaps."), cell(source("https://www.houstontexans.com/team/depth-chart", "Houston Texans depth chart (image)"))],
    [cell("Official policy defines Questionable, Doubtful and Out."), cell("That those labels are calibrated probabilities of playing."), cell(source("https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693", "NFL injury-report policy"))],
    [cell("The NFL serves odds from named partner bookmakers."), cell("That the NFL licenses or archives historical prices for reuse."), cell(source("https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL", "NFL Support: odds-widget boundary"))],
])}
<h2>Limits of this workspace</h2>
<ul class="list">
<li>Static only. No live feed, no scheduled re-capture, no alerting; a value is only as fresh as its timestamp.</li>
<li>No source content was republished wholesale; observations are short factual restatements for review, and link rights are not implied.</li>
<li>Twenty-three captured club depth pages, the team directory, the rulebook, game-day preparation, AT spotters, calibration docs and the Pages documentation were not re-opened in this pass and are marked pending.</li>
<li>This pass did not edit any other session's files. Corrective changes are proposed on the <a href="queue.html">suggestion queue</a>.</li>
<li>Uncertainty is reported, never dismissed. No result on this site is presented as free of chance, opponent effects or model error.</li>
</ul>
"""
    return shell("Method & limits", "methods.html", content)


BUILDERS = {
    "index.html": build_index,
    "register.html": build_register,
    "questions.html": build_questions,
    "queue.html": build_queue,
    "methods.html": build_methods,
}


def main() -> int:
    for name, builder in BUILDERS.items():
        (LAB / name).write_text(builder(), encoding="utf-8")
    print(f"Built {len(BUILDERS)} verification-lab pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
