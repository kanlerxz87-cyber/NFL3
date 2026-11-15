#!/usr/bin/env python3
"""Build the enhanced canonical R01-R26 matrix in the existing landing-page slot.

The decision-lab register supplies recorded status/evidence/next steps and registered sources.
The criteria file contains proposed project-policy thresholds, not NFL facts or model results.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "decision-lab/data/catalog.json"
CRITERIA_PATH = ROOT / "decision-readiness/data/criteria.json"
INDEX_PATH = ROOT / "index.html"
START = "<!-- DECISION_READINESS_START -->"
END = "<!-- DECISION_READINESS_END -->"
LEGACY_START = '<div class="section-head"><div><div class="section-label">00 / DECISION READINESS</div>'
LEGACY_END = '<div class="section-head"><div><div class="section-label">DATED SNAPSHOT / 2026-11-12</div>'

# Exact host allowlist for registry links used by the 26 canonical rows. Host approval
# does not prove that a source supports unrelated claims; registered scope/limits render per row.
APPROVED_SOURCE_HOSTS = {
    "nfl.com", "www.nfl.com", "operations.nfl.com", "support.nfl.com",
    "nextgenstats.nfl.com", "www.commanders.com", "www.steelers.com",
    "www.houstontexans.com", "docs.github.com", "itl.nist.gov",
    "www.itl.nist.gov", "scikit-learn.org",
}


def load_data() -> tuple[dict, dict, dict[str, dict], dict[str, dict]]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    criteria_doc = json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))
    requirements = catalog.get("requirements", [])
    sources = {row["id"]: row for row in catalog.get("sources", [])}
    gates = {row["id"]: row for row in catalog.get("gates", [])}
    criteria_rows = criteria_doc.get("criteria", [])
    criteria = {row.get("req_id", ""): row for row in criteria_rows}
    errors: list[str] = []

    req_ids = [row.get("id", "") for row in requirements]
    if len(req_ids) != len(set(req_ids)):
        errors.append("duplicate requirement IDs in decision-lab/data/catalog.json")
    crit_ids = [row.get("req_id", "") for row in criteria_rows]
    if len(crit_ids) != len(set(crit_ids)):
        errors.append("duplicate req_id values in decision-readiness/data/criteria.json")
    if set(req_ids) != set(crit_ids):
        errors.append(
            "criteria IDs do not match catalog requirements "
            f"(missing={sorted(set(req_ids)-set(crit_ids))}, extra={sorted(set(crit_ids)-set(req_ids))})"
        )
    if not criteria_doc.get("criteria_date", "").strip():
        errors.append("proposed acceptance criteria date is missing")
    if "proposed" not in criteria_doc.get("classification", "").lower():
        errors.append("criteria classification must explicitly say proposed")

    for req in requirements:
        req_id = req.get("id", "")
        item = criteria.get(req_id)
        if item is None:
            continue
        if not item.get("number", "").strip() or not re.search(r"\d", item["number"]):
            errors.append(f"{req_id}: missing proposed numeric clearance target")
        if not item.get("criterion", "").strip():
            errors.append(f"{req_id}: missing clearance evidence rule")
        if not item.get("basis", "").strip():
            errors.append(f"{req_id}: missing proposed-target basis/caveat")
        gate_ids = item.get("gates", [])
        if not gate_ids:
            errors.append(f"{req_id}: no blocking gate is mapped")
        for gate_id in gate_ids:
            if gate_id not in gates:
                errors.append(f"{req_id}: unknown blocking gate {gate_id}")
            elif not gates[gate_id].get("fail", "").strip():
                errors.append(f"{req_id}: blocking gate {gate_id} has no failure condition")

        # Deliberately use only the source ID already registered on this canonical requirement.
        source_id = req.get("source", "")
        source = sources.get(source_id)
        if not source:
            errors.append(f"{req_id}: registered source ID {source_id!r} is absent from the official-source registry")
            continue
        parsed = urlsplit(source.get("url", ""))
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in APPROVED_SOURCE_HOSTS:
            errors.append(f"{req_id}: source is not an approved HTTPS registry host: {source.get('url', '')}")
        if not source.get("publisher", "").strip() or not source.get("title", "").strip():
            errors.append(f"{req_id}: registered source title or publisher is missing")

    if errors:
        raise ValueError("\n".join(errors))
    return catalog, criteria_doc, criteria, gates


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def source_link(source: dict) -> str:
    label = f"{source['title']} — {source['publisher']}"
    scope = source.get("scope", "")
    limit = source.get("limit", "")
    title = "; ".join(part for part in (scope, limit) if part)
    return (
        f'<a class="source" href="{esc(source["url"])}" target="_blank" '
        f'rel="noopener noreferrer" title="{esc(title)}">{esc(label)} ↗</a>'
        f'<details><summary>Source scope and limits</summary>'
        f'<p>{esc(scope) or "Source scope not recorded; treat coverage as unverified."}</p>'
        f'<p><b>Limit:</b> {esc(limit) or "No source limitation is recorded; verify before relying on it."}</p></details>'
    )


def render_section() -> str:
    catalog, criteria_doc, criteria, gates = load_data()
    requirements = catalog["requirements"]
    sources = {row["id"]: row for row in catalog["sources"]}
    updated = catalog.get("updated", "") or "not recorded"
    state_counts = Counter(row.get("state", "unverified") for row in requirements)
    gate_page = "decision-lab/validation.html"
    state_class = {"implemented": "ok", "partial": "warn", "blocked": "danger"}

    rows: list[str] = []
    for req in requirements:
        req_id = req["id"]
        item = criteria[req_id]
        source = sources[req["source"]]
        status = req.get("state", "unverified").lower()
        pill = f'<span class="pill {state_class.get(status, "warn")}">{esc(status)}</span>'
        evidence = req.get("evidence", "")
        next_step = req.get("next", "")
        evidence_text = esc(evidence) if evidence else '<span class="unverified">UNVERIFIED — no evidence is recorded.</span>'
        next_text = esc(next_step) if next_step else '<span class="unverified">UNVERIFIED — no next step is recorded.</span>'

        gate_items = []
        failure_items = []
        for gate_id in item["gates"]:
            gate = gates[gate_id]
            gate_items.append(
                f'<a href="{gate_page}" title="{esc(gate.get("rule", ""))}">'
                f'{esc(gate_id)} {esc(gate["name"])}</a>'
            )
            failure_items.append(
                f'<li><b>{esc(gate_id)} {esc(gate["name"])}:</b> {esc(gate["fail"])}</li>'
            )
        rows.append(
            f'<tr><td>{esc(req_id)}</td>'
            f'<td>{esc(req["requirement"])}</td>'
            f'<td>{pill}<details><summary>Recorded evidence and next step</summary>'
            f'<p><b>Evidence recorded:</b> {evidence_text}</p>'
            f'<p><b>Recorded next step / blocker:</b> {next_text}</p></details></td>'
            f'<td>{"<br>".join(gate_items)}'
            f'<div class="readiness-next"><b>Gate failure conditions:</b><ul>{"".join(failure_items)}</ul></div></td>'
            f'<td><strong>{esc(item["number"])}</strong>'
            f'<div>{esc(item["criterion"])}</div>'
            f'<small class="readiness-basis">Proposed basis: {esc(item["basis"])}</small></td>'
            f'<td>{source_link(source)}</td></tr>'
        )

    count = len(requirements)
    implemented = state_counts.get("implemented", 0)
    partial = state_counts.get("partial", 0)
    blocked = state_counts.get("blocked", 0)
    recorded_summary = ", ".join(f"{n} {state}" for state, n in sorted(state_counts.items()))
    return (
        f'{START}\n'
        '<div class="section-head"><div><div class="section-label">00 / DECISION READINESS</div>'
        '<h2>One row per requirement: the recorded state, blocking gates and proposed clearance rule.</h2>'
        '<p>Each canonical R-series row links to its registered source and records evidence, the next step, '
        'the gate failure condition and a measurable proposal for clearing the requirement. '
        '<a href="readiness.html">Open the full-scope gate register and flagged irregularities →</a></p></div></div>'
        '<div class="notice"><b>Evidence boundary.</b> Recorded state/evidence below is copied from '
        f'<code>decision-lab/data/catalog.json</code> (last updated {esc(updated)}), not a live or reverified status. '
        f'That snapshot records {esc(recorded_summary)} across {count} requirements. '
        f'Clearance targets are proposed internal acceptance criteria dated {esc(criteria_doc["criteria_date"])}; '
        'they are not official NFL facts or observed performance. A registered source link supports only its '
        'recorded scope, not the target, data rights or model skill. Missing empirical values stay blank and are '
        'flagged for review.</div>'
        '<div class="table-wrap"><table id="decision-readiness-table">'
        '<caption>Canonical R01–R26 readiness matrix. A row clears only when the proposed evidence rule is met and every named gate passes.</caption>'
        '<thead><tr><th scope="col">ID</th><th scope="col">Requirement</th>'
        '<th scope="col">Recorded state, evidence and next step</th>'
        '<th scope="col">Blocking gates and failure conditions</th>'
        '<th scope="col">Proposed measurable clearance target</th>'
        '<th scope="col">Registered source / scope and limits</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        f'<div class="notice warn"><b>Readiness summary:</b> {implemented} of {count} requirements implemented, '
        f'{partial} partial, {blocked} blocked. These are catalog labels as of {esc(updated)}, not a claim of current '
        'completion. See the <a href="flagged.html">root Flagged for Review</a> page for the Game Book reuse restriction '
        'and other open issues.</div></div>\n'
        f'{END}'
    )


def update_index(section: str, *, write: bool) -> bool:
    text = INDEX_PATH.read_text(encoding="utf-8")
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("index.html must contain either zero readiness markers or exactly one matched pair")
    if START in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        updated = before + section + after
    else:
        # PR #69 already added the canonical 26-row table. Replace that block in place so the
        # proposed criteria and per-row evidence enhance the single matrix rather than duplicating it.
        if text.count(LEGACY_START) != 1 or text.count(LEGACY_END) != 1:
            raise ValueError("could not find the unique existing root decision-readiness block")
        start = text.index(LEGACY_START)
        end = text.index(LEGACY_END, start)
        updated = text[:start] + section + "\n" + text[end:]
    if write:
        INDEX_PATH.write_text(updated, encoding="utf-8")
    return updated == INDEX_PATH.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the root matrix differs from generated output")
    args = parser.parse_args()
    try:
        section = render_section()
        catalog, _, _, _ = load_data()
        if args.check:
            current = INDEX_PATH.read_text(encoding="utf-8")
            if START not in current or END not in current:
                raise ValueError("decision-readiness matrix has not been generated")
            before, rest = current.split(START, 1)
            _, after = rest.split(END, 1)
            expected = before + section + after
            if expected != current:
                raise ValueError("index.html readiness matrix is stale; run python3 decision-readiness/scripts/build.py")
            print(f"Decision readiness: {len(catalog['requirements'])} canonical requirements, proposed criteria, gates and registered source rows match the input registers.")
        else:
            update_index(section, write=True)
            print("Rendered the enhanced decision-readiness matrix in the existing root landing-page slot.")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Decision readiness build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
