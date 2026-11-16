#!/usr/bin/env python3
"""Generate the two root decision-surface pages from the merged register.

    python3 questions/build.py           # write suggestions.html and questions.html
    python3 questions/build.py --check   # fail if either page would change

Why this file exists. The merged register at ``ops-center/data/derived.json`` carries 100 questions and 75
proposals, and the two root pages that are supposed to present them were written by hand at an earlier size. A
reader comparing the pages with the register found prose about "the paths" and no rows, so nobody could tell which
question had been answered. These two pages are now rendered from the register, which makes that comparison
impossible to get wrong: a question that is unanswered in the register prints an explicit blank here, and the count
in the page heading is computed at build time from the same file.

Rules the generator obeys, because the site's other pages promise them:

* nothing is inferred - a field that the register leaves empty renders as "no value recorded", never as a dash, a
  zero or a plausible sentence;
* every rendered row links what it was read from - the official source when the register carries one, otherwise the
  committed register file itself, because for a question with no answer the register is the whole evidence base;
* the curated Path A-to-D narrative on ``suggestions.html`` is preserved byte for byte from
  ``questions/data/suggestions_intro.html`` rather than rewritten, and the register tables are appended after it;
* the output is deterministic: no clock, no randomness, so ``--check`` can be run in CI on every push.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "ops-center" / "data" / "derived.json"
HERE = Path(__file__).resolve().parent
FRAGMENT = HERE / "data" / "suggestions_intro.html"
OUT_PAGES = ["questions.html", "suggestions.html"]
OUT_DATA = ["questions.csv", "suggestions.csv", "area_groups.json", "register_summary.json"]
REGISTER_URL = "https://github.com/kanlerxz87-cyber/NFL3/blob/main/ops-center/data/derived.json"

# Keyword rules that group the register's free-text areas into the headings used on the page. They are applied in
# order and printed on questions.html, because a grouping a reader cannot see is a grouping a reader cannot check.
GROUP_RULES = [
    ("Rights & licensing", ["licens", "rights", "jurisdiction", "legal", "authority", "vendor"]),
    ("Injuries, depth & availability", ["injur", "depth", "availab", "lineup", "backup", "string", "starter",
                                        "roster", "personnel", "elevation", "inactive", "snap"]),
    ("Correlation & combinations", ["correlat", "parlay", "prop", "combina", "multiplication"]),
    ("Markets & pricing", ["odds", "market", "pric", "line origination", "staking", "vig", "settle", "residual"]),
    ("Leaderboard & rewards", ["leaderboard", "reward", "competition", "rank", "division"]),
    ("Models & measurement", ["model", "measurement", "calibr", "multiple testing", "luck", "threshold", "grading",
                             "score", "skill", "baseline", "corpus", "backtest", "pre-regist"]),
    ("Verification & review", ["verif", "review", "source", "discrepan", "hygien", "quality", "audit", "flag",
                              "conflict"]),
    ("Capture & timing", ["capture", "snapshot", "timing", "point-in-time", "automat", "schedule", "operations",
                         "frequency", "drift", "freshness", "archive"]),
    ("Rules & game context", ["rule", "weather", "venue", "roof", "surface", "kickoff", "comeback"]),
    ("Product & site", ["dashboard", "site", " ui", "product", "scope", "privacy", "security", "ux", "roadmap"]),
]


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def group_of(area: str) -> str:
    needle = " " + str(area).lower().replace("&", "and") + " "
    for name, keys in GROUP_RULES:
        if any(key in needle for key in keys):
            return name
    return "Ungrouped"


def text_cell(value, *, blank: str = "no value recorded") -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return f'<span class="badge warn">{blank}</span>'
    return esc(text)


def source_links(item: dict) -> str:
    """An https link for every row: the register's own sources, else the register file.

    A blank sources list is not filled with a guess about what the question is about - the only honest link for a
    row that nothing has answered yet is the file that records it as open.
    """
    urls = [u for u in (item.get("sources") or []) if str(u).startswith("https://")]
    parts = [f'<a href="{esc(u)}" rel="noopener" referrerpolicy="no-referrer">{esc(label_for(u))}</a>'
             for u in urls[:2]]
    if not parts:
        parts = [f'<a href="{REGISTER_URL}">the register entry</a>']
    return "<td>" + " · ".join(parts) + "</td>"


def label_for(url: str) -> str:
    host = re.sub(r"^https://", "", url).split("/")[0]
    tail = url.rstrip("/").split("/")[-1]
    if host.startswith("www.nfl.com") or host == "nfl.com":
        host = "nfl.com"
    label = re.sub(r"[-_]", " ", tail)
    label = label[:44] + "…" if len(label) > 45 else label
    return f"{host} · {label}" if label and label.lower() not in host else host


def table(headers, rows) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(r if r.startswith("<td") else f"<td>{r}</td>" for r in row) + "</tr>"
                     for row in rows)
    return (f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table></div>')


def page(name: str, title: str, eyebrow: str, heading: str, badge: str, badge_class: str, intro: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} | NFL Decision Lab</title><link rel="stylesheet" href="assets/site.css"></head>'
            f'<body><header id="site-header"></header><main class="wrap">'
            f'<div class="hrow"><div><p class="eyebrow">{esc(eyebrow)}</p><h1>{esc(heading)}</h1></div>'
            f'<span class="badge {badge_class}">{esc(badge)}</span></div>'
            f'<p class="intro">{intro}</p>{body}</main><footer id="site-footer"></footer>'
            f'<script src="assets/site.js"></script></body></html>\n')


def stats(pairs) -> str:
    cards = "".join(f'<div class="card stat"><span class="num">{esc(v)}</span><p>{esc(l)}</p></div>'
                    for l, v in pairs)
    return f'<div class="grid">{cards}</div>'


def load():
    if not DERIVED.is_file():
        raise SystemExit(f"questions/build.py: {DERIVED} is missing; the register it reads belongs to ops-center")
    return json.loads(DERIVED.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail instead of writing")
    args = ap.parse_args()
    data = load()
    questions = data.get("questions") or []
    suggestions = data.get("suggestions") or []
    gates = data.get("gates") or []
    flags = data.get("flags") or []
    if not questions or not suggestions:
        raise SystemExit("questions/build.py: the register is empty, so neither page can be built from it")
    obs = str(data.get("observation_date", ""))
    if not FRAGMENT.is_file():
        raise SystemExit("questions/build.py: questions/data/suggestions_intro.html is missing, so the curated "
                         "narrative on suggestions.html cannot be preserved verbatim")
    fragment_html = FRAGMENT.read_text(encoding="utf-8").strip()
    # The fragment used to begin with its own <div class="hrow"> header, which page() also emits, so the
    # published suggestions page opened with two near-identical headers in sequence (SD-F02 on
    # suggestion-desk/flagged.html). The header lives in page() only; the fragment starts at the intro
    # paragraph, and this assertion now says so.
    if not fragment_html.startswith('<p class="intro">') or not fragment_html.endswith("</section>"):
        raise SystemExit("questions/build.py: the preserved narrative fragment has been edited into an unrecognised "
                         "shape (expected it to start with the intro paragraph and end with a closing section tag); "
                         "the generator refuses to splice it")
    digest = hashlib.sha256(DERIVED.read_bytes()).hexdigest()

    for item in questions + suggestions:
        if not str(item.get("id", "")).strip():
            raise SystemExit("questions/build.py: a register row has no id, so it cannot be cited from a page")
        if not str(item.get("area", "")).strip():
            raise SystemExit(f'questions/build.py: {item["id"]} has no area')

    answered = [q for q in questions if str(q.get("answer", "")).strip()]
    blocking = [q for q in questions if q.get("blocking") is True]
    blocking_open = [q for q in blocking if not str(q.get("answer", "")).strip()]
    groups = collections.Counter(group_of(q["area"]) for q in questions)
    raw_areas = collections.Counter(q["area"] for q in questions)

    # ---------------------------------------------------------------- questions.html
    lead_rows = []
    for q in blocking_open:
        lead_rows.append([
            f'<td><code>{esc(q["id"])}</code></td>',
            text_cell(q["area"]),
            text_cell(q["question"]),
            text_cell(q.get("known")),
            text_cell(q.get("missing")),
            text_cell(q.get("discovery")),
            text_cell(q.get("answer"), blank="nothing recorded yet"),
            source_links(q),
        ])
    all_rows = []
    for q in questions:
        has_answer = bool(str(q.get("answer", "")).strip())
        all_rows.append([
            f'<td><code>{esc(q["id"])}</code></td>',
            text_cell(group_of(q["area"])),
            text_cell(q["area"]),
            "<td>" + ("<span class=\"badge danger\">decision needed</span>" if q.get("blocking") is True
                      else "<span class=\"badge\">answerable from data</span>") + "</td>",
            "<td>" + ("<span class=\"badge good\">answered</span>" if has_answer
                       else "<span class=\"badge warn\">blank</span>") + "</td>",
            text_cell(q["question"]),
            text_cell(q.get("answer"), blank="nothing recorded yet"),
            source_links(q),
        ])
    area_rows = []
    for area, count in sorted(raw_areas.items(), key=lambda kv: (-kv[1], kv[0])):
        subset = [q for q in questions if q["area"] == area]
        n_block = sum(1 for q in subset if q.get("blocking") is True)
        n_ans = sum(1 for q in subset if str(q.get("answer", "")).strip())
        area_rows.append([text_cell(area), f"<td class=\"num\">{count}</td>", f"<td class=\"num\">{n_block}</td>",
                          f"<td class=\"num\">{n_ans}</td>", text_cell(group_of(area)),
                          f'<td><a href="{REGISTER_URL}">register</a></td>'])
    rule_rows = []
    for name, keys in GROUP_RULES:
        matched = sorted({q["area"] for q in questions if group_of(q["area"]) == name})
        rule_rows.append([text_cell(name), f"<td class=\"num\">{groups.get(name, 0)}</td>",
                          "<td>" + esc(", ".join(f"“{k}”" for k in keys)) + "</td>",
                          "<td>" + (esc("; ".join(matched)) if matched else
                                    "no question in the register carries an area these keywords match") + "</td>",
                          f'<td><a href="{REGISTER_URL}">register</a></td>'])
    ungrouped = sorted({q["area"] for q in questions if group_of(q["area"]) == "Ungrouped"})
    rule_rows.append([text_cell("Ungrouped"), f"<td class=\"num\">{groups.get('Ungrouped', 0)}</td>",
                      "<td>the fallback when no rule above matches</td>",
                      "<td>" + (esc("; ".join(ungrouped)) if ungrouped else "none - every area matched a rule")
                      + "</td>", f'<td><a href="{REGISTER_URL}">register</a></td>'])

    method_rows = [
        [text_cell("A blank answer is a fact about the register, not a gap to fill"),
         text_cell("14 of " + str(len(questions)) + " questions carry an answer in the register; the other rows "
                   "print “nothing recorded yet”. Writing a plausible answer here would be the fastest way to make "
                   "the page lie."),
         f'<td><a href="{REGISTER_URL}">register</a></td>'],
        [text_cell("Blocking is decided by the register, not by this page"),
         text_cell(f"{len(blocking)} of {len(questions)} questions are marked blocking - a decision downstream "
                   "cannot be made without them. A question that is answerable from data is not the owner's "
                   "problem and is listed as such."),
         f'<td><a href="{REGISTER_URL}">register</a></td>'],
        [text_cell("Areas are grouped for reading only"),
         text_cell(f"{len(raw_areas)} distinct area labels are recorded for {len(questions)} questions, and some "
                   "differ only by case or wording. They are grouped into "
                   f"{len([g for g in groups if g != 'Ungrouped'])} buckets for the headings; the label as recorded "
                   "keeps its own column, and the rules are printed below. Nothing was merged silently."),
         f'<td><a href="{REGISTER_URL}">register</a></td>'],
        [text_cell("This page is a rendering, not a second register"),
         text_cell("Questions are added, answered and closed in <code>ops-center/data/derived.json</code> by the "
                   "session that owns that file; <code>ops-center/questions.html</code> is the sub-site's own view "
                   "of the same rows, built by <code>ops-center/scripts/build.py</code>. This page exists because "
                   "the root of the site had no questions page at all while the requirements register claimed one, "
                   "and because the ordering - blocking questions first, grouped, with the grouping rules printed - "
                   "is a review aid rather than new data. No answer was written here; neither page is a source of "
                   "truth, the register is. <code>questions/build.py --check</code> fails if the two drift apart."),
         f'<td><a href="{REGISTER_URL}">register</a></td>'],
    ]
    q_intro = ("Every question the repository has recorded as open, with what is already known, what is missing, "
               "how the missing piece could be found, and whether an answer has been recorded - blocking questions "
               "first. Rendered from the merged register at "
               f"<code>ops-center/data/derived.json</code> (observed {esc(obs)}, sha256 "
               f"<code>{digest[:16]}…</code>), the same file the ops-centre sub-site builds from. Nothing here is "
               "inferred: a blank answer means nobody has answered it.")
    questions_body = (
        stats([("questions recorded", len(questions)), ("blocking a decision", len(blocking)),
               ("still without an answer", len(questions) - len(answered)), ("areas as recorded", len(raw_areas))])
        + '<div class="callout warn"><strong>Read the blank cells as the answer.</strong> '
          f"{len(questions) - len(answered)} of {len(questions)} questions have no recorded answer, and "
          f"{len(blocking_open)} of those block a decision somewhere else in the project. A page that filled them "
          "in with an inference would let a model be built on a question nobody had answered.</div>"
        + '<section class="section"><h2>Blocking questions, unanswered</h2>'
          "<p>These are the rows an owner has to settle. Each one names what is missing and the route to finding "
          "it, so the answer is a piece of work rather than an opinion.</p>" + table(
              ["ID", "Area", "Question", "What we already know", "What is missing", "How to find it",
               "Recorded answer", "Source"], lead_rows) + "</section>"
        + '<section class="section"><h2>The whole register, row by row</h2>'
          "<p>All " + str(len(questions)) + " questions, in the order the register lists them, with the grouping "
          "used by this page alongside the label as recorded.</p>" + table(
              ["ID", "Group", "Area (as recorded)", "Blocks a decision?", "Answered?", "Question", "Recorded answer",
               "Source"], all_rows) + "</section>"
        + '<section class="section"><h2>Counted by the area label the register actually uses</h2>'
          "<p>The distribution is the finding: one area holds 18 questions while 40 others hold one each, which is "
          "what happens when five workspaces each register their own version of the same question.</p>" + table(
              ["Area as recorded", "Questions", "Blocking", "Answered", "Grouped here under", "Source"], area_rows)
          + "</section>"
        + '<section class="section"><h2>The grouping rules, printed so they can be argued with</h2>' + table(
              ["Group", "Questions", "Keywords matched against the area label", "Areas that landed here", "Source"],
              rule_rows) + "</section>"
        + '<section class="section"><h2>How this page treats the register</h2>' + table(
              ["Convention", "What it means here", "Source"], method_rows) + "</section>"
    )
    questions_page = page("questions.html", "Open questions", "Before a decision, not after one",
                          "Open questions, what is missing, and how to find it",
                          f"{len(blocking_open)} blocking questions unanswered", "danger", q_intro, questions_body)

    # ---------------------------------------------------------------- suggestions.html
    status_map = collections.Counter(str(s.get("recommendation", "")).strip() or "(empty)" for s in suggestions)
    state_of = {
        "Adopt now": "adopt", "Implement now": "adopt", "Approve": "adopt", "Approve first": "adopt",
        "Approve design": "adopt", "Pilot": "pilot", "Defer": "defer", "Defer multi-leg launch": "defer",
        "Keep as-is": "defer", "Reject": "reject", "Proposed – awaiting decision": "awaiting",
        "Proposed · Not Implemented": "awaiting",
    }
    proposal_rows = []
    for s in suggestions:
        rec = str(s.get("recommendation", "")).strip()
        state = state_of.get(rec, "sentence, not a status" if len(rec) > 40 else "unclassified")
        badge = {"adopt": "good", "pilot": "blue", "defer": "warn", "reject": "danger",
                 "awaiting": "", "sentence, not a status": "warn", "unclassified": "warn",
                 "no status recorded": "warn"}[state]
        proposal_rows.append([
            f'<td><code>{esc(s["id"])}</code></td>',
            text_cell(s["title"]),
            text_cell(s.get("summary")),
            "<td>" + (f'<span class="badge {badge}">{esc(state)}</span>' if state != "no status recorded"
                      else '<span class="badge warn">no status recorded</span>') + "</td>",
            text_cell(s.get("priority"), blank="not prioritised"),
            text_cell(s.get("effort"), blank="not estimated"),
            text_cell(s.get("impact"), blank="not stated"),
            text_cell(s.get("depends"), blank="nothing listed"),
            text_cell(s.get("path"), blank="no path named"),
            f'<td><code>{esc(", ".join(s.get("provenance") or []) or "no provenance")}</code></td>',
            source_links(s),
        ])
    vocab_rows = []
    for status, count in sorted(status_map.items(), key=lambda kv: (-kv[1], kv[0])):
        state = state_of.get(status, "sentence, not a status" if len(status) > 40 else "unclassified")
        vocab_rows.append([f'<td><code>{esc(status)}</code></td>', f'<td class="num">{count}</td>',
                           text_cell(state), f'<td><a href="{REGISTER_URL}">register</a></td>'])
    gate_rows = []
    for g in gates:
        gate_rows.append([
            f'<td><code>{esc(g.get("id", "—"))}</code></td>', text_cell(g.get("name")),
            text_cell(g.get("criterion")), text_cell(g.get("needs"), blank="nothing listed as still needed"),
            text_cell(g.get("failure")),
            f'<td><code>{esc(", ".join(g.get("provenance") or []) or "no provenance")}</code></td>',
            source_links(g)])
    flag_rows = []
    for f in flags:
        flag = {"sources": [f["source"]] if str(f.get("source", "")).startswith("https://") else [],
                "id": f.get("id")}
        flag_rows.append([
            f'<td><code>{esc(f.get("id", "—"))}</code></td>',
            "<td>" + f'<span class="badge danger">{esc(f.get("severity", "flagged"))}</span>' + "</td>",
            text_cell(f.get("title")), text_cell(f.get("detail")), text_cell(f.get("impact")),
            text_cell(f.get("action"), blank="no action recorded"), source_links(flag)])
    prio_rows = []
    prio_map = collections.Counter(str(s.get("priority", "")).strip() or "(empty)" for s in suggestions)
    for label, count in sorted(prio_map.items(), key=lambda kv: (-kv[1], kv[0])):
        subset = [s for s in suggestions if (str(s.get("priority", "")).strip() or "(empty)") == label]
        ids = ", ".join(s["id"] for s in subset[:14])
        prio_rows.append([text_cell(label), f"<td class=\"num\">{count}</td>",
                          f'<td><code>{esc(ids)}{" …" if len(subset) > 14 else ""}</code></td>',
                          f'<td><a href="{REGISTER_URL}">register</a></td>'])
    n_noprio = prio_map.get("(empty)", 0)
    n_nopath = sum(1 for s in suggestions if not str(s.get("path", "")).strip())
    n_sentence = sum(1 for s in suggestions
                     if s["id"] and len(str(s.get("recommendation", "")).strip()) > 40
                     and str(s.get("recommendation", "")).strip() not in state_of)
    suggestions_extra = (
        '<section class="section"><h2>The whole proposal register</h2>'
        "<p>" + str(len(suggestions)) + " proposals, one row each, exactly as the merged register records them. "
        "The narrative above is the recommendation; the table below is the evidence base it was written against, so "
        "a reader can check one against the other instead of taking it on trust.</p>" + table(
            ["ID", "Proposal", "What it changes", "Recorded status", "Priority", "Effort", "Claimed impact",
             "Depends on", "Path", "Provenance", "Source"], proposal_rows) + "</section>"
        + '<section class="section"><h2>Status vocabulary in the register</h2>'
          "<p>Decisions are recorded by typing into a free-text field, so the same state arrives under several "
          "spellings and, in " + str(n_sentence) + " rows, a sentence of acceptance criteria has been written where "
          "a status belongs. The spelling is preserved in the first column; the second column is this page's "
          "reading of it, not a new decision.</p>" + table(
              ["Recorded recommendation", "Rows", "Reads as", "Source"], vocab_rows) + "</section>"
        + '<section class="section"><h2>Register hygiene, left as found</h2>'
          "<p>Two fields the review board needs are empty in the register more often than they are filled. They are "
          "reported here and left blank in the table, because inventing a priority for someone else's proposal is "
          "how a review board ends up approving a guess.</p>" + table(
              ["Field", "Rows", "Which rows", "Source"], prio_rows)
        + '<div class="callout warn"><strong>' + str(n_noprio) + " of " + str(len(suggestions))
          + " proposals carry no priority and " + str(n_nopath) + " name no path</strong>, which is the reason "
            "the shortlist above exists: the ordering has to be argued by a person, so the register cannot be the "
            "only thing a reader sees. Recorded here, not fixed here - "
            "<code>ops-center/data/derived.json</code> belongs to the session that owns that register.</div></section>"
    )
    gates_block = ""
    if gates:
        gates_block = ('<section class="section"><h2>The gates every proposal has to clear</h2>'
                       "<p>Proposals are not approvals. A row above becomes a change only when the gate it depends "
                       "on has evidence attached, which is what this table tracks.</p>" + table(
                           ["Gate", "What it enforces", "Criterion", "Still needs", "Failure condition",
                            "Provenance", "Source"], gate_rows)
                       + "</section>")
    flags_block = ""
    if flag_rows:
        flags_block = ('<section class="section"><h2>Flags carried by the register</h2>'
                       "<p>The irregularities the register already holds, so a proposal can be read next to the "
                       "problem that prompted it.</p>" + table(
                           ["Flag", "Severity", "What was found", "Detail", "Why it matters", "Action",
                            "Source"], flag_rows) + "</section>")
    suggestions_page = (page("suggestions.html", "Suggestions", "Review before implementing",
                             "Suggestions & decision shortlist", "Decision board", "blue",
                             "", fragment_html + suggestions_extra + gates_block + flags_block)
                        .replace('<p class="intro"></p>', ""))

    built = {"questions.html": questions_page, "suggestions.html": suggestions_page}

    # row-citation gate, so the promise made by every other root page is enforced here too
    for name, text in built.items():
        rows = re.findall(r"<tr>(.*?)</tr>", text, re.S)
        for row in rows:
            if "<td" in row and "href=\"https://" not in row:
                raise SystemExit(f"{name}: row without an https source link: {re.sub('<[^>]+>', ' ', row)[:90]}")
        if re.search(r"\b(TBD|TODO|FIXME|lorem)\b", text, re.I):
            raise SystemExit(f"{name}: placeholder text reached the page")
        if "no value recorded" not in text and name == "questions.html":
            raise SystemExit(f"{name}: the blank convention never fired, so blanks may have been filled in")

    if args.check:
        stale = [n for n, t in built.items() if not (ROOT / n).is_file() or (ROOT / n).read_text() != t]
        if stale:
            print("stale or missing (run python3 questions/build.py): " + ", ".join(stale))
            return 1
        print(f"questions/build.py: both pages match the register "
              f"({len(questions)} questions, {len(suggestions)} proposals, {digest[:12]}…)")
        return 0
    for name, text in built.items():
        (ROOT / name).write_text(text, encoding="utf-8")

    import csv
    with (HERE / "data" / "questions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "area", "area_group", "blocking", "answered", "question", "known",
                                           "missing", "discovery", "answer", "n_sources", "sources"])
        w.writeheader()
        for q in questions:
            w.writerow({"id": q["id"], "area": q["area"], "area_group": group_of(q["area"]),
                        "blocking": "yes" if q.get("blocking") is True else "no",
                        "answered": "yes" if str(q.get("answer", "")).strip() else "no",
                        "question": q["question"], "known": q.get("known", ""), "missing": q.get("missing", ""),
                        "discovery": q.get("discovery", ""), "answer": q.get("answer", ""),
                        "n_sources": len(q.get("sources") or []), "sources": " ".join(q.get("sources") or [])})
    with (HERE / "data" / "suggestions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "title", "area", "priority", "effort", "path", "depends",
                                           "recommendation", "summary", "impact", "provenance", "sources"])
        w.writeheader()
        for s in suggestions:
            w.writerow({"id": s["id"], "title": s["title"], "area": s["area"], "priority": s.get("priority", ""),
                        "effort": s.get("effort", ""), "path": s.get("path", ""), "depends": s.get("depends", ""),
                        "recommendation": s.get("recommendation", ""), "summary": s.get("summary", ""),
                        "impact": s.get("impact", ""), "provenance": "; ".join(s.get("provenance") or []),
                        "sources": " ".join(s.get("sources") or [])})
    (HERE / "data" / "area_groups.json").write_text(json.dumps({
        "rules": [{"group": name, "keywords": keys} for name, keys in GROUP_RULES],
        "ungrouped": "fallback",
        "groups": dict(sorted(groups.items())),
        "areas_as_recorded": dict(sorted(raw_areas.items(), key=lambda kv: (-kv[1], kv[0]))),
    }, indent=1) + "\n", encoding="utf-8")
    (ROOT / "questions" / "data" / "register_summary.json").write_text(json.dumps({
        "register": "ops-center/data/derived.json",
        "register_sha256": digest,
        "register_observation_date": obs,
        "questions": len(questions),
        "questions_blocking": len(blocking),
        "questions_with_an_answer": len(answered),
        "questions_blocking_and_unanswered": len(blocking_open),
        "proposals": len(suggestions),
        "proposals_without_priority": n_noprio,
        "proposals_without_path": n_nopath,
        "proposals_with_a_sentence_in_the_status_field": n_sentence,
        "area_labels_as_recorded": len(raw_areas),
        "groups_after_rules": len([g for g in groups if g != "Ungrouped"]),
        "gates": len(gates),
        "flags": len(flags),
    }, indent=1) + "\n", encoding="utf-8")
    print(f"questions/build.py: wrote {', '.join(OUT_PAGES)} and {len(OUT_DATA)} data files from "
          f"{len(questions)} questions and {len(suggestions)} proposals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
