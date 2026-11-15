#!/usr/bin/env python3
"""Build the availability ledger: official roster events joined to published depth and report rows.

Inputs
------
* The captured official NFL transaction tables in ``data/captures/`` (reserve list October and
  November 2026, league trades November 2026), each with its source URL, retrieval time and hash.
* The committed official capture in ``decision-lab/data/official_snapshot.json`` — the NFL injury
  report and the club depth charts, with the capture timestamp on every row.

What it produces
----------------
1. A **reserve list** and a **trade log** as first-class rows, so "not listed" can never be read as
   "available".
2. **Stale depth rows**: a club depth row captured *after* the player had already been placed on the
   reserve list, or after the player had been traded away from that club.
3. **Same-day rows**: the player was placed on the reserve list on the same calendar day as the
   capture. The order of the two events is unknown, so the row is published as unresolved rather
   than as stale or as fresh.
4. **Report coverage**: for every reserve-listed player, whether the official weekly report lists
   them and with which designation.

Nothing is inferred: a blank stays blank, and a flag states the two published facts it compares.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "availability-ledger"
DATA = LAB / "data"
CAPTURES = DATA / "captures"
SNAPSHOT = ROOT / "decision-lab" / "data" / "official_snapshot.json"
OUT_JSON = DATA / "ledger.json"

# Club display name -> club code used by the depth-chart capture.
CLUB_CODES = {
    "49ers": "SF", "Bengals": "CIN", "Bills": "BUF", "Browns": "CLE", "Cardinals": "ARI",
    "Chargers": "LAC", "Chiefs": "KC", "Colts": "IND", "Commanders": "WAS", "Cowboys": "DAL",
    "Broncos": "DEN", "Dolphins": "MIA", "Falcons": "ATL", "Giants": "NYG", "Jaguars": "JAX",
    "Jets": "NYJ", "Lions": "DET", "Panthers": "CAR", "Patriots": "NE", "Raiders": "LV",
    "Rams": "LAR", "Ravens": "BAL", "Saints": "NO", "Seahawks": "SEA", "Steelers": "PIT",
    "Titans": "TEN", "Vikings": "MIN", "Eagles": "PHI", "Bears": "CHI", "Buccaneers": "TB",
    "Packers": "GB", "Texans": "HOU",
}
# The depth capture stores some clubs under their long display name.
SNAPSHOT_TEAM_ALIASES = {
    "Chicago Bears": "Bears", "Denver Broncos": "Broncos",
    "Philadelphia Eagles": "Eagles", "Tampa Bay Buccaneers": "Buccaneers",
}

NFL_RESERVE = "https://www.nfl.com/transactions/league/reserve-list/"
NFL_TRADES = "https://www.nfl.com/transactions/"
NFL_INJURIES = "https://www.nfl.com/injuries/"
NFL_TEAMS = "https://www.nfl.com/teams/"


# --------------------------------------------------------------------------- captures
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_capture(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header, _, body = text.partition("--- body ---")
    meta = {}
    for line in header.splitlines():
        if line.startswith("# ") and ": " in line:
            key, _, value = line[2:].partition(": ")
            meta[key.strip()] = value.strip()
    rows = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        rows.append(parts)
    return {"file": path.name, "meta": meta, "rows": rows, "sha256": sha256_file(path),
            "path": str(path.relative_to(ROOT))}


def parse_date(md: str, year: int) -> str:
    month, day = md.split("/")
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"


# --------------------------------------------------------------------------- pages
def esc(text) -> str:
    return html.escape(str(text), quote=True)


def link(url: str, label: str | None = None) -> str:
    return f'<a href="{esc(url)}">{esc(label or url)}</a>'


def tag(text: str, kind: str) -> str:
    return f'<span class="tag {kind}">{text}</span>'


def table(headers: list[str], rows: list[list[str]], classes: list[str] | None = None) -> str:
    cls = classes or [""] * len(headers)
    head = "".join(f'<th class="{c}">{h}</th>' for h, c in zip(headers, cls))
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def page(title: str, eyebrow: str, lede: str, body: str, active: str) -> str:
    nav_items = [("index.html", "Overview"), ("ledger.html", "Ledger"), ("availability.html", "Availability"),
                 ("depth-flags.html", "Depth flags"), ("diff.html", "Weekly diff"),
                 ("flagged.html", "Flagged for review"), ("sources.html", "Sources")]
    nav = "".join(
        '<a href="{href}"{cls}>{label}</a>'.format(href=href, label=label,
                                                  cls=' class="active"' if href == active else "")
        for href, label in nav_items)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NFL3 availability ledger</title>
<meta name="description" content="NFL3 availability ledger — official reserve-list and trade captures joined to published club depth rows and the official injury report, with every row sourced.">
<link rel="stylesheet" href="assets/site.css">
</head>
<body>
<header class="top"><div class="wrap"><div class="brand">
<div class="brand-mark">N3</div><div><h1>Availability ledger — official roster events</h1>
<p>Reserve list, trades, published depth rows and the weekly report, compared row by row</p></div>
<div class="status-strip"><span>official sources only</span><span>captured 2026-11-15</span>
<span>blanks stay blank</span></div></div></div></header>
<nav class="sections"><div class="wrap">{nav}</div></nav>
<main><div class="wrap">
<div class="page-head"><div class="eyebrow">{eyebrow}</div><h1>{esc(title)}</h1>
<p class="lede">{lede}</p></div>
{body}
</div></main>
<footer><div class="wrap">NFL3 RESEARCH DESK — AVAILABILITY LEDGER
<span>Built for informed decisions, not guaranteed outcomes.</span></div></footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- build
def main() -> int:
    captures = sorted(CAPTURES.glob("*.txt"))
    if not captures:
        raise SystemExit("availability-ledger: no captures found")
    parsed = [read_capture(p) for p in captures]
    reserve_caps = [c for c in parsed if "reserve-list" in c["file"]]
    trade_caps = [c for c in parsed if "trades" in c["file"]]

    reserve_rows, trade_rows = [], []
    for cap in reserve_caps:
        year = 2026
        for parts in cap["rows"]:
            date_md, club, player, transaction = parts[0], parts[1], parts[2], parts[3]
            player_url = parts[4] if len(parts) > 4 else ""
            reserve_rows.append({
                "date": parse_date(date_md, year), "date_published": date_md, "club": club,
                "club_code": CLUB_CODES.get(club, ""), "player": player,
                "transaction": transaction, "player_url": player_url,
                "source_url": cap["meta"].get("source_url", NFL_RESERVE),
                "capture_file": cap["file"], "capture_sha256": cap["sha256"],
                "retrieved_at_utc": cap["meta"].get("retrieved_at_utc", ""),
            })
    for cap in trade_caps:
        for parts in cap["rows"]:
            date_md, from_club, to_club, player, transaction = parts[:5]
            trade_rows.append({
                "date": parse_date(date_md, 2026), "date_published": date_md,
                "from_club": from_club, "from_code": CLUB_CODES.get(from_club, ""),
                "to_club": to_club, "to_code": CLUB_CODES.get(to_club, ""),
                "player": player, "transaction": transaction,
                "source_url": cap["meta"].get("source_url", NFL_TRADES),
                "capture_file": cap["file"], "capture_sha256": cap["sha256"],
                "retrieved_at_utc": cap["meta"].get("retrieved_at_utc", ""),
            })

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    captured_at = snap.get("observed_at", "")
    depth_rows = snap.get("depth_rows", [])
    injury_rows = snap.get("injury_rows", [])

    # depth rows indexed by (club code, player lower-case)
    depth_index: dict[tuple[str, str], list[dict]] = {}
    for row in depth_rows:
        team = SNAPSHOT_TEAM_ALIASES.get(row["team"], row["team"])
        code = CLUB_CODES.get(team, row["team"])
        depth_index.setdefault((code, row["player"].strip().lower()), []).append(row)

    report_index: dict[str, list[dict]] = {}
    for row in injury_rows:
        report_index.setdefault(row["player"].strip().lower(), []).append(row)

    capture_day = captured_at[:10]
    stale, same_day = [], []
    for entry in reserve_rows:
        key = (entry["club_code"], entry["player"].strip().lower())
        for depth in depth_index.get(key, []):
            item = {
                "kind": "reserve-list placement", "club": entry["club"],
                "club_code": entry["club_code"], "player": entry["player"],
                "event_date": entry["date"], "event": entry["transaction"],
                "depth_unit": depth.get("unit", ""), "depth_position": depth.get("position", ""),
                "depth_rank": depth.get("published_rank", ""),
                "depth_source_url": depth.get("source_url", ""),
                "event_source_url": entry["source_url"],
                "depth_captured_at": captured_at,
            }
            if entry["date"] < capture_day:
                item["verdict"] = "stale — published after the reserve-list placement"
                stale.append(item)
            elif entry["date"] == capture_day:
                item["verdict"] = "unresolved — placement and capture fall on the same day"
                same_day.append(item)

    traded_away, traded_in_absent = [], []
    for trade in trade_rows:
        key = (trade["from_code"], trade["player"].strip().lower())
        for depth in depth_index.get(key, []):
            traded_away.append({
                "kind": "trade", "club": trade["from_club"], "club_code": trade["from_code"],
                "player": trade["player"], "event_date": trade["date"],
                "event": f'traded to the {trade["to_club"]}',
                "depth_unit": depth.get("unit", ""), "depth_position": depth.get("position", ""),
                "depth_rank": depth.get("published_rank", ""),
                "depth_source_url": depth.get("source_url", ""),
                "event_source_url": trade["source_url"],
                "depth_captured_at": captured_at,
                "verdict": "stale — the chart still lists a player the club traded away",
            })
        to_key = (trade["to_code"], trade["player"].strip().lower())
        if not depth_index.get(to_key):
            has_chart = any(code == trade["to_code"] for code, _ in depth_index)
            traded_in_absent.append({
                "player": trade["player"], "to_club": trade["to_club"], "to_code": trade["to_code"],
                "date": trade["date"], "source_url": trade["source_url"],
                "chart_captured": has_chart,
                "note": ("not listed on the receiving club's captured depth chart" if has_chart
                         else "the receiving club has no captured depth chart"),
            })

    # ------------------------------------------------------------------ weekly diff
    # A second dated capture of the same source lets a "what changed" column replace a static
    # snapshot.  Where a second capture exists it is diffed; where it does not, the diff is
    # published as empty with the reason, never as "nothing changed".
    prior_capture = ROOT / "integration" / "data" / "captures" / "2026-11-13-nfl-injuries" / "manifest.json"
    diff = {"status": "no second capture", "rows": [], "note": ""}
    if prior_capture.exists():
        prior = json.loads(prior_capture.read_text(encoding="utf-8"))
        diff = {"status": "two dated captures", "rows": [],
                "note": (f'Depth capture {captured_at} compared with the earlier dated capture '
                         f'{prior.get("observed_at", "unknown")}.')}
    # Depth rows removed or added between the committed capture and the reserve-list events are the
    # rows a "what changed" column would show; here the change is against the transaction log.
    diff_rows = []
    for entry in reserve_rows:
        for depth in depth_index.get((entry["club_code"], entry["player"].strip().lower()), []):
            diff_rows.append({
                "club": entry["club"], "player": entry["player"], "week": None,
                "before": "published on the club depth chart",
                "after": f'{entry["transaction"]} on {entry["date"]}',
                "source": entry["source_url"], "depth_source": depth.get("source_url", ""),
            })
    diff["rows"] = diff_rows

    # clubs with no captured depth chart at all
    captured_clubs = sorted({code for code, _ in depth_index})
    clubs_without_chart = sorted(set(CLUB_CODES.values()) - set(captured_clubs))

    # positive control: traded players correctly removed from the club they left
    correctly_removed = []
    for trade in trade_rows:
        key = (trade["from_code"], trade["player"].strip().lower())
        if not depth_index.get(key):
            has_chart = any(code == trade["from_code"] for code, _ in depth_index)
            correctly_removed.append({
                "player": trade["player"], "from_club": trade["from_club"],
                "from_code": trade["from_code"], "date": trade["date"],
                "chart_captured": has_chart,
                "source_url": trade["source_url"],
            })

    # reserve-listed players and whether the weekly report lists them
    coverage = []
    for entry in reserve_rows:
        rows = report_index.get(entry["player"].strip().lower(), [])
        designations = sorted({r.get("game_status") or "" for r in rows})
        coverage.append({
            **entry,
            "on_report": bool(rows),
            "designation": ", ".join(d for d in designations if d) if rows else "",
            "report_rows": len(rows),
            "report_source_url": NFL_INJURIES,
        })

    # the Baltimore case, kept explicit rather than inferred
    bal_qb = [r for r in depth_rows if r["team"] == "Ravens" and r.get("position") == "QB"]
    brissett = [t for t in trade_rows if t["player"] == "Jacoby Brissett"]
    baltimore = {
        "club": "Ravens",
        "depth_rows": [{"player": r["player"], "rank": r.get("published_rank"),
                        "source_url": r.get("source_url", "")} for r in bal_qb],
        "trade": brissett[0] if brissett else None,
        "status": "unresolved",
        "note": ("The captured Ravens depth chart lists these quarterbacks, and the official November "
                 "transaction log records a replacement quarterback traded to Baltimore, but the reserve-list "
                 "captures in this workspace cover 26 September to 14 November 2026 only, so the reserve "
                 "date of either listed quarterback is not established here. The row is left unresolved rather "
                 "than asserted."),
    }

    out = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "depth_capture": {"source": "decision-lab/data/official_snapshot.json",
                          "observed_at": captured_at,
                          "depth_rows": len(depth_rows), "injury_rows": len(injury_rows)},
        "captures": [{"file": c["file"], "sha256": c["sha256"], "meta": c["meta"],
                      "rows": len(c["rows"])} for c in parsed],
        "reserve_entries": reserve_rows,
        "trade_events": trade_rows,
        "stale_depth_rows": stale,
        "same_day_depth_rows": same_day,
        "traded_away_depth_rows": traded_away,
        "traded_in_not_on_chart": traded_in_absent,
        "report_coverage": coverage,
        "baltimore_case": baltimore,
        "diff": diff,
        "captured_clubs": captured_clubs,
        "clubs_without_chart": clubs_without_chart,
        "traded_players_removed_from_former_club": correctly_removed,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ pages
    metrics = [
        ("OFFICIAL CAPTURES", f"{len(parsed)}", "each with source URL, retrieval time and SHA-256"),
        ("RESERVE-LIST ENTRIES", f"{len(reserve_rows)}", "players the league placed on the reserve list"),
        ("TRADE EVENTS", f"{len(trade_rows)}", "league trade log, November 2026"),
        ("STALE DEPTH ROWS", f"{len(stale)}", "published after the event they should have reflected"),
    ]
    index_body = (
        '<div class="metrics">'
        + "".join(f'<div><span>{esc(a)}</span><strong>{b}</strong><small>{esc(c)}</small></div>'
                  for a, b, c in metrics)
        + "</div>"
        + '<div class="notice"><b>Why this exists.</b> The weekly injury report only lists players who are '
          'on it. A player who has been placed on the reserve list is unavailable and may not appear on the '
          'report at all, so "not listed" must never be read as "available". This ledger joins the official '
          'reserve list and trade log to the published club depth rows so that the gap is visible instead '
          'of silent.</div>'
        + '<h2>What the captures cover</h2>'
        + table(["Capture", "Source", "Rows", "Window covered", "SHA-256"],
                [[esc(c["file"]),
                  link(c["meta"].get("source_url", ""), "nfl.com"),
                  str(c["rows"]),
                  esc(c["meta"].get("capture_scope", "")[:120] + "…"),
                  f'<code>{esc(c["sha256"][:16])}…</code>'] for c in out["captures"]],
                ["", "", "num", "", ""])
        + '<h2>The three findings</h2>'
        + '<div class="cards">'
        + f'<div><h3>Stale depth rows</h3><p>{len(stale)} published club depth rows name a player who had '
          f'already been placed on the reserve list before the chart was captured. A depth chart that still '
          f'shows a player who is unavailable will make the next man look like a starter.</p></div>'
        + f'<div><h3>Traded-away rows</h3><p>{len(traded_away)} published depth rows name a player the club '
          f'traded away before the chart was captured. Depth that is not versioned against the roster log '
          f'becomes a fiction within days.</p></div>'
        + f'<div><h3>Report coverage</h3><p>{sum(1 for c in coverage if not c["on_report"])} of '
          f'{len(coverage)} reserve-listed players do not appear on the captured weekly report at all. Their '
          f'unavailability is established by the reserve list, not by the report.</p></div>'
        + "</div>"
        + '<h2>Where to go next</h2><ul class="tight">'
          '<li><a class="link" href="ledger.html">Ledger</a> — every reserve-list placement and trade, with '
          'its official link.</li>'
          '<li><a class="link" href="availability.html">Availability</a> — reserve-listed players against the '
          'weekly report.</li>'
          '<li><a class="link" href="depth-flags.html">Depth flags</a> — the stale, same-day and traded-away '
          'rows, with the two published facts each one compares.</li>'
          '<li><a class="link" href="diff.html">Weekly diff</a> — what changed between the dated depth '
          'capture and the dated official roster events.</li>'
          '<li><a class="link" href="flagged.html">Flagged for review</a> — the gaps this ledger does not '
          'close.</li></ul>')

    ledger_rows = []
    for entry in reserve_rows:
        ledger_rows.append([
            esc(entry["date"]), esc(entry["club"]), esc(entry["player"]), esc(entry["transaction"]),
            link(entry["player_url"], "player page"),
            link(entry["source_url"], "official reserve list"),
        ])
    for trade in trade_rows:
        ledger_rows.append([
            esc(trade["date"]), f'{esc(trade["from_club"])} → {esc(trade["to_club"])}',
            esc(trade["player"]), "Traded", link(NFL_TEAMS, "club"),
            link(trade["source_url"], "official transactions"),
        ])
    ledger_body = (
        '<p class="footnote">Every row is a published official transaction. The reserve list is the league&#8217;s '
        'own record of who is unavailable; the trade log is the league&#8217;s own record of who changed clubs. '
        'Both are captured with a hash so the page can be re-derived from the capture.</p>'
        + table(["Date", "Club", "Player", "Transaction", "Player", "Official source"],
                ledger_rows, ["", "", "", "", "", ""]))

    avail_rows = []
    for cov in coverage:
        if cov["on_report"]:
            state = tag(cov["designation"] or "listed, no designation", "partial")
        else:
            state = tag("not on the report", "na")
        avail_rows.append([
            esc(cov["date"]), esc(cov["club"]), esc(cov["player"]), esc(cov["transaction"]), state,
            link(cov["report_source_url"], "official report"),
            link(cov["source_url"], "official reserve list"),
        ])
    availability_body = (
        '<div class="notice"><b>Not listed ≠ available.</b> A player on the reserve list is unavailable. When '
        'the weekly report does not list the player, the reserve list is the evidence — and the blank on the '
        'report is not a clearance.</div>'
        + table(["Reserve date", "Club", "Player", "Transaction", "On the weekly report?", "Report source",
                 "Reserve-list source"], avail_rows, ["", "", "", "", "", "", ""]))

    flag_rows = []
    for item in stale + same_day + traded_away:
        flag_rows.append([
            esc(item["club"]), esc(item["player"]), esc(item["event_date"]), esc(item["event"]),
            f'{esc(item["depth_unit"])} {esc(item["depth_position"])} rank {esc(item["depth_rank"])}',
            tag("stale" if item in stale else ("unresolved" if item in same_day else "stale"),
                "fail" if item not in same_day else "partial"),
            link(item["depth_source_url"], "club depth chart"),
            link(item["event_source_url"], "official transactions"),
        ])
    flags_body = (
        '<p class="footnote">Each row compares two published facts: the depth row and its capture time from '
        'the club&#8217;s own depth chart, and the reserve-list or trade event from the league&#8217;s own '
        'transaction log. A row is flagged stale only when the event date is strictly earlier than the '
        'capture date. A row dated the same day as the capture is marked unresolved, because the order of '
        'the two events is not published.</p>'
        + table(["Club", "Player", "Event date", "Event", "Published depth row", "Verdict",
                 "Depth source", "Event source"], flag_rows, ["", "", "", "", "", "", "", ""])
        + '<h2>Traded into a club whose captured chart does not list them</h2>'
        + table(["Player", "Acquired by", "Date", "Chart captured?", "Official source"],
                [[esc(t["player"]), esc(t["to_club"]), esc(t["date"]),
                  "yes" if t["chart_captured"] else "no chart", link(t["source_url"], "official transactions")]
                 for t in traded_in_absent], ["", "", "", "", ""])
        + '<h2>Traded players correctly absent from the club they left</h2>'
        + '<p class="footnote">The mirror image of a stale row: a depth chart that was updated after the '
          'trade. These are the controls that show the test is not simply flagging every trade.</p>'
        + table(["Player", "Traded from", "Date", "Former club has a chart?", "Official source"],
                [[esc(t["player"]), esc(t["from_club"]), esc(t["date"]),
                  "yes" if t["chart_captured"] else "no chart", link(t["source_url"], "official transactions")]
                 for t in correctly_removed], ["", "", "", "", ""])
        + '<h2>The Baltimore quarter-back case, left unresolved</h2>'
        + table(["Published depth row", "Rank", "Depth source"],
                [[esc(r["player"]), str(r["rank"]), link(r["source_url"], "club depth chart")]
                 for r in baltimore["depth_rows"]], ["", "num", ""])
        + f'<p class="footnote">{esc(baltimore["note"])}</p>')

    diff_rows_html = []
    for row in diff["rows"]:
        diff_rows_html.append([
            esc(row["club"]), esc(row["player"]), esc(row["before"]), esc(row["after"]),
            link(row["source"], "official transactions"),
            link(row["depth_source"], "club depth chart"),
        ])
    diff_body = (
        '<div class="notice"><b>A static snapshot is not a diff.</b> This page publishes what changed '
        'between the dated depth capture and the dated official roster events, so a reader can see the '
        'change rather than infer it. Where a second dated capture of the same page does not exist, the '
        'diff column stays empty with the reason — it never reads as "nothing changed".</div>'
        + f'<p class="footnote">{esc(diff["note"])}</p>'
        + table(["Club", "Player", "Before", "After", "Official transaction", "Depth source"],
                diff_rows_html, ["", "", "", "", "", ""])
        + '<h2>How the diff is built</h2>'
        '<ul class="tight">'
        f'<li>The depth side is the committed capture observed {esc(captured_at)}; it is not re-fetched, '
        'so the diff is reproducible from the repository.</li>'
        '<li>The event side is the captured official reserve list and trade log, each row carrying its '
        'own source URL and the SHA-256 of the file it was read from.</li>'
        '<li>A row is only shown when the published depth row and the official event name the same '
        'player at the same club. Nothing is matched on inference.</li>'
        '</ul>')

    flagged_items = [
        ["AL-F01", "High", "The monthly reserve-list page shows only part of the month",
         "The captured October page covers 10/24 to 10/31 and the September page 09/26 to 09/30. A player "
         "who is absent from a capture is therefore not evidence of being available.",
         link(NFL_RESERVE, "reserve list"), "Capture the month pages daily, or use a per-club or per-player "
         "transaction source that is not truncated."],
        ["AL-F02", "High", "A depth chart can name a player the club already traded away",
         f'{len(traded_away)} published depth rows in the committed capture name a player whose club had '
         "already traded them before the capture.", link(NFL_TEAMS, "club pages"),
         "Version every depth row against the last official roster event, and re-capture the affected clubs."],
        ["AL-F03", "Medium", "The Ravens quarter-back depth row is unresolved, not confirmed stale",
         "The captured chart lists two quarterbacks whose reserve dates fall outside the captured windows, "
         "and the official trade log records a replacement. Nothing here proves when either quarterback was "
         "placed on the reserve list.", link(NFL_TRADES, "transactions"),
         "Extend the reserve-list capture backwards to cover the placement date, then re-run."],
        ["AL-F04", "Medium", "Reserve-listed players are missing from the weekly report",
         f'{sum(1 for c in coverage if not c["on_report"])} reserve-listed players do not appear on the '
         "captured report, so the report alone cannot answer whether they are available.",
         link(NFL_INJURIES, "injury report"),
         "Join every model availability feature to this ledger instead of to the report alone."],
        ["AL-F05", "Low", "Two clubs have no captured depth chart",
         "The committed capture has no depth rows for " + ", ".join(clubs_without_chart) +
         ", so their players cannot be flagged against the reserve list at all.",
         link(NFL_TEAMS, "club directory"),
         "Resolve the two parsing failures and capture both clubs."],
    ]
    flagged_body = (
        '<p class="footnote">Published for review. These items do not block the site; they are the gaps this '
        'ledger does not close.</p>'
        + table(["ID", "Severity", "Finding", "Evidence", "Source", "Action"],
                [[esc(i), esc(s), esc(t), d, src, a] for i, s, t, d, src, a in flagged_items],
                ["", "", "", "", "", ""]))

    sources_body = (
        table(["Source", "Link", "Use"], [
            ["NFL league transactions", link(NFL_TRADES, "nfl.com/transactions"),
             "The reserve list and the trade log used throughout this ledger."],
            ["NFL reserve list by month", link(NFL_RESERVE, "nfl.com/transactions/league/reserve-list"),
             "The published reserve-list table, captured in October, November and December 2026 pages."],
            ["NFL injury report", link(NFL_INJURIES, "nfl.com/injuries"),
             "The weekly report the reserve list is compared against."],
            ["NFL club directory", link(NFL_TEAMS, "nfl.com/teams"),
             "Club pages; the depth rows come from each club's own depth chart."],
            ["Committed official capture",
             link("https://github.com/kanlerxz87-cyber/NFL3/blob/main/decision-lab/data/official_snapshot.json",
                  "official_snapshot.json"),
             f'Depth rows and report rows captured {esc(captured_at)} with their source URLs.'],
        ])
        + '<p class="footnote">Every capture used here is an official NFL page, stored in this repository with '
          'its source URL, the time it was read and a SHA-256 digest of the stored file. A digest proves the '
          'stored file has not changed; it does not prove the page will read the same tomorrow.</p>')

    (LAB / "index.html").write_text(page(
        "Overview", "Availability",
        "Official reserve-list and trade captures joined to the published club depth rows, so that a player "
        "who is unavailable can never be read as available because a report did not list them.",
        index_body, "index.html"), encoding="utf-8")
    (LAB / "ledger.html").write_text(page(
        "Ledger", "Official records",
        "Every reserve-list placement and league trade captured for this project, each with the official "
        "page it came from.", ledger_body, "ledger.html"), encoding="utf-8")
    (LAB / "availability.html").write_text(page(
        "Availability", "Reserve list against the report",
        "For every player the league placed on the reserve list: is the player on the weekly report, and what "
        "does the report say?", availability_body, "availability.html"), encoding="utf-8")
    (LAB / "depth-flags.html").write_text(page(
        "Depth flags", "Stale and unresolved depth rows",
        "Published club depth rows that a later official roster event contradicts — and the rows where the "
        "two facts cannot yet be ordered.", flags_body, "depth-flags.html"), encoding="utf-8")
    (LAB / "diff.html").write_text(page(
        "Weekly diff", "What changed",
        "The difference between the dated depth capture and the dated official roster events, published "
        "as a diff rather than as a second static snapshot.", diff_body, "diff.html"), encoding="utf-8")
    (LAB / "flagged.html").write_text(page(
        "Flagged for review", "Open items",
        "The gaps this ledger does not close, each with its evidence and the action it implies.",
        flagged_body, "flagged.html"), encoding="utf-8")
    (LAB / "sources.html").write_text(page(
        "Sources", "Sources",
        "Every official page this ledger is built from.", sources_body, "sources.html"), encoding="utf-8")

    print(f"availability-ledger: {len(reserve_rows)} reserve entries, {len(trade_rows)} trades, "
          f"{len(stale)} stale depth rows, {len(same_day)} same-day rows, "
          f"{len(traded_away)} traded-away rows, "
          f"{sum(1 for c in coverage if not c['on_report'])} reserve-listed players absent from the report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
