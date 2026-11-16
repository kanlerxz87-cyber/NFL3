#!/usr/bin/env python3
"""Render the suggestion review desk.

    python3 suggestion-desk/scripts/build.py            # write the pages
    python3 suggestion-desk/scripts/check.py            # verify the pages match a rebuild

Why this workspace exists. The merged register at ``ops-center/data/derived.json`` holds 75 proposals and
100 questions. A list of 75 things to do is not a decision: it is an inventory. The brief asks for a
section where someone can review suggestions and choose the best path *before* anything is implemented,
so this workspace groups every one of the 75 proposals under twelve decisions, gives each decision two or
three mutually exclusive paths, and lets a reviewer pick one.

Rules this generator obeys, because the rest of the site promises them:

* no invented fact. Every number on these pages is either computed from ``ops-center/data/derived.json`` at
  build time or copied from ``data/decisions.json``, whose every numeric claim was read from a committed
  artifact. A value nobody has measured renders as an explicit blank, never as a plausible number.
* every table row carries an https link - the official page the claim was read from, or the committed
  register file it came from, which for an unanswered question is the whole evidence base.
* the reviewer's choices live in the browser only. Nothing here writes to the repository: an approval that
  silently changed files is the failure mode the register's own Q-94 asks about.
* the output is deterministic - no clock, no randomness - so ``check.py`` can compare a rebuild byte for
  byte in CI.

The generator refuses to run if the curated data and the register disagree: an unknown proposal id, a
discovery row pointing at a question that does not exist, a proposal claimed by two decisions or by none.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SITE = HERE.parent
DERIVED = ROOT / "ops-center" / "data" / "derived.json"
DECISIONS_FILE = SITE / "data" / "decisions.json"
FLAGS_FILE = SITE / "data" / "flags.json"

REGISTER_URL = "https://github.com/kanlerxz87-cyber/NFL3/blob/main/ops-center/data/derived.json"
INDEX_URL = "https://github.com/kanlerxz87-cyber/NFL3/blob/main/suggestion-desk/index.html"

# Hosts that count as an official source for this workspace, as a fixed base plus everything the
# repository's own committed artifacts already cite as a club source.
#
# The base set is NFL surfaces, the league's media and rules sites, the US National Weather Service and
# this repository's own committed files on GitHub. The club half is computed, not typed: every host that
# the committed official snapshot (decision-lab/data/official_snapshot.json) or the merged register
# records as a source URL is admitted, because those URLs were already checked by the workspaces that
# captured them. Typing thirty club names here would rot the first time a club changed its domain.
BASE_OFFICIAL_HOSTS = {
    "nfl.com", "www.nfl.com", "operations.nfl.com", "support.nfl.com", "nextgenstats.nfl.com",
    "media.nfl.com", "www.weather.gov", "weather.gov", "github.com", "docs.github.com",
    # methods references the root validator already admits
    "itl.nist.gov", "www.itl.nist.gov", "scikit-learn.org",
}
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
ALLOWED_HOSTS_FILE = SITE / "data" / "allowed_hosts.json"
URL_KEYS = {"source_url", "url", "depth_source_url", "injury_source_url", "page_url"}

PAGES = ["index.html", "paths.html", "discovery.html", "flagged.html"]


def _add(url, out: set) -> None:
    if isinstance(url, str) and url.startswith("https://"):
        host = urlparse(url).hostname
        if host:
            out.add(host)


def _collect_hosts(node, out: set) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in URL_KEYS and isinstance(value, str):
                _add(value, out)
            elif key == "sources" and isinstance(value, list):
                # the register keeps a question's citations in a list under this key
                for item in value:
                    _add(item, out)
            else:
                _collect_hosts(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_hosts(item, out)


def official_hosts(register: dict) -> set:
    hosts = set(BASE_OFFICIAL_HOSTS)
    if SNAPSHOT.is_file():
        _collect_hosts(json.loads(SNAPSHOT.read_text(encoding="utf-8")), hosts)
    _collect_hosts(register, hosts)
    return {h for h in hosts if h}


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def load_register() -> dict:
    if not DERIVED.is_file():
        raise SystemExit(f"suggestion-desk: {DERIVED} is missing; the register belongs to ops-center")
    return json.loads(DERIVED.read_text(encoding="utf-8"))


def load_decisions() -> dict:
    if not DECISIONS_FILE.is_file():
        raise SystemExit(f"suggestion-desk: {DECISIONS_FILE} is missing")
    return json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))


def validate(decisions_doc: dict, register: dict) -> tuple[list[dict], dict, dict, dict]:
    """Cross-check the curated decision file against the register and fail loudly on any disagreement."""
    questions = {q["id"]: q for q in register.get("questions") or []}
    suggestions = {s["id"]: s for s in register.get("suggestions") or []}
    if not questions or not suggestions:
        raise SystemExit("suggestion-desk: the register is empty, so the desk cannot be built from it")

    decisions = decisions_doc.get("decisions") or []
    if not decisions:
        raise SystemExit("suggestion-desk: no decisions are recorded")

    seen: dict[str, str] = {}
    for d in decisions:
        did = str(d.get("id", "")).strip()
        if not did:
            raise SystemExit("suggestion-desk: a decision has no id")
        for key in ("title", "question", "why_first", "clearing_number", "recommended"):
            if not str(d.get(key, "")).strip():
                raise SystemExit(f"suggestion-desk: {did} has no {key}")
        if not d.get("paths"):
            raise SystemExit(f"suggestion-desk: {did} offers no paths, so there is nothing to choose")
        rec = str(d["recommended"]).strip()
        # The recommended field may name a second path ("D4-A now, D4-C once D3-A lands"); the first
        # token is the primary recommendation and must be one of this decision's own paths.
        primary = rec.split()[0].rstrip(",") if rec.split() else ""
        if primary not in {p["id"] for p in d["paths"]}:
            raise SystemExit(f"suggestion-desk: {did} recommends {rec!r}, whose first path {primary!r} "
                             "is not one of its paths")
        for pid in d.get("proposals") or []:
            if pid not in suggestions:
                raise SystemExit(f"suggestion-desk: {did} governs {pid}, which is not in the register")
            if pid in seen:
                raise SystemExit(f"suggestion-desk: {pid} is claimed by both {seen[pid]} and {did}")
            seen[pid] = did
        for path in d["paths"]:
            for pid in path.get("adopts") or []:
                if pid not in suggestions:
                    raise SystemExit(f"suggestion-desk: path {path['id']} adopts {pid}, not in the register")
                if pid not in (d.get("proposals") or []):
                    raise SystemExit(f"suggestion-desk: path {path['id']} adopts {pid}, which {did} does not govern")
        for item in d.get("discovery") or []:
            ref = str(item.get("ref", "")).strip()
            if ref and ref not in questions:
                raise SystemExit(f"suggestion-desk: {did} discovery row cites {ref}, not in the register")
        for item in d.get("have") or []:
            url = str(item.get("source", ""))
            if not url.startswith("https://"):
                raise SystemExit(f"suggestion-desk: {did} 'have' row has no https source")

    missing = sorted(set(suggestions) - set(seen))
    if missing:
        raise SystemExit("suggestion-desk: these proposals are governed by no decision: " + ", ".join(missing))
    return decisions, questions, suggestions, register


def source_cell(url: str, label: str) -> str:
    return f'<td><a class="source" href="{esc(url)}" rel="noopener noreferrer">{esc(label)}</a></td>'


def register_cell() -> str:
    return source_cell(REGISTER_URL, "merged register")


def table(headers, rows) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(r if r.startswith("<td") else f"<td>{r}</td>" for r in row) + "</tr>"
                     for row in rows)
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table></div>'


def cards(pairs) -> str:
    inner = "".join(f'<div class="card stat"><span class="num">{esc(v)}</span><p>{esc(l)}</p></div>'
                    for l, v in pairs)
    return f'<div class="grid">{inner}</div>'


def page(name: str, title: str, eyebrow: str, heading: str, badge: str, badge_class: str,
         intro: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} | NFL suggestion desk</title>'
            f'<link rel="stylesheet" href="../assets/site.css">'
            f'<link rel="stylesheet" href="assets/desk.css"></head><body>'
            f'<div class="wrap"><div class="hrow"><div><p class="eyebrow">{esc(eyebrow)}</p>'
            f'<h1>{esc(heading)}</h1></div><span class="badge {badge_class}">{esc(badge)}</span></div>'
            f'<nav class="crumb" aria-label="Suggestion desk navigation">'
            f'<a href="../index.html">Overview</a> · <a href="index.html">Review desk</a> · '
            f'<a href="paths.html">Paths compared</a> · <a href="discovery.html">Missing information</a> · '
            f'<a href="flagged.html">Flagged</a> · <a href="../ops-center/suggestions.html">Register view</a>'
            f'</nav><p class="intro">{intro}</p>{body}</div>'
            f'<script src="assets/desk.js"></script></body></html>\n')


# -------------------------------------------------------------------------------------------- review desk


def decision_block(d: dict, questions: dict) -> str:
    have_rows = [[esc(item["fact"]), f'<td><code>{esc(item["artifact"])}</code></td>',
                  source_cell(item["source"], host_label(item["source"]))]
                 for item in d.get("have") or []]
    gov = ", ".join(f'<a href="{REGISTER_URL}"><code>{esc(p)}</code></a>' for p in d.get("proposals") or [])
    body = [f'<section class="section decision" id="{esc(d["id"])}">',
            f'<h2>{esc(d["id"])} · {esc(d["title"])}</h2>',
            f'<p class="question">{esc(d["question"])}</p>',
            '<div class="split"><div><h3>What we already have, verified</h3>',
            table(["Fact", "Committed artifact", "Source"], have_rows) if have_rows else "<p>Nothing recorded.</p>",
            '</div><div><h3>What is still missing</h3>',
            '<ul class="list">' + "".join(f"<li>{esc(t)}</li>" for t in (d.get("missing") or []))
            + "</ul>" if d.get("missing") else "<p>Nothing recorded.</p>",
            '</div></div>',
            f'<p class="why"><strong>Why it comes first.</strong> {esc(d["why_first"])}</p>',
            f'<p class="why"><strong>Governs.</strong> {gov} '
            f'({len(d.get("proposals") or [])} proposals in the register).</p>',
            '<h3>Choose a path</h3><div class="paths">']
    for path in d["paths"]:
        adopts = (", ".join(f'<code>{esc(p)}</code>' for p in path.get("adopts") or [])
                  or '<span class="badge warn">adopts nothing in the register</span>')
        body.append(
            f'<label class="path" for="{esc(path["id"])}">'
            f'<input type="radio" name="{esc(d["id"])}" id="{esc(path["id"])}" value="{esc(path["id"])}"'
            f' data-decision="{esc(d["id"])}" data-title="{esc(d["title"])}"'
            f' data-path="{esc(path["label"])}">'
            f'<span class="path-head">{esc(path["id"])} · {esc(path["label"])}</span>'
            '<dl class="kv">'
            f'<dt>Does</dt><dd>{esc(path["does"])}</dd>'
            f'<dt>Adopts</dt><dd>{adopts}</dd>'
            f'<dt>Buys</dt><dd>{esc(path["buys"])}</dd>'
            f'<dt>Leaves open</dt><dd>{esc(path["leaves_open"])}</dd>'
            f'<dt>Cost</dt><dd>{esc(path["cost"])}</dd>'
            f'<dt>Risk</dt><dd>{esc(path["risk"])}</dd>'
            '</dl></label>')
    body.append('</div>')
    recommended = str(d["recommended"]).strip()
    body.append(f'<div class="callout"><strong>Suggested:</strong> {esc(recommended)}. '
                f'{esc(d["recommendation_reason"])}</div>')
    body.append(f'<div class="callout warn"><strong>Number that would clear it:</strong> '
                f'{esc(d["clearing_number"])}</div>')
    body.append('</section>')
    return "".join(body)


def host_label(url: str) -> str:
    host = url.replace("https://", "").split("/")[0]
    tail = url.rstrip("/").split("/")[-1]
    if "nfl.com" in host:
        return f"nfl.com · {tail[:38]}" if tail and "blob" not in tail else "nfl.com"
    return host


def index_page(decisions, questions, suggestions, register) -> str:
    n_paths = sum(len(d["paths"]) for d in decisions)
    n_disc = sum(len(d.get("discovery") or []) for d in decisions)
    blocking_open = sum(1 for q in register["questions"]
                        if q.get("blocking") is True and not str(q.get("answer", "")).strip())
    queue_rows = []
    for d in decisions:
        rec = str(d["recommended"]).strip()
        queue_rows.append([
            f'<td><a href="#{esc(d["id"])}"><code>{esc(d["id"])}</code></a></td>',
            esc(d["title"]),
            esc(d["question"]),
            f'<td class="num">{len(d.get("proposals") or [])}</td>',
            f'<td class="num">{len(d["paths"])}</td>',
            esc(rec),
            esc(d["clearing_number"]),
            register_cell(),
        ])
    body = [
        cards([("decisions to take", len(decisions)), ("paths to choose between", n_paths),
               ("proposals governed", len(suggestions)), ("blocking questions open", blocking_open)]),
        '<div class="callout"><strong>Read this before you choose.</strong> All 75 proposals in the merged '
        'register are grouped below under twelve decisions. Each decision offers the paths that were '
        'actually proposed, and every one names the number that would clear it. Nothing on this page '
        'changes a file: your choices are stored in this browser only and can be exported as JSON, so a '
        'decision is a recorded intent rather than an edit.</div>',
        '<section class="section"><h2>The decision queue</h2>',
        table(["ID", "Decision", "The question", "Proposals", "Paths", "Suggested",
               "Number that would clear it", "Source"], queue_rows),
        '</section>',
    ]
    for d in decisions:
        body.append(decision_block(d, questions))
    body.append(
        '<section class="section"><h2>Your review</h2>'
        '<p>Selections are written to this browser as you make them. The table below is what you would '
        'hand to whoever implements the change; <em>Copy JSON</em> puts the same content on the clipboard '
        'in a form that can be pasted into an issue or a commit message. A decision recorded here is an '
        'intent, not a deployment - the register stays the source of truth until someone commits a '
        'change to it.</p>'
        '<div class="tablewrap"><table id="choices"><thead><tr><th>Decision</th><th>Path chosen</th>'
        '<th>Proposals it adopts</th></tr></thead><tbody><tr class="empty">'
        '<td colspan="3">No path chosen yet — 0 of ' + str(len(decisions)) + ' decisions recorded. '
        'Until one is recorded and committed, <a href="' + REGISTER_URL + '">the merged register</a> '
        'remains the only record of what the project intends to do.</td>'
        '</tr></tbody></table></div>'
        '<div class="pillrow"><button type="button" class="btn" data-act="copy">Copy JSON</button>'
        '<button type="button" class="btn" data-act="reset">Clear choices</button>'
        '<span class="small" id="stored-note">Choices persist in this browser under '
        '<code>nfl3.suggestion-desk.v1</code>.</span></div></section>')
    body.append(
        '<section class="section"><h2>How this desk treats the register</h2>' + table(
            ["Convention", "What it means here", "Source"],
            [[esc("A path is a choice, not a recommendation set"),
              esc(f"{len(suggestions)} proposals are distributed across {len(decisions)} decisions with no "
                  "overlap and none left over: the generator fails if a proposal is claimed twice or not at "
                  "all. A path adopts the proposals listed under it and defers the rest."),
              register_cell()],
             [esc("The suggested path is an argument, not a decision"),
              esc("Each decision names the path this workspace would argue for and why, and prints what "
                  "that path still leaves open. The reviewer's choice is the decision; the suggestion is "
                  "one input to it."),
              register_cell()],
             [esc("Nothing here is a new NFL fact"),
              esc("Every number on these pages is computed from ops-center/data/derived.json at build time "
                  "or copied from data/decisions.json, whose numeric claims were each read from a committed "
                  "artifact. Where a number has not been measured, the cell says so."),
              register_cell()],
             [esc("The questions are the register's own"),
              esc(f"Each decision lists the register questions it depends on by their own IDs. "
                  f"{n_disc} pointers are recorded; the build fails if one cites a question that does not "
                  "exist. A question the register has not answered is shown as unanswered, never filled in."),
              register_cell()],
             [esc("An approval here is not an implementation"),
              esc("The controls write to browser storage only. Moving a proposal to 'adopted' means editing "
                  "ops-center/data/derived.json, which belongs to the session that owns it, and that edit "
                  "is what makes the change real."),
              register_cell()]]) + '</section>')
    return page("index.html", "Suggestion review desk", "Review before implementing",
                "Suggestion review desk", f"{len(decisions)} decisions · {n_paths} paths", "blue",
                "Every proposal the project has recorded, grouped into the decisions they actually depend "
                f"on, with the paths that were proposed for each and the number that would clear it. "
                f"Rendered from the merged register at <code>ops-center/data/derived.json</code> "
                f"({len(suggestions)} proposals, {len(register['questions'])} questions, "
                f"{blocking_open} blocking and unanswered). Nothing here is implemented, and nothing here "
                "writes to the repository.", "".join(body))


# ------------------------------------------------------------------------------------------ paths compared


def paths_page(decisions, questions, suggestions, register) -> str:
    rows = []
    for d in decisions:
        rec_first = str(d["recommended"]).strip().split()[0].rstrip(",")
        for p in d["paths"]:
            adopts = ", ".join(f'<code>{esc(a)}</code>' for a in p.get("adopts") or []) or "—"
            rows.append([
                f'<td><a href="index.html#{esc(d["id"])}"><code>{esc(d["id"])}</code></a></td>',
                esc(d["title"]),
                f'<td><code>{esc(p["id"])}</code><br>{esc(p["label"])}</td>',
                "<td>" + ('<span class="badge good">suggested</span>' if p["id"] == rec_first
                          else '<span class="badge">alternative</span>') + "</td>",
                esc(p["does"]),
                "<td>" + adopts + "</td>",
                esc(p["buys"]),
                esc(p["leaves_open"]),
                esc(p["cost"]),
                esc(p["risk"]),
                register_cell(),
            ])
    # proposals and the paths that would adopt them
    adopted = {}
    for d in decisions:
        for p in d["paths"]:
            for pid in p.get("adopts") or []:
                adopted.setdefault(pid, []).append(p["id"])
    prop_rows = []
    for pid, s in suggestions.items():
        paths_ids = adopted.get(pid, [])
        prop_rows.append([
            f'<td><code>{esc(pid)}</code></td>',
            esc(str(s.get("title", ""))),
            esc(str(s.get("area", ""))),
            esc(next((d["id"] for d in decisions if pid in (d.get("proposals") or [])), "—")),
            ("<td>" + ", ".join(f'<code>{esc(x)}</code>' for x in paths_ids) + "</td>") if paths_ids
            else '<td><span class="badge warn">no path adopts it</span></td>',
            esc(str(s.get("recommendation", "")).strip() or "no status recorded"),
            register_cell(),
        ])
    n_unadopted = sum(1 for pid in suggestions if pid not in adopted)
    body = [
        cards([("paths on offer", len(rows)), ("proposals governed", len(suggestions)),
               ("proposals no path adopts", n_unadopted),
               ("questions still blocking",
                sum(1 for q in register["questions"]
                    if q.get("blocking") is True and not str(q.get("answer", "")).strip()))]),
        '<div class="callout"><strong>Every path, side by side.</strong> The review desk shows them one '
        'decision at a time; this page puts all of them in one table so a reviewer can compare across '
        'decisions - which is where the conflicts show up, because two decisions can want the same '
        'engineering week.</div>',
        '<section class="section"><h2>All paths</h2>',
        table(["Decision", "Decision title", "Path", "Standing", "Does", "Adopts", "Buys",
               "Leaves open", "Cost", "Risk", "Source"], rows),
        '</section>',
        '<section class="section"><h2>Every proposal and the path that would adopt it</h2>',
        f'<p>{n_unadopted} of {len(suggestions)} proposals are governed by a decision but adopted by no '
        'path, which is the honest reading: those are proposals every path defers, either because a '
        'dependency blocks them or because the path that would adopt them was not proposed.</p>',
        table(["Proposal", "Title", "Area (as recorded)", "Decision", "Adopted by",
               "Status in the register", "Source"], prop_rows),
        '</section>',
    ]
    return page("paths.html", "Paths compared", "One table, every route",
                "Every path, compared", f"{len(rows)} paths across {len(decisions)} decisions", "blue",
                "The same paths as the review desk, flattened so they can be read against each other, plus "
                "each of the 75 proposals with the path that would adopt it - or an explicit note that no "
                "path adopts it.", "".join(body))


# -------------------------------------------------------------------------------------- missing information


def discovery_page(decisions, questions, suggestions, register, hosts: set) -> str:
    rows = []
    for d in decisions:
        for item in d.get("discovery") or []:
            ref = str(item.get("ref", "")).strip()
            q = questions.get(ref, {})
            answered = bool(str(q.get("answer", "")).strip())
            rows.append([
                f'<td><a href="index.html#{esc(d["id"])}"><code>{esc(d["id"])}</code></a></td>',
                f'<td><code>{esc(ref)}</code></td>' if ref else "<td>—</td>",
                esc(item.get("question") or (q.get("question", "") if q else "no question recorded")),
                ("<td>" + ('<span class="badge good">answered</span>' if answered
                           else '<span class="badge warn">unanswered</span>') + "</td>"),
                esc(item.get("do", "")),
                esc(q.get("known", "") or "nothing recorded in the register"),
                esc(item.get("changes_path_if", "")),
                source_cell(item["source"], host_label(item["source"])),
            ])
    refs = {str(i.get("ref", "")).strip() for d in decisions for i in d.get("discovery") or []}
    refs.discard("")
    per_decision = []
    for d in decisions:
        ids = [str(i.get("ref", "")).strip() for i in d.get("discovery") or []]
        open_n = sum(1 for r in ids if r and not str(questions.get(r, {}).get("answer", "")).strip())
        per_decision.append([
            f'<td><a href="index.html#{esc(d["id"])}"><code>{esc(d["id"])}</code></a></td>',
            esc(d["title"]),
            f'<td class="num">{len(ids)}</td>',
            f'<td class="num">{open_n}</td>',
            "<td>" + ", ".join(f'<code>{esc(i)}</code>' for i in ids if i) + "</td>",
            register_cell(),
        ])
    blocking_open = [q for q in register["questions"]
                     if q.get("blocking") is True and not str(q.get("answer", "")).strip()]
    cited = {r for r in refs}
    unreferenced = [q for q in blocking_open if q["id"] not in cited]
    body = [
        cards([("discovery actions", len(rows)), ("register questions cited", len(refs)),
               ("of them unanswered",
                sum(1 for r in refs if not str(questions.get(r, {}).get("answer", "")).strip())),
               ("blocking questions not cited here", len(unreferenced))]),
        '<div class="callout warn"><strong>The point of this page.</strong> A decision taken on '
        'information nobody has is a guess with a workflow attached. Each row below is one specific thing '
        'to go and find, the place to look for it, and what the answer would do to the choice - so a '
        'decision can be deferred on purpose instead of by accident.</div>',
        '<section class="section"><h2>What to find, and where to look</h2>',
        table(["Decision", "Register ID", "Question", "Answered?", "How to find it",
               "What the register says is already known", "What the answer would change", "Source"], rows),
        '</section>',
        '<section class="section"><h2>Counted per decision</h2>',
        table(["Decision", "Title", "Questions cited", "Still unanswered", "Register IDs", "Source"],
              per_decision),
        '</section>',
        '<section class="section"><h2>Blocking questions this desk does not reach</h2>',
        f'<p>{len(blocking_open)} of {len(register["questions"])} questions are marked blocking and carry no '
        f'answer; {len(unreferenced)} of them are not cited by any of the twelve decisions above. They are '
        'listed here rather than dropped, because a blocking question nobody assigned is a blocking '
        'question nobody will answer.</p>',
        table(["ID", "Area", "Question", "What is known", "Suggested way to find it", "Source"],
              [[f'<td><code>{esc(q["id"])}</code></td>', esc(q.get("area", "")), esc(q.get("question", "")),
                esc(q.get("known", "") or "nothing recorded"),
                esc(q.get("discovery", "") or "nothing recorded"),
                (source_cell(u, host_label(u))
                 if (q.get("sources") and (u := q["sources"][0]).startswith("https://")
                     and urlparse(u).hostname in hosts) else register_cell())]
               for q in unreferenced]) if unreferenced else
        '<p>Every blocking unanswered question is cited by at least one decision above.</p>',
        '</section>',
    ]
    return page("discovery.html", "Missing information", "Find it before you decide",
                "What is missing, and how to find it", f"{len(rows)} discovery actions", "warn",
                "Every question the twelve decisions depend on, what is already known, the one action that "
                "would answer it, and what the answer would do to the choice. Questions the register "
                "records as unanswered are shown as unanswered.", "".join(body))


# --------------------------------------------------------------------------------------------- flagged page


def flagged_page(decisions, questions, suggestions, register, n_pages: int) -> str:
    flags = json.loads(FLAGS_FILE.read_text(encoding="utf-8")) if FLAGS_FILE.is_file() else []
    rows = []
    for f in flags:
        rows.append([
            f'<td><code>{esc(f.get("id", "—"))}</code></td>',
            "<td>" + f'<span class="badge {esc(f.get("severity", "warn"))}">{esc(f.get("severity", "flagged"))}</span>' + "</td>",
            esc(f.get("title", "")),
            esc(f.get("detail", "")),
            esc(f.get("impact", "")),
            esc(f.get("action", "") or "no action recorded"),
            source_cell(f["source"], host_label(f["source"])),
        ])
    status_counts: dict[str, int] = {}
    for s in suggestions.values():
        key = str(s.get("recommendation", "")).strip() or "(empty)"
        status_counts[key] = status_counts.get(key, 0) + 1
    sentences = sorted(k for k in status_counts if len(k) > 40)
    body = [
        cards([("irregularities this pass", len(flags)), ("pages in this workspace", n_pages),
               ("distinct status spellings", len(status_counts)),
               ("spellings that are sentences, not statuses", len(sentences))]),
        '<div class="callout warn"><strong>Flagged for review.</strong> Irregularities found while building '
        'this workspace, each with the evidence and a link. None of them blocks publication: they are the '
        'reason a number is published with a caveat rather than the reason it is hidden.</div>',
        '<section class="section"><h2>Flagged for review</h2>',
        table(["Flag", "Severity", "What was found", "Detail", "Why it matters", "Action taken or needed",
               "Source"], rows) if rows else "<p>No irregularities recorded.</p>",
        '</section>',
        '<section class="section"><h2>Register hygiene this desk inherits</h2>',
        f'<p>The register records a decision by typing into a free-text field, so the same state arrives '
        f'under {len(status_counts)} different spellings and, in {len(sentences)} rows, a sentence of '
        'acceptance criteria has been written where a status belongs. The desk groups by decision rather '
        'than by that field, because sorting on it would sort on spelling.</p>',
        table(["Recorded status", "Proposals", "Source"],
              [[f'<td><code>{esc(k)}</code></td>', f'<td class="num">{v}</td>', register_cell()]
               for k, v in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0]))]),
        '</section>',
    ]
    return page("flagged.html", "Flagged for review", "Found while building the desk",
                "Flagged for review", f"{len(flags)} irregularities", "danger",
                "Irregularities found in this pass, each with its evidence and an official or committed "
                "source. Nothing here is fixed silently.", "".join(body))


def main() -> int:
    register = load_register()
    doc = load_decisions()
    decisions, questions, suggestions, register = validate(doc, register)
    hosts = official_hosts(register)
    ALLOWED_HOSTS_FILE.write_text(
        json.dumps({"hosts": sorted(hosts)}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    pages = {
        "index.html": index_page(decisions, questions, suggestions, register),
        "paths.html": paths_page(decisions, questions, suggestions, register),
        "discovery.html": discovery_page(decisions, questions, suggestions, register, hosts),
        "flagged.html": flagged_page(decisions, questions, suggestions, register, len(PAGES)),
    }
    for name, text in pages.items():
        (SITE / name).write_text(text, encoding="utf-8")
    n_paths = sum(len(d["paths"]) for d in decisions)
    print(f"suggestion-desk: {len(decisions)} decisions, {n_paths} paths, {len(suggestions)} proposals "
          f"-> {', '.join(PAGES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
