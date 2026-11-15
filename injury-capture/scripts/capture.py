#!/usr/bin/env python3
"""Fetch the official NFL injury report, verify its structure, and archive the raw bytes.

Every run appends exactly one line to captures/nfl-injuries/index.jsonl, so the history records each
read with its clock time, including reads that failed. Raw bytes are stored once per distinct content
under their SHA-256 (content-addressed, never overwritten). A drift or fetch failure is recorded and
exits non-zero so the scheduled workflow goes red and notifies the repository watchers.

Exit codes: 0 read recorded (ok); 3 structural drift (raw kept, not published as valid); 4 fetch failed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(url: str, timeout: int) -> tuple[bytes, str, int]:
    request = urllib.request.Request(url, headers={"User-Agent": common.UA, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        status = response.status
        raw = response.read(12_000_001)
    parsed = urlparse(final_url)
    if parsed.scheme != "https" or parsed.hostname not in common.ALLOWED_HOSTS:
        raise ValueError(f"unexpected redirect outside the official host: {final_url}")
    if len(raw) > 12_000_000:
        raise ValueError("source exceeds the 12 MB capture limit")
    return raw, final_url, status


def record_read(archive: Path, raw: bytes | None, final_url: str, http_status: int | None,
                requested_at: str, captured_at: str, url: str, error: str = "") -> int:
    """Store the read (if any) and append one index line. Returns the process exit code."""
    index = archive / "index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    previous = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if index.exists() else []
    last_ok = next((r for r in reversed(previous) if r.get("status") == "ok"), None)

    base = {"captured_at_utc": captured_at, "requested_at_utc": requested_at, "source_url": url}
    if raw is None:
        entry = {**base, "status": "fetch_failed", "error": error[:300]}
        exit_code = 4
    else:
        result = common.inspect_html(raw, final_url, captured_at)
        raw_dir = archive / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{result['sha256']}.html.gz"
        if not raw_path.exists():
            raw_path.write_bytes(gzip.compress(raw, mtime=0))
        if gzip.decompress(raw_path.read_bytes()) != raw:
            raise RuntimeError("stored raw capture does not round-trip to the fetched bytes")
        entry = {
            **base,
            "final_url": final_url,
            "http_status": http_status,
            "sha256": result["sha256"],
            "bytes": result["bytes"],
            "raw_file": str(raw_path.relative_to(common.ROOT)) if raw_path.is_relative_to(common.ROOT)
            else raw_path.name,
            "week": result["week"],
            "season": result["season"],
            "day_sections": result["day_sections"],
            "team_sections": result["team_sections"],
            "injury_tables": result["injury_tables"],
            "injury_rows": result["injury_rows"],
            "no_injury_sections": result["no_injury_sections"],
            "previous_sha256": last_ok["sha256"] if last_ok else None,
            "changed_vs_previous": (last_ok is None) or (last_ok["sha256"] != result["sha256"]),
            "conflict_flags": common.conflict_flags(result["rows"]),
        }
        if result["failures"]:
            entry["status"] = "drift"
            entry["failure_count"] = len(result["failures"])
            entry["failures"] = result["failures"][:50]
            exit_code = 3
        else:
            entry["status"] = "ok"
            exit_code = 0

    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    summary = {k: entry.get(k) for k in ("captured_at_utc", "status", "sha256", "week", "season",
                                         "injury_rows", "no_injury_sections", "changed_vs_previous")}
    print(json.dumps(summary, indent=2))
    if entry.get("failures"):
        print("STRUCTURAL DRIFT — failing the run:", file=sys.stderr)
        for failure in entry["failures"]:
            print(f"  - {failure}", file=sys.stderr)
    if entry["status"] == "fetch_failed":
        print(f"FETCH FAILED: {entry['error']}", file=sys.stderr)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=common.SOURCE_URL)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--archive", type=Path, default=common.ARCHIVE)
    parser.add_argument("--from-file", type=Path, help="Archive a saved capture instead of fetching (tests only)")
    args = parser.parse_args()
    requested = utc_now()
    if args.from_file:
        raw, final_url, status = args.from_file.read_bytes(), args.url, 200
    else:
        try:
            raw, final_url, status = fetch(args.url, args.timeout)
        except Exception as exc:  # any network, redirect or size failure is recorded, not hidden
            return record_read(args.archive, None, args.url, None, requested, utc_now(), args.url,
                               error=f"{type(exc).__name__}: {exc}")
    return record_read(args.archive, raw, final_url, status, requested, utc_now(), args.url)


if __name__ == "__main__":
    raise SystemExit(main())
