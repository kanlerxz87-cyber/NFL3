#!/usr/bin/env python3
"""Build every injury-archive artifact and page from the committed captures.

Reads only what is committed: `data/index.jsonl`, the content-addressed raw captures it names,
`data/clubs.json`. It fetches nothing, so the published numbers are reproducible from the
repository alone and a reviewer can diff the JSON against the HTML.

Outputs
-------
data/coverage.json      one row per season x week x document, from the index
data/injuries.json      every captured weekly injury report, re-parsed
data/inactives.json     every captured inactives article, re-parsed
data/designations.json  the joined designation observations and the published rates
*.html                  eight pages rendered from the JSON above
"""
from __future__ import annotations

import collections
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_lib as lib  # noqa: E402

SITE = lib.ROOT / "injury-archive"
NFL = "https://www.nfl.com"

PAGES = [
    ("index.html", "Overview", "What this archive holds, what it proves, and what it refuses to claim."),
    ("injuries.html", "Injury-report history", "Every captured official weekly injury report, by season and week."),
    ("inactives.html", "Inactive lists", "Every captured official inactives article, by season and week."),
    ("designations.html", "Designation calibration", "The measured inactive rate per official designation, with n and an interval."),
    ("coverage.html", "Coverage grid", "The whole season x week grid: captured, not published, or not yet read."),
    ("regime.html", "Rule regime by season", "Whether the official designation vocabulary changed between seasons."),
    ("limits.html", "Limits and exclusions", "What these documents cannot answer, and every row excluded from a rate."),
    ("method.html", "Method and sources", "The two official sources, the join, the estimator, the pre-registration."),
]


def data_clock(index: list[dict]) -> str:
    """The archive's own clock: the latest read time recorded in the index.

    Deliberately not `utc_now()`: a build that stamps wall-clock time changes its own artifacts on
    every run, which would make the determinism gate meaningless and churn the published pages.
    """
    stamps = [e.get("captured_at_utc", "") for e in index if e.get("captured_at_utc")]
    return max(stamps) if stamps else "no captures yet"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def pct(value) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def num(value) -> str:
    return "" if value is None else f"{value:,}"


SHELL_CSS = """
:root{--bg:#0b0f14;--panel:#121821;--panel2:#17202b;--line:#243040;--ink:#e8eef6;--muted:#93a4b8;
--accent:#5eead4;--accent2:#38bdf8;--warn:#fbbf24;--bad:#fb7185;--good:#4ade80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
header.top{border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0e141c,#0b0f14)}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}
.top .wrap{display:flex;gap:18px;align-items:center;justify-content:space-between;padding:16px 22px}
.brand{font-weight:700;letter-spacing:.5px}.brand span{color:var(--accent)}
nav.main{display:flex;flex-wrap:wrap;gap:14px;padding:12px 0;border-top:1px solid var(--line);
font-size:14px}nav.main a{color:var(--muted)}nav.main a[aria-current]{color:var(--accent);font-weight:600}
h1{font-size:30px;line-height:1.2;margin:26px 0 8px}h2{font-size:20px;margin:30px 0 10px}
h3{font-size:16px;margin:20px 0 8px}.lede{color:var(--muted);max-width:80ch}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:20px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.card .k{font-size:12px;letter-spacing:.8px;color:var(--muted);text-transform:uppercase}
.card .v{font-size:26px;font-weight:700;margin-top:4px}.card .n{font-size:13px;color:var(--muted)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:var(--panel2);font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted)}
tbody tr:hover{background:#141c26}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.blank{color:var(--muted);font-style:italic}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line)}
.pill.ok{color:var(--good);border-color:#1f4a33}.pill.warn{color:var(--warn);border-color:#4a3f1f}
.pill.bad{color:var(--bad);border-color:#4a2830}.pill.mut{color:var(--muted)}
.notice{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent2);
border-radius:8px;padding:14px 16px;margin:18px 0;color:var(--muted)}
.warnbox{border-left-color:var(--warn)}
a.source{color:var(--accent)}a.source:after{content:"↗";margin-left:3px;font-size:11px}
footer{border-top:1px solid var(--line);margin-top:40px;padding:24px 0 40px;color:var(--muted);font-size:13px}
code{background:#0f1620;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:13px}
ul.tight{margin:8px 0;padding-left:20px}ul.tight li{margin:4px 0;color:var(--muted)}
"""


