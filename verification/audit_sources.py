#!/usr/bin/env python3
"""Independent, offline source-authority review for NFL3.

This review intentionally does not import a source allowlist from captured rows.
It checks publisher hosts against a fixed registry, checks row-level citations,
and reproduces the existing decision-lab audit's snapshot-self-authorization gap.
No HTTP requests are made; host approval is not proof that a page supports a claim.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "decision-lab"
VERIFY = ROOT / "verification"
SNAPSHOT_PATH = LAB / "data/official_snapshot.json"
CATALOG_PATH = LAB / "data/catalog.json"

# Frozen publisher map for the 32 NFL clubs. It is deliberately independent of
# `official_snapshot.json`; review the domains against the NFL team directory (S05)
# when updating it. A listed domain is a host-level check, not a content check.
TEAM_HOSTS = {
    "Arizona Cardinals": "www.azcardinals.com",
    "Atlanta Falcons": "www.atlantafalcons.com",
    "Baltimore Ravens": "www.baltimoreravens.com",
    "Buffalo Bills": "www.buffalobills.com",
    "Carolina Panthers": "www.panthers.com",
    "Chicago Bears": "www.chicagobears.com",
    "Cincinnati Bengals": "www.bengals.com",
    "Cleveland Browns": "www.clevelandbrowns.com",
    "Dallas Cowboys": "www.dallascowboys.com",
    "Denver Broncos": "www.denverbroncos.com",
    "Detroit Lions": "www.detroitlions.com",
    "Green Bay Packers": "www.packers.com",
    "Houston Texans": "www.houstontexans.com",
    "Indianapolis Colts": "www.colts.com",
    "Jacksonville Jaguars": "www.jaguars.com",
    "Kansas City Chiefs": "www.chiefs.com",
    "Las Vegas Raiders": "www.raiders.com",
    "Los Angeles Chargers": "www.chargers.com",
    "Los Angeles Rams": "www.therams.com",
    "Miami Dolphins": "www.miamidolphins.com",
    "Minnesota Vikings": "www.vikings.com",
    "New England Patriots": "www.patriots.com",
    "New Orleans Saints": "www.neworleanssaints.com",
    "New York Giants": "www.giants.com",
    "New York Jets": "www.newyorkjets.com",
    "Philadelphia Eagles": "www.philadelphiaeagles.com",
    "Pittsburgh Steelers": "www.steelers.com",
    "San Francisco 49ers": "www.49ers.com",
    "Seattle Seahawks": "www.seahawks.com",
    "Tampa Bay Buccaneers": "www.buccaneers.com",
    "Tennessee Titans": "www.tennesseetitans.com",
    "Washington Commanders": "www.commanders.com",
}

TEAM_ALIASES: dict[str, str] = {}
for _team in TEAM_HOSTS:
    TEAM_ALIASES[_team.casefold()] = _team
    TEAM_ALIASES[_team.split()[-1].casefold()] = _team
# The canonical report uses "Bears" and "Broncos" in a few tables and full
# names elsewhere; suffix aliases above intentionally cover both forms.

NFL_PUBLISHER_HOSTS = {
    "nfl.com",
    "www.nfl.com",
    "operations.nfl.com",
    "support.nfl.com",
    "nextgenstats.nfl.com",
    "media.nfl.com",
    "static.www.nfl.com",
}
# Authorities for method, weather, and platform-documentation statements in the
# repository. These do not establish NFL game facts and are kept distinct from
# NFL/club publishers in the report.
OTHER_PRIMARY_HOSTS = {
    "api.weather.gov",
    "weather.gov",
    "www.weather.gov",
    "gaming.nv.gov",
    "www.gaming.nv.gov",
    "kansspelautoriteit.nl",
    "www.kansspelautoriteit.nl",
    "itl.nist.gov",
    "www.itl.nist.gov",
    "tsapps.nist.gov",
    "scikit-learn.org",
    "docs.github.com",
}
APPROVED_HOSTS = NFL_PUBLISHER_HOSTS | set(TEAM_HOSTS.values()) | OTHER_PRIMARY_HOSTS
COMMUNITY_HOSTS = {"github.com", "nflreadr.nflverse.com", "nflverse.com", "www.nflverse.com"}

EXPECTED_CAPTURE_HOSTS = {
    "nfl-injuries": {"www.nfl.com"},
    "nfl-teams": {"www.nfl.com"},
    "commanders-depth": {"www.commanders.com"},
    "giants-depth": {"www.giants.com"},
    "colts-depth": {"www.colts.com"},
}
SUPPLEMENTAL_SOURCES = [{
    "id": "SUP-01",
    "title": "NIST-hosted supplemental publication (pub_id 933682)",
    "publisher": "NIST domain, not in the canonical source catalog",
    "url": "https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=933682",
    "scope": "A source link already used by preserved research-workspace rows and referenced in the existing coordination log.",
    "limit": "Not reopened by this independent offline audit; confirm the publication title and claim relevance manually.",
}]

def strict_https_host(url: str) -> str | None:
    """Return a normalized host only for plain HTTPS URLs on default port."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port not in (None, 443):
            return None
        return parsed.hostname.casefold().rstrip(".")
    except (ValueError, TypeError):
        return None


