#!/usr/bin/env python3
"""Additional decision-lab pages: availability, verification and decision paths.

Imported by ``build.py``. Helpers are pulled from the ``build`` module at call
time to avoid a circular import at module load.
"""
from __future__ import annotations


def _ui():
    import build as b  # already initialised when these builders run
    return b


def build_availability() -> str:
    B = _ui()
    e, td, table, shell, metric, pill, source_link, raw_source = (
        B.e, B.td, B.table, B.shell, B.metric, B.pill, B.source_link, B.raw_source)
    A = B.AVAILABILITY
    if not A:
        return shell("Availability & replacements", "availability.html",
                     '<div class="eyebrow">Availability</div><h1>Availability analysis unavailable</h1>'
                     '<p class="lede">Run <code>python3 decision-lab/scripts/availability.py</code>. '
                     'No values are shown rather than guessed.</p>')
    cov, status = A["coverage"], A["report_status_counts"]
    designated = sum(v for k, v in status["game_status"].items() if k != "blank")
    depleted = [s for s in A["depth_slots"] if s["top3_listed"] >= 2]
    metrics = "".join([
        metric("Report rows", str(cov["injury_rows"]), "NFL.com Week 10 capture"),
        metric("Joined to club depth", str(cov["matched_rows"]), f'{cov["unmatched_rows"]} unmatched, all listed'),
        metric("Replacement leads", str(cov["replacement_leads"]), "rank-1 players with a next man published"),
        metric("Depleted slots", str(len(depleted)), "2+ of the top 3 on the report"),
        metric("Matchups complete", f'{cov["clubs_represented"]}/{2 * cov["matchups"]}', "club sections captured"),
        metric("Game designations", str(designated), "of 254 rows carry Out/Questionable"),
    ])
    content = (
        '<div class="eyebrow">Offense and defense depth pressure</div><h1>Availability, depth and replacement evidence</h1>'
        '<p class="lede">Which published starters are on this week\'s official report, who the club lists next, and where the '
        'data cannot answer the question. Every row links to the official source. Nothing here is a projection.</p>'
        '<div class="notice danger"><strong>Read the boundary first:</strong> a published depth rank is column order on a club '
        f'page — not a confirmed starter, snap share or assignment. A blank injury designation is <em>not</em> evidence that a player '
        f'is active: the NFL policy says a player certain to play is not listed in the game-status report, and {status["game_status"].get("blank", 0)} '
        'of 254 rows carry no designation. Availability cannot be inferred from this page alone.</div>'
        f'<div class="metrics">{metrics}</div>'
        '<h2>How the evidence is joined</h2>'
        + table("Method, stated so it can be attacked.", ["Step", "Rule", "Source"], [
            [td("1 · Capture"), td("Official NFL report plus each club's published depth page, hashed at capture time."), td(source_link("S01"))],
            [td("2 · Join"), td(e(A["method"]["join_key"])), td(source_link("S05"))],
            [td("3 · Families"), td(e(A["method"]["position_families"])), td(source_link("S29"))],
            [td("3b · Non-tabular charts"), td("Two clubs do not publish a parseable table: the Texans publish an image, the Packers prepend jersey numbers."), td(source_link("S28") + "<br>" + source_link("S29"))],
            [td("4 · Replacement lead"), td(e(A["method"]["replacement_rule"])), td(source_link("S06"))],
            [td("5 · Blanks"), td("A blank game designation is not 'active': the policy says a player certain to play is not listed in the game-status report."), td(source_link("S03"))],
        ])
        + '<h2>Coverage and why rows are missing</h2>'
        + table("Every unmatched row has a stated reason.", ["Clubs on report", "Clubs with parsed depth", "Unmatched rows",
                                                            "Clubs without parsed depth", "Source"], [
            [td(str(cov["clubs_on_report"])), td(str(cov["clubs_with_depth"])), td(str(cov["unmatched_rows"])),
             td(", ".join(cov["clubs_on_report_without_depth"]) or "none"), td(source_link("S24"))],
        ])
    )
    unmatched_rows = [[td(e(u["team"])), td(e(u["player"])), td(e(u["position"])), td(e(u["practice_status"])),
                       td(e(u["game_status"]) or "—"), td(e(u["reason"])),
                       td(raw_source(u["report_url"], "NFL report")),
                       td(raw_source(u["depth_url"], "Club depth") if u["depth_url"] else "—")]
                      for u in A["unmatched"]]
    content += (f'<h2>Unmatched report rows ({len(unmatched_rows)})</h2>'
                '<p>These players appear on the official report but could not be matched to a captured club depth row. '
                'They are not dropped, and no replacement is guessed.</p>')
    content += table("Unmatched rows with the reason and both source links.",
                     ["Team", "Player", "Pos", "Practice", "Game", "Reason", "Report", "Depth page"], unmatched_rows)
    depleted_rows = [[td(e(s["team"])), td(e(s["unit"])), td(e(s["slot"])), td(str(s["top3_listed"])),
                      td("; ".join(f'{x["player"]} (#{x["rank"]}, {x["practice_status"]}'
                                   + (f', {x["game_status"]}' if x["game_status"] else "") + ")"
                                   for x in s["listed_on_report"])),
                      td(raw_source(s["report_url"], "NFL report")), td(raw_source(s["depth_url"], "Club depth"))]
                     for s in depleted]
    content += (f'<h2>Depleted depth slots ({len(depleted_rows)})</h2>'
                '<p>A slot is listed when at least two of its top three published players appear on this week\'s report. '
                'This is a research lead: confirmation needs the inactive list and snap counts, which are not captured.</p>')
    content += table("Slots where more than one published player is on the report.",
                     ["Team", "Unit", "Slot", "Listed", "Players on report", "Report", "Depth page"], depleted_rows)
    leads = [[td(e(r["team"])), td(e(r["player"])), td(e(r["position"])), td(e(r["game_status"]) or "—"),
              td(e(r["practice_status"])), td(e(r["published_slot"])), td(e(r["next_player"])),
              td(e(r["next_position"])), td(str(r["next_rank"])), td(e(r["next_status"]) or "not on report"),
              td(e(r["note"])), td(raw_source(r["depth_url"], "Club depth"))]
             for r in A["replacement_leads"]]
    content += (f'<h2>Replacement leads ({len(leads)})</h2>'
                '<p>For each published rank-1 player who is on the report, the next player the club publishes in the same unit '
                'and position family. The lead is a question to verify, not a lineup.</p>')
    content += table("Published next-man evidence for listed rank-1 players.",
                     ["Team", "Listed player", "Pos", "Game status", "Practice", "Published slot", "Next published",
                      "Pos", "Rank", "Next player status", "Note", "Depth page"], leads)
    content += ('<div class="notice warn"><strong>What this page cannot do:</strong> it cannot say who will start, who will be '
                'inactive, how many snaps a backup will play, or how much a replacement changes the score. Those require the '
                'inactive list, snap counts and measured performance. See <a href="questions.html">questions Q23–Q28</a> and '
                '<a href="flagged.html">flagged items F15–F22</a>.</div>')
    content += table("No-injury sections are evidence too.", ["Team", "Matchup", "Published text", "Source"],
                     [[td(e(r["team"])), td(e(r["matchup"])), td(e(r["text"])), td(raw_source(r["source_url"], "NFL report"))]
                      for r in A["no_injury_sections"]])
    return shell("Availability & replacements", "availability.html", content)


