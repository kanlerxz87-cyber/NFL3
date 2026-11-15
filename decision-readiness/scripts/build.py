#!/usr/bin/env python3
"""Render the canonical requirement readiness table into the root landing page.

The source register (decision-lab/data/catalog.json) supplies recorded status/evidence.
The thresholds in data/criteria.json are project proposals, not verified NFL facts.
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

# Exact host allowlist for the primary NFL, club, statistics, method and platform
# references used by the 26 canonical requirement rows. Host approval does not
# prove that a source supports unrelated claims; the row's source scope is shown.
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
        errors.append(f"criteria IDs do not match catalog requirements (missing={sorted(set(req_ids)-set(crit_ids))}, extra={sorted(set(crit_ids)-set(req_ids))})")

    for req in requirements:
        req_id = req.get("id", "")
        item = criteria.get(req_id)
        if item is None:
            continue
        if not item.get("number", "").strip() or not re.search(r"\d", item["number"]):
            errors.append(f"{req_id}: missing proposed numeric clearance target")
        if not item.get("criterion", "").strip():
            errors.append(f"{req_id}: missing clearance criterion")
        if not item.get("basis", "").strip():
            errors.append(f"{req_id}: missing threshold basis/caveat")
        for gate_id in item.get("gates", []):
            if gate_id not in gates:
                errors.append(f"{req_id}: unknown blocking gate {gate_id}")
        source_id = req.get("source", "")
        source = sources.get(source_id)
        if not source:
            errors.append(f"{req_id}: source ID {source_id!r} is absent from the official-source registry")
            continue
        parsed = urlsplit(source.get("url", ""))
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in APPROVED_SOURCE_HOSTS:
            errors.append(f"{req_id}: source is not an approved official HTTPS host: {source.get('url', '')}")
        if not source.get("publisher", "").strip():
            errors.append(f"{req_id}: official-source publisher is missing")

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
        f'<p>{esc(scope) or "Source scope not recorded."}</p>'
        f'<p><b>Limit:</b> {esc(limit) or "No source limitation recorded."}</p></details>'
    )


def render_section() -> str:
    catalog, criteria_doc, criteria, gates = load_data()
    requirements = catalog["requirements"]
    updated = catalog.get("updated", "") or "not recorded"
    state_counts = Counter(row.get("state", "unverified") for row in requirements)
    gate_page = "decision-lab/validation.html"

    rows: list[str] = []
    for req in requirements:
        req_id = req["id"]
        item = criteria[req_id]
        source = next(row for row in catalog["sources"] if row["id"] == req["source"])
        gate_items = []
        for gate_id in item["gates"]:
            gate = gates[gate_id]
            gate_items.append(
                f'<a href="{gate_page}" title="{esc(gate.get("rule", ""))}">'
                f'{esc(gate_id)} {esc(gate["name"])}</a>'
            )
        status = req.get("state", "unverified").replace("_", " ").title()
        evidence = req.get("evidence", "")
        next_step = req.get("next", "")
        rows.append(
            f'<tr id="{esc(req_id)}">'
            f'<td><strong>{esc(req_id)}</strong></td>'
            f'<td><strong>{esc(req["requirement"])}</strong>'
            f'<div class="readiness-state">Recorded state: {esc(status)} (register date {esc(updated)})</div>'
            f'<details><summary>Recorded evidence and next step</summary>'
            f'<p><b>Evidence recorded:</b> {esc(evidence)}</p>'
            f'<p><b>Recorded next step / blocker:</b> {esc(next_step)}</p></details></td>'
            f'<td>{"<br>".join(gate_items)}'
            f'<div class="readiness-next"><b>Gate failure condition:</b> '
            f'{"; ".join(esc(gates[g]["fail"]) for g in item["gates"])}</div></td>'
            f'<td><strong>{esc(item["number"])}</strong>'
            f'<div>{esc(item["criterion"])}</div>'
            f'<small class="readiness-basis">{esc(item["basis"])}</small></td>'
            f'<td>{source_link(source)}</td></tr>'
        )

    recorded_summary = ", ".join(
        f"{count} {state}" for state, count in sorted(state_counts.items())
    )
    return (
        f'{START}\n'
        '<section class="readiness" aria-labelledby="readiness-heading">'
        '<div class="section-head"><div>'
        '<div class="section-label">DECISION READINESS / GATED REQUIREMENTS</div>'
        '<h2 id="readiness-heading">What blocks each requirement — and what clears it?</h2>'
        '<p>One row per canonical R-series requirement. The detailed 75-item suggestions register remains on '
        '<a href="ops-center/suggestions.html">Suggestions</a>; this table does not treat a proposal as a verified result.</p>'
        '</div><p><a href="decision-lab/requirements.html">Open the full requirement register →</a></p></div>'
        '<div class="notice"><b>Evidence boundary.</b> Recorded state/evidence below is copied from '
        f'<code>decision-lab/data/catalog.json</code> (last updated {esc(updated)}), not a live status feed. '
        f'That snapshot records {esc(recorded_summary)} across {len(requirements)} requirements. '
        f'The clearance targets are proposed internal acceptance criteria dated {esc(criteria_doc.get("criteria_date", "not recorded"))}, not official NFL facts or observed performance. '
        'The linked primary source supports the stated source context only; it does not prove the proposed threshold, data rights, or model skill. '
        'Unknown empirical values stay blank and are listed on '
        '<a href="ops-center/flagged.html">Flagged for review</a>.</div>'
        '<div class="table-wrap"><table id="decision-readiness-table">'
        '<caption>Canonical requirement readiness. A row is not cleared until its evidence meets the proposed target and every named gate passes.</caption>'
        '<thead><tr><th scope="col">ID</th><th scope="col">Requirement and recorded status</th>'
        '<th scope="col">Blocking gate(s) and failure condition</th>'
        '<th scope="col">Proposed clearance number and evidence rule</th>'
        '<th scope="col">Official source / context</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        '<p class="footnote">Gate definitions: <a href="decision-lab/validation.html">validation rules</a>. '
        'A positive source link does not mean a requirement has passed. Where a threshold is explicitly described as proposed, it needs governance approval before a prospective evaluation begins.</p>'
        '</section>\n'
        f'{END}'
    )


def update_index(section: str, *, write: bool) -> bool:
    text = INDEX_PATH.read_text(encoding="utf-8")
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("root index must contain either zero readiness markers or exactly one matched pair")
    if START in text:
        before, rest = text.split(START, 1)
        old, after = rest.split(END, 1)
        updated = before + section + after
    else:
        guide = '<div class="section-head"><div><div class="section-label">SITE GUIDE / NAVIGATE BY CATEGORY</div>'
        if text.count(guide) != 1:
            raise ValueError("could not find the unique site-guide insertion point in index.html")
        nav_item = '<a href="ops-center/questions.html"><span>Q</span>Questions</a>'
        if text.count(nav_item) != 1:
            raise ValueError("could not find the unique root category navigation insertion point")
        text = text.replace(nav_item, '<a href="#decision-readiness"><span>D</span>Decision readiness</a>' + nav_item, 1)
        updated = text.replace(guide, section + guide, 1)
    if write:
        INDEX_PATH.write_text(updated, encoding="utf-8")
    return updated == INDEX_PATH.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the root page differs from generated output")
    args = parser.parse_args()
    try:
        section = render_section()
        catalog, _, _, _ = load_data()
        if args.check:
            current = INDEX_PATH.read_text(encoding="utf-8")
            if START not in current or END not in current:
                raise ValueError("decision-readiness section has not been generated")
            before, rest = current.split(START, 1)
            _, after = rest.split(END, 1)
            expected = before + section + after
            if expected != current:
                raise ValueError("index.html readiness section is stale; run python3 decision-readiness/scripts/build.py")
            print(f"Decision readiness: {len(catalog['requirements'])} canonical requirements, gates, clearance targets and official-source rows match the registers.")
        else:
            update_index(section, write=True)
            print("Rendered the decision-readiness section in index.html from the canonical requirement/source registers.")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Decision readiness build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
