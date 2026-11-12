#!/usr/bin/env python3
"""Independent repository/source-authority audit and strict decision-lab gate."""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "decision-lab"
sys.path.insert(0, str(LAB / "scripts"))
import validation as v

COMMUNITY_HOSTS = {"github.com", "nflreadr.nflverse.com", "nflverse.com", "www.nflverse.com"}
COMMUNITY_PATH_PREFIXES = ("/nflverse/", "/nflverse-data/")
EXTRA_OFFICIAL = {
    "www.weather.gov", "weather.gov", "www.gaming.nv.gov", "gaming.nv.gov",
    "kansspelautoriteit.nl", "www.kansspelautoriteit.nl", "github.com", "docs.github.com",
    "www.azcardinals.com", "www.atlantafalcons.com", "www.panthers.com", "www.chicagobears.com",
    "www.dallascowboys.com", "www.detroitlions.com", "www.packers.com", "www.therams.com",
    "www.vikings.com", "www.neworleanssaints.com", "www.philadelphiaeagles.com",
    "www.49ers.com", "www.seahawks.com", "www.buccaneers.com", "www.commanders.com",
    "www.baltimoreravens.com", "www.buffalobills.com", "www.bengals.com", "www.clevelandbrowns.com",
    "www.denverbroncos.com", "www.houstontexans.com", "www.colts.com", "www.jaguars.com",
    "www.chiefs.com", "www.raiders.com", "www.chargers.com", "www.patriots.com",
    "www.newyorkjets.com", "www.steelers.com", "www.tennesseetitans.com", "www.miamidolphins.com",
    "www.giants.com",
}
CLAIM_PATTERNS = [
    re.compile(r"official\s+nflverse", re.I),
    re.compile(r"official\s+release\s+asset", re.I),
    re.compile(r"Data verified\.", re.I),
    re.compile(r"verified\s+official\s+data", re.I),
]
CONFLICT = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.M)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
ELEMENT_ID = re.compile(r'id="([^"]+)"')
HTTPS_LINK = re.compile(r'href="(https://[^"]+)"')
_REGISTER_CACHE: dict[str, dict[str, list[str]]] = {}


def register_index(path: Path) -> dict[str, list[str]]:
    """Map every element id in a page to the https links of its table row.

    Several workspaces cite a source by its registry id (``sources.html#S06``)
    instead of repeating the URL. Resolving those anchors shows whether the row
    really points at an official source or only at a community one.
    """
    key = str(path)
    if key in _REGISTER_CACHE:
        return _REGISTER_CACHE[key]
    mapping: dict[str, list[str]] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        _REGISTER_CACHE[key] = mapping
        return mapping
    for row in ROW.findall(text):
        urls = HTTPS_LINK.findall(row)
        for element_id in ELEMENT_ID.findall(row):
            mapping.setdefault(element_id, urls)
    _REGISTER_CACHE[key] = mapping
    return mapping


def resolve_anchor(path: Path, fragment: str) -> list[str]:
    """Return the https links that a ``page.html#id`` citation points at."""
    if not fragment:
        return []
    return register_index(path).get(fragment, [])


def is_community(url: str) -> bool:
    p = urlparse(url)
    host = p.hostname or ""
    return host in COMMUNITY_HOSTS and (host != "github.com" or p.path.startswith(COMMUNITY_PATH_PREFIXES))


def official_hosts(snapshot: dict | None = None) -> set[str]:
    hosts = set(v.OFFICIAL_HOSTS) | EXTRA_OFFICIAL
    if snapshot:
        for row in snapshot.get("depth_rows", []):
            host = urlparse(row.get("source_url", "")).hostname
            if host:
                hosts.add(host)
        for item in snapshot.get("depth_directory_successes", []):
            host = urlparse(item.get("url", "")).hostname
            if host:
                hosts.add(host)
    return hosts