def build_integrity() -> str:
    B = _ui()
    e, td, table, shell, metric, pill, raw_source = B.e, B.td, B.table, B.shell, B.metric, B.pill, B.raw_source
    doc = B.VERIFICATION
    if not doc:
        return shell("Verification & integrity", "integrity.html",
                     '<div class="eyebrow">Verification</div><h1>No automated verification run recorded</h1>'
                     '<p class="lede">Run <code>python3 decision-lab/scripts/verify_live.py</code> (live) or with <code>--offline</code>.</p>')
    totals = doc["row_totals"]
    metrics = "".join([
        metric("Run mode", doc.get("mode", "live"), "live re-fetches; offline is structure only"),
        metric("Status", doc.get("status", ""), "verified / drift / row-set-differs / partial / structural-only"),
        metric("Checks run", str(doc["checks_run"]), f'{doc["checks_compared"]} comparable'),
        metric("Rows compared", str(totals["rows_checked"]), f'{totals["mismatched"]} field mismatch(es)'),
        metric("Sources unreachable", str(doc["checks_unreachable"]), "never counted as a pass"),
    ])
    content = (
        '<div class="eyebrow">Line-by-line integrity</div><h1>Verification &amp; integrity</h1>'
        '<p class="lede">Every published value is re-derived from the official source and compared field by field. A source '
        'that cannot be reached is reported as unreachable and is never counted as a pass. This page is the automated live '
        'check; the independent hand-checked transcription lives on the <a href="verification.html">Verification log</a>.</p>'
        f'<div class="notice"><strong>Run at</strong> {e(doc["run_at"])} · <strong>snapshot captured</strong> '
        f'{e(doc["snapshot_observed_at"])} · <strong>method</strong> {e(doc.get("mode", "live"))} re-parse with the same parser '
        'that produced the snapshot, then a field-by-field comparison.</div>'
        f'<div class="metrics">{metrics}</div>'
    )
    fam = [[td(e(f["id"])), td(e(f["name"])),
            td(pill(f["status"], "ok" if f["status"] == "match" else ("danger" if f["status"] in {"drift", "unreachable"} else "warn"))),
            td(e(f["method"])), td(f'{f["matched"]}/{f["rows_checked"]}' if f["rows_checked"] else "—"),
            td(str(f["mismatched"])), td(e(f["note"])),
            td(raw_source(f["source_url"], "Official source") if f["source_url"] else "—")]
           for f in doc["families"]]
    content += table("Verification families. Each family is an independent claim about the data; catch-all rows exist so the families are visible even when a live fetch fails.",
                     ["ID", "Check", "Status", "Method", "Match", "Mismatch", "Note", "Source"], fam)
    if doc.get("skipped_offline"):
        content += (f'<div class="notice warn"><strong>Skipped in this run ({e(doc.get("mode"))}):</strong> '
                    f'{e("; ".join(doc["skipped_offline"]))}. The scheduled publication workflow runs the live re-fetch.</div>')
    if doc["mismatches"]:
        rows = [[td(e(m.get("scope", ""))), td(e(m["key"])), td(e(m["field"])), td(e(str(m.get("published", "")))),
                 td(e(str(m.get("live", "")))), td(raw_source(m["source_url"], "Source") if m.get("source_url") else "—")]
                for m in doc["mismatches"][:200]]
        content += f'<h2>Mismatches and drift ({doc["mismatch_count"]})</h2>'
        content += table("Every mismatch, published versus live. Reported, never auto-corrected.",
                         ["Scope", "Row", "Field", "Published", "Live", "Source"], rows)
    if doc["unreachable"]:
        rows = [[td(e(u["family"])), td(e(u["url"])), td(e(u["error"])), td(raw_source(u["url"], "Retry source"))]
                for u in doc["unreachable"][:80]]
        content += (f'<h2>Unreachable sources ({len(doc["unreachable"])})</h2>'
                    '<p>An unreachable source proves nothing about the data. These checks are recorded as not comparable.</p>')
        content += table("Sources that could not be fetched during this run.", ["Family", "URL", "Error", "Source"], rows)
    content += table("What each status means, and why a row difference is not a value error.",
                     ["Status", "Meaning", "Action", "Source"], [
        [td("match"), td("Every compared field equals the official source, and the row set is unchanged."), td("Verified for this moment only."), td(B.source_link("S01"))],
        [td("row-set-differs"), td("No published value changed, but the live page lists a different set of rows (for example it moved on to the next week)."), td("Re-capture and re-version; do not describe this as a data error."), td(B.source_link("S01"))],
        [td("drift"), td("A value that exists in both published and live data differs."), td("Treat as a real discrepancy; the official source wins."), td(B.source_link("S01"))],
        [td("unreachable"), td("The source could not be fetched, so nothing was compared."), td("Do not treat the published value as verified."), td(B.source_link("S01"))],
        [td("structural-only"), td("Offline run: joins and coverage were checked, live fields were not."), td("Wait for the scheduled live run."), td(B.source_link("S16"))],
    ])
    content += table("Superseded status wording (kept only so older runs are readable).", ["Status", "Meaning", "Action", "Source"], [
        [td("match"), td("Every compared field equals the official source at run time."), td("Verified for this moment only."), td(B.source_link("S01"))],
        [td("drift"), td("At least one published value differs from the live official source."), td("Open the mismatch table; the official source wins."), td(B.source_link("S01"))],
        [td("unreachable"), td("The official source could not be fetched. Nothing was compared."), td("Do not treat the published value as verified."), td(B.source_link("S01"))],
        [td("structural-only"), td("Offline run: joins and coverage were checked, live fields were not."), td("Wait for the scheduled live run."), td(B.source_link("S16"))],
    ])
    content += table("Honest limits of this verification.", ["Limit", "Consequence", "Source"], [
        [td("It proves agreement at one moment."), td("A page edited after capture is drift, not a data error; a page edited before capture is invisible."), td(B.source_link("S01"))],
        [td("A hash proves bytes, not truth."), td("Capture integrity never establishes factual accuracy, authorship or reuse rights."), td(B.source_link("S12"))],
        [td("Parsers can agree with themselves."), td("The live check re-uses the same parser, so a bug shared by both runs is invisible; structural families plus manual page reads are the cross-check."), td(B.source_link("S16"))],
        [td("Depth rank is not usage."), td("Verification confirms a club published a name in a column. It says nothing about snaps."), td(B.source_link("S29"))],
    ])
    return shell("Verification & integrity", "integrity.html", content)


