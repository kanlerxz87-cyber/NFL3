#!/usr/bin/env python3
"""Build the Week 11 venue register (venues/index.html and venues/flagged.html).

Every number and cell on the pages comes from the committed files under venues/data/. Nothing is
fetched from the network here: the official values were read with fetch_page on 2026-11-16 and are
recorded, with their source URLs, in those files. verify.py checks the pages against the evidence.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DATA = OUT / "data"

TOTAL_FIXTURES = 272  # official: "Complete 18-Week, 272-Game Regular-Season Schedule" (media.nfl.com, 2026-05-14)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def link(url: str, label: str = "source ↗") -> str:
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


def load_rows() -> list[dict]:
    with (DATA / "week11_venues.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


CSS = """
:root{--ink:#14202b;--mute:#5b6b7a;--line:#dfe6ee;--bg:#f6f8fb;--card:#fff;--ok:#1d7a3e;--warn:#9a5b00;--accent:#0b5cad}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0f2538;color:#fff;padding:18px 24px}header h1{margin:0;font-size:22px}header p{margin:4px 0 0;color:#b8c7d6;font-size:13px}
nav{background:#fff;border-bottom:1px solid var(--line);padding:8px 24px;display:flex;gap:16px;flex-wrap:wrap}nav a{color:var(--accent);text-decoration:none;font-weight:600}
main{padding:20px 24px;max-width:1200px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}.card b{display:block;font-size:24px}.card span{color:var(--mute);font-size:12px}
.tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#eef3f8;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--mute)}
a{color:var(--accent)}.ok{color:var(--ok);font-weight:600}.warn{color:var(--warn);font-weight:600}
.box{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:18px 0}
h2{font-size:17px;margin:22px 0 8px}small,.mute{color:var(--mute)}
.sev-irregularity{color:#a11d1d;font-weight:600}.sev-corrected{color:var(--ok);font-weight:600}.sev-note,.sev-scope{color:var(--warn);font-weight:600}
"""

NAV = (
    '<nav><a href="index.html">Week 11 venues</a><a href="flagged.html">Flagged for Review</a>'
    '<a href="../readiness.html">Decision readiness</a><a href="../dashboard/index.html">Dashboard</a>'
    '<a href="../index.html">Home</a></nav>'
)


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)} | NFL3 venues</title><style>{CSS}</style></head><body>"
        "<header><h1>NFL3 · Week 11 venue register</h1>"
        "<p>Venues transcribed from official NFL game-centre pages. Blank means not verified.</p></header>"
        f"{NAV}<main>{body}</main></body></html>\n"
    )


def build_index(rows: list[dict], schedule: dict, announcement: dict) -> str:
    n = len(rows)
    cards = (
        '<div class="cards">'
        f'<div class="card"><b>{n}</b><span>Week 11 fixtures with a verified venue</span></div>'
        f'<div class="card"><b>{n}</b><span>fixtures with an official game-centre link</span></div>'
        '<div class="card"><b>0</b><span>venues unverified on this page</span></div>'
        f'<div class="card"><b>{TOTAL_FIXTURES - n}</b><span>of {TOTAL_FIXTURES} 2026 fixtures not yet transcribed</span></div>'
        "</div>"
    )
    head = (
        "<tr><th>#</th><th>Kickoff (ET)</th><th>Matchup (away at home)</th><th>Network</th>"
        "<th>Venue</th><th>City, state / country</th><th>Official sources</th><th>Status</th></tr>"
    )
    body_rows = []
    for i, r in enumerate(rows, 1):
        matchup = f"{r['away_team']} at {r['home_team']}"
        sources = f"{link(r['venue_source_url'], 'game centre ↗')} · {link(r['schedule_source_url'], 'schedule ↗')}"
        body_rows.append(
            f"<tr><td>{i}</td><td>{esc(r['kickoff_et'])}</td><td>{esc(matchup)}</td><td>{esc(r['network'])}</td>"
            f"<td>{esc(r['venue_stadium'])}</td><td>{esc(r['venue_city_state'])}</td><td>{sources}</td>"
            f'<td><span class="ok">Verified (venue, kickoff, network)</span></td></tr>'
        )
    table = (
        '<div class="tablewrap"><table><caption class="mute">Week 11 (2026) fixtures. Venue from the game-centre '
        "Game Info block; kickoff and network from the Week 11 schedule page. Both read 2026-11-16.</caption>"
        f"<thead>{head}</thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )
    ann = (
        '<div class="box"><h2>League schedule announcement (dated)</h2>'
        f"<p><b>{esc(announcement['title'])}</b> · published {esc(announcement['published'])} · "
        f"{link(announcement['url'], 'announcement ↗')}</p>"
        f"<p>Quoted: “{esc(announcement['quote'])}”. Fixtures in the announced schedule: "
        f"{announcement['fixtures_in_announcement']}.</p>"
        f"<p>Live schedule capture beside it: {link(announcement['live_schedule_url'], 'NFL Week 11 schedule ↗')} "
        f"(read {esc(announcement['live_schedule_fetched_utc'])}; lists {schedule['listed_games']} games and "
        f"{len(schedule['bye_teams'])} clubs on bye).</p></div>"
    )
    notes = (
        '<div class="box"><h2>How this was checked</h2><ul>'
        "<li>Each venue was read from the game-centre page of that fixture (one page per game). The stored lines are in "
        "<code>venues/data/evidence/week11_game_centre_info.json</code>.</li>"
        "<li>Kickoff and network were checked against the Week 11 schedule page "
        "(<code>venues/data/evidence/week11_schedule_list.json</code>).</li>"
        "<li>The Vikings at 49ers fixture is listed at Mexico City, not at the 49ers' home stadium. See Flagged for Review.</li>"
        "<li>No venue for the other 259 fixtures is shown here. Those are not transcribed yet.</li></ul></div>"
    )
    return page("Week 11 venues", cards + table + ann + notes)


def build_flagged(flags: list[dict]) -> str:
    rows = []
    for f in flags:
        rows.append(
            f"<tr><td>{esc(f['id'])}</td><td class=\"sev-{esc(f['severity'])}\">{esc(f['severity'])}</td>"
            f"<td><b>{esc(f['title'])}</b><br><small>{esc(f['detail'])}</small></td>"
            f"<td>{link(f['source'], f['source_label'] + ' ↗')}</td></tr>"
        )
    intro = (
        '<div class="box"><h2>Flagged for Review</h2><p>These items are published, not hidden. None of them blocks '
        "the venue register. Each row links its source. Items marked <b>irregularity</b> need an owner's decision; "
        "<b>corrected</b> items were fixed from the official page on the date shown; <b>note</b> and <b>scope</b> items "
        "are facts a reader must keep in mind.</p></div>"
    )
    table = (
        '<div class="tablewrap"><table><thead><tr><th>ID</th><th>Type</th><th>Item</th><th>Source</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )
    return page("Flagged for Review", intro + table)


def main() -> int:
    rows = load_rows()
    schedule = load_json("evidence/week11_schedule_list.json")
    announcement = load_json("announcement.json")
    flags = load_json("flags.json")
    (OUT / "index.html").write_text(build_index(rows, schedule, announcement), encoding="utf-8")
    (OUT / "flagged.html").write_text(build_flagged(flags), encoding="utf-8")
    print(f"venues: {len(rows)} fixtures, {len(flags)} flags -> venues/index.html, venues/flagged.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