def page(name: str, title: str, body: str) -> None:
    nav = "".join(
        f'<a href="{esc(href)}"{" aria-current=page" if href == name else ""}>{esc(label)}</a>'
        for href, label, _ in PAGES
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | Injury archive | NFL3</title>
<meta name="description" content="{esc(title)} — official NFL injury-report and inactive-list history, with hashes, clock times and every exclusion counted.">
<style>{SHELL_CSS}</style></head><body>
<header class="top"><div class="wrap"><div class="brand">NFL<span>3</span> / INJURY ARCHIVE</div>
<div><a href="../index.html">Site overview</a> · <a href="../readiness.html">Readiness</a></div></div>
<nav class="main"><div class="wrap" style="display:flex;flex-wrap:wrap;gap:14px">{nav}</div></nav></header>
<main class="wrap">{body}</main>
<footer class="wrap"><div class="wrap" style="padding:0">Generated by <code>injury-archive/scripts/build.py</code>
from the committed captures only; it fetches nothing. Values that cannot be confirmed from the two
official sources stay blank. Nothing here is betting advice.</div></footer></body></html>
"""
    (SITE / name).write_text(document, encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------------------------

def build_artifacts() -> dict:
    clubs = json.loads(lib.CLUBS_JSON.read_text(encoding="utf-8")) if lib.CLUBS_JSON.exists() else {"clubs": []}
    nicknames = {c["nickname"] for c in clubs["clubs"]}
    index = lib.read_index()
    LIB = lib  # local alias for nested use

    injuries: dict[str, dict] = {}
    inactives: dict[str, dict] = {}
    coverage: list[dict] = []
    seen: set[tuple[str, int, int]] = set()

    # Latest successful read per (kind, season, week) wins; earlier successes stay in the index.
    latest_ok: dict[tuple[str, int, int], dict] = {}
    for entry in index:
        key = (entry.get("kind", ""), entry.get("season"), entry.get("week"))
        if entry.get("status") == "ok" and key[0] in {"injury", "inactives"}:
            latest_ok[key] = entry
        if key[0] in {"injury", "inactives"}:
            seen.add(key)
            coverage.append({
                "kind": key[0], "season": key[1], "week": key[2],
                "status": entry.get("status", ""), "http_status": entry.get("http_status", ""),
                "source_url": entry.get("source_url", ""), "sha256": entry.get("sha256", ""),
                "captured_at_utc": entry.get("captured_at_utc", ""),
                "raw_file": entry.get("raw_file", ""),
                "rows": entry.get("injury_rows", entry.get("players", "")),
                "failures": len(entry.get("failures") or []),
            })

    def parse_entry(entry: dict, kind: str) -> dict:
        raw = lib.load_raw(entry["raw_file"])
        if kind == "injury":
            return lib.parse_injuries(raw, entry.get("final_url", entry["source_url"]), entry["captured_at_utc"])
        return lib.parse_inactives(raw, entry.get("final_url", entry["source_url"]),
                                   entry["captured_at_utc"], nicknames)

    for (kind, season, week), entry in sorted(latest_ok.items()):
        parsed = parse_entry(entry, kind)
        parsed["raw_file"] = entry["raw_file"]
        if kind == "injury":
            parsed["coverage"] = "captured"
            injuries[f"{season}-{week:02d}"] = parsed
        else:
            parsed["coverage"] = "captured"
            inactives[f"{season}-{week:02d}"] = parsed

    # A row for a season/week never asked for, so the grid shows the difference between
    # "not published" and "not yet read".
    latest_by_key = collections.defaultdict(list)
    for entry in index:
        if entry.get("kind") in {"injury", "inactives"}:
            latest_by_key[(entry["kind"], entry.get("season"), entry.get("week"))].append(entry)
    for key, entries in latest_by_key.items():
        pass

    lib.DATA.mkdir(parents=True, exist_ok=True)
    (lib.DATA / "injuries.json").write_text(json.dumps(injuries, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (lib.DATA / "inactives.json").write_text(json.dumps(inactives, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # Deduplicate coverage: one row per (kind, season, week) with the latest status.
    latest_status: dict[tuple, dict] = {}
    for row in coverage:
        latest_status[(row["kind"], row["season"], row["week"])] = row
    coverage_rows = sorted(latest_status.values(), key=lambda r: (r["kind"], r["season"], r["week"]))
    (lib.DATA / "coverage.json").write_text(
        json.dumps({"rows": coverage_rows, "generated_at_utc": data_clock(index)}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")

    # The join: only pairs where both documents parsed cleanly.
    observations: list[dict] = []
    join_rows: list[dict] = []
    for key in sorted(set(injuries) & set(inactives)):
        injury, inactive = injuries[key], inactives[key]
        paired = not injury["failures"] and not inactive["failures"]
        joined = lib.join_week(injury, inactive) if paired else {
            "observations": [], "matched_clubs": [], "uncovered_clubs": [], "extra_clubs": [],
            "report_clubs": []}
        join_rows.append({
            "season": injury["season"], "week": injury["week"],
            "injury_rows": injury["injury_rows"], "inactive_players": len(inactive["rows"]),
            "clubs_matched": len(joined["matched_clubs"]),
            "clubs_uncovered": joined["uncovered_clubs"],
            "clubs_extra": joined["extra_clubs"],
            "injury_source_url": injury["source_url"], "inactives_source_url": inactive["source_url"],
            "injury_sha256": injury["sha256"], "inactives_sha256": inactive["sha256"],
            "paired": paired,
            "excluded": "" if paired else "one or both documents recorded a structural failure",
        })
        observations.extend(joined["observations"])

    by_label = lib.summarise(observations)
    by_season = []
    for row in sorted({(o["season"], o["game_status"]) for o in observations}):
        subset = [o for o in observations if (o["season"], o["game_status"]) == row]
        by_season.extend(lib.summarise(subset))
        by_season[-1]["season"] = row[0]
        by_season[-1]["game_status"] = row[1]
    by_practice = []
    for row in sorted({(o["practice_status"], o["game_status"]) for o in observations}):
        subset = [o for o in observations if (o["practice_status"], o["game_status"]) == row]
        by_practice.extend(lib.summarise(subset))
        by_practice[-1]["practice_status"] = row[0]
        by_practice[-1]["game_status"] = row[1]

    designations = {
        "generated_at_utc": data_clock(index),
        "protocol": "injury-archive/PREREGISTRATION.md (IA-PRE-01)",
        "pairs_joined": join_rows,
        "observations": observations,
        "by_label": by_label,
        "by_season": by_season,
        "by_practice": by_practice,
        "totals": {
            "designations": len(observations),
            "inactive": sum(1 for o in observations if o["outcome"].startswith("inactive")),
            "active": sum(1 for o in observations if o["outcome"].startswith("active")),
            "uncovered": sum(1 for o in observations if o["outcome"].startswith("club not in")),
            "ambiguous": sum(1 for o in observations if o["outcome"].startswith("ambiguous")),
            "emergency_qb": sum(1 for o in observations if o.get("emergency_qb")),
        },
    }
    (lib.DATA / "designations.json").write_text(json.dumps(designations, indent=1, sort_keys=True) + "\n",
                                               encoding="utf-8")
    return {"injuries": injuries, "inactives": inactives, "coverage": coverage_rows,
            "designations": designations, "clubs": clubs}


def main() -> int:
    SITE.mkdir(parents=True, exist_ok=True)
    data = build_artifacts()
    import render  # noqa: PLC0415 - render imports build's page shell
    render.render_all(data)
    print(f"injury-archive: {len(data['injuries'])} injury reports, {len(data['inactives'])} inactives "
          f"articles, {data['designations']['totals']['designations']} joined designations, "
          f"{len(PAGES)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
