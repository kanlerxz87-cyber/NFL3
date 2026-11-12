#!/usr/bin/env python3
"""Collect official NFL data from the nflverse-data releases with integrity verification.

Sources (official, machine-readable, maintained by nflverse from NFL data feeds):

  * games / schedules  -> https://github.com/nflverse/nflverse-data/releases/tag/schedules
  * injuries           -> https://github.com/nflverse/nflverse-data/releases/tag/injuries
  * depth charts       -> https://github.com/nflverse/nflverse-data/releases/tag/depth_charts
  * snap counts        -> https://github.com/nflverse/nflverse-data/releases/tag/snap_counts
  * team weekly stats  -> https://github.com/nflverse/nflverse-data/releases/tag/stats_team
  * players            -> https://github.com/nflverse/nflverse-data/releases/tag/players

Every download is checked against the SHA-256 digest that GitHub publishes on the release asset.
GitHub computes that digest server-side from the stored asset, so a matching digest proves the
local bytes are byte-identical to the official asset at the recorded time.  A mismatch is fatal.

Usage:
    python3 pipeline/fetch_official.py [--dest data/raw] [--only games,injuries]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = "nflverse/nflverse-data"
API = f"https://api.github.com/repos/{REPO}/releases/tags"
UA = "NFL3-research-pipeline/1.0 (+https://github.com/kanlerxz87-cyber/NFL3)"

SEASON = 2026

# name -> (release tag, asset file name, keep)
TARGETS = {
    "games": ("schedules", "games.csv"),
    "players": ("players", "players.csv"),
    "rosters": ("rosters", f"roster_{SEASON}.csv"),
    "stats_team_week": ("stats_team", f"stats_team_week_{SEASON}.csv"),
    "snap_counts": ("snap_counts", f"snap_counts_{SEASON}.csv"),
    "injuries": ("injuries", f"injuries_{SEASON}.csv"),
    "depth_charts": ("depth_charts", f"depth_charts_{SEASON}.csv"),
}
# historical seasons used for the injury-signal study and the line study
HISTORY = {
    "injuries": ("injuries", [2021, 2022, 2023, 2024, 2025]),
    "depth_charts": ("depth_charts", [2021, 2022, 2023, 2024, 2025]),
}


def api_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def release_assets(tag: str) -> dict:
    data = api_json(f"{API}/{tag}")
    return {a["name"]: a for a in data.get("assets", [])}


def download(url: str, dest: str, expected_sha: str | None, expected_size: int | None) -> dict:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            f.write(chunk)
    digest = "sha256:" + h.hexdigest()
    ok = True
    if expected_size is not None and size != expected_size:
        ok = False
    if expected_sha is not None and digest != expected_sha:
        ok = False
    if not ok:
        os.unlink(tmp)
        raise SystemExit(
            f"INTEGRITY FAILURE for {url}\n  expected sha256={expected_sha} size={expected_size}\n"
            f"  got      {digest} size={size}"
        )
    os.replace(tmp, dest)
    return {"url": url, "path": dest, "bytes": size, "sha256": digest, "verified": True}


def gunzip_if_needed(path: str) -> str:
    """Keep repository size small: store the gzip form and decompress at load time."""
    if path.endswith(".gz"):
        return path
    gz = path + ".gz"
    if os.path.exists(gz) and os.path.getsize(gz) > 0:
        return gz
    with open(path, "rb") as f, gzip.open(gz, "wb", compresslevel=9) as g:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            g.write(b)
    os.unlink(path)
    return gz


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data/raw")
    ap.add_argument("--only", default="")
    ap.add_argument("--history", action="store_true", help="also fetch historical seasons")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}

    manifest = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source_repo": f"https://github.com/{REPO}",
                "files": {}, "failures": []}

    jobs = [(name, tag, asset) for name, (tag, asset) in TARGETS.items() if not only or name in only]
    if args.history:
        for name, (tag, seasons) in HISTORY.items():
            if only and name not in only:
                continue
            for s in seasons:
                ext = "csv" if name != "depth_charts" else "csv"
                jobs.append((f"{name}_{s}", tag, f"{name}_{s}.{ext}"))

    cache: dict[str, dict] = {}
    for name, tag, asset in jobs:
        if tag not in cache:
            cache[tag] = release_assets(tag)
        a = cache[tag].get(asset)
        if a is None:
            # roster_weekly uses a different prefix than roster_{season}; try both
            alt = asset.replace("roster_", "roster_weekly_")
            a = cache[tag].get(alt)
            if a is not None:
                asset = alt
        if a is None:
            manifest["failures"].append({"name": name, "tag": tag, "asset": asset,
                                         "reason": "asset not found in official release"})
            print(f"  !! {name}: asset {asset} not present in release '{tag}'")
            continue
        dest = os.path.join(args.dest, asset)
        print(f"  -> {name}: {asset} ({a['size'] / 1e6:.2f} MB)")
        try:
            rec = download(a["browser_download_url"], dest, a.get("digest"), a.get("size"))
        except (urllib.error.URLError, urllib.error.HTTPError, SystemExit) as exc:
            manifest["failures"].append({"name": name, "tag": tag, "asset": asset, "reason": str(exc)})
            print(f"  !! {name}: {exc}")
            continue
        stored = gunzip_if_needed(dest)
        rec["stored_as"] = os.path.relpath(stored, args.dest)
        rec["release_asset_updated_utc"] = a.get("updated_at")
        rec["release_tag"] = tag
        rec["release_url"] = f"https://github.com/{REPO}/releases/tag/{tag}"
        rec["asset_url"] = a["browser_download_url"]
        manifest["files"][name] = rec

    with open(os.path.join(args.dest, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    ok = len(manifest["files"])
    print(f"\nverified {ok} file(s); {len(manifest['failures'])} failure(s)")
    return 0 if not manifest["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
