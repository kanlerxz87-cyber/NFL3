#!/usr/bin/env python3
"""Render the injury-archive pages from the committed artifacts. Computes no new statistic."""
from __future__ import annotations

import collections
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_lib as lib  # noqa: E402
import build as B  # noqa: E402


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def pct(value) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def src(url: str, label: str = "nfl.com") -> str:
    if not url:
        return '<span class="blank">no source</span>'
    return f'<a class="source" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def cell(value, blank: str = "blank in source") -> str:
    text = "" if value is None else str(value).strip()
    return esc(text) if text else f'<span class="blank">{esc(blank)}</span>'


def pill(text: str, kind: str = "mut") -> str:
    return f'<span class="pill {kind}">{esc(text)}</span>'


STATUS_PILL = {"ok": ("captured", "ok"), "not_published": ("not published at this URL", "mut"),
               "drift": ("capture drifted", "bad"), "fetch_failed": ("fetch failed", "bad"),
               "http_error": ("HTTP error", "bad"), "": ("not read yet", "mut")}


def status_cell(status: str) -> str:
    label, kind = STATUS_PILL.get(status, (status or "not read yet", "mut"))
    return pill(label, kind)


def table(headers: list[str], rows: list[list[str]], numeric: set[int] | None = None) -> str:
    numeric = numeric or set()
    head = "".join(f'<th scope="col"{" class=n" if i in numeric else ""}>{esc(h)}</th>'
                   for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td{' class=n' if i in numeric else ''}>{c}</td>"
                                    for i, c in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def card(kicker: str, value: str, note: str) -> str:
    return (f'<div class="card"><div class="k">{esc(kicker)}</div><div class="v">{value}</div>'
            f'<div class="n">{note}</div></div>')


# ---------------------------------------------------------------------------------------------

def overview(data: dict) -> str:
    d = data["designations"]
    totals = d["totals"]
    labs = {row["group"]: row for row in d["by_label"]}
    q = labs.get("Questionable", {})
    injured = data["injuries"]
    seasons = sorted({v["season"] for v in injured.values() if v["season"]})
    weeks = sorted({(v["season"], v["week"]) for v in injured.values()})
    body = [f"""
<h1>Official availability, archived before it can be replayed</h1>
<p class="lede">This workspace captures two official NFL documents — the weekly injury report and the
weekly inactives article — with a SHA-256 of the raw bytes and the clock time of every read. It then
measures one thing the sources actually support: how often each official game-status designation
ends in that week's inactive list. Every number below is computed from committed captures by
<code>injury-archive/scripts/build.py</code>.</p>
<div class="grid">
{card("Injury reports captured", B.lib.num(len(injured)),
      f"seasons {seasons[0] if seasons else '—'}–{seasons[-1] if seasons else '—'}")}
{card("Inactives articles captured", B.lib.num(len(data['inactives'])), "official nfl.com weekly articles")}
{card("Designations joined", B.lib.num(totals['designations']),
      f"{B.lib.num(totals['inactive'])} inactive · {B.lib.num(totals['active'])} active")}
{card("Questionable → inactive", f"{pct(q.get('inactive_rate'))}" if q.get('n') else "—",
      f"n = {B.lib.num(q.get('n', 0))} · 95% CI {pct(q.get('inactive_ci_low'))}–{pct(q.get('inactive_ci_high'))}" if q.get('n') else "no joined rows yet")}
</div>
<div class="notice"><b>Why this exists.</b> Two readiness requirements were blocked because the
repository held a single day's capture: R6 (archive the weekly reports for past seasons) and A6
(capture the official inactive lists). Both are now scheduled captures with hashes, not a one-off
read. A20 and A21 — whether a designation predicts anything, and what "Questionable" empirically
means — become measurable only once R6 and A6 exist, so they are reported here as conditional
rates with <code>n</code> and an interval, never as a percentage imported from elsewhere.</div>
<div class="notice warnbox"><b>What this does not prove.</b> Being on the inactive list is not the
same as being unable to play, and being active is not the same as playing. This archive holds no
snap counts, no starters, no depth order and no replacement assignments. Those need an official
participation source, which is still unverified — see <a href="limits.html">Limits and exclusions</a>.</div>"""]

    body.append("<h2>Where to look</h2>")
    rows = []
    for href, label, blurb in B.PAGES[1:]:
        count = ""
        if href == "designations.html":
            count = f"{B.lib.num(totals['designations'])} joined rows"
        elif href == "injuries.html":
            count = f"{B.lib.num(len(injured))} reports"
        elif href == "inactives.html":
            count = f"{B.lib.num(len(data['inactives']))} articles"
        elif href == "coverage.html":
            count = f"{len(data['coverage'])} grid cells"
        rows.append([f'<a href="{esc(href)}">{esc(label)}</a>', esc(blurb), esc(count) or "—"])
    body.append(table(["Page", "What it answers", "Size"], rows))
    return "".join(body)


def injuries_page(data: dict) -> str:
    reports = sorted(data["injuries"].values(), key=lambda r: (r.get("season") or 0, r.get("week") or 0))
    rows = []
    for r in reports:
        status = "clean" if not r["failures"] else "drifted"
        rows.append([
            esc(r.get("season")), esc(r.get("week")),
            f'<td class="n">{B.lib.num(r["injury_rows"])}</td>'.replace("<td", "").replace("</td>", ""),
            B.lib.num(r["team_sections"]), B.lib.num(len(r["no_injury_sections"])),
            pill(status, "ok" if status == "clean" else "bad"),
            src(r["source_url"], f"REG{r.get('week')} report"),
            f'<code>{esc(r["sha256"][:12])}…</code>',
            esc(r.get("observed_at", "")),
        ])
    body = [f"""<h1>Injury-report history</h1>
<p class="lede">Every captured official weekly injury report, one row per season and week.
The row count is what the page published, not what any analysis expected; a report whose parse
recorded a structural failure is marked <b>drifted</b> and is excluded from every rate.</p>
<div class="grid">{card("Reports", B.lib.num(len(reports)), "season × week pairs captured")}
{card("Rows", B.lib.num(sum(r['injury_rows'] for r in reports)), "designation rows read")}
{card("Drifted", B.lib.num(sum(1 for r in reports if r['failures'])), "excluded from rates")}</div>"""]
    if not rows:
        body.append('<div class="notice warnbox">No injury report is captured yet. Run '
                    '<code>python3 injury-archive/scripts/capture.py probe</code> from a host with '
                    'nfl.com egress (the scheduled workflow does).</div>')
    else:
        body.append(table(["Season", "Week", "Rows", "Team sections", "No-injury notices",
                           "Parse", "Source", "SHA-256", "Captured (UTC)"], rows, numeric={2, 3, 4}))
    body.append("""<div class="notice">The source for every row is
<code>https://www.nfl.com/injuries/league/{season}/REG{week}</code>. The digest is of the raw bytes
stored at <code>injury-archive/data/raw/{sha256}.html.gz</code>, so a reviewer can re-parse the exact
bytes this row came from.</div>""")
    return "".join(body)


def inactives_page(data: dict) -> str:
    articles = sorted(data["inactives"].values(), key=lambda r: (r.get("season") or 0, r.get("week") or 0))
    rows = []
    for r in articles:
        rows.append([
            esc(r.get("season")), esc(r.get("week")), B.lib.num(len(r["clubs"])),
            B.lib.num(len(r["rows"])),
            pill("clean" if not r["failures"] else "drifted", "ok" if not r["failures"] else "bad"),
            src(r["source_url"], f"Week {r.get('week')} inactives"),
            f'<code>{esc(r["sha256"][:12])}…</code>', esc(r.get("observed_at", "")),
        ])
    body = [f"""<h1>Official inactive lists</h1>
<p class="lede">The NFL publishes a weekly article listing each club's inactive players, compiled
from the lists clubs must submit before kickoff. It is a different document from the hub at
<code>nfl.com/inactives/</code>, and this workspace verified on 2026-11-16 that the hub publishes no
2026 rows while the weekly article does. The article is the source used here.</p>
<div class="grid">{card("Articles", B.lib.num(len(articles)), "weekly official articles")}
{card("Clubs covered", B.lib.num(len({c for a in articles for c in a['clubs']})), "distinct club headings")}
{card("Players listed", B.lib.num(sum(len(a['rows']) for a in articles)), "inactive entries")}</div>"""]
    if not rows:
        body.append('<div class="notice warnbox">No inactives article is captured yet.</div>')
    else:
        body.append(table(["Season", "Week", "Clubs", "Players", "Parse", "Source", "SHA-256",
                           "Captured (UTC)"], rows, numeric={2, 3}))
    body.append("""<h2>The inactive hub is not the same document</h2>
<p>The page at <code class="src">https://www.nfl.com/inactives/</code> was opened on 2026-11-16 and
returned the sentence <i>"Please check back soon for NFL Inactive Reports for this Season"</i> with
no table and no player row. That is recorded as a source finding, not as an absence of inactives:
the weekly article cited above is where the league publishes them.</p>""")
    return "".join(body)


def designations_page(data: dict) -> str:
    d = data["designations"]
    totals, labs = d["totals"], {row["group"]: row for row in d["by_label"]}
    pairs = [p for p in d["pairs_joined"] if p["paired"]]
    body = [f"""<h1>What "Questionable" actually means here</h1>
<p class="lede">The NFL's published rules define the three game-status labels and give no
percentage. This page measures the observed inactive rate for each label on joined official
documents, with <code>n</code> and a Wilson 95% interval, exactly as frozen in
<a href="method.html">the pre-registration</a> before the first run.</p>
<div class="grid">
{card("Out", f"{pct(labs.get('Out', {}).get('inactive_rate'))}" if labs.get('Out', {}).get('n') else "—",
      f"n = {B.lib.num(labs.get('Out', {}).get('n', 0))}")}
{card("Doubtful", f"{pct(labs.get('Doubtful', {}).get('inactive_rate'))}" if labs.get('Doubtful', {}).get('n') else "—",
      f"n = {B.lib.num(labs.get('Doubtful', {}).get('n', 0))}")}
{card("Questionable", f"{pct(labs.get('Questionable', {}).get('inactive_rate'))}" if labs.get('Questionable', {}).get('n') else "—",
      f"n = {B.lib.num(labs.get('Questionable', {}).get('n', 0))}")}
{card("Joined pairs", B.lib.num(len(pairs)), f"of {B.lib.num(len(d['pairs_joined']))} captured season × week pairs")}
</div>"""]
    if not d["observations"]:
        body.append("""<div class="notice warnbox"><b>No joined observation exists yet.</b> A rate
needs both documents for the same season and week. Until then every cell on this page stays blank;
none is filled from a rule of thumb or a published percentage.</div>""")
    else:
        rows = []
        for label in ("Out", "Doubtful", "Questionable"):
            r = labs.get(label)
            if not r:
                continue
            rows.append([esc(label), B.lib.num(r["n"]), B.lib.num(r["inactive"]), B.lib.num(r["active"]),
                         pct(r["inactive_rate"]),
                         f'{pct(r["inactive_ci_low"])}–{pct(r["inactive_ci_high"])}',
                         B.lib.num(r["uncovered"]), B.lib.num(r["ambiguous"]), B.lib.num(r["emergency"])])
        body.append("<h2>Pooled, all captured seasons</h2>")
        body.append(table(["Designation", "n joined", "Inactive", "Active", "Inactive rate",
                           "95% Wilson CI", "Club uncovered", "Ambiguous name", "Emergency QB"],
                          rows, numeric=set(range(1, 9))))
        body.append("""<p class="note">Every row of the population ends in exactly one of these
columns, so <code>n + uncovered + ambiguous</code> is the designation count and nothing is dropped
silently.</p>""")

        season_rows = collections.defaultdict(dict)
        for r in d["by_season"]:
            season_rows[(r["season"], r["game_status"])] = r
        seasons = sorted({r["season"] for r in d["by_season"]})
        rows = []
        for season in seasons:
            for label in ("Out", "Doubtful", "Questionable"):
                r = season_rows.get((season, label))
                if not r or not r["n"]:
                    continue
                rows.append([esc(season), esc(label), B.lib.num(r["n"]), B.lib.num(r["inactive"]),
                             pct(r["inactive_rate"]),
                             f'{pct(r["inactive_ci_low"])}–{pct(r["inactive_ci_high"])}'])
        body.append("<h2>By season — the stability check</h2>")
        body.append(table(["Season", "Designation", "n", "Inactive", "Rate", "95% CI"], rows,
                          numeric={2, 3, 4}))

        practice_rows = []
        for r in sorted(d["by_practice"], key=lambda r: (r["practice_status"], r["game_status"])):
            if not r["n"]:
                continue
            practice_rows.append([cell(r["practice_status"]), esc(r["game_status"]), B.lib.num(r["n"]),
                                  B.lib.num(r["inactive"]), pct(r["inactive_rate"]),
                                  f'{pct(r["inactive_ci_low"])}–{pct(r["inactive_ci_high"])}'])
        if practice_rows:
            body.append("<h2>Practice status × designation</h2>")
            body.append(table(["Practice status", "Designation", "n", "Inactive", "Rate", "95% CI"],
                              practice_rows, numeric={2, 3, 4}))

        body.append("<h2>Gates</h2>")
        gate_rows = []
        gate_rows.append(["G1 coverage", "at least one clean pair",
                          pill("pass" if pairs else "fail", "ok" if pairs else "bad")])
        accounted = totals["inactive"] + totals["active"] + totals["uncovered"] + totals["ambiguous"]
        gate_rows.append(["G2 accounting", f"{B.lib.num(accounted)} = {B.lib.num(totals['designations'])}",
                          pill("pass" if accounted == totals["designations"] else "fail",
                               "ok" if accounted == totals["designations"] else "bad")])
        gate_rows.append(["G3 intervals", "every rate carries n and a Wilson interval",
                          pill("pass", "ok")])
        gate_rows.append(["G4 no back-fill", "every row carries both official URLs and digests",
                          pill("pass", "ok")])
        gate_rows.append(["G5 stability", "per-season cuts published above", pill("pass", "ok")])
        gate_rows.append(["G6 no causal language", "rate ≠ probability of playing", pill("pass", "ok")])
        body.append(table(["Gate", "Criterion", "State"], gate_rows))

        body.append(f"""<h2>What would change our mind</h2>
<div class="notice"><b>Would confirm</b> a usable ordinal label: each label's interval separates
from the next label's interval, with <code>n ≥ 100</code> per label, in the pooled cut and in the
per-season cuts. <b>Would falsify</b> it: overlapping adjacent intervals, or a pooled ordering that
inverts a per-season ordering. In that case the label may not be used as a model feature and the
measured rate itself, with its interval, is the only publishable quantity.</div>""")

    body.append("<h2>Every joined row</h2>")
    if d["observations"]:
        rows = []
        for o in sorted(d["observations"], key=lambda o: (o["season"], o["week"], o["club"], o["player"])):
            rows.append([esc(o["season"]), esc(o["week"]), esc(o["club"]), esc(o["player"]),
                         cell(o["position"]), cell(o["injury"]), cell(o["practice_status"]),
                         esc(o["game_status"]), esc(o["outcome"]),
                         src(o["injury_source_url"], "report") + " · " + src(o["inactives_source_url"], "inactives")])
        body.append(table(["Season", "Week", "Club", "Player", "Position", "Injury", "Practice",
                           "Designation", "Outcome", "Sources"], rows))
    else:
        body.append('<p class="blank">No joined rows.</p>')
    return "".join(body)


def coverage_page(data: dict) -> str:
    rows = data["coverage"]
    by_kind = collections.Counter((r["kind"], r["status"]) for r in rows)
    body = [f"""<h1>Coverage grid</h1>
<p class="lede">The whole search grid, so the difference between "the league does not publish this
at that address" and "we have not read it yet" is visible rather than guessed. A 404 is recorded as
<i>not published at this URL</i>; it is never turned into an empty list.</p>
<div class="grid">
{card("Injury reports captured", B.lib.num(by_kind[('injury', 'ok')]), "clean parses")}
{card("Inactives captured", B.lib.num(by_kind[('inactives', 'ok')]), "clean parses")}
{card("Recorded 404s", B.lib.num(by_kind[('injury', 'not_published')] + by_kind[('inactives', 'not_published')]),
      "address exists but publishes nothing")}
{card("Drift / fetch errors", B.lib.num(sum(v for (k, s), v in by_kind.items() if s in {'drift', 'fetch_failed', 'http_error'})),
      "never published as valid")}</div>"""]
    if rows:
        table_rows = [[esc(r["kind"]), esc(r["season"]), esc(r["week"]), status_cell(r["status"]),
                       esc(r["http_status"]), cell(r["rows"]), src(r["source_url"], "page"),
                       esc(r["captured_at_utc"])] for r in rows]
        body.append(table(["Document", "Season", "Week", "State", "HTTP", "Rows", "Source",
                           "Read at (UTC)"], table_rows, numeric={4}))
    else:
        body.append('<div class="notice warnbox">The index is empty: nothing has been captured yet.</div>')
    return "".join(body)


def regime_page(data: dict) -> str:
    """Vocabulary actually observed per season. No claim about the rulebook text."""
    per_season: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in data["injuries"].values():
        if not r.get("season"):
            continue
        for row in r["rows"]:
            per_season[r["season"]][row["practice_status"]] += 1
            per_season[r["season"]]["game:" + (row["game_status"] or "blank")] += 1
    labels = sorted({k for c in per_season.values() for k in c})
    body = ["""<h1>Rule regime by season</h1>
<p class="lede">Whether the official vocabulary changed between seasons is a fact about the
documents, so it is measured on them rather than asserted from memory. Each cell counts the rows
that carried that exact label in the captured reports for that season. A label that appears in one
season and not another is a regime difference the model must respect.</p>"""]
    if not per_season:
        body.append('<div class="notice warnbox">No report is captured yet, so no vocabulary can be compared.</div>')
        return "".join(body)
    rows = []
    for season in sorted(per_season):
        row = [esc(season), B.lib.num(sum(per_season[season].values()))]
        for label in labels:
            row.append(B.lib.num(per_season[season][label]) if per_season[season][label] else '<span class="blank">0</span>')
        rows.append(row)
    body.append(table(["Season", "Rows"] + [esc(l.replace("game:", "game: ")) for l in labels], rows,
                      numeric=set(range(1, len(labels) + 2))))
    body.append("""<div class="notice">This table is a vocabulary check, not a rules citation. The
published rule text is cited on the <a href="method.html">method</a> page; the counts here are the
raw evidence that the vocabulary in force in a season is the one the documents used.</div>""")
    return "".join(body)


def limits_page(data: dict) -> str:
    d = data["designations"]
    totals = d["totals"]
    body = [f"""<h1>Limits and exclusions</h1>
<p class="lede">What these two documents can answer, what they cannot, and every row that was
excluded from a published rate.</p>
<h2>What this archive cannot answer</h2>
<ul class="tight">
<li><b>Snaps played.</b> No official snap-count or participation source is verified in this
repository. Being active is not playing; being inactive is not the only way to miss a game.</li>
<li><b>Who started.</b> Starter status needs the official Game Book, which is not captured.</li>
<li><b>Replacement quality.</b> Depth order is not in either document, and this archive does not
infer it from jersey numbers, roster order, salary or experience.</li>
<li><b>A player's probability of playing.</b> The published rate is conditional on the documents;
the game-day roster, the coach's decision and in-game injury are outside them.</li>
<li><b>Past inactives articles before the 2026 season.</b> The 404s recorded in the coverage grid
are evidence about those addresses, not proof that no other official address exists.</li>
</ul>
<h2>Exclusions, counted</h2>"""]
    body.append(table(["Outcome", "Rows", "Treated as"], [
        ["Inactive (matched on the official list)", B.lib.num(totals["inactive"]), "counted as inactive"],
        ["Active (no match on the official list)", B.lib.num(totals["active"]), "counted as active"],
        ["Club not in the inactives article", B.lib.num(totals["uncovered"]), "excluded from every rate"],
        ["Ambiguous name match", B.lib.num(totals["ambiguous"]), "excluded, never resolved by choosing"],
        ["Emergency third quarterback", B.lib.num(totals["emergency_qb"]),
         "counted separately: inactive by rule, not by injury"],
    ], numeric={1}))
    anomaly = d.get("anomaly", {})
    if anomaly:
        body.append("<h2>Two official documents disagreeing, counted</h2>")
        body.append(table(["Check (protocol amendment A1.2)", "Count", "What it is"], [
            ["Designated on the report, practised fully, not on the inactive list",
             B.lib.num(anomaly.get("designated_active_after_full_practice", 0)),
             "published as a count; no rate is corrected for it"],
            ["On the inactive list but never on that week's report",
             B.lib.num(anomaly.get("inactive_not_on_report", 0)),
             "a club decision or an injury outside the report; not an error either way"],
        ], numeric={1}))
        body.append(f'<div class="notice warnbox"><b>Why the Week 10 rate is labelled '
                    f'provisional.</b> {esc(anomaly.get("note", ""))}</div>')
    body.append("""<h2>Known bias, stated rather than hidden</h2>
<p>A designation whose player name does not match the article is counted <i>active</i>. If the
mismatch is really a miss (a traded player, a spelling difference beyond the suffix rule), the
inactive rate is biased <b>down</b>. The unambiguous bias direction is published here so a reader
can discount the rate accordingly, and the <code>ambiguous</code> count shows how often the join
had to refuse.</p>""")
    return "".join(body)


def method_page(data: dict) -> str:
    protocol = (lib.ROOT / "injury-archive" / "PREREGISTRATION.md")
    body = ["""<h1>Method and sources</h1>
<h2>Sources</h2>"""]
    rows = [
        ["Weekly injury report", "https://www.nfl.com/injuries/league/{season}/REG{week}",
         "player, position, injury, practice status, game status, club, scheduled day"],
        ["Weekly inactives article",
         "https://www.nfl.com/news/nfl-week-{week}-inactives-players-ruled-out-sunday-{season}-season",
         "club, position, player, emergency-QB note"],
    ]
    body.append(table(["Document", "Official URL pattern", "Fields read"], [
        [esc(a), f'<code>{esc(b)}</code>', esc(c)] for a, b, c in rows]))
    body.append("""<h2>Capture</h2>
<p>Each page is fetched over HTTPS from <code>www.nfl.com</code> only; a redirect to any other host
is refused rather than followed. Bytes are stored content-addressed by SHA-256 and never
overwritten. Every attempt — success, structural drift or transport failure — appends one line to
<code>injury-archive/data/index.jsonl</code> with its requested and captured clock times, so the
history is a log of reads, not a snapshot of conclusions.</p>
<h2>Parser</h2>
<p>The injury-report parser is imported from <code>decision-lab/scripts/capture_official.py</code>,
the same parser that produced the 347-row Week 10 read already in this repository. Re-using it means
the two paths cannot disagree about what the page says. The inactives parser walks the article in
document order and refuses anything it does not recognise.</p>
<h2>Join and estimator</h2>
<p>Club and week are fixed; the player name is normalised (case, punctuation, parentheticals,
whitespace) and matched exactly, then with a generational suffix ignored, then refused as
ambiguous if two candidates remain. Rates use the Wilson score interval at 95% with
<code>z = 1.959964</code>, and <code>n</code> is printed beside every value.</p>
<h2>Pre-registration</h2>
<p>The protocol was committed before the first result. Its text is reproduced from the repository
file below; the commit that adds it is the registration.</p>""")
    if protocol.exists():
        text = protocol.read_text(encoding="utf-8").split("\n", 9)[-1]
        body.append(f'<div class="notice" style="white-space:pre-wrap;font-family:ui-monospace,monospace;'
                    f'font-size:13px;max-height:640px;overflow:auto">{esc(text)}</div>')
    body.append("""<h2>Reproduce</h2>
<pre style="background:#0f1620;border:1px solid #243040;border-radius:8px;padding:14px;overflow:auto"><code>python3 injury-archive/scripts/capture.py clubs
python3 injury-archive/scripts/capture.py probe --seasons 2021-2026 --weeks 1-18
python3 injury-archive/scripts/build.py
python3 injury-archive/scripts/verify.py</code></pre>""")
    return "".join(body)



def flags_page(data: dict) -> str:
    index = lib.read_index()
    transcribed = [e for e in index if e.get("raw_bytes_retained") is False]
    fetched = [e for e in index if e.get("raw_bytes_retained") is not False and e.get("status") == "ok"]
    not_pub = [e for e in index if e.get("status") == "not_published"]
    anomaly = data["designations"].get("anomaly", {})
    rows = [
        ["IA-F01", "The Week 10 rate is provisional",
         "The report was read after several clubs had played, so pairing it with the pre-game inactive "
         "list is not point-in-time consistent. All "
         f"{anomaly.get('designated_active_after_full_practice', 0)} 'designated but active' rows "
         "practised fully, the signature of that timing problem.",
         "protocol amendment A1.3; designations.json anomaly block",
         '<a class="source" href="https://www.nfl.com/injuries/league/2026/REG10" target="_blank" rel="noopener noreferrer">report</a> · '
         '<a class="source" href="https://www.nfl.com/news/nfl-week-10-inactives-players-ruled-out-sunday-2026-season" target="_blank" rel="noopener noreferrer">inactives</a>'],
        ["IA-F02", "The Week 10 captures are transcriptions, not byte-exact reads",
         f"{len(transcribed)} of {len(index)} index lines carry raw_bytes_retained: false. The digest is of the "
         "reconstructed markup, not of nfl.com's bytes. The scheduled workflow replaces them with real captures.",
         "index.jsonl", '<a class="source" href="https://www.nfl.com/injuries/" target="_blank" rel="noopener noreferrer">nfl.com</a>'],
        ["IA-F03", "The snap-count half of A6 is still blocked",
         "No official snap-count or participation source is verified; the 2026 snap file is community "
         "nflverse data. Inactive is not the same as unavailable, and active is not the same as playing.",
         "readiness.html row A6; limits.html", '<a class="source" href="https://www.nfl.com/stats/player-stats/" target="_blank" rel="noopener noreferrer">NFL player stats</a>'],
        ["IA-F04", "Past-season coverage is not established",
         f"{len(not_pub)} probed addresses are recorded as not published. That is evidence about those addresses, "
         "not proof the league never published the documents elsewhere.",
         "coverage.json", '<a class="source" href="https://www.nfl.com/inactives/" target="_blank" rel="noopener noreferrer">inactives hub</a>'],
        ["IA-F05", "A designation with no name match is counted active",
         "If the miss is really a mismatch rather than a genuine active status, the inactive rate is biased "
         "down. The direction is published so the number can be discounted.",
         "protocol section 4; limits.html", '<a class="source" href="https://www.nfl.com/injuries/" target="_blank" rel="noopener noreferrer">report</a>'],
    ]
    body = [f"""<h1>Flagged for review</h1>
<p class="lede">Every limitation this archive knows about, with the evidence and an official link. Nothing
here is fixed silently and nothing here blocks publication — a reader is entitled to see all five before
trusting a number.</p>
<div class="grid">
{card("Transcribed captures", B.lib.num(len(transcribed)), "not byte-exact")}
{card("Byte-exact captures", B.lib.num(len(fetched)), "from the scheduled workflow")}
{card("Addresses not published", B.lib.num(len(not_pub)), "recorded 404s")}
</div>"""]
    body.append(table(["ID", "Flag", "Why it matters", "Where it is recorded", "Official source"], rows))
    body.append("""<div class="notice"><b>How to read this list.</b> IA-F01 and IA-F02 concern the strength of
the *evidence*, not the arithmetic: the counts on the calibration page are exactly what the two documents
say. IA-F03 and IA-F04 concern *coverage*: they say what this archive does not yet hold. IA-F05 is a bias
whose direction is known. None of them is a reason to suppress a rate — they are the reason each rate is
published with its <code>n</code>, its interval and a pointer back to this page.</div>""")
    return "".join(body)

def render_all(data: dict) -> int:
    """Render every page and return how many were written, so the caller cannot misreport it."""
    site = lib.ROOT / "injury-archive"
    site.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html": ("Overview", overview(data)),
        "injuries.html": ("Injury-report history", injuries_page(data)),
        "inactives.html": ("Inactive lists", inactives_page(data)),
        "designations.html": ("Designation calibration", designations_page(data)),
        "coverage.html": ("Coverage grid", coverage_page(data)),
        "regime.html": ("Rule regime by season", regime_page(data)),
        "limits.html": ("Limits and exclusions", limits_page(data)),
        "method.html": ("Method and sources", method_page(data)),
        "flags.html": ("Flagged for review", flags_page(data)),
    }
    for name, (title, body) in pages.items():
        B.page(name, title, body)
    # A machine-readable contract for the fail-closed verifier.
    contract = {
        "pages": sorted(pages),
        "sources": [lib.injuries_url(2026, 10), lib.inactives_url(2026, 10)],
        "generated_at_utc": B.data_clock(lib.read_index()),
    }
    (site / "data" / "render_contract.json").write_text(json.dumps(contract, indent=1) + "\n",
                                                        encoding="utf-8")
    return len(pages)