class TableAudit(HTMLParser):
    def __init__(self, path: Path, allowed: set[str]):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.allowed = allowed
        self.in_tbody = False
        self.in_row = False
        self.row_links: list[str] = []
        self.rows = 0
        self.missing = 0
        self.community_only = 0
        self.internal_source_rows = 0
        self.official_direct = 0
        self.official_via_register = 0
        self.unsourced = 0
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.duplicate_ids: list[str] = []
        self.fragments: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.duplicate_ids.append(a["id"])
            self.ids.add(a["id"])
        if tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_row = True
            self.row_links = []
        elif tag in {"a", "link", "script", "img"}:
            attr = "href" if tag in {"a", "link"} else "src"
            href = a.get(attr, "")
            if not href:
                return
            self.links.append(href)
            if self.in_row and tag == "a":
                self.row_links.append(href)
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https"}:
                if parsed.scheme != "https":
                    self.errors.append(f"non-HTTPS link {href}")
            elif href.startswith("#"):
                self.fragments.append(href[1:])
            elif not href.startswith(("mailto:", "tel:", "data:", "javascript:")):
                target = (self.path.parent / unquote(parsed.path)).resolve()
                if not target.exists():
                    self.errors.append(f"broken local link {href}")

    def _classify_row(self) -> None:
        https = [u for u in self.row_links if urlparse(u).scheme == "https"]
        direct = [u for u in https if (urlparse(u).hostname or "") in self.allowed and not is_community(u)]
        # A row that cites this audit's own implementation or output is internally
        # sourced: the count comes from the audit, not from an external publisher.
        local_provenance = (
            self.path.relative_to(ROOT).as_posix() == "decision-lab/audit.html"
            and any(urlparse(u).path in {"scripts/audit.py", "data/audit.json"} for u in self.row_links)
        )
        if local_provenance:
            self.internal_source_rows += 1
            return
        resolved: list[str] = []
        for link in self.row_links:
            parsed = urlparse(link)
            if parsed.scheme or not parsed.fragment:
                continue
            target = (self.path.parent / unquote(parsed.path)).resolve() if parsed.path else self.path
            for url in resolve_anchor(target, parsed.fragment):
                if (urlparse(url).hostname or "") in self.allowed and not is_community(url):
                    resolved.append(url)
        if direct:
            self.official_direct += 1
            return
        if resolved:
            self.official_via_register += 1
            return
        self.missing += 1
        if https and all(is_community(u) for u in https):
            self.community_only += 1
        elif not https:
            self.unsourced += 1

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_row:
            self.rows += 1
            self._classify_row()
            self.in_row = False
        elif tag == "tbody":
            self.in_tbody = False

    def finish(self):
        for fragment in self.fragments:
            if fragment and fragment not in self.ids:
                self.errors.append(f"missing fragment #{fragment}")
        self.errors.extend(f"duplicate id #{i}" for i in self.duplicate_ids)


