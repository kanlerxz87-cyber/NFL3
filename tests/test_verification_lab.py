#!/usr/bin/env python3
"""Fail-closed checks for the verification lab.

These checks enforce only what a static build can actually prove:
  1. every built page exists and every local link/asset resolves;
  2. every table row carries a source link;
  3. every claimed host is registered as a trusted authority;
  4. every non-confirmed record has an action and an official source;
  5. blank cells stay blank - no value is injected at render time;
  6. the question register never invents an answer;
  7. the queue's P0 rows reference verification IDs that exist;
  8. no page claims that luck was eliminated, or that a strategy is validated.

They do not prove that a source still shows what it showed when it was opened.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

LAB = Path(__file__).resolve().parents[1] / "verification-lab"
DATA = LAB / "data"
TRUSTED = json.loads((DATA / "recheck.json").read_text())["trusted_hosts"]
LOCAL = {"index.html", "register.html", "questions.html", "queue.html", "methods.html"}

errors: list[str] = []
warnings: list[str] = []


class RowAudit(HTMLParser):
    def __init__(self, name: str):
        super().__init__(convert_charrefs=True)
        self.name = name
        self.in_tbody = 0
        self.row_has_link = False
        self.rows = 0
        self.bad_rows = 0
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tbody":
            self.in_tbody += 1
        elif tag == "tr" and self.in_tbody:
            self.rows += 1
            self.row_has_link = False
        elif tag == "a":
            href = attrs.get("href", "")
            if self.in_tbody:
                self.row_has_link = True
            self._check(href, "a")
        elif tag in {"link", "script", "img"}:
            ref = attrs.get("href") or attrs.get("src") or ""
            self._check(ref, tag)

    def _check(self, href: str, kind: str):
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"}:
            if parsed.scheme != "https":
                errors.append(f"{self.name}: non-HTTPS link {href}")
            if kind == "a" and "//" in href:
                host = href.split("/")[2]
                if not host.endswith("github.io") and host not in TRUSTED:
                    warnings.append(f"{self.name}: link to unregistered host {host}")
            return
        target = (LAB / parsed.path).resolve()
        if not target.exists():
            errors.append(f"{self.name}: broken local reference {href}")

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_tbody:
            if not self.row_has_link:
                self.bad_rows += 1
        elif tag == "tbody":
            self.in_tbody = max(0, self.in_tbody - 1)


def official(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in TRUSTED


def check_registers() -> None:
    recheck = json.loads((DATA / "recheck.json").read_text())
    questions = json.loads((DATA / "questions.json").read_text())
    queue = json.loads((DATA / "queue.json").read_text())

    ids = [r["id"] for r in recheck["records"]]
    if len(ids) != len(set(ids)):
        errors.append("recheck.json: duplicate record ids")
    for r in recheck["records"]:
        for field in ("id", "category", "claim", "observed", "status", "action", "source_url", "source_label", "source_type"):
            if not str(r.get(field, "")).strip():
                errors.append(f"recheck.json {r.get('id')}: empty field {field}")
        if r["status"] not in {"confirmed", "discrepancy", "gap"}:
            errors.append(f"recheck.json {r['id']}: unknown status {r['status']}")
        if not official(r["source_url"]):
            errors.append(f"recheck.json {r['id']}: source host not trusted")
        if r["status"] in {"discrepancy", "gap"} and len(r["action"]) < 20:
            errors.append(f"recheck.json {r['id']}: non-confirmed record needs a real action")
        # A confirmed record must not still require a change.
        if r["status"] == "confirmed" and "re-capture" in r["action"].lower():
            errors.append(f"recheck.json {r['id']}: confirmed record asks for a correction")

    qids = [q["id"] for q in questions["questions"]]
    if len(qids) != len(set(qids)):
        errors.append("questions.json: duplicate question ids")
    for q in questions["questions"]:
        if not official(q["source_url"]):
            errors.append(f"questions.json {q['id']}: source host not trusted")
        if q.get("unknown", "") != "":
            errors.append(f"questions.json {q['id']}: 'unknown' must stay blank, not be guessed")
        if len(q["discovery"]) < 20:
            errors.append(f"questions.json {q['id']}: discovery action too vague")
        if not isinstance(q["blocking"], bool):
            errors.append(f"questions.json {q['id']}: blocking must be a boolean")

    for item in queue["items"]:
        if not official(item["source_url"]):
            errors.append(f"queue.json {item['id']}: source host not trusted")
        if item["priority"] not in {"P0", "P1", "P2"}:
            errors.append(f"queue.json {item['id']}: unknown priority")
        if item["kind"] not in {"fix", "decision"}:
            errors.append(f"queue.json {item['id']}: unknown kind")
        if item["kind"] == "fix" and not item["fixes"]:
            errors.append(f"queue.json {item['id']}: a fix must cite the verification it corrects")
        for ref in [x.strip() for x in item["fixes"].split(",") if x.strip()]:
            if ref not in ids:
                errors.append(f"queue.json {item['id']}: cites unknown verification id {ref}")
        for field in ("why", "how", "acceptance", "risk"):
            if len(item[field]) < 20:
                errors.append(f"queue.json {item['id']}: field {field} too thin")

    # Every contradiction should be covered by at least one queued proposal.
    covered = {x.strip() for item in queue["items"] for x in item["fixes"].split(",") if x.strip()}
    for r in recheck["records"]:
        if r["status"] == "discrepancy" and r["id"] not in covered:
            warnings.append(f"recheck.json {r['id']}: contradiction not yet queued as work")


def check_pages() -> None:
    forbidden = [
        (re.compile(r"luck (?:has been |was )?(?:removed|eliminated)", re.I), "claims luck removed"),
        (re.compile(r"validated (?:betting )?(?:strategy|edge) (?:is|was) (?:proven|confirmed)", re.I), "claims a validated edge"),
        (re.compile(r"guaranteed", re.I), "guarantee language"),
    ]
    total_rows = 0
    for name in LOCAL:
        path = LAB / name
        if not path.exists():
            errors.append(f"missing page {name}")
            continue
        text = path.read_text()
        audit = RowAudit(name)
        audit.feed(text)
        total_rows += audit.rows
        if audit.rows == 0:
            errors.append(f"{name}: no table rows rendered")
        if audit.bad_rows:
            errors.append(f"{name}: {audit.bad_rows} table row(s) without a source link")
        if "=======" in text or "<<<<<<<" in text:
            errors.append(f"{name}: conflict marker")
        for pattern, why in forbidden:
            if pattern.search(text):
                errors.append(f"{name}: {why}")
        # Every blank cell must be the deliberate marker, not an empty <td></td>.
        if re.search(r"<td></td>", text):
            errors.append(f"{name}: silent empty cell (blanks must be marked unverified)")
    if total_rows < 60:
        errors.append(f"expected at least 60 sourced rows across the lab, found {total_rows}")
    print(f"Checked {len(LOCAL)} pages, {total_rows} table rows")


def main() -> int:
    check_registers()
    check_pages()
    for w in warnings:
        print("WARN", w)
    for err in errors:
        print("FAIL", err)
    print("verification-lab checks:", "PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
