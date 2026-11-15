#!/usr/bin/env python3
"""Build injury-capture/index.html and captures/nfl-injuries/deltas.json from the archive.

Reads captures/nfl-injuries/index.jsonl and the raw captures it references, re-parses each distinct raw
capture with the verified parser, and publishes (a) every read with its clock time, (b) the field-level
delta between consecutive distinct reads, (c) official game-status designations in the latest read and
(d) flags. Nothing is inferred: blank source cells stay blank and no health, participation or
replacement is derived.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

OUT_HTML = common.ROOT / "injury-capture" / "index.html"
OUT_JSON = common.ARCHIVE / "deltas.json"
SOURCE = common.SOURCE_URL


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def pretty_time(stamp: str) -> str:
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).strftime("%a %d %b %Y, %H:%M:%S UTC")
    except (TypeError, ValueError):
        return stamp or ""


def plural(n, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def source_link(url: str, label: str = "nfl.com injury report") -> str:
    return f'<a class="source" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'


def archive_link(path: str, label: str) -> str:
    return f'<a class="archive" href="../{esc(path)}">{esc(label)}</a>'


def build_distinct(entries: list[dict]) -> list[dict]:
    """One parsed capture per run of identical content, in time order, starting from the baseline."""
    distinct: list[dict] = []
    baseline = common.baseline_capture()
    if baseline:
        distinct.append(baseline)
    last_sha = None
    for entry in entries:
        if entry.get("status") != "ok":
            continue
        if entry["sha256"] == last_sha:
            continue
        last_sha = entry["sha256"]
        distinct.append(common.load_archived_capture(entry))
    return distinct


def main() -> int:
    entries = common.read_index()
    if not entries:
        print("No archive reads yet; nothing to publish.", file=sys.stderr)
        return 1
    distinct = build_distinct(entries)
    deltas: list[dict] = []
    for previous, current in zip(distinct, distinct[1:]):
        if (previous.get("season"), previous.get("week")) != (current.get("season"), current.get("week")):
            deltas.append({"kind": "new-week", "from_utc": previous["captured_at_utc"],
                           "to_utc": current["captured_at_utc"], "note": "report week changed; no delta computed"})
            continue
        deltas.extend(common.diff_captures(previous, current))
    latest = distinct[-1]
    ok_reads = [e for e in entries if e.get("status") == "ok"]
    failures = [e for e in entries if e.get("status") != "ok"]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "schema": "nfl3-injury-deltas/v1",
        "source_url": SOURCE,
        "reads_recorded": len(entries),
        "distinct_captures": [{"id": c["id"], "captured_at_utc": c["captured_at_utc"], "sha256": c["sha256"],
                               "week": c["week"], "season": c["season"], "parsed_only": c["parsed_only"],
                               "raw_file": c["raw_file"], "rows": len(c["rows"]),
                               "no_injury_sections": len(c["no_results"])} for c in distinct],
        "deltas": deltas,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(render(entries, distinct, deltas, latest, ok_reads, failures), encoding="utf-8")
    print(f"reads={len(entries)} distinct={len(distinct)} deltas={len(deltas)} "
          f"latest_rows={len(latest['rows'])} failures={len(failures)}")
    return 0


def render(entries, distinct, deltas, latest, ok_reads, failures) -> str:
    latest_read = entries[-1]
    last_ok = next((e for e in reversed(entries) if e.get("status") == "ok"), None)
    week_label = f"Week {latest.get('week')} of the {latest.get('season')} season" if latest.get("week") else "week unknown"

    banner = ""
    if latest_read.get("status") != "ok":
        banner = (f'<div class="callout"><div><h2>Most recent read did not pass</h2><p>The read at '
                  f'{esc(pretty_time(latest_read["captured_at_utc"]))} ended as “{esc(latest_read["status"])}”. '
                  f'The figures below come from the last valid read, not from that run. See the Reads table. '
                  f'{source_link(SOURCE)}</p></div></div>')

    read_rows = []
    for entry in reversed(entries):
        if entry.get("status") == "ok":
            sha = entry["sha256"]
            sha_cell = f'{esc(sha[:16])}… {archive_link(entry["raw_file"], "raw file")}'
            changed = "first read" if entry.get("previous_sha256") is None else (
                "changed" if entry.get("changed_vs_previous") else "unchanged")
            detail = f'{plural(entry.get("injury_rows"), "row")} · {plural(entry.get("no_injury_sections"), "no-injury team")}'
        else:
            sha_cell = ""
            changed = ""
            detail = esc(entry.get("error") or f"{entry.get('failure_count', '')} structural check(s) failed")
        read_rows.append(
            "<tr>"
            f"<td>{esc(pretty_time(entry['captured_at_utc']))}</td>"
            f"<td>{esc(entry['status'])}</td>"
            f"<td>{esc(('Week ' + str(entry['week'])) if entry.get('week') else '')}</td>"
            f"<td>{sha_cell}</td>"
            f"<td>{esc(changed)}</td>"
            f"<td>{detail}</td>"
            f"<td>{source_link(SOURCE)}</td>"
            "</tr>"
        )

    delta_rows = []
    for delta in reversed(deltas):
        if delta.get("kind") == "new-week":
            delta_rows.append(
                f"<tr><td>{esc(pretty_time(delta['from_utc']))}</td><td>{esc(pretty_time(delta['to_utc']))}</td>"
                f"<td colspan=\"5\">{esc(delta['note'])}</td><td>—</td><td>—</td><td>{source_link(SOURCE)}</td></tr>")
            continue
        if delta["kind"] == "section":
            item, link = "Team section", source_link(SOURCE)
        else:
            item = f"{esc(delta['player'])}<br><small>{esc(delta['position'])}</small>"
            link = source_link(delta["player_url"] or SOURCE, "player page on nfl.com")
        delta_rows.append(
            "<tr>"
            f"<td>{esc(pretty_time(delta['from_utc']))}</td>"
            f"<td>{esc(pretty_time(delta['to_utc']))}</td>"
            f"<td>{esc(delta['team'])}</td>"
            f"<td>{item}</td>"
            f"<td>{esc(delta['kind'])}</td>"
            f"<td>{esc(delta['field'])}</td>"
            f"<td>{esc(delta['before'])}</td>"
            f"<td>{esc(delta['after'])}</td>"
            f"<td>{link}</td>"
            "</tr>")

    designated = [r for r in latest["rows"] if r["game_status"]]
    designation_rows = [
        "<tr>"
        f"<td>{esc(r['team'])}</td>"
        f"<td>{esc(r['player'])}<br><small>{esc(r['position'])}</small></td>"
        f"<td>{esc(r['injury'])}</td>"
        f"<td>{esc(r['practice_status'])}</td>"
        f"<td><b>{esc(r['game_status'])}</b></td>"
        f"<td>{esc(r['day'])}</td>"
        f"<td>{source_link(r['player_url'] or SOURCE, 'player page on nfl.com')}</td>"
        "</tr>"
        for r in designated
    ]

    lions = [r for r in latest["rows"] if r["team"] == "Lions"]
    lions_rows = [
        "<tr>"
        f"<td>{esc(r['player'])}<br><small>{esc(r['position'])}</small></td>"
        f"<td>{esc(r['injury'])}</td>"
        f"<td>{esc(r['practice_status'])}</td>"
        f"<td>{esc(r['game_status'])}</td>"
        f"<td>{source_link(r['player_url'] or SOURCE, 'player page on nfl.com')}</td>"
        "</tr>"
        for r in lions
    ]

    flag_items = []
    for capture in distinct:
        for failure in capture.get("failures", []):
            flag_items.append(f"<li>{esc(failure)}</li>")
    conflicts = common.conflict_flags(latest["rows"])
    for flag in conflicts:
        flag_items.append(f"<li><b>Internal conflict:</b> {esc(flag)} {source_link(SOURCE)}</li>")

    lions_count = len(lions)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Timestamped archive of the official NFL injury report: every read, the delta between reads, and official game-status designations.">
<title>Injury report capture | NFL3</title><link rel="stylesheet" href="../assets/style.css"></head><body>
<div class="layout"><aside class="sidebar"><a class="brand" href="../index.html"><span class="brand-icon">N<span>3</span></span><span>NFL<span class="brand-light"> / LAB</span><small>RESEARCH DESK</small></span></a>
<div class="nav-label">START HERE</div><nav aria-label="Main navigation"><a href="../index.html"><span>01</span>Overview</a><a href="../ops-center/index.html"><span>02</span>Ops centre</a><a href="../decision-lab/index.html"><span>03</span>Canonical decision lab</a></nav>
<div class="nav-label">THIS SECTION</div><nav aria-label="Section navigation"><a aria-current="page" href="index.html"><span>I</span>Injury report capture</a><a href="../readiness.html"><span>D</span>Decision readiness</a><a href="../review.html"><span>F</span>Flagged for review</a></nav>
<div class="side-bottom"><span class="status-dot"></span> Research mode <small>Official source reads only</small></div></aside>
<main><header class="topbar"><span>FOOTBALL INTELLIGENCE <b>/</b> INJURY REPORT CAPTURE</span><span class="top-right"><span class="status-dot"></span> ARCHIVE</span></header><div class="content">
<div class="eyebrow"><span></span> TIMESTAMPED OFFICIAL READS</div>
<h1>Injury report: what changed between reads</h1>
<p class="lede">The official NFL injury report is captured on a schedule with a clock time and a content hash for every read. This page publishes the differences between reads, not a snapshot of the level. Blank source cells stay blank; nothing here infers health, participation or a replacement.</p>
{banner}<div class="notice"><b>Latest valid read:</b> {esc(pretty_time(latest['captured_at_utc']))} · {esc(week_label)} · {plural(len(latest['rows']), 'player row')} · {plural(len(latest['no_results']), 'team')} with “No Injuries Reported” · {plural(len(designated), 'row')} with a game-status designation · {plural(len(entries), 'read')} recorded · {plural(len(distinct), 'distinct capture')} (baseline included) · {len(failures)} failed or drifted reads. Source: {source_link(SOURCE)}</div>

<div class="section-head"><div><div class="section-label">01 / READS</div><h2>Every read, with its clock time</h2></div><p>Each scheduled or manual run is listed, including failed runs. A changed hash means the official page bytes changed.</p></div>
<div class="table-wrap"><table><thead><tr><th scope="col">Read at (UTC)</th><th scope="col">Status</th><th scope="col">Report week</th><th scope="col">SHA-256 (raw)</th><th scope="col">vs previous read</th><th scope="col">Detail</th><th scope="col">Source</th></tr></thead><tbody>
{''.join(read_rows) or '<tr><td colspan="7">No reads recorded.</td></tr>'}
</tbody></table></div>

<div class="section-head"><div><div class="section-label">02 / DELTAS</div><h2>What changed between distinct reads</h2></div><p>Field-level differences only, newest first. The first distinct read after the 12 Nov baseline is compared with the baseline, which was parsed from a capture whose raw bytes were not retained.</p></div>
<div class="table-wrap"><table><thead><tr><th scope="col">From (UTC)</th><th scope="col">To (UTC)</th><th scope="col">Team</th><th scope="col">Player</th><th scope="col">Change</th><th scope="col">Field</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Source</th></tr></thead><tbody>
{''.join(delta_rows) or '<tr><td colspan="9">No differences between distinct reads yet.</td></tr>'}
</tbody></table></div>

<div class="section-head"><div><div class="section-label">03 / GAME STATUS</div><h2>Official game-status designations, latest read</h2></div><p>The only level shown here: the designation text as published on the official page. {len(designated)} rows carry one.</p></div>
<div class="table-wrap"><table><thead><tr><th scope="col">Team</th><th scope="col">Player</th><th scope="col">Injury</th><th scope="col">Practice status</th><th scope="col">Game status</th><th scope="col">Game day</th><th scope="col">Source</th></tr></thead><tbody>
{''.join(designation_rows) or '<tr><td colspan="7">No game-status designations in the latest read.</td></tr>'}
</tbody></table></div>

<div class="section-head"><div><div class="section-label">04 / DETROIT LIONS</div><h2>Lions rows in the latest read ({lions_count} listed)</h2></div><p>Kerby Joseph, Cade Mays and D.J. Reed had blank game-status cells in the dashboard table. This section shows what the official page published in the latest read. A separate read of the same official page on 15 Nov 2026 showed the same three rows (Did Not Participate in Practice, game status Out).</p></div>
<div class="table-wrap"><table><thead><tr><th scope="col">Player</th><th scope="col">Injury</th><th scope="col">Practice status</th><th scope="col">Game status</th><th scope="col">Source</th></tr></thead><tbody>
{''.join(lions_rows) or '<tr><td colspan="5">No Lions rows in the latest read.</td></tr>'}
</tbody></table></div>

<div class="section-head"><div><div class="section-label">05 / FLAGS</div><h2>Flagged for review</h2></div><p>Structural failures and internal conflicts are listed, not corrected. Each carries its source.</p></div>
<div class="callout"><div><h2>Irregularities recorded for review</h2><ul>
<li><b>IC-1 · Repository snapshot is older than the live site.</b> <code>decision-lab/data/official_snapshot.json</code> was observed 2026-11-12T06:32:36Z (254 injury rows, 4 no-injury teams). The deployed decision-lab integrity page reports a capture at 2026-11-15T12:42Z that was never committed. {source_link(SOURCE)}</li>
<li><b>IC-6 · Older row counts are superseded.</b> The 254-row decision-lab table and the 279-row ops-centre figure both predate this read, which holds {plural(len(latest['rows']), 'player row')} across {len({r['team'] for r in latest['rows']})} teams with a listed injury and {len(latest['no_results'])} teams with “No Injuries Reported”. Neither older table was edited here. {source_link(SOURCE)}</li>
<li><b>IC-2 · Dashboard table is stale.</b> <code>dashboard/data/injuries_2026_w10.csv</code> shows Kerby Joseph as Limited Participation with a blank game status; the latest read shows the designations in section 04. The dashboard table was not edited here. {source_link(SOURCE)}</li>
<li><b>IC-3 · Baseline is parsed-only.</b> The 12 Nov baseline's raw bytes were not retained (its hash is recorded). Deltas from it depend on the parser version.</li>
<li><b>IC-4 · Raw captures are public.</b> The raw files sit under the Pages root and are published with the site. Moving them to a private store is not implemented.</li>
<li><b>IC-5 · Schedule runs from the default branch only.</b> GitHub runs scheduled workflows only on the default branch, so the schedule is active after the merge.</li>
{''.join(flag_items)}
</ul></div><a class="button" href="../review.html">Open flagged review <span>↗</span></a></div>

<footer>NFL3 RESEARCH DESK <span>Built for informed decisions, not guaranteed outcomes.</span></footer></div></main></div></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