def approved_authority_url(url: str) -> bool:
    host = strict_https_host(url)
    return host in APPROVED_HOSTS if host else False


def approved_nfl_or_club_url(url: str) -> bool:
    host = strict_https_host(url)
    return host in (NFL_PUBLISHER_HOSTS | set(TEAM_HOSTS.values())) if host else False


def canonical_team(name: str) -> str | None:
    return TEAM_ALIASES.get(" ".join(name.split()).casefold())


def digest_is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class TableCitationAudit(HTMLParser):
    """Count `<tbody>` rows with an HTTPS link to an allowlisted primary host."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tbody_depth = 0
        self.row_stack: list[list[str]] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "tbody":
            self.tbody_depth += 1
        elif tag == "tr" and self.tbody_depth:
            self.row_stack.append([])
        elif tag == "a" and self.row_stack:
            href = attrs_map.get("href") or ""
            if href:
                self.row_stack[-1].append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row_stack:
            self.rows.append(self.row_stack.pop())
        elif tag == "tbody" and self.tbody_depth:
            self.tbody_depth -= 1


def scan_html_rows() -> dict:
    per_page = []
    official_missing = 0
    nfl_missing = 0
    community_only = 0
    pages = 0
    row_count = 0
    host_counts: Counter[str] = Counter()
    for path in sorted(ROOT.rglob("*.html")):
        relative = path.relative_to(ROOT)
        if any(part in {".git", "node_modules", "__pycache__"} for part in relative.parts):
            continue
        if relative.parts[0] == "verification":
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        parser = TableCitationAudit()
        parser.feed(source)
        pages += 1
        missing = 0
        for links in parser.rows:
            row_count += 1
            hosts = {strict_https_host(link) for link in links}
            hosts.discard(None)
            host_counts.update(hosts)
            has_approved = bool(hosts & APPROVED_HOSTS)
            has_nfl = bool(hosts & (NFL_PUBLISHER_HOSTS | set(TEAM_HOSTS.values())))
            if not has_approved:
                missing += 1
                official_missing += 1
            if not has_nfl:
                nfl_missing += 1
            if links and all((strict_https_host(link) or "") in COMMUNITY_HOSTS for link in links):
                community_only += 1
        if missing:
            per_page.append({"path": relative.as_posix(), "rows_missing_approved_primary_link": missing,
                             "rows": len(parser.rows)})
    return {
        "html_pages": pages,
        "table_rows": row_count,
        "rows_missing_approved_primary_link": official_missing,
        "rows_missing_nfl_or_club_link": nfl_missing,
        "rows_community_only": community_only,
        "host_link_counts_in_tables": dict(sorted(host_counts.items())),
        "pages_with_missing_primary_links": per_page,
    }


def _code_line(path: Path, needle: str) -> int | None:
    try:
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                return index
    except OSError:
        return None
    return None


def reproduce_existing_allowlist_gaps() -> dict:
    """Exercise the existing audit's host-selection logic with synthetic hosts."""
    audit_path = LAB / "scripts/audit.py"
    spec = importlib.util.spec_from_file_location("decision_lab_audit_review_target", audit_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {audit_path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(LAB / "scripts"))
    spec.loader.exec_module(module)

    capture_path = LAB / "scripts/capture_official.py"
    capture_spec = importlib.util.spec_from_file_location("decision_lab_capture_review_target", capture_path)
    if capture_spec is None or capture_spec.loader is None:
        raise RuntimeError(f"Unable to load {capture_path}")
    capture_module = importlib.util.module_from_spec(capture_spec)
    capture_spec.loader.exec_module(capture_module)
    synthetic_directory = '<a title="View Example Website" href="https://untrusted.invalid/">'
    directory_hosts = [urlsplit(url).hostname for _, url in capture_module.club_directory(synthetic_directory)]

    synthetic_host = "untrusted.invalid"
    accepted_snapshot = {"depth_rows": [{"source_url": f"https://{synthetic_host}/depth-chart"}],
                         "depth_directory_successes": []}
    accepted = synthetic_host in module.official_hosts(accepted_snapshot)

    github_url = "https://github.com/unrelated-owner/unverified-data"
    github_accepted_as_official = ("github.com" in module.official_hosts({})
                                   and not module.is_community(github_url))

    http_url = "http://www.packers.com/team/depth-chart"
    http_host_accepted_by_depth_host_test = (
        (urlsplit(http_url).hostname or "") in module.official_hosts({})
    )
    return {
        "snapshot_declared_host_added_to_allowlist": accepted,
        "directory_host_from_synthetic_html_is_adopted": synthetic_host in directory_hosts,
        "arbitrary_github_repository_not_classified_community": github_accepted_as_official,
        "http_url_host_passes_host_only_membership_check": http_host_accepted_by_depth_host_test,
        "static_allowlist_rejects_snapshot_declared_host": not approved_authority_url(
            f"https://{synthetic_host}/depth-chart"),
        "static_allowlist_rejects_http": not approved_authority_url(http_url),
        "source_lines": {
            "dynamic_depth_host_add": _code_line(audit_path, 'hosts.add(host)'),
            "host_only_depth_row_test": _code_line(audit_path, 'if host not in allowed:'),
            "github_community_classifier": _code_line(audit_path, 'def is_community('),
            "github_extra_official_entry": _code_line(audit_path, '"kansspelautoriteit.nl", "www.kansspelautoriteit.nl", "github.com", "docs.github.com",'),
            "directory_host_adoption": _code_line(LAB / "scripts/capture_official.py", 'found[host] = name'),
            "discovered_host_allowlist": _code_line(LAB / "scripts/capture_official.py", 'allowed = {host, host.removeprefix("www."),'),
        },
    }


def check_snapshot(snapshot: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_by_id: dict[str, dict] = {}
    for entry in snapshot.get("manifest", []):
        ident = entry.get("id", "")
        manifest_by_id[ident] = entry
        expected = EXPECTED_CAPTURE_HOSTS.get(ident)
        for url_key in ("url", "final_url"):
            url = entry.get(url_key, "")
            host = strict_https_host(url)
            if expected is None:
                errors.append(f"manifest {ident}: no fixed publisher host registered")
            elif host not in expected:
                errors.append(f"manifest {ident}: {url_key} host is not in its fixed publisher set: {host}")
        if not digest_is_sha256(entry.get("sha256")):
            errors.append(f"manifest {ident}: invalid SHA-256")
    missing_manifest = sorted(set(EXPECTED_CAPTURE_HOSTS) - set(manifest_by_id))
    if missing_manifest:
        errors.append("missing expected manifest sources: " + ", ".join(missing_manifest))

    injury_manifest = manifest_by_id.get("nfl-injuries", {})
    injury_hash = injury_manifest.get("sha256")
    for index, row in enumerate(snapshot.get("injury_rows", []), 1):
        if strict_https_host(row.get("source_url", "")) != "www.nfl.com":
            errors.append(f"injury row {index}: source is not the fixed NFL report host")
        if row.get("source_sha256") != injury_hash:
            errors.append(f"injury row {index}: source digest does not match NFL injury manifest")
        if row.get("player_url") and strict_https_host(row["player_url"]) != "www.nfl.com":
            errors.append(f"injury row {index}: player URL is not on the NFL host")
        for field in ("confirmed_active", "replacement_player", "replacement_rank", "expected_snaps"):
            if row.get(field) not in ("", None):
                errors.append(f"injury row {index}: inferred field {field} is nonblank")
    for index, row in enumerate(snapshot.get("no_injury_sections", []), 1):
        if strict_https_host(row.get("source_url", "")) != "www.nfl.com":
            errors.append(f"no-injury section {index}: source is not the fixed NFL report host")
        if row.get("source_sha256") != injury_hash:
            errors.append(f"no-injury section {index}: source digest does not match NFL injury manifest")

    success_by_source: dict[tuple[str, str], dict] = {}
    successes = snapshot.get("depth_directory_successes", [])
    for index, entry in enumerate(successes, 1):
        team = canonical_team(entry.get("team", ""))
        expected_host = TEAM_HOSTS.get(team or "")
        actual_host = strict_https_host(entry.get("url", ""))
        if not team or not expected_host:
            errors.append(f"depth success {index}: team label has no fixed club mapping")
        elif actual_host != expected_host:
            errors.append(f"depth success {index}: {entry.get('team')} URL host {actual_host} != {expected_host}")
        if not digest_is_sha256(entry.get("sha256")):
            errors.append(f"depth success {index}: invalid SHA-256")
        if not isinstance(entry.get("rows"), int) or entry["rows"] < 1:
            errors.append(f"depth success {index}: invalid row count")
        if actual_host:
            success_by_source[(actual_host, str(entry.get("sha256", "")))] = entry

    # The canonical lab also has three pre-captured club sources. They are
    # authorized only by their fixed manifest IDs/hosts, never by their own URL.
    for source_id, expected_team in (("commanders-depth", "Washington Commanders"),
                                     ("giants-depth", "New York Giants"),
                                     ("colts-depth", "Indianapolis Colts")):
        entry = manifest_by_id.get(source_id)
        if not entry:
            continue
        host = strict_https_host(entry.get("final_url", ""))
        digest = str(entry.get("sha256", ""))
        if host in EXPECTED_CAPTURE_HOSTS.get(source_id, set()) and digest_is_sha256(digest):
            success_by_source[(host, digest)] = {"team": expected_team, "url": entry.get("final_url", ""),
                                                 "sha256": digest, "manifest_id": source_id}

    for index, row in enumerate(snapshot.get("depth_rows", []), 1):
        team = canonical_team(row.get("team", ""))
        expected_host = TEAM_HOSTS.get(team or "")
        actual_host = strict_https_host(row.get("source_url", ""))
        if not team or not expected_host:
            errors.append(f"depth row {index}: team label has no fixed club mapping: {row.get('team')}")
        elif actual_host != expected_host:
            errors.append(f"depth row {index}: {row.get('team')} source host {actual_host} != {expected_host}")
        if not digest_is_sha256(row.get("source_sha256")):
            errors.append(f"depth row {index}: invalid SHA-256")
        if (actual_host, str(row.get("source_sha256", ""))) not in success_by_source:
            errors.append(f"depth row {index}: source host/digest not present in fixed club capture manifest")
        for field in ("confirmed_starter", "replacement_assignment", "expected_snaps"):
            if row.get(field) not in ("", None):
                errors.append(f"depth row {index}: inferred field {field} is nonblank")

    for index, entry in enumerate(snapshot.get("depth_directory_failures", []), 1):
        team = canonical_team(entry.get("team", ""))
        expected_host = TEAM_HOSTS.get(team or "")
        directory_host = strict_https_host(entry.get("directory_url", ""))
        source_host = strict_https_host(entry.get("source_url", ""))
        if not team or not expected_host:
            errors.append(f"depth failure {index}: team label has no fixed club mapping")
        elif directory_host != expected_host:
            errors.append(f"depth failure {index}: directory host {directory_host} != {expected_host}")
        if source_host != "www.nfl.com":
            errors.append(f"depth failure {index}: directory citation is not the fixed NFL host")
        warnings.append(f"depth coverage absent for {entry.get('team', '')}: {entry.get('reason', '')}")

    coverage = snapshot.get("coverage", {})
    expected_counts = {
        "injury_rows": len(snapshot.get("injury_rows", [])),
        "no_injury_sections": len(snapshot.get("no_injury_sections", [])),
        "depth_rows": len(snapshot.get("depth_rows", [])),
        "depth_teams": sorted({row.get("team", "") for row in snapshot.get("depth_rows", [])}),
        "depth_directory_successes": len(successes),
        "depth_directory_failures": len(snapshot.get("depth_directory_failures", [])),
    }
    for key, expected in expected_counts.items():
        if coverage.get(key) != expected:
            errors.append(f"coverage.{key} mismatch: stored={coverage.get(key)!r}, actual={expected!r}")

    return {
        "injury_rows": len(snapshot.get("injury_rows", [])),
        "no_injury_sections": len(snapshot.get("no_injury_sections", [])),
        "depth_rows": len(snapshot.get("depth_rows", [])),
        "depth_successes": len(successes),
        "depth_failures": len(snapshot.get("depth_directory_failures", [])),
        "depth_teams": len({row.get("team", "") for row in snapshot.get("depth_rows", [])}),
        "snapshot_observed_at": snapshot.get("observed_at", ""),
        "fixed_host_check_errors": errors,
        "coverage_warnings": warnings,
    }


def collect_report() -> dict:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    snapshot_report = check_snapshot(snapshot)
    row_report = scan_html_rows()
    reproduced = reproduce_existing_allowlist_gaps()
    saved_audit_path = LAB / "data/audit.json"
    saved_audit = json.loads(saved_audit_path.read_text(encoding="utf-8")) if saved_audit_path.exists() else {}
    audit_count_comparison = {
        "saved_rows_missing_official_source": saved_audit.get("rows_missing_official_source"),
        "independent_rows_missing_approved_primary_link": row_report["rows_missing_approved_primary_link"],
        "saved_rows_community_only": saved_audit.get("rows_community_only"),
        "independent_rows_community_only": row_report["rows_community_only"],
        "note": "Not directly comparable: this audit rejects all github.com hosts as NFL-authority evidence and accepts the supplemental tsapps.nist.gov publisher; the saved audit used different host/path rules.",
    }
    sources = []
    for item in catalog.get("sources", []):
        url = item.get("url", "")
        sources.append({
            "id": item.get("id", ""),
            "label": item.get("title", ""),
            "url": url,
            "publisher": item.get("publisher", ""),
            "checked_in_catalog": item.get("checked", ""),
            "status_in_catalog": item.get("status", ""),
            "scope": item.get("scope", ""),
            "limit": item.get("limit", ""),
            "catalogued": True,
            "host_approved": approved_authority_url(url),
        })
    for item in SUPPLEMENTAL_SOURCES:
        sources.append({
            "id": item["id"], "label": item["title"], "url": item["url"],
            "publisher": item["publisher"], "checked_in_catalog": "",
            "status_in_catalog": "supplemental reference only", "scope": item["scope"],
            "limit": item["limit"], "catalogued": False,
            "host_approved": approved_authority_url(item["url"]),
        })
    catalog_source_errors = [
        f"{source['id']}: source host is not in the fixed primary-source registry ({strict_https_host(source['url'])})"
        for source in sources if not source["host_approved"]
    ]
    findings = []
    if reproduced["snapshot_declared_host_added_to_allowlist"]:
        findings.append({
            "id": "SRC-01", "severity": "High", "status": "Confirmed by offline synthetic tests",
            "title": "Source-host checks are not independent of the data being checked",
            "detail": "`official_hosts(snapshot)` adds hosts from `depth_rows` and `depth_directory_successes`; `verify_lab()` then accepts a depth row when its host is in that same set. A synthetic `untrusted.invalid` host is admitted. Separately, `capture_official.py` adopts matching hostnames from the team-directory HTML and creates its redirect allowlist from the discovered hostname; a synthetic directory entry was accepted. Add a static 32-club host map before either gate. These are verifier design gaps, not evidence that current club hosts are malicious.",
            "code": ["decision-lab/scripts/audit.py", "decision-lab/scripts/capture_official.py"],
            "official_reference": "S05",
        })
    if reproduced["http_url_host_passes_host_only_membership_check"]:
        findings.append({
            "id": "SRC-02", "severity": "High", "status": "Confirmed by offline synthetic test",
            "title": "The depth-row check does not require HTTPS",
            "detail": "The existing depth-row gate compares only `urlparse(source_url).hostname` against an allowlist; an HTTP URL on an allowed hostname passes that part of the check. The independent fixed allowlist rejects HTTP.",
            "code": ["decision-lab/scripts/audit.py", "decision-lab/scripts/validation.py"],
            "official_reference": "S05",
        })
    if reproduced["arbitrary_github_repository_not_classified_community"]:
        findings.append({
            "id": "SRC-03", "severity": "High", "status": "Confirmed by offline synthetic test",
            "title": "The broad repo audit can treat unrelated GitHub repositories as official",
            "detail": "`github.com` is in the broad `EXTRA_OFFICIAL` host set, while `is_community()` only excludes two nflverse path prefixes. A test URL under an unrelated GitHub owner is therefore eligible to count as an official table citation. GitHub hosting/digests establish neither NFL authorship nor NFL factual authority.",
            "code": ["decision-lab/scripts/audit.py"],
            "official_reference": "S05",
        })
    if snapshot_report["fixed_host_check_errors"]:
        findings.append({
            "id": "SRC-04", "severity": "High", "status": "Current snapshot needs review",
            "title": "Current snapshot has a publisher, digest, team-mapping, or coverage inconsistency",
            "detail": "At least one captured record failed the independent static checks; see `report.json` for exact field-level errors.",
            "code": ["decision-lab/data/official_snapshot.json", "verification/audit_sources.py"],
            "official_reference": "S05",
        })
    findings.append({
        "id": "SRC-05", "severity": "High", "status": "Open requirement / review finding",
        "title": "Many repository table rows still lack a link to an approved primary-source host",
        "detail": f"The independent fixed-host scanner counted {row_report['rows_missing_approved_primary_link']} such rows among {row_report['table_rows']} `<tbody>` rows on {row_report['html_pages']} HTML pages. This is a host-level count only; it does not judge whether a link's content supports its row. See `pages_with_missing_primary_links` in `report.json` for a per-page breakdown.",
        "code": ["verification/audit_sources.py", "decision-lab/data/audit.json"],
        "official_reference": "S05",
    })
    findings.append({
        "id": "SRC-06", "severity": "Review required", "status": "Coverage explicitly incomplete",
        "title": "Two club depth-chart probes did not parse a table",
        "detail": "; ".join(snapshot_report["coverage_warnings"]) or "No depth coverage warnings.",
        "code": ["decision-lab/data/official_snapshot.json"],
        "official_reference": "S05",
    })
    if catalog_source_errors:
        findings.append({
            "id": "SRC-07", "severity": "High", "status": "Source-register host review required",
            "title": "At least one catalog source is outside the fixed primary-source registry",
            "detail": "; ".join(catalog_source_errors),
            "code": ["decision-lab/data/catalog.json", "verification/audit_sources.py"],
            "official_reference": "S05",
        })
    strategy_status = Counter(str(item.get("status", "unspecified")) for item in catalog.get("strategies", []))
    return {
        "report_version": 1,
        "scope": "Offline source-authority and row-citation audit of the repository state; no external URLs fetched.",
        "limitations": [
            "This run does not fetch or re-open NFL/club pages. Links are provided for manual review; availability and page contents may change.",
            "An approved hostname proves only the publisher domain, not that a linked page supports the specific claim or that the extracted row is parsed correctly.",
            "SHA-256 checksums support byte-integrity comparisons only; they do not prove NFL authorship, truth, license, or currentness.",
            "The static club-domain map is a review aid based on the official NFL team directory URL in catalog source S05; verify it again when updating the map.",
            "The historical snapshot timestamp is not a live injury/depth feed or a guarantee about current lineups; this HTML/report is generated from the checked-in snapshot and is not refreshed automatically by the Pages deployment capture step.",
            "No odds/proposition ledger, validated strategy edge, empirical parlay correlation, or funded reward result is established by this audit.",
        ],
        "snapshot": snapshot_report,
        "table_citations": row_report,
        "audit_count_comparison": audit_count_comparison,
        "existing_gate_reproduction": reproduced,
        "sources": sources,
        "catalog_source_errors": catalog_source_errors,
        "strategy_status_counts": dict(sorted(strategy_status.items())),
        "strategies_total": sum(strategy_status.values()),
        "strategies_validated": strategy_status.get("Validated", 0) + strategy_status.get("Pass", 0),
        "findings": findings,
    }


def code_url(path: str, line: int | None) -> str:
    suffix = f"#L{line}" if line else ""
    return f"https://github.com/kanlerxz87-cyber/NFL3/blob/main/{path}{suffix}"


def render_html(report: dict) -> str:
    snap = report["snapshot"]
    table = report["table_citations"]
    comparison = report["audit_count_comparison"]
    summary_cards = [
        ("NFL injury rows", snap["injury_rows"], "https://www.nfl.com/injuries/league/2026/REG10"),
        ("Club depth rows", snap["depth_rows"], "https://www.nfl.com/teams/"),
        ("Club depth publishers", snap["depth_successes"], "https://www.nfl.com/teams/"),
        ("Unparsed club charts", snap["depth_failures"], "https://www.nfl.com/teams/"),
        ("Repo table rows without approved primary host", table["rows_missing_approved_primary_link"], "https://www.nfl.com/teams/"),
        ("Strategies marked validated", report["strategies_validated"], "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL"),
        ("Strategies still not run", report["strategy_status_counts"].get("Not run", 0), "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"),
    ]
    cards = "\n".join(
        f'<article class="metric"><h3>{html.escape(str(label))}</h3><p>{html.escape(str(value))}</p>'
        f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">Official source/context</a></article>'
        for label, value, url in summary_cards
    )
    finding_cards = []
    for finding in report["findings"]:
        code_links = []
        for path in finding.get("code", []):
            source_lines = report["existing_gate_reproduction"]["source_lines"]
            if finding["id"] == "SRC-03" and path.startswith("decision-lab/scripts/audit.py"):
                for key in ("github_extra_official_entry", "github_community_classifier"):
                    line = source_lines.get(key)
                    code_links.append(f'<a href="{html.escape(code_url(path, line), quote=True)}" target="_blank" rel="noopener">{html.escape(path)}{f":L{line}" if line else ""}</a>')
                continue
            if finding["id"] == "SRC-01" and path.endswith("capture_official.py"):
                for key in ("directory_host_adoption", "discovered_host_allowlist"):
                    line = source_lines.get(key)
                    code_links.append(f'<a href="{html.escape(code_url(path, line), quote=True)}" target="_blank" rel="noopener">{html.escape(path)}{f":L{line}" if line else ""}</a>')
                continue
            line = None
            if path.startswith("decision-lab/scripts/audit.py"):
                key = "dynamic_depth_host_add"
                if finding["id"] == "SRC-02": key = "host_only_depth_row_test"
                line = source_lines.get(key)
            elif path.endswith("capture_official.py"):
                line = source_lines.get("directory_host_adoption")
            code_links.append(f'<a href="{html.escape(code_url(path, line), quote=True)}" target="_blank" rel="noopener">{html.escape(path)}{f":L{line}" if line else ""}</a>')
        refs = {source["id"]: source for source in report["sources"]}
        source = refs.get(finding.get("official_reference"), {})
        source_link = (f'<a href="{html.escape(source["url"], quote=True)}" target="_blank" rel="noopener">'
                       f'{html.escape(source["id"] + " — " + source["label"])}</a>') if source else ""
        finding_cards.append(
            f'<article class="finding"><div class="finding-top"><strong>{html.escape(finding["id"])} · {html.escape(finding["severity"])}</strong>'
            f'<span>{html.escape(finding["status"])}</span></div><h3>{html.escape(finding["title"])}</h3>'
            f'<p>{html.escape(finding["detail"])}</p><p class="refs">Code: {" · ".join(code_links)}<br>Official review link: {source_link}</p></article>'
        )
    source_rows = []
    for source in report["sources"]:
        status = "Fixed host approved" if source["host_approved"] else "Host unverified — flagged"
        if not source["catalogued"]:
            status += " (supplemental; not in canonical catalog)"
        link_label = "Open catalog source" if source["catalogued"] else "Open supplemental source"
        source_rows.append(
            f'<tr><td>{html.escape(source["id"])}</td><td>{html.escape(source["label"])}</td>'
            f'<td>{html.escape(source["publisher"])}</td>'
            f'<td><a href="{html.escape(source["url"], quote=True)}" target="_blank" rel="noopener">{link_label}</a></td>'
            f'<td>{html.escape(source["scope"])}</td><td>{html.escape(source["limit"])}</td>'
            f'<td>{html.escape(status)}</td></tr>'
        )
    club_rows = []
    success_counts: Counter[str] = Counter()
    success_urls: dict[str, str] = {}
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    for row in snapshot.get("depth_rows", []):
        name = canonical_team(row.get("team", "")) or row.get("team", "Unmapped")
        success_counts[name] += 1
        success_urls[name] = row.get("source_url", "")
    failed_names = {canonical_team(row.get("team", "")) or row.get("team", "")
                    for row in snapshot.get("depth_directory_failures", [])}
    for team in sorted(TEAM_HOSTS):
        count = success_counts.get(team, 0)
        host = TEAM_HOSTS[team]
        if count:
            source_url = success_urls[team]
            status = f"{count} parsed rows; club-published, not confirmation of starter/active status"
        elif team in failed_names:
            source_url = "https://www.nfl.com/teams/"
            status = "No depth table parsed; flagged — do not infer a lineup"
        else:
            source_url = "https://www.nfl.com/teams/"
            status = "No depth row in this capture; coverage not established"
        club_rows.append(
            f'<tr><td>{html.escape(team)}</td><td>{count if count else ""}</td>'
            f'<td>{html.escape(host if count else "")}</td><td><a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener">'
            f'{"Open club source" if count else "NFL directory / review"}</a></td><td>{html.escape(status)}</td></tr>'
        )
    error_list = snap["fixed_host_check_errors"]
    error_section = ("<p class=\"pass\">All present snapshot publisher/team/hash/coverage checks matched the fixed offline register.</p>"
                     if not error_list else "<ul class=\"errors\">" + "".join(f"<li>{html.escape(e)}</li>" for e in error_list) + "</ul>")
    warning_section = ("<p>No depth coverage warnings recorded.</p>" if not snap["coverage_warnings"] else
                       "<ul class=\"warnings\">" + "".join(f"<li>{html.escape(e)}</li>" for e in snap["coverage_warnings"]) + "</ul>")
    limitations = "".join(f"<li>{html.escape(x)}</li>" for x in report["limitations"])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Independent offline source-authority audit and open review flags for NFL3.">
<title>Independent Source Authority Audit — NFL3</title>
<style>
:root{{--bg:#f4f7fb;--card:#fff;--ink:#182230;--muted:#526174;--line:#d7e0ea;--navy:#102b4e;--teal:#007e87;--red:#9d252c;--amber:#805600;--green:#176343;--shadow:0 10px 28px rgba(20,42,68,.08)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
a{{color:#075e9e}}a:focus,button:focus{{outline:3px solid #f0b429;outline-offset:2px}}.wrap{{max-width:1160px;margin:auto;padding:24px}}
header{{background:var(--navy);color:#fff;padding:30px 0}}header a{{color:#c7e6ff}}.kicker{{text-transform:uppercase;letter-spacing:.12em;font-weight:800;color:#b9d7f4;font-size:.8rem}}
h1{{font-size:clamp(2rem,4vw,3.1rem);line-height:1.1;margin:.3rem 0 .7rem}}.lede{{max-width:850px;color:#e5eef8}}
nav{{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}}nav a{{display:inline-block;padding:7px 11px;border:1px solid #8ca8c2;border-radius:8px;text-decoration:none;color:white}}
.alert{{border-left:7px solid var(--red);background:#fff1f0;padding:16px 18px;border-radius:10px;margin:22px 0;box-shadow:var(--shadow)}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px;margin:18px 0 26px}}.metric,.finding,.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:17px;box-shadow:var(--shadow)}}.metric h3{{font-size:.93rem;margin:0;color:var(--muted)}}.metric p{{font-size:2rem;font-weight:850;margin:.15rem 0}}.metric a{{font-size:.85rem}}
h2{{margin:2rem 0 .8rem;font-size:1.55rem}}h3{{line-height:1.25}}.findings{{display:grid;gap:13px}}.finding-top{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--red)}}.finding-top span{{font-size:.86rem;color:var(--muted)}}.finding h3{{margin:.6rem 0}}.refs{{font-size:.9rem;color:var(--muted)}}
.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:#fff}}table{{border-collapse:collapse;width:100%;min-width:760px}}caption{{text-align:left;font-weight:700;padding:12px}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#e9f0f7}}tbody tr:last-child td{{border-bottom:0}}.pass{{color:var(--green);font-weight:700}}.warnings{{color:var(--amber)}}.errors{{color:var(--red)}}.note{{color:var(--muted)}}.source-list{{columns:2;column-gap:36px}}.source-list li{{break-inside:avoid;margin:0 0 .7rem}}
@media(max-width:600px){{.wrap{{padding:16px}}header{{padding:22px 0}}.finding-top{{display:block}}.source-list{{columns:1}}}}
</style></head>
<body>
<header><div class="wrap"><div class="kicker">NFL3 · Independent verification</div><h1>Source authority &amp; row-citation audit</h1>
<p class="lede">Offline review of the canonical decision-lab publisher checks, captured injury/depth metadata, and repository table citations. This page is a review artifact—not a live odds feed, injury service, or betting system.</p>
<nav aria-label="Primary"><a href="../index.html">Main NFL3 site</a><a href="../decision-lab/index.html">Canonical decision lab</a><a href="../decision-lab/flagged.html">Flagged for Review</a><a href="../decision-lab/sources.html">Source register</a></nav>
</div></header>
<main class="wrap">
<div class="alert"><strong>Review required:</strong> the existing canonical audit's source-host gate can trust a host declared inside the snapshot it is validating. An offline synthetic test reproduced that behavior. This does <strong>not</strong> show that current club hosts are malicious; it means the current gate is not sufficient proof of publisher authority. The independent fixed-host checks below passed for the checked-in capture, subject to the stated limits. This report is pinned to the snapshot timestamp shown below and does not automatically refresh when the Pages workflow captures newer data.</div>
<section aria-labelledby="snapshot-stats"><h2 id="snapshot-stats">Current captured evidence</h2><div class="metrics">{cards}</div>
<p><strong>Snapshot observed:</strong> {html.escape(snap['snapshot_observed_at'])}. <strong>Rows/pages scanned:</strong> {table['table_rows']} table rows across {table['html_pages']} HTML pages. <strong>Rows lacking a link to an approved primary-source host:</strong> {table['rows_missing_approved_primary_link']}. <strong>Rows without an NFL/club host:</strong> {table['rows_missing_nfl_or_club_link']} (methodology rows may appropriately cite other primary authorities). Counts treat every &lt;tbody&gt; row as requiring a citation; this may include question, suggestion, navigation, and finding rows.</p>
<p class="note"><strong>Count reconciliation:</strong> the stored `decision-lab/data/audit.json` reports {comparison['saved_rows_missing_official_source']} missing-source rows and {comparison['saved_rows_community_only']} community-only rows; this independent scan reports {comparison['independent_rows_missing_approved_primary_link']} and {comparison['independent_rows_community_only']}, respectively. These are not like-for-like counts: the independent scan rejects every `github.com` link as NFL-authored evidence and recognizes `tsapps.nist.gov` as a supplemental NIST source. The per-page differences are in `report.json`.</p>
</section>
<section aria-labelledby="findings"><h2 id="findings">Findings and required follow-up</h2><div class="findings">{''.join(finding_cards)}</div>
<p><strong>Recommended corrective path:</strong> maintain a versioned static allowlist of NFL and club domains; validate each snapshot row's team-to-host mapping and HTTPS scheme against that independent list; validate discovered team-directory links against the known club roster; and classify all GitHub-hosted data as non-NFL-authored unless there is a separately verified NFL publisher record. Keep unverified values blank and retain affected decisions behind a fail-closed gate.</p></section>
<section aria-labelledby="checks"><h2 id="checks">Snapshot checks against the fixed host register</h2>{error_section}{warning_section}
<div class="table-wrap"><table><caption>Club depth coverage from the recorded snapshot; table rows link to the publishing club or official NFL team directory</caption><thead><tr><th>Club</th><th>Rows</th><th>Expected publisher host</th><th>Source</th><th>Evidence boundary</th></tr></thead><tbody>{''.join(club_rows)}</tbody></table></div>
<p class="note">A club-published chart may be explicitly unofficial and is not proof of active status, starter status, replacement assignment, or expected snaps. Those fields remain blank in the canonical data unless official evidence supports them.</p>
</section>
<section aria-labelledby="sources"><h2 id="sources">Official source links for manual review</h2><p class="note">The URLs below are the source-register entries used for this audit's NFL, club, statistics-method, and workflow context. This run did not fetch these pages; source links are provided for review.</p>
<div class="table-wrap"><table><caption>All 17 canonical catalog sources plus one supplemental NIST link (each row links to its primary source)</caption><thead><tr><th>ID</th><th>Reference</th><th>Publisher as saved</th><th>Official link</th><th>Saved scope</th><th>Saved limitation</th><th>Fixed-host review</th></tr></thead><tbody>{''.join(source_rows)}</tbody></table></div>
</section>
<section aria-labelledby="limits"><h2 id="limits">What this audit does not establish</h2><ul>{limitations}</ul><p>Full machine-readable results: <a href="report.json">report.json</a>. Reproduce offline: <code>python3 verification/test_audit_sources.py</code> and <code>python3 verification/audit_sources.py --write</code>.</p></section>
</main>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write verification/report.json and verification/index.html")
    parser.add_argument("--check", action="store_true", help="fail if generated report/page differ from current source inputs")
    args = parser.parse_args()
    report = collect_report()
    report_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    page_text = render_html(report) + "\n"
    json_path, html_path = VERIFY / "report.json", VERIFY / "index.html"
    if args.check:
        failures = []
        if not json_path.exists() or json_path.read_text(encoding="utf-8") != report_text:
            failures.append("verification/report.json is missing or stale")
        if not html_path.exists() or html_path.read_text(encoding="utf-8") != page_text:
            failures.append("verification/index.html is missing or stale")
        if failures:
            print("\n".join(failures), file=sys.stderr)
            return 1
        print(f"Fresh independent report: {report['snapshot']['injury_rows']} injury rows, "
              f"{report['snapshot']['depth_rows']} depth rows; "
              f"{report['table_citations']['rows_missing_approved_primary_link']} table rows lack approved primary-host links; "
              f"{len(report['findings'])} findings.")
        return 0
    if args.write or not json_path.exists() or not html_path.exists():
        VERIFY.mkdir(parents=True, exist_ok=True)
        json_path.write_text(report_text, encoding="utf-8")
        html_path.write_text(page_text, encoding="utf-8")
    print(f"Independent source audit: {report['snapshot']['injury_rows']} injury rows, "
          f"{report['snapshot']['depth_rows']} depth rows, "
          f"{report['snapshot']['depth_successes']} successful clubs, {report['snapshot']['depth_failures']} coverage failures.")
    print(f"HTML tables: {report['table_citations']['html_pages']} pages / {report['table_citations']['table_rows']} rows; "
          f"{report['table_citations']['rows_missing_approved_primary_link']} lack a link to the fixed approved primary-host registry.")
    print(f"Reproduced self-authorization: {report['existing_gate_reproduction']['snapshot_declared_host_added_to_allowlist']}; "
          f"HTTP host-only pass: {report['existing_gate_reproduction']['http_url_host_passes_host_only_membership_check']}; "
          f"broad GitHub acceptance: {report['existing_gate_reproduction']['arbitrary_github_repository_not_classified_community']}.")
    print("Fixed snapshot checks: " + ("PASS" if not report['snapshot']['fixed_host_check_errors'] else "FAIL"))
    return 1 if report["snapshot"]["fixed_host_check_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
