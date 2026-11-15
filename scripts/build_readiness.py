#!/usr/bin/env python3
"""Render the canonical readiness detail page from the register and gate data."""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "decision-lab/data/readiness.json"
REQUIREMENTS = ROOT / "decision-lab/requirements.html"
DETAIL = ROOT / "decision-lab/readiness.html"


class RequirementsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: dict[str, dict[str, str]] = {}
        self.row: list[dict[str, str]] | None = None
        self.cell: dict[str, str] | None = None
        self.anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "tr":
            self.row = []
        elif tag == "td" and self.row is not None:
            self.cell = {"text": "", "href": "", "link_text": ""}
            self.row.append(self.cell)
        elif tag == "a" and self.cell is not None:
            self.anchor = {"href": attrs.get("href", ""), "text": ""}

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell["text"] += data
        if self.anchor is not None:
            self.anchor["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.anchor is not None:
            if self.cell is not None and not self.cell["href"]:
                self.cell["href"] = self.anchor["href"]
                self.cell["link_text"] = self.anchor["text"].strip()
            self.anchor = None
        elif tag == "td":
            self.cell = None
        elif tag == "tr":
            if self.row:
                cells = self.row
                req_id = cells[0]["text"].strip() if cells else ""
                if re.fullmatch(r"R\d{2}", req_id):
                    source = next((c for c in reversed(cells) if c["href"].startswith("https://")), None)
                    if source is None:
                        raise ValueError(f"{req_id} has no HTTPS source link in requirements.html")
                    self.rows[req_id] = {
                        "requirement": cells[1]["text"].strip(),
                        "state": cells[2]["text"].strip(),
                        "source": source["href"],
                        "source_label": source["link_text"] or "Open cited source",
                    }
            self.row = None


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def get_requirements() -> dict[str, dict[str, str]]:
    parser = RequirementsParser()
    parser.feed(REQUIREMENTS.read_text(encoding="utf-8"))
    return parser.rows


def matrix(data: dict, reqs: dict[str, dict[str, str]]) -> str:
    rows = []
    for item in data["requirements"]:
        req = reqs[item["id"]]
        state = req["state"]
        state_class = "ok" if state == "implemented" else "warn"
        number = item.get("number")
        number_status = item.get("number_status", "Specified in the documented/project acceptance gate.")
        number_html = esc(number) if number else ""
        if not number:
            number_html = '<span class="blank" aria-label="No verified numeric threshold">&nbsp;</span>'
            number_status = item.get("number_status", "Unverified — no numeric clearance threshold is defined.")
        rows.append(
            "<tr>"
            f"<td>{esc(item['id'])}</td>"
            f"<td>{esc(req['requirement'])}</td>"
            f'<td><span class="pill {state_class}">{esc(state)}</span></td>'
            f"<td>{esc(item['gate'])}</td>"
            f"<td>{esc(item['blocker'])}</td>"
            f"<td>{esc(item['clearance'])}</td>"
            f"<td>{number_html}<small>{esc(number_status)}</small></td>"
            f'<td><a href="{esc(req["source"])}" target="_blank" rel="noopener noreferrer">{esc(req["source_label"])} ↗</a></td>'
            "</tr>"
        )
    return (
        '<div class="tablewrap table-wrap"><table><caption>Every canonical requirement, its blocking gate, current evidence gap, and the explicit clearance condition. The numeric column is blank and flagged where no threshold has been pre-registered or verified.</caption>'
        '<thead><tr><th scope="col">ID</th><th scope="col">Requirement</th><th scope="col">State</th><th scope="col">Blocking gate</th><th scope="col">What blocks it now</th><th scope="col">What would clear it</th><th scope="col">Numeric clearance</th><th scope="col">Source</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    reqs = get_requirements()
    items = data["requirements"]
    item_ids = [x["id"] for x in items]
    if len(item_ids) != len(set(item_ids)) or set(item_ids) != set(reqs):
        raise SystemExit(f"Readiness IDs must match requirement IDs exactly: readiness={len(item_ids)} requirements={len(reqs)}")
    for item in items:
        if not item.get("gate") or not item.get("blocker") or not item.get("clearance"):
            raise SystemExit(f"{item['id']} is missing a gate, blocker, or clearance condition")
        if item.get("number") is None and not item.get("number_status"):
            raise SystemExit(f"{item['id']} has an unverified blank numeric target but no visible flag")
        if urlparse(reqs[item["id"]]["source"]).scheme != "https":
            raise SystemExit(f"{item['id']} has a non-HTTPS source")

    table = matrix(data, reqs)
    detail = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Decision readiness | NFL3 Decision Lab</title><link rel="stylesheet" href="assets/style.css"></head><body><div class="shell"><aside class="side"><a class="brand" href="index.html">NFL3<small>DECISION LAB</small></a><nav class="nav" aria-label="Decision lab navigation"><a href="index.html">Overview</a><a href="requirements.html">Requirements</a><a href="validation.html">Validation gates</a><a href="questions.html">Questions &amp; gaps</a><a href="suggestions.html">Suggestions</a><a href="readiness.html" class="active" aria-current="page">Decision readiness</a><a href="flagged.html">Flagged for review</a></nav><div class="side-note">Readiness is not approval to bet. Unknown values stay blank.</div></aside><div class="main"><header class="top"><span>NFL research / decision support</span><span>As of {esc(data['as_of'])}</span></header><main class="wrap"><div class="eyebrow">Decision gates</div><h1>Decision readiness</h1><p class="lede">{esc(data['note'])}</p><div class="notice danger"><strong>Current boundary:</strong> no strategy, fair line, market residual, correlation estimate or reward is verified for deployment. A cleared site/build gate does not clear data, model or legal gates.</div><div class="notice"><strong>How to read the numeric column:</strong> a number appears only when a documented gate or a concrete completeness check supplies it. A blank numeric cell is intentional and accompanied by an explicit unverified note; do not substitute an estimate. Internal acceptance targets are project gates, not NFL facts. The <a href="../docs/PRE_REGISTRATION.md">pre-registered performance gates</a> and <a href="validation.html">validation-gate definitions</a> state their provenance; a source link in a requirement row does not grant data reuse rights.</div>{table}<p><a href="../index.html">← Repository landing page</a> · <a href="validation.html">All validation gate definitions →</a> · <a href="requirements.html">Full requirement register →</a></p></main><footer class="footer">NFL3 Decision Lab · Research-only. No model or wagering recommendation.</footer></div></div></body></html>'''
    DETAIL.write_text(detail, encoding="utf-8")


if __name__ == "__main__":
    main()
