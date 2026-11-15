#!/usr/bin/env python3
"""Fail-closed ingestion for the price-snapshot store.

Rules enforced here come from pricing/PRICE_DATA_POLICY.md and pricing/schema.json.
A payload that fails any check is rejected whole: there is no partial row. Nothing is
fetched from the network; this tool only validates and files a payload the operator
already holds under written terms.

Usage:
    python3 pricing/ingest.py --input payload.csv --source-id PS-01 \
        --licence-id LIC-001 --terms terms.txt --phase open

The raw payload bytes are hashed (sha256) and the hash is stored with every row, so a
capture can be replayed byte for byte. Rows are appended to
pricing/snapshots/<fetched_at_utc>-<source_id>.jsonl and to the published flat view
pricing/prices.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / "pricing"
SNAPSHOTS = PRICING / "snapshots"
SCHEMA = json.loads((PRICING / "schema.json").read_text(encoding="utf-8"))
REQUIRED = SCHEMA["price_snapshot_row"]["required"]
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MARKET_TYPES = {"side", "total", "moneyline"}
PHASES = {"open", "close", "intraday"}
FORMATS = {"american", "decimal", "line"}
PUBLISHED_COLS = ["market_id", "game_id", "season", "week", "market_type", "market_side", "price",
                  "price_format", "price_as_of", "fetched_at_utc", "phase", "source_id", "licence_id",
                  "capture_hash", "supersedes"]


class Reject(Exception):
    pass


def load_sources() -> dict[str, dict]:
    with (PRICING / "sources.csv").open(newline="", encoding="utf-8") as fh:
        return {r["source_id"]: r for r in csv.DictReader(fh)}


def validate_row(row: dict, source_id: str, licence_id: str, phase: str, sources: dict[str, dict]) -> None:
    missing = [k for k in REQUIRED if k not in row or (row[k] in ("", None) and k not in ("price_as_of", "supersedes"))]
    if missing:
        raise Reject(f"row {row.get('market_id', '?')}: missing required fields {missing}")
    if not re.match(SCHEMA["price_snapshot_row"]["properties"]["market_id"]["pattern"], row["market_id"]):
        raise Reject(f"row {row['market_id']}: market_id does not match the schema pattern")
    if int(row["season"]) < 2000 or not (1 <= int(row["week"]) <= 22):
        raise Reject(f"row {row['market_id']}: season/week out of range")
    if row["market_type"] not in MARKET_TYPES:
        raise Reject(f"row {row['market_id']}: market_type must be one of {sorted(MARKET_TYPES)}")
    if row.get("phase", phase) not in PHASES:
        raise Reject(f"row {row['market_id']}: phase must be one of {sorted(PHASES)}")
    if row.get("price_format") not in FORMATS:
        raise Reject(f"row {row['market_id']}: price_format must be one of {sorted(FORMATS)}")
    try:
        float(row["price"])
    except (TypeError, ValueError):
        raise Reject(f"row {row['market_id']}: price is not numeric: {row['price']!r}")
    if not TS.match(row["fetched_at_utc"]):
        raise Reject(f"row {row['market_id']}: fetched_at_utc must be UTC ISO to the second")
    if row.get("price_as_of") and not TS.match(row["price_as_of"]):
        raise Reject(f"row {row['market_id']}: price_as_of must be UTC ISO to the second or blank")
    if row["source_id"] != source_id or row["licence_id"] != licence_id:
        raise Reject(f"row {row['market_id']}: source/licence in the row must match the run arguments")
    src = sources.get(source_id)
    if src is None:
        raise Reject(f"source_id {source_id} is not registered in pricing/sources.csv")
    if src.get("status") != "licensed":
        raise Reject(f"source_id {source_id} has status {src.get('status')!r}; only 'licensed' sources may be ingested")
    if not licence_id:
        raise Reject("licence_id must be named; a blank licence means the source may not be used")


def ingest(payload: Path, source_id: str, licence_id: str, terms: Path, phase: str) -> Path:
    if not terms.is_file() or not terms.read_text(encoding="utf-8").strip():
        raise Reject("written terms must be supplied as a non-empty file; no licence, no store")
    raw = payload.read_bytes()
    capture_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    sources = load_sources()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    if not rows:
        raise Reject("payload has no rows")
    for row in rows:
        row.setdefault("price_as_of", "")
        row.setdefault("supersedes", "")
        row["source_id"] = source_id
        row["licence_id"] = licence_id
        row["phase"] = phase
        row["capture_hash"] = capture_hash
        validate_row(row, source_id, licence_id, phase, sources)
    stamps = {row["fetched_at_utc"] for row in rows}
    if len(stamps) != 1:
        raise Reject("one capture run must carry one fetched_at_utc for all rows")
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOTS / f"{sorted(stamps)[0].replace(':', '').replace('-', '')}-{source_id}.jsonl"
    if out.exists():
        raise Reject(f"{out.name} already exists; the store is append-only, use a new capture time")
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({k: row.get(k, "") for k in PUBLISHED_COLS}, sort_keys=True) + "\n")
    with (PRICING / "prices.csv").open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PUBLISHED_COLS, extrasaction="ignore", lineterminator="\n")
        for row in rows:
            w.writerow({k: row.get(k, "") for k in PUBLISHED_COLS})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--licence-id", required=True)
    ap.add_argument("--terms", required=True, type=Path)
    ap.add_argument("--phase", required=True, choices=sorted(PHASES))
    a = ap.parse_args()
    try:
        out = ingest(a.input, a.source_id, a.licence_id, a.terms, a.phase)
    except Reject as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"filed {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
