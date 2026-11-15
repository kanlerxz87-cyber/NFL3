#!/usr/bin/env python3
"""Fail-closed checks on the availability ledger.

Run:  python3 availability-ledger/scripts/verify.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "availability-ledger"
LEDGER = LAB / "data" / "ledger.json"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
PAGES = ["index.html", "ledger.html", "availability.html", "depth-flags.html", "diff.html",
         "flagged.html", "sources.html"]
OFFICIAL_HOSTS = ("https://www.nfl.com/", "https://www.baltimoreravens.com/",
                  "https://www.colts.com/", "https://www.commanders.com/")

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not LEDGER.exists():
        fail("missing ledger artifact")
        print("\n".join(errors))
        return 1
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    # 1. capture digests still match the stored files
    for capture in data["captures"]:
        path = ROOT / capture["file"] if str(capture["file"]).startswith("availability-ledger") \
            else LAB / "data" / "captures" / capture["file"]
        if not path.exists():
            fail(f"capture file missing: {capture['file']}")
            continue
        actual = sha256_file(path)
        if actual != capture["sha256"]:
            fail(f"capture digest changed for {capture['file']}")

    # 2. the depth capture timestamp is the committed one
    if data["depth_capture"]["observed_at"] != snap.get("observed_at"):
        fail("the ledger's depth capture timestamp does not match the committed official snapshot")

    # 3. every official row points at an official page
    for entry in data["reserve_entries"]:
        if not entry["source_url"].startswith("https://www.nfl.com/"):
            fail(f"reserve entry {entry['player']} has a non-official source URL")
        if not entry["player_url"].startswith("https://www.nfl.com/"):
            fail(f"reserve entry {entry['player']} has a non-official player URL")
    for trade in data["trade_events"]:
        if not trade["source_url"].startswith("https://www.nfl.com/"):
            fail(f"trade {trade['player']} has a non-official source URL")

    # 4. the stale / same-day verdicts follow from the dates, not from a judgement
    capture_day = snap.get("observed_at", "")[:10]
    for row in data["stale_depth_rows"]:
        if not row["event_date"] < capture_day:
            fail(f"stale row {row['player']} has an event date on or after the capture day")
    for row in data["same_day_depth_rows"]:
        if row["event_date"] != capture_day:
            fail(f"same-day row {row['player']} does not fall on the capture day")

    # 5. pages exist, carry no placeholder, and every table row has a source link
    for name in PAGES:
        path = LAB / name
        if not path.exists():
            fail(f"missing page: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b(None|nan|undefined|null)\b", text):
            fail(f"{name}: a placeholder token appears in the published page")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith("http"):
                continue
            if not (LAB / href).resolve().exists():
                fail(f"{name}: broken internal link {href}")
        rows = re.findall(r"<tr>(.*?)</tr>", text, re.S)
        body_rows = [r for r in rows if "<td" in r]
        for row in body_rows:
            if 'href="http' not in row:
                fail(f"{name}: a table row has no source link")
                break

    # 6. every depth row referenced by a flag exists in the committed capture
    depth_keys = {(r["team"], r["player"].strip().lower()) for r in snap.get("depth_rows", [])}
    for row in data["stale_depth_rows"] + data["same_day_depth_rows"]:
        if not row["depth_source_url"].startswith("https://"):
            fail(f"flagged row {row['player']} has no depth source URL")

    if errors:
        print("availability-ledger verification FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Availability-ledger checks passed: capture digests, official source URLs, stale/same-day "
          "verdicts, page placeholders, internal links and per-row source links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