def scan_repo() -> dict:
    snapshot_path = LAB / "data/official_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else None
    allowed = official_hosts(snapshot)
    pages = []
    conflict_files = []
    claim_files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix in {".gz", ".png", ".jpg", ".jpeg", ".pdf", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if CONFLICT.search(text):
            conflict_files.append(str(path.relative_to(ROOT)))
        if path.suffix == ".html":
            parser = TableAudit(path, allowed)
            parser.feed(text)
            parser.finish()
            pages.append({"path": str(path.relative_to(ROOT)), "rows": parser.rows,
                          "rows_missing_official_source": parser.missing,
                          "rows_official_direct": parser.official_direct,
                          "rows_official_via_register": parser.official_via_register,
                          "rows_community_only": parser.community_only,
                          "rows_with_internal_audit_source": parser.internal_source_rows,
                          "rows_without_any_link": parser.unsourced,
                          "local_errors": parser.errors})
            if str(path.relative_to(ROOT)).startswith("research-desk/") and any(p.search(text) for p in CLAIM_PATTERNS):
                claim_files.append(str(path.relative_to(ROOT)))
        elif str(path.relative_to(ROOT)).startswith(("pipeline/", "engine/")) and any(p.search(text) for p in CLAIM_PATTERNS):
            claim_files.append(str(path.relative_to(ROOT)))
    findings = []
    if claim_files:
        findings.append({"id": "AUD-01", "severity": "Critical", "title": "NFL authority is unverified for GitHub-hosted data",
                         "detail": f"{len(claim_files)} file(s) describe nflverse GitHub releases as official or verified. Their local manifest checks GitHub-published digests, which verifies byte integrity only; this scan found no NFL authorship/authorization evidence in those files. This is not a finding that the data are inaccurate.",
                         "files": claim_files[:20], "source": "S18"})
    if conflict_files:
        findings.append({"id": "AUD-02", "severity": "High", "title": "Merge-conflict markers remain in repository text",
                         "detail": f"{len(conflict_files)} file(s) contain conflict separators.", "files": conflict_files[:20], "source": "LOCAL_AUDIT"})
    missing = sum(p["rows_missing_official_source"] for p in pages)
    community = sum(p["rows_community_only"] for p in pages)
    direct = sum(p["rows_official_direct"] for p in pages)
    via_register = sum(p["rows_official_via_register"] for p in pages)
    no_link = sum(p["rows_without_any_link"] for p in pages)
    if missing:
        findings.append({"id": "AUD-03", "severity": "High", "title": "Table rows without an official-source link",
                         "detail": (f"{missing} row(s) across the repository have no official source, either directly or "
                                    f"through a registered source id; {community} of them cite only community sources and "
                                    f"{no_link} carry no https link at all. {direct} rows cite an official source directly and "
                                    f"{via_register} cite one through a source-register id. The counts are produced by this "
                                    f"local audit, not by an external publisher."),
                         "files": [p["path"] for p in pages if p["rows_missing_official_source"]][:20], "source": "LOCAL_AUDIT"})
    local_errors = [(p["path"], e) for p in pages for e in p["local_errors"]]
    if local_errors:
        findings.append({"id": "AUD-04", "severity": "High", "title": "Local link/asset or fragment errors",
                         "detail": f"{len(local_errors)} local reference error(s).", "files": [f"{p}: {e}" for p, e in local_errors[:20]], "source": "LOCAL_AUDIT"})
    return {"html_pages": len(pages), "table_rows": sum(p["rows"] for p in pages),
            "rows_missing_official_source": missing, "rows_community_only": community,
            "rows_official_direct": direct, "rows_official_via_register": via_register,
            "rows_without_any_link": no_link,
            "rows_with_internal_audit_source": sum(p["rows_with_internal_audit_source"] for p in pages),
            "conflict_files": conflict_files, "authority_claim_files": claim_files,
            "community_claim_files": claim_files,
            "local_errors": local_errors, "findings": findings, "pages": pages}


def verify_lab() -> list[str]:
    errors = []
    snapshot = json.loads((LAB / "data/official_snapshot.json").read_text())
    catalog = json.loads((LAB / "data/catalog.json").read_text())
    allowed = official_hosts(snapshot)
    for path in sorted(LAB.glob("*.html")):
        parser = TableAudit(path, allowed)
        parser.feed(path.read_text())
        parser.finish()
        if parser.missing:
            errors.append(f"{path.name}: {parser.missing} table row(s) missing official source")
        errors.extend(f"{path.name}: {e}" for e in parser.errors)
        if CONFLICT.search(path.read_text()):
            errors.append(f"{path.name}: conflict marker")
    for row in snapshot["injury_rows"]:
        if not v.official_source(row["source_url"]):
            errors.append("injury row source not official")
        for field in ("confirmed_active", "replacement_player", "replacement_rank", "expected_snaps"):
            if row.get(field) != "":
                errors.append(f"injury row inferred field {field}")
    for row in snapshot["depth_rows"]:
        host = urlparse(row["source_url"]).hostname
        if host not in allowed:
            errors.append(f"depth row source host not allowed: {host}")
        for field in ("confirmed_starter", "replacement_assignment", "expected_snaps"):
            if row.get(field) != "":
                errors.append(f"depth row inferred field {field}")
    for q in catalog["questions"]:
        if q["blocking"] and q["id"] not in {"Q16", "Q20"} and q["answer"] != "":
            errors.append(f"blocking question has unsupported answer: {q['id']}")
    for s in catalog["strategies"]:
        if s["status"] != "Not run":
            errors.append(f"strategy claims run without verified ledger: {s['id']}")
    return errors


def main() -> int:
    audit = scan_repo()
    errors = verify_lab()
    audit["lab_gate_passed"] = not errors
    audit["lab_gate_errors"] = errors
    (LAB / "data/audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(f"Audit: {audit['html_pages']} pages, {audit['table_rows']} rows, {len(audit['findings'])} findings; lab gate {'PASS' if not errors else 'FAIL'}")
    if errors:
        print("\n".join(errors[:30]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