def build_decisions() -> str:
    B = _ui()
    e, td, table, shell, metric, source_link = B.e, B.td, B.table, B.shell, B.metric, B.source_link
    paths = B.CATALOG.get("paths", [])
    rows = [[td(e(p["id"])), td(e(p["name"])), td(e(p["summary"])), td(e(p["prerequisites"])), td(e(p["cost"])),
             td(e(p["benefit"])), td(e(p["risk"])), td(e(p["recommended_for"])), td(source_link("S16"))] for p in paths]
    crit = [s for s in B.CATALOG["suggestions"] if s["priority"] == "Critical"]
    blocking = sum(1 for q in B.CATALOG["questions"] if q["blocking"] and not q["answer"])
    content = (
        '<div class="eyebrow">Choose before building</div><h1>Decision paths</h1>'
        '<p class="lede">Three coherent routes, compared on prerequisites, cost, benefit and risk. Nothing on this site '
        'implements a change without a recorded human choice. Use the <a href="suggestions.html">Suggestions page</a> to mark '
        'approvals and export them.</p>'
        '<div class="notice warn"><strong>Recommended now: Path A.</strong> The site has verified official facts but no '
        'permissioned price data, no inactive lists and no snap counts. Path B cannot start until those exist, and Path C '
        'cannot start until Path B passes and Q01, Q03 and Q18 are answered.</div>'
        f'<div class="metrics">{metric("Paths", str(len(paths)), "Compared side by side")}'
        f'{metric("Options", str(len(B.CATALOG["suggestions"])), "Individually reviewable")}'
        f'{metric("Critical first", str(len(crit)), "Approve before anything else")}'
        f'{metric("Blocking answers", str(blocking), "Still blank")}</div>'
        '<h2>Compare the paths</h2>'
        + table("Three routes. A decision is a choice of path plus specific options.",
                ["Path", "Name", "Summary", "Prerequisites", "Cost", "Benefit", "Risk", "Recommended for", "Source"], rows)
        + '<h2>What blocks what</h2>'
        + table("Dependency chain. A blocked node cannot start until its prerequisite is answered.",
                ["Order", "Decision needed", "Blocks", "Tracked at", "Source"], [
            [td("1"), td("Official-only evidence contract (SG13)"), td("Every downstream number"), td('<a href="suggestions.html">SG13</a>'), td(source_link("S12"))],
            [td("2"), td("Product scope and jurisdiction (Q01, Q18)"), td("Any reward, wager or paid feature"), td('<a href="questions.html">Q01, Q18</a>'), td(source_link("S12"))],
            [td("3"), td("Price and settlement rights (Q03, Q04)"), td("Line origination, market-relative skill, parlays, props"), td('<a href="questions.html">Q03, Q04</a>'), td(source_link("S12"))],
            [td("4"), td("Automated multi-day capture (SG16)"), td("Any historical availability study"), td('<a href="suggestions.html">SG16</a>'), td(source_link("S01"))],
            [td("5"), td("Inactive list and snap counts (SG18)"), td("Confirmed replacement usage and ablations"), td('<a href="questions.html">Q25</a>'), td(source_link("S01"))],
            [td("6"), td("Singles shadow baseline (SG19)"), td("Leaderboard eligibility"), td('<a href="strategies.html">Strategies</a>'), td(source_link("S13"))],
        ])
        + '<h2>Quick wins that need no new data</h2><ol class="list"><li>Fix jersey-number name matching to recover the Packers rows (SG16).</li>'
          '<li>Model depth slots as groups rather than a single starter (SG19).</li>'
          '<li>Keep the flagged-review queue and verification page published with sources (SG24, SG25).</li></ol>'
        '<div class="callout"><div><div class="section-label">NEXT</div><h2>Record one decision.</h2>'
        '<p>Mark each option approve, defer or reject, export the review file, and log the chosen path and date in COORDINATION.md.</p></div>'
        '<a class="button" href="suggestions.html">Open the suggestions register →</a></div>'
    )
    return shell("Decision paths", "decisions.html", content)
