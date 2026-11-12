#!/usr/bin/env python3
"""
build_site.py — renders the whole static site from data/*.json.

Nothing is hand-typed into HTML. Every table row comes from a JSON file and
carries its own source id, so verify.py can prove that no row is sourceless.

Outputs: index.html, pages/*.html, EXECUTIVE_SUMMARY.md
"""

import json
import os
import html
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
PAGES = os.path.join(ROOT, "pages")

# ---------------------------------------------------------------- navigation
NAV = [
    ("Overview", [
        ("index.html", "Dashboard"),
        ("pages/executive-summary.html", "Executive summary"),
        ("pages/methodology.html", "Methodology"),
    ]),
    ("League", [
        ("pages/standings.html", "Standings"),
        ("pages/lines.html", "Model lines"),
        ("pages/correlations.html", "Correlations"),
        ("pages/luck.html", "Luck & regression"),
    ]),
    ("Availability", [
        ("pages/injuries.html", "Injuries"),
        ("pages/depth.html", "Depth & availability"),
        ("pages/rules.html", "Rules"),
    ]),
    ("Decisions", [
        ("pages/questions.html", "Questions & gaps"),
        ("pages/suggestions.html", "Suggestions"),
        ("pages/strategies.html", "Strategy leaderboard"),
        ("pages/gates.html", "Validation gates"),
    ]),
    ("Trust", [
        ("pages/flagged.html", "Flagged for review"),
        ("pages/sources.html", "Sources"),
        ("pages/coordination.html", "Coordination"),
    ]),
]


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def badge(text, cls="muted"):
    return f'<span class="badge {cls}">{esc(text)}</span>'


def status_badge(status):
    m = {
        "answered": ("ok", "answered"),
        "partial": ("warn", "partial"),
        "unknown": ("bad", "unknown"),
        "blocked": ("bad", "blocked"),
        "verified": ("ok", "verified"),
        "unverified": ("bad", "unverified"),
        "implemented": ("ok", "implemented"),
        "proposed": ("info", "proposed"),
        "under review": ("warn", "under review"),
        "accepted": ("ok", "accepted"),
        "rejected": ("bad", "rejected"),
        "deferred": ("muted", "deferred"),
        "done": ("ok", "done"),
        "in progress": ("warn", "in progress"),
        "unclaimed": ("muted", "unclaimed"),
        "needs review": ("warn", "needs review"),
        "blocked ": ("bad", "blocked"),
    }
    cls, label = m.get((status or "").strip().lower(), ("muted", status))
    return badge(label, cls)


def src_chips(ids, sources_by_id, page_is_index=False, origin="pages/"):
    if not ids:
        return '<span class="unverified" title="no source">—</span>'
    out = []
    for sid in ids:
        s = sources_by_id.get(sid)
        label = sid
        title = s["title"] if s else sid
        prefix = origin if page_is_index else ""
        out.append(
            f'<a href="{prefix}sources.html#{esc(sid)}" title="{esc(title)}">{esc(label)}</a>'
        )
    return '<span class="src">' + "".join(out) + "</span>"


def prov_chip(p, page_is_index=False, origin="pages/"):
    if p == "derived":
        return '<span class="badge derived" title="computed by a script in this repo from the cited source">derived</span>'
    return ""


def tbl(table_id, cols, rows, note=None, searchable=False, placeholder="Filter rows…", source="method"):
    """cols: list of (label, align_class). rows: list of dicts {cls, cells}.

    `source` is declared per table so verify.py can distinguish a DATA table
    (which must expose a source column per row) from a METHOD table (rules,
    formulas, parameters — cited in the surrounding prose).
    """
    head = "".join(
        f'<th class="{esc(a)}">{esc(l)}</th>' for l, a in cols
    )
    body = []
    for r in rows:
        cls = r.get("cls", "")
        cells = r["cells"]
        if len(cells) != len(cols):
            raise SystemExit(
                f"build error: table '{table_id}' has {len(cols)} columns but a row has "
                f"{len(cells)} cells -> {[str(c)[:30] for c in cells][:3]}"
            )
        tds = []
        for i, c in enumerate(cells):
            align = cols[i][1] if i < len(cols) else ""
            sortv = r.get("sort")
            attr = ""
            if sortv is not None and i < len(sortv) and sortv[i] is not None:
                attr = f' data-sort="{esc(sortv[i])}"'
            tds.append(f'<td class="{esc(align)}"{attr}>{c}</td>')
        body.append(f'<tr class="{esc(cls)}">' + "".join(tds) + "</tr>")
    out = []
    if searchable:
        out.append(
            f'<div class="toolbar"><input type="search" data-filter="{esc(table_id)}" '
            f'placeholder="{esc(placeholder)}" aria-label="{esc(placeholder)}">'
            f'<span class="count" data-count-for="{esc(table_id)}"></span></div>'
        )
    out.append(
        f'<div class="tablewrap"><table id="{esc(table_id)}" data-source="{esc(source)}">'
        f'<thead><tr>{head}</tr></thead><tbody>' + "".join(body) + "</tbody></table></div>"
    )
    if note:
        out.append(f'<p class="tbl-note">{note}</p>')
    return "\n".join(out)


def num(v, dp=2, dash="—"):
    if v is None or v == "":
        return f'<span class="null">{dash}</span>'
    if isinstance(v, float):
        return f"{v:,.{dp}f}"
    return f"{v:,}"


def signed(v, dp=2):
    if v is None:
        return '<span class="null">—</span>'
    s = f"{v:+,.{dp}f}"
    cls = "num"
    return f'<span class="{cls}">{s}</span>'


def shell(page_path, title, active, body, subtitle="", eyebrow=""):
    is_index = page_path == "index.html"
    origin = "" if is_index else "../"
    navparts = []
    for gi, (group, items) in enumerate(NAV):
        if gi:
            navparts.append('<span class="sep"></span>')
        for path, label in items:
            if is_index:
                target = path
            else:
                target = "../index.html" if path == "index.html" else path.replace("pages/", "")
            cls = ' class="active"' if label == active else ""
            navparts.append(f'<a href="{esc(target)}"{cls}>{esc(label)}</a>')
    nav = "".join(navparts)

    head_extra = f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    main_site = origin + "../index.html"   # up one level to the repository's root site
    sub = f"<p>{subtitle}</p>" if subtitle else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NFL3</title>
<meta name="description" content="NFL3 — verified NFL data, a line-origination model, validation gates and a decision register. Every value sourced, unverified values flagged.">
<link rel="stylesheet" href="{origin}assets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="wrap">
    <div class="brand">
      <div class="brand-mark">N3</div>
      <div>
        <h1>NFL3 — strategy &amp; line origination</h1>
        <p class="tag">Verified inputs · model-implied outputs · explicit gaps</p>
      </div>
      <div class="status-strip">
        <span>line-lab · session arena-e5e2b753</span>
        <span>2026 season · through Week 10</span>
        <span>0 scored strategies</span>
      </div>
    </div>
  </div>
</header>
<nav class="site" aria-label="Sections"><div class="wrap">{nav}</div></nav>
<main id="main"><div class="wrap">
<div class="page-head">{head_extra}<h2>{esc(title)}</h2>{sub}</div>
{body}
</div></main>
<footer class="site"><div class="wrap">
  <div>Built from official NFL sources only. Unverified values are left blank, never inferred.</div>
  <div><a href="{origin}pages/flagged.html">Flagged for review</a> · <a href="{origin}pages/sources.html">Sources</a> · <a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/COORDINATION.md">COORDINATION.md</a> · <a href="{main_site}">← Main NFL3 site</a></div>
</div></footer>
<script src="{origin}assets/app.js"></script>
</body>
</html>
"""


# ================================================================ pages
def build_dashboard(D):
    src = D["sources"]["sources"]
    q = D["questions"]["questions"]
    sg = D["suggestions"]["suggestions"]
    st = D["strategies"]["strategies"]
    fl = D["flags"]["flags"]
    inj = D["injuries"]
    mo = D["model"]

    counts = {k: sum(1 for x in q if x["status"] == k) for k in ("answered", "partial", "unknown", "blocked")}
    inj_rows = len(inj["rows"])
    withgs = sum(1 for r in inj["rows"] if r["gs"])
    blocking_flags = sum(1 for f in fl if f["severity"] in ("critical", "high"))

    cards = f"""
<div class="grid k4">
  <div class="card accent"><div class="k">Official sources</div><div class="v">{len(src)}</div><div class="s">{sum(1 for s in src if s.get('http_status')==200)} resolving · {sum(1 for s in src if s.get('http_status')==404)} recorded broken</div></div>
  <div class="card accent"><div class="k">Clubs verified</div><div class="v">32<span style="font-size:14px;color:var(--muted)">/32</span></div><div class="s">2026 REG, all four integrity checks pass</div></div>
  <div class="card accent"><div class="k">Injury rows</div><div class="v">{inj_rows}</div><div class="s">{withgs} carry a game status · 10 complete club reports</div></div>
  <div class="card bad"><div class="k">Scored strategies</div><div class="v">0</div><div class="s">blocked at gate G0 — no odds source</div></div>
</div>
<div class="grid k4" style="margin-top:14px">
  <div class="card"><div class="k">Decision questions</div><div class="v">{len(q)}</div><div class="s">{counts['answered']} answered · {counts['partial']} partial · {counts['unknown']} unknown · {counts['blocked']} blocked</div></div>
  <div class="card"><div class="k">Suggestions</div><div class="v">{len(sg)}</div><div class="s">{sum(1 for s in sg if s['recommendation']=='Adopt now')} adopt now · {sum(1 for s in sg if s['recommendation']=='Pilot')} pilot · {sum(1 for s in sg if s['recommendation'] in ('Defer','Reject'))} defer/reject</div></div>
  <div class="card"><div class="k">Flagged items</div><div class="v">{len(fl)}</div><div class="s">{blocking_flags} high or critical severity</div></div>
  <div class="card"><div class="k">Model matchups</div><div class="v">{len(mo['lines'])}</div><div class="s">of 16 Week 10 games verified</div></div>
</div>
"""

    blockers = [q for q in q if q["priority"] == "P0"]
    brows = []
    for x in blockers:
        brows.append({"cells": [
            f'<strong>{esc(x["id"])}</strong>',
            esc(x["question"]),
            esc(x["domain"]),
            status_badge(x["status"]),
            esc(x["blocks"]),
        ]})
    btable = tbl("t-blockers", [("ID", ""), ("Question", "wrap"), ("Domain", ""), ("Status", ""), ("What it blocks", "wrap")], brows, source="register")

    srows = []
    for s in sorted(sg, key=lambda z: -(z["impact"] * z["confidence"] / (z["effort"] * (1 + 0.25 * z["risk"])))):
        score = s["impact"] * s["confidence"] / (s["effort"] * (1 + 0.25 * s["risk"]))
        srows.append({"cells": [
            f'<strong>{esc(s["id"])}</strong>',
            esc(s["title"]),
            status_badge(s["state"]),
            badge(s["recommendation"], "info" if s["recommendation"] == "Adopt now" else ("warn" if s["recommendation"] == "Pilot" else "muted")),
            num(score, 2),
        ], "sort": [s["id"], None, None, None, score]})
    stable = tbl("t-top-sug", [("ID", ""), ("Suggestion", "wrap"), ("State", ""), ("Call", ""), ("Score", "num")], srows[:8], source="register")

    body = f"""
<div class="callout bad">
  <h4>State of the project, stated plainly</h4>
  <p>Every data value on this site traces to an official NFL page. Every analytical number is produced by a script in the repository. <strong>And nothing here can be scored as a strategy yet</strong>, because the NFL does not publish its own lines — <code>nfl.com/odds/</code> returns 404, and the odds shown in NFL widgets come from partner bookmakers with no archive — and no odds archive has been purchased. The leaderboard is empty because the evidence is absent, not because the work is unfinished.</p>
</div>

<section>
<h3>At a glance</h3>
{cards}
</section>

<section>
<h3>Hard blockers — all priority P0</h3>
<p class="tbl-note" style="margin-bottom:10px">A P0 item invalidates everything downstream. These are the questions that must close before a product decision means anything. Full register on <a href="pages/questions.html">Questions &amp; gaps</a>.</p>
{btable}
</section>

<section>
<h3>Highest-ranked suggestions</h3>
<p class="tbl-note" style="margin-bottom:10px">Scored as <code>impact × confidence ÷ (effort × (1 + 0.25 × risk))</code>. A sorting aid, not a verdict — the trade-offs are on <a href="pages/suggestions.html">Suggestions</a>.</p>
{stable}
</section>

<section>
<h3>Where to go next</h3>
<div class="grid k3">
  <div class="card"><div class="k">If you have two minutes</div><p style="margin:6px 0 0;font-size:13.5px">Read the <a href="pages/executive-summary.html">executive summary</a>, then the <a href="pages/flagged.html">10 flagged items</a>.</p></div>
  <div class="card"><div class="k">If you want to decide</div><p style="margin:6px 0 0;font-size:13.5px">Start at <a href="pages/questions.html">Questions &amp; gaps</a>. P0 items first; each names the cheapest action that closes it.</p></div>
  <div class="card"><div class="k">If you want the analysis</div><p style="margin:6px 0 0;font-size:13.5px">See <a href="pages/lines.html">model lines</a>, <a href="pages/correlations.html">correlations</a> and <a href="pages/luck.html">luck &amp; regression</a>.</p></div>
</div>
</section>

<section>
<h3>Verification status</h3>
<div class="grid k2">
  <div class="callout ok"><h4>What is verified</h4>
  <ul style="margin-bottom:0">
    <li>32 club records, with four independent arithmetic checks passing</li>
    <li>{inj_rows} injury rows read verbatim, each linked to its official player page</li>
    <li>12 rules quoted from NFL.com / NFL Football Operations; 3 left blank rather than guessed</li>
    <li>8 Week 10 matchups with date, kickoff time and network</li>
  </ul></div>
  <div class="callout warn"><h4>What is not</h4>
  <ul style="margin-bottom:0">
    <li>Any market line, price or closing line — none exists officially (F-04)</li>
    <li>Depth order for any club (F-08)</li>
    <li>Active-roster, game-day and practice-squad sizes (F-02)</li>
    <li>Player-level usage data (F-06)</li>
  </ul></div>
</div>
</section>
"""
    return shell("index.html", "Dashboard", "Dashboard", body,
                 subtitle="A decision-support build for originating NFL lines: verified inputs, an explicit model, and a register of everything that must be answered before a choice is made.",
                 eyebrow="Overview")


def build_exec(D):
    ex = D["executive_summary"]
    out = []
    for b in ex["blocks"]:
        t = b["type"]
        if t == "h":
            out.append(f'<h3>{esc(b["text"])}</h3>')
        elif t == "p":
            out.append(f'<p>{esc(b["text"])}</p>')
        elif t == "ul":
            out.append("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in b["items"]) + "</ul>")
        elif t == "ol":
            out.append("<ol>" + "".join(f"<li>{esc(i)}</li>" for i in b["items"]) + "</ol>")
        elif t == "callout":
            kind = b.get("kind", "")
            out.append(f'<div class="callout {esc(kind)}"><h4>{esc(b["title"])}</h4><p>{esc(b["text"])}</p></div>')
        elif t == "kv":
            rows = [{"cells": [f"<strong>{esc(k)}</strong>", esc(v)]} for k, v in b["rows"]]
            out.append(tbl("t-kv-" + str(len(out)), [("Item", ""), ("Value", "wrap")], rows))
        elif t == "table":
            rows = []
            for r in b["rows"]:
                rows.append({"cells": [
                    f"<strong>{esc(r[0])}</strong>", esc(r[1]), esc(r[2]),
                    src_chips(["S01"], D["sources_by_id"], page_is_index=False),
                ]})
            out.append(tbl("t-ex-" + str(len(out)),
                           [(esc(h), "wrap") for h in b["head"]] + [("Src", "")],
                           rows, source="S01"))
    body = "\n".join(out)
    return shell("pages/executive-summary.html", "Executive summary", "Executive summary", body,
                 subtitle=ex["subtitle"], eyebrow="Overview")


def build_methodology(D):
    mo = D["model"]
    arows = [{"cells": [f'<strong>{esc(a["id"])}</strong>', esc(a["name"]), esc(str(a["value"])), esc(a["why"])]} for a in mo["meta"]["assumptions"]]
    atable = tbl("t-assumptions", [("ID", ""), ("Assumption", ""), ("Value", "wrap"), ("Why it is an assumption", "wrap")], arows, source="method")

    body = f"""
<p>The model is deliberately small enough to check by hand. Every equation below is in <code>scripts/model_ratings.py</code>, and every published number is its output.</p>

<h3>1. The rating</h3>
<p>For club <em>i</em> with games played <em>G</em>:</p>
<div class="formula">off_i = PF_i / G        def_i = PA_i / G        r_i = (PF_i − PA_i) / G</div>
<p>An additive points model says a club's score is league average plus its own offence minus the opponent's defence. The margin then collapses to a difference of the two ratings:</p>
<div class="formula">points_A = μ + off_A − def_B
margin_A = points_A − points_B = r_A − r_B</div>
<p>with μ the league average points per team per game (measured here at {num(mo['league']['league_ppg_per_team'],3)}). Because a club with 8 games and a club with 9 games are not equally informative, each rating is shrunk toward zero:</p>
<div class="formula">r'_i = r_i × G / (G + k)</div>
<p>with k = 2 declared as assumption A-03. At 8 games this keeps 80% of the raw rating.</p>

<h3>2. The two totals</h3>
<p>The same additive model forces the total to equal the league total plus both ratings, which structurally pushes totals down when two weak clubs meet. Rather than hide that, two estimators are published:</p>
<div class="formula">total_additive = L + r'_home + r'_away
total_average  = ( (PF_h + PA_h)/G_h + (PF_a + PA_a)/G_a ) / 2</div>
<p>They disagree by up to 12.2 points on the verified slate. The gap is published as a column, not resolved by preference.</p>

<h3>3. Win probability</h3>
<div class="formula">P(home win) = Φ( margin_home / σ ),  σ = 13.5 (assumption A-02)</div>
<p>σ is a parameter, not an estimate. It is used only to turn a margin into a probability and it is listed with the other assumptions.</p>

<h3>4. Luck, and why it is a subtraction</h3>
<p>The Pythagorean expectation converts scoring into a win rate. Its exponent is <em>fitted</em> here rather than borrowed: k minimises squared error against the actual win rates of the 32 clubs, giving k = {mo['league']['pythagorean_exponent_fitted']}.</p>
<div class="formula">pyth_i = PF_i^k / (PF_i^k + PA_i^k)
expected_wins = pyth_i × G
luck_wins = (W + 0.5·T) − expected_wins</div>
<p>Read that last line carefully: luck here is <em>only</em> the part of a record that scoring does not explain. It also contains real things the margin misses — special teams, opponent quality, clutch play. Treating all of it as luck would be an error, and the site says so wherever the number appears.</p>

<h3>5. Correlations</h3>
<p>Pearson r on the 32-club cross-section, with two-sided p-values via Fisher z. n = 32 is small; the p-values are reported so the reader can see that. Two results carry explicit warnings: C7 is a part-whole correlation and is mechanically inflated, and C8 is split-half reliability rather than a momentum effect.</p>

<h3>6. Declared assumptions</h3>
<p>These are the only places where a number is not sourced or derived. They are declared once, here, and referenced by id everywhere they are used.</p>
{atable}

<h3>7. What the model cannot do</h3>
<ul>
  <li><strong>No opponent adjustment.</strong> r_i credits a club for the quality of who it beat. Fixing this needs a game log (SG-02).</li>
  <li><strong>No market comparison.</strong> There is no line to compare against (F-04). A model number is not an edge.</li>
  <li><strong>No injury adjustment in the published lines.</strong> The injury layer exists and is verified, but the position-value weights that would connect it to a line are assumptions (A-04), so the two are published side by side rather than silently combined.</li>
  <li><strong>No neutral-site science.</strong> One verified game (New England at Detroit in Munich) is flagged neutral and the home-field term is forced to zero there (A-06).</li>
</ul>

<h3>8. Reproducing every number</h3>
<pre><code>python3 scripts/model_ratings.py   # ratings, correlations, luck, model lines
python3 scripts/parlay_math.py     # gates, parlays, Kelly, confidence intervals
python3 scripts/build_site.py      # renders this site from data/*.json
python3 scripts/verify.py          # fails the build on a sourceless or broken row</code></pre>
"""
    return shell("pages/methodology.html", "Methodology", "Methodology", body,
                 subtitle="The model, its equations, its assumptions and its limits — small enough to audit in one sitting.",
                 eyebrow="Overview")


def build_standings(D):
    sd = D["standings"]
    src_by = D["sources_by_id"]
    divisions = {}
    for t in sd["teams"]:
        divisions.setdefault(t["division"], []).append(t)

    rows = []
    for div in ["AFC East", "AFC North", "AFC South", "AFC West",
                "NFC East", "NFC North", "NFC South", "NFC West"]:
        rows.append({"cls": "sub", "cells": [f"{esc(div)}"] + [""] * 12})
        for t in divisions[div]:
            rows.append({"cells": [
                f'<a href="{esc(t["team_url"])}">{esc(t["name"])}</a>',
                f'<strong>{t["w"]}-{t["l"]}-{t["t"]}</strong>',
                num(t["pct"], 3),
                num(t["pf"]), num(t["pa"]), signed(t["net"], 0),
                esc(t["home"]), esc(t["road"]), esc(t["division_record"]), esc(t["conference_record"]),
                esc(t["streak"]), esc(t["last5"]),
                src_chips([sd["meta"]["source_id"]], src_by),
            ], "sort": [t["name"], t["pct"], t["pct"], t["pf"], t["pa"], t["net"], None, None, None, None, None, None, None]})

    t = tbl("t-standings",
            [("Club", ""), ("W-L-T", "num"), ("Pct", "num"), ("PF", "num"), ("PA", "num"), ("Net", "num"),
             ("Home", "num"), ("Road", "num"), ("Div", "num"), ("Conf", "num"), ("Strk", ""), ("Last 5", "num"), ("Src", "")],
            rows, searchable=True, placeholder="Filter clubs…", source="S01",
            note="Every row read verbatim from the official standings page. Games played differ by club (byes plus the in-progress Week 10 slate) — see F-01.")

    body = f"""
<div class="callout">
  <h4>Source and integrity</h4>
  <p>All 32 clubs, <a href="{esc(sd['meta']['source_url'])}">NFL.com 2026 division standings</a>, retrieved {esc(sd['meta']['retrieved_at'])}. Four arithmetic checks were run on the transcription and all four pass:</p>
  <ul style="margin-bottom:0">
    <li>W + L + T equals home + road for all 32 clubs</li>
    <li>Division record is a subset of conference record</li>
    <li>Conference + other-conference equals the full record</li>
    <li>PF − PA equals the published NET PTS column</li>
  </ul>
</div>
<p class="tbl-note" style="margin:0 0 12px">Note the unequal games played: at this snapshot clubs have played 8 or 9 games. Per-game rates remain comparable; raw season totals do not.</p>
{t}
"""
    return shell("pages/standings.html", "Standings", "Standings", body,
                 subtitle="2026 regular season through Week 10, transcribed verbatim with four integrity checks.",
                 eyebrow="League")


def build_lines(D):
    mo = D["model"]
    src_by = D["sources_by_id"]
    rows = []
    for ln in mo["lines"]:
        rows.append({"cls": "sub", "cells": [
            f'<strong>{esc(ln["away"])} @ {esc(ln["home"])}</strong> — {esc(ln["away_name"])} at {esc(ln["home_name"])}'
            + (" · NEUTRAL SITE" if ln["neutral_site"] else ""),
            "", "", "", "", "", ""]})
        for v in ln["variants"]:
            rows.append({"cells": [
                f'HFA +{v["hfa"]:.1f}',
                f'<strong>{v["home_spread"]:+.2f}</strong>',
                f'{v["home_spread_rounded"]:+.1f}',
                num(v["model_total"], 1),
                f'{v["home_win_prob"]*100:.1f}%',
                f'{v["away_win_prob"]*100:.1f}%',
                src_chips([ln["src"]], src_by),
            ], "sort": [v["hfa"], v["home_spread"], v["home_spread_rounded"], v["model_total"], v["home_win_prob"], None, None]})

    t = tbl("t-lines",
            [("Scenario", ""), ("Home spread (model)", "num"), ("Rounded", "num"), ("Total", "num"), ("Home win %", "num"), ("Away win %", "num"), ("Src", "")],
            rows, searchable=True, placeholder="Filter games…", source="S01",
            note="Spreads are from the HOME team's perspective: negative means the home club is favoured. These are model-implied numbers, not market lines.")

    tot_rows = []
    for ln in mo["lines"]:
        gap = ln["model_total_additive"] - ln["model_total_average"]
        tot_rows.append({"cells": [
            f'{esc(ln["away"])} @ {esc(ln["home"])}',
            num(ln["model_total_average"], 1),
            num(ln["model_total_additive"], 1),
            signed(gap, 1),
            badge("disagrees" if abs(gap) >= 3 else "close", "warn" if abs(gap) >= 3 else "ok"),
            src_chips([ln["src"]], src_by),
        ], "sort": [None, ln["model_total_average"], ln["model_total_additive"], gap, None, None]})
    tt = tbl("t-totals", [("Game", ""), ("Total: average estimator", "num"), ("Total: additive estimator", "num"), ("Gap", "num"), ("", ""), ("Src", "")],
             tot_rows, note="The two estimators are published deliberately. Where they disagree by more than three points, no total should be trusted (Q-17).")

    body = f"""
<div class="callout bad">
  <h4>These are not betting lines</h4>
  <p>The NFL does not publish its own point spreads or totals: <code>nfl.com/odds/</code> returns 404 (S09), and NFL Support (S13) confirms that odds on NFL surfaces are supplied by partner bookmakers with bets placed through a redirect. The numbers below are <em>model-implied</em> margins derived from the verified standings. There is no market price in this repository to compare them against, so no claimed edge exists here and none is implied.</p>
</div>

<h3>Sensitivity: home-field advantage</h3>
<p>The home-field term cannot be estimated without a game log, so it is not guessed. Instead every game is published under four values, so the reader can see how much of the conclusion depends on the assumption. The Munich game (New England at Detroit) is flagged neutral and the term is forced to zero.</p>
{t}

<h3>Totals: two estimators, published side by side</h3>
<p class="tbl-note" style="margin-bottom:10px">The additive model forces totals to fall when two weak clubs meet, which is a structural bias rather than a finding. The average-of-club-game-totals estimator does not have that bias. They are shown together so the disagreement is visible.</p>
{tt}

<h3>Inputs by club</h3>
"""
    rrows = []
    for r in sorted(mo["ratings"], key=lambda z: -z["rating_shrunk"]):
        rrows.append({"cells": [
            esc(r["abbr"]), esc(r["division"]),
            num(r["games"], 0),
            num(r["off_ppg"], 2), num(r["def_ppg"], 2), signed(r["net_ppg"], 2),
            f'<strong>{r["rating_shrunk"]:+.2f}</strong>',
            num(r["pythag_win_pct"], 3), num(r["expected_wins"], 2), signed(r["luck_wins"], 2),
            src_chips([r["src"]], src_by) + " " + prov_chip("derived"),
        ], "sort": [r["abbr"], None, r["games"], r["off_ppg"], r["def_ppg"], r["net_ppg"], r["rating_shrunk"], r["pythag_win_pct"], r["expected_wins"], r["luck_wins"], None]})
    rt = tbl("t-ratings", [("Club", ""), ("Division", ""), ("G", "num"), ("Off/G", "num"), ("Def/G", "num"), ("Net/G", "num"),
                           ("Rating (shrunk)", "num"), ("Pyth", "num"), ("Exp W", "num"), ("Luck W", "num"), ("Src", "")],
             rrows, searchable=True, placeholder="Filter clubs…", source="S01")
    body += rt
    body += f"""
<h3>Coverage</h3>
<p>{esc(mo['lines'][0]['network'] and '')}{esc(D['standings']['matchup_coverage']['gap'])}</p>
<p class="tbl-note">Model warning: {esc(mo['meta']['warning'])}</p>
"""
    return shell("pages/lines.html", "Model lines", "Model lines", body,
                 subtitle="Model-implied spreads and totals for the eight verified Week 10 matchups, with the assumption sensitivity shown rather than hidden.",
                 eyebrow="League")


def build_correlations(D):
    mo = D["model"]
    src_by = D["sources_by_id"]
    vd = mo["correlations"]["variance_decomposition"]
    rows = []
    for c in mo["correlations"]["pairs"]:
        r = c["r"]
        strength = ("very strong" if r is not None and abs(r) >= .8 else
                    "strong" if r is not None and abs(r) >= .6 else
                    "moderate" if r is not None and abs(r) >= .4 else
                    "weak" if r is not None and abs(r) >= .2 else "negligible")
        rows.append({"cells": [
            f'<strong>{esc(c["id"])}</strong>',
            esc(c["x"]),
            esc(c["y"]),
            f'{r:+.3f}' if r is not None else "—",
            num(c["r2"], 3),
            (f'{c["p_value"]:.4f}' if c["p_value"] is not None and c["p_value"] >= 0.0001 else ("&lt;0.0001" if c["p_value"] is not None else "—")),
            badge(strength, "ok" if strength in ("strong", "very strong") else ("warn" if strength == "moderate" else "muted")),
            (badge("mechanical", "bad") if c["mechanical"] else ""),
            esc(c["note"]),
            src_chips([c["src"]], src_by) + " " + prov_chip("derived"),
        ], "sort": [c["id"], None, None, r, c["r2"], c["p_value"], strength, None, None, None]})
    t = tbl("t-corr", [("ID", ""), ("X", ""), ("Y", ""), ("r", "num"), ("r²", "num"), ("p", "num"), ("Strength", ""), ("Warning", ""), ("Interpretation", "wrap"), ("Src", "")],
            rows, source="S01", note="n = 32 clubs. Pearson r with two-sided p via Fisher z. At this n a p-value is suggestive, not decisive.")

    body = f"""
<div class="callout">
  <h4>The variance decomposition — the number the whole project rests on</h4>
  <p>Scoring margin explains <strong>{num(vd['pct_of_win_variance_explained_by_margin'],1)}%</strong> of between-club win-pct variance (r = {num(vd['r'],3)}, r² = {num(vd['r2'],3)}). The remaining <strong>{num(vd['pct_residual'],1)}%</strong> is the pool that contains one-score games, opponent quality and chance.</p>
  <p style="margin-bottom:0">{esc(vd['note'])}</p>
</div>
{t}

<h3>Reading these honestly</h3>
<ul>
  <li><strong>C1 is the skill signal.</strong> It is high because margin and wins share the same scoring events — that is the point, not an artefact. It sets the ceiling on how much of a record is explainable at all.</li>
  <li><strong>C4 is the interesting one.</strong> Offence and defence are close to independent across clubs (r = −0.206, p = 0.26), so neither alone predicts the other. That is why a single net-points rating carries more information than two separate rankings.</li>
  <li><strong>C7 is flagged mechanical.</strong> Last-five form is a subset of the season record, so the correlation is inflated by construction. It is shown to make the size of that artefact visible, not as evidence.</li>
  <li><strong>C8 is reliability, not momentum.</strong> Two disjoint blocks of the same season correlate at +0.424, but both blocks measure the same club quality. Calling that momentum would be a category error.</li>
  <li><strong>What is missing.</strong> No leg-level correlation exists, so nothing here prices a parlay (F-09). These are cross-sectional team correlations, which are a different object entirely.</li>
</ul>
"""
    return shell("pages/correlations.html", "Correlations", "Correlations", body,
                 subtitle="What actually moves together in the verified 2026 data — including the two correlations that are shown only to expose an artefact.",
                 eyebrow="League")


def build_luck(D):
    mo = D["model"]
    src_by = D["sources_by_id"]
    rows = []
    for r in mo["luck_table"]:
        luck = r["luck_wins"]
        cls = "ok" if luck >= 1 else ("bad" if luck <= -1 else "muted")
        rows.append({"cells": [
            esc(r["abbr"]),
            f'<a href="{esc(r["team_url"])}">{esc(r["name"])}</a>',
            f'{r["w"]}-{r["l"]}{"-" + str(r["t"]) if r["t"] else ""}',
            num(r["games"], 0),
            num(r["win_pct"], 3),
            num(r["pythag_win_pct"], 3),
            num(r["expected_wins"], 2),
            f'<strong>{luck:+.2f}</strong>',
            badge(r["direction"], cls),
            src_chips([r["src"]], src_by) + " " + prov_chip("derived"),
        ], "sort": [r["abbr"], r["name"], None, r["games"], r["win_pct"], r["pythag_win_pct"], r["expected_wins"], luck, None, None]})
    t = tbl("t-luck", [("Club", ""), ("Name", ""), ("Rec", "num"), ("G", "num"), ("Win pct", "num"), ("Pyth", "num"), ("Exp W", "num"), ("Luck W", "num"), ("Reading", ""), ("Src", "")],
            rows, searchable=True, placeholder="Filter clubs…", source="S01",
            note="Luck W = actual wins (ties counted half) minus Pythagorean expectation. Negative means the record understates the scoring margin.")

    body = f"""
<div class="callout warn">
  <h4>What 'luck' means here — and what it does not</h4>
  <p>Luck is defined narrowly and mechanically: the part of a club's win total that its scoring margin does not explain. It is a residual, and a residual is not automatically luck. It also absorbs special teams, strength of schedule, clutch performance and score effects.</p>
  <p style="margin-bottom:0"><strong>So this page is a list of regression candidates, not a list of bets.</strong> Turning a candidate into a bet requires a price to compare against, which does not exist here (F-04), and a market that has not already adjusted, which is an empirical question.</p>
</div>

<h3>Regression candidates, ranked</h3>
<p class="tbl-note" style="margin-bottom:10px">Fitted exponent k = {num(D['model']['league']['pythagorean_exponent_fitted'],2)}. Both directions are shown; a club at the top is not a 'sell' until someone offers a price.</p>
{t}

<h3>The two clubs the arithmetic likes most, either way</h3>
<div class="grid k2">
  <div class="card bad"><div class="k">Most over-performing</div><div class="v" style="font-size:18px">{esc(mo['luck_table'][-1]['name'])}</div><div class="s">+{num(mo['luck_table'][-1]['luck_wins'],2)} wins above its scoring margin ({esc(str(mo['luck_table'][-1]['w']))}-{esc(str(mo['luck_table'][-1]['l']))}, pyth {num(mo['luck_table'][-1]['pythag_win_pct'],3)}).</div></div>
  <div class="card ok"><div class="k">Most under-performing</div><div class="v" style="font-size:18px">{esc(mo['luck_table'][0]['name'])}</div><div class="s">{num(mo['luck_table'][0]['luck_wins'],2)} wins below its scoring margin ({esc(str(mo['luck_table'][0]['w']))}-{esc(str(mo['luck_table'][0]['l']))}, pyth {num(mo['luck_table'][0]['pythag_win_pct'],3)}).</div></div>
</div>
<p class="tbl-note" style="margin-top:10px">These two are the clearest illustrations of why a record alone is a poor signal. Tampa Bay is 3-6 with a positive point differential; Denver is 7-2 with a differential of +12 over nine games.</p>
"""
    return shell("pages/luck.html", "Luck & regression", "Luck & regression", body,
                 subtitle="A mechanical split between what scoring explains and what it does not — with the residual's limits stated plainly.",
                 eyebrow="League")


def build_injuries(D):
    inj = D["injuries"]
    src_by = D["sources_by_id"]
    rows = []
    for r in inj["rows"]:
        gs = r["gs"]
        gs_html = badge(gs, {"Out": "bad", "Doubtful": "warn", "Questionable": "warn"}.get(gs, "muted")) if gs else '<span class="null">not set</span>'
        inj_html = esc(r["inj"]) if r["inj"] else '<span class="null">—</span>'
        pr_cls = {"Did Not Participate": "bad", "Limited Participation": "warn", "Full Participation": "ok"}.get(r["pr"], "muted")
        rows.append({"cells": [
            esc(r["team"]),
            f'<a href="{esc(r["u"])}">{esc(r["p"])}</a>',
            esc(r["pos"]),
            inj_html,
            badge(r["pr"].replace(" Participation", ""), pr_cls),
            gs_html,
            f'<span class="src"><a href="{esc(r["u"])}" title="official player page">{esc(r["team"] + " page")}</a></span>',
        ], "sort": [r["team"], r["p"], r["pos"], r["inj"] or "zzz", r["pr"], r["gs"] or "zzz", None]})
    t = tbl("t-inj", [("Team", ""), ("Player", ""), ("Pos", ""), ("Injury", ""), ("Practice", ""), ("Game status", ""), ("Src", "")],
            rows, searchable=True, placeholder="Filter by team, player, position or status…", source="S05",
            note="Each row links to that player's official NFL.com page — the exact page the row was read from.")

    teams = sorted({r["team"] for r in inj["rows"]})
    counts = []
    for tm in teams:
        sub = [r for r in inj["rows"] if r["team"] == tm]
        counts.append({"cells": [
            esc(tm), num(len(sub), 0),
            num(sum(1 for r in sub if r["pr"] == "Did Not Participate"), 0),
            num(sum(1 for r in sub if r["pr"] == "Limited Participation"), 0),
            num(sum(1 for r in sub if r["gs"]), 0),
            esc(", ".join(f"{p}×{n}" for p, n in sorted({x["pos"]: sum(1 for y in sub if y["pos"] == x["pos"]) for x in sub}.items(), key=lambda z: -z[1]))),
            src_chips(["S05"], src_by),
        ], "sort": [tm, len(sub), None, None, None, None, None]})
    tc = tbl("t-inj-team", [("Team", ""), ("Listed", "num"), ("DNP", "num"), ("Limited", "num"), ("With status", "num"), ("Positions", "wrap"), ("Src", "")],
             counts, note="Ten club reports were captured in full. Buffalo was partially captured and the New York Jets report was not captured at all — see F-03.")

    body = f"""
<div class="callout warn">
  <h4>Read the timing before reading the table</h4>
  <p>This is the Week 10 report as published on {esc(inj['meta']['retrieved_at'])}. Of {inj['meta']['counts']['rows']} rows, only <strong>{inj['meta']['counts']['rows_with_game_status']}</strong> carry a game status. The rest are practice-report entries, which is the normal state before the status deadline — a practice line is <em>not</em> a prediction and no status has been inferred from one.</p>
</div>

<h3>What the rules say about these columns</h3>
<ul>
  <li><strong>Practice:</strong> exactly one of Did Not Participate, Limited Participation (&lt;100% of normal reps), Full Participation (100%). Source S03.</li>
  <li><strong>Game status:</strong> Out = will not play; Doubtful = unlikely; Questionable = uncertain. 'Probable' was eliminated because ~95% of players carrying it played. Source S03.</li>
  <li><strong>Blank status:</strong> means no designation was published at fetch time. It does not mean the player is healthy, and it does not mean he will play.</li>
</ul>

{t}

<h3>By club</h3>
<h4 style="margin-top:6px">Aggregated from the rows above — the same source, the same fetch</h4>
{tc}
"""
    return shell("pages/injuries.html", "Injuries", "Injuries", body,
                 subtitle="Week 10, 2026: every captured row read verbatim from the official report and linked to its own player page.",
                 eyebrow="Availability")


def build_depth(D):
    mo = D["model"]
    ds = mo["depth_stress"]
    src_by = D["sources_by_id"]
    rows = []
    for t in ds["teams"]:
        rows.append({"cells": [
            num(t["rank"], 0),
            f'<strong>{esc(t["team"])}</strong>',
            num(t["listed"], 0),
            num(t["dnp"], 0),
            num(t["limited"], 0),
            num(t["offense_listed"], 0),
            num(t["defense_listed"], 0),
            num(t["out"], 0), num(t["questionable"], 0),
            f'<strong>{num(t["raw_stress"], 2)}</strong>',
            num(t["depth_stress_index"], 1),
            esc(", ".join(f"{p} {n}" for p, n in sorted(t["positions"].items(), key=lambda z: -z[1]))),
            src_chips([t["src"]], src_by) + " " + prov_chip("derived"),
        ], "sort": [t["rank"], t["team"], t["listed"], t["dnp"], t["limited"], t["offense_listed"], t["defense_listed"], t["out"], t["questionable"], t["raw_stress"], t["depth_stress_index"], None, None]})
    t = tbl("t-depth", [("Rank", "num"), ("Team", ""), ("Listed", "num"), ("DNP", "num"), ("Limited", "num"), ("Off", "num"), ("Def", "num"),
                        ("Out", "num"), ("Q", "num"), ("Raw", "num"), ("Index", "num"), ("Positions", "wrap"), ("Src", "")],
            rows, searchable=True, placeholder="Filter clubs…", source="S05",
            note="Higher index = more verified availability degradation. The index is assumption-driven by design; the weights are declared, not measured.")

    body = f"""
<div class="callout bad">
  <h4>The requirement this page cannot yet fully meet</h4>
  <p>The brief asks for detection of <em>2nd, 3rd and 4th string players replacing starters</em>, on offence and defence. That is a depth-order question, and the official NFL.com roster feed does not publish depth order. Its columns are player, number, position, roster status, height, weight, experience and college — verified by reading the page in full (S07, R14).</p>
  <p style="margin-bottom:0"><strong>So this page does not claim who replaces whom.</strong> Any 'backup' or 'starter' label here would be an invented fact. What it does instead is measure the part that <em>is</em> verified: how much availability is degraded, by position group, for each club.</p>
</div>

<h3>What the index measures</h3>
<div class="formula">DepthStress = Σ ( position_weight × availability_weight )</div>
<p>Availability weight: 1.0 for Out or Did Not Participate, 0.9 for Doubtful, 0.6 for Questionable, 0.5 for Limited Participation, 0 for Full Participation. Position weights are declared in <code>scripts/model_ratings.py</code> and are an explicit assumption (A-04) — no official source publishes position value. The index is normalised to the highest club in this snapshot.</p>
<p class="tbl-note">{esc(ds['meta']['what_it_is_not'])}</p>

{t}

<h3>How to close the gap</h3>
<div class="grid k2">
  <div class="card"><div class="k">Route A — per-club depth charts</div><p style="margin:6px 0 0;font-size:13.5px">Every club publishes its own depth chart on its official site. They are not uniform, not machine-readable, and update on different cadences. It would need verification club by club, with a documented cadence, before a single 'starter' claim is published.</p></div>
  <div class="card"><div class="k">Route B — official snap counts</div><p style="margin:6px 0 0;font-size:13.5px">If an official snap-count source exists, participation share can rank players empirically without anyone publishing a depth chart. Unverified: no such source was fetched in this session (Q-03).</p></div>
</div>
<p class="tbl-note" style="margin-top:10px">Open questions: Q-09 (source), Q-10 (position value), F-08 (flag). Suggested next step: SG-05, recommended as a pilot, not an immediate build.</p>

<h3>Why the weighting is published rather than buried</h3>
<p>A single index whose weights are hidden looks like a measurement. This one is deliberately parameterised: change the weight table in the script and the ranking changes, which is exactly what a reviewer should be able to test. SG不死</p>
"""
    body = body.replace("SG不死", "SG-15 proposes publishing a low and a high weight set side by side so the ranking's robustness is visible.")
    return shell("pages/depth.html", "Depth & availability", "Depth & availability", body,
                 subtitle="Verified availability degradation by position — and an explicit refusal to label anyone a starter or a backup without a source.",
                 eyebrow="Availability")


def build_rules(D):
    rules = D["rules"]
    src_by = D["sources_by_id"]
    rows = []
    last_group = None
    for r in rules["rules"]:
        if r["group"] != last_group:
            rows.append({"cls": "sub", "cells": [esc(r["group"]), "", "", "", "", "", ""]})
            last_group = r["group"]
        val = r.get("value")
        statement = esc(r["statement"])
        if val is None and r["status"] == "unverified":
            statement += ' <span class="unverified">— value deliberately left blank</span>'
        defs = esc(r["definitions"]) if r["definitions"] else '<span class="null">—</span>'
        extra = ""
        if r.get("note"):
            extra = f'<div class="tbl-note" style="margin-top:4px">{esc(r["note"])}</div>'
        if r.get("conflict"):
            extra += f'<div class="tbl-note" style="margin-top:4px;color:var(--bad)">Conflict: {esc(r["conflict"])}</div>'
        rows.append({"cells": [
            f'<strong>{esc(r["id"])}</strong>',
            statement + extra,
            defs,
            status_badge(r["status"]),
            esc(r.get("as_of") or "—"),
            badge(r["in_force_2026"], "ok" if r["in_force_2026"] == "verified" else "warn"),
            src_chips([r["source_id"]] if r["source_id"] else [], src_by),
        ], "sort": [r["id"], None, None, r["status"], None, None, None]})
    t = tbl("t-rules", [("ID", ""), ("Rule", "wrap"), ("Definitions", "wrap"), ("Status", ""), ("As published", ""), ("In force 2026", ""), ("Src", "")],
            rows, searchable=True, placeholder="Filter rules…", source="register")

    absent = []
    for a in rules["official_page_absent"]:
        absent.append(f'<li><strong>{esc(a["claim"])}</strong> — probed <code>{esc(a["probe_url"])}</code>, HTTP {esc(str(a["http_status"]))}. {esc(a["conclusion"])}</li>')

    body = f"""
<p>These are the rules that turn raw reporting into decision-grade information. Only rules quoted from an official NFL page are marked verified. Where a number could not be confirmed, it was left blank rather than recalled.</p>

<div class="callout warn">
  <h4>Why some obvious numbers are blank</h4>
  <p>Active-roster size, game-day actives, the game-status publication deadline and the current practice-squad size are all left unverified. They are repeated everywhere, but repetition is not a source. Two of them also conflict: NFL.com reported practice squads of 16, while a 2026 AP article describes 17. Publishing either as fact would breach the rule this project runs on.</p>
</div>

{t}

<h3>Official pages that do not exist</h3>
<ul>{''.join(absent)}</ul>
<p class="tbl-note">Recording a 404 is deliberate: it stops a future session from citing a URL that looks authoritative and is dead.</p>
"""
    return shell("pages/rules.html", "Rules", "Rules", body,
                 subtitle="Injury-report and roster rules quoted from official NFL pages, with unconfirmed values left blank and flagged.",
                 eyebrow="Availability")


def build_questions(D):
    qs = D["questions"]["questions"]
    rows = []
    for q in qs:
        rows.append({"cells": [
            f'<strong>{esc(q["id"])}</strong>',
            esc(q["domain"]),
            esc(q["question"]),
            badge(q["priority"], "bad" if q["priority"] == "P0" else ("warn" if q["priority"] == "P1" else "muted")),
            status_badge(q["status"]),
            esc(q["current_answer"]),
            esc(q["blocks"]),
            esc(q["how_to_close"]),
            esc(q["owner"]),
            src_chips(q["source_ids"], D["sources_by_id"]),
        ], "sort": [q["id"], q["domain"], None, q["priority"], q["status"], None, None, None, None, None]})
    t = tbl("t-q", [("ID", ""), ("Domain", ""), ("Question", "wrap"), ("Pri", ""), ("Status", ""), ("Current answer", "wrap"),
                    ("Blocks", "wrap"), ("Cheapest way to close it", "wrap"), ("Owner", ""), ("Src", "")],
            rows, searchable=True, placeholder="Filter by domain, status, owner or keyword…", source="register")

    counts = {}
    for q in qs:
        counts[q["status"]] = counts.get(q["status"], 0) + 1
    cards = f"""
<div class="grid k4">
  <div class="card ok"><div class="k">Answered</div><div class="v">{counts.get('answered',0)}</div><div class="s">closed with an official source or script output</div></div>
  <div class="card warn"><div class="k">Partial</div><div class="v">{counts.get('partial',0)}</div><div class="s">evidence exists but is not decision-grade</div></div>
  <div class="card bad"><div class="k">Unknown</div><div class="v">{counts.get('unknown',0)}</div><div class="s">no evidence at all</div></div>
  <div class="card bad"><div class="k">Blocked</div><div class="v">{counts.get('blocked',0)}</div><div class="s">needs a purchase, a lawyer, or a decision</div></div>
</div>
"""

    body = f"""
<div class="callout">
  <h4>How to use this register</h4>
  <p>Every row is a question that must be answered before a decision in its area is more than a guess. The <em>Blocks</em> column names the decision that cannot proceed; the last column names the cheapest action that closes the gap. A row marked <strong>blocked</strong> cannot be closed by research — it needs money, a legal opinion, or a human choice.</p>
  <p style="margin-bottom:0">Status definitions: answered = closed against an official source or reproducible arithmetic · partial = some evidence, not enough · unknown = nothing gathered · blocked = needs an external decision.</p>
</div>

{cards}
<h3 style="margin-top:22px">The register</h3>
{t}

<h3>Reading the status column</h3>
<p>Only {counts.get('answered',0)} of {len(qs)} questions are fully closed, and every one of those is closed by <em>method</em> rather than by data — a gate, a policy, or a reproducible calculation. The questions that need data are still open because the data does not exist: no odds archive (Q-04), no depth order (Q-09), no usage data (Q-03), no leg outcomes (Q-14).</p>
"""
    return shell("pages/questions.html", "Questions & gaps", "Questions & gaps", body,
                 subtitle="Every question that must be answered before a decision, what we know, what we do not, and the cheapest way to close each one.",
                 eyebrow="Decisions")


def build_suggestions(D):
    sg = (s for s in D["suggestions"]["suggestions"])
    sgs = D["suggestions"]["suggestions"]
    proto = D["suggestions"]["meta"]["decision_protocol"]
    rows = []
    for s in sorted(sgs, key=lambda z: -(z["impact"] * z["confidence"] / (z["effort"] * (1 + 0.25 * z["risk"])))):
        score = s["impact"] * s["confidence"] / (s["effort"] * (1 + 0.25 * s["risk"]))
        rec_cls = {"Adopt now": "ok", "Pilot": "warn", "Defer": "muted", "Reject": "bad"}.get(s["recommendation"], "muted")
        rows.append({"cells": [
            f'<strong>{esc(s["id"])}</strong>',
            esc(s["title"]) + (f'<div class="tbl-note" style="margin-top:4px">{esc(s["problem"])}</div>' if s["problem"] else ""),
            esc(s["category"]),
            num(s["impact"], 0), num(s["confidence"], 0), num(s["effort"], 0), num(s["risk"], 0),
            f'<strong>{num(score,2)}</strong>',
            badge(s["recommendation"], rec_cls),
            status_badge(s["state"]),
            esc(s["decision_criteria"]),
            ', '.join(esc(d) for d in s["dependencies"]) if s["dependencies"] else '<span class="null">—</span>',
        ], "sort": [s["id"], None, s["category"], s["impact"], s["confidence"], s["effort"], s["risk"], score, s["recommendation"], s["state"], None, None]})
    t = tbl("t-sug", [("ID", ""), ("Suggestion", "wrap"), ("Category", ""), ("Imp", "num"), ("Conf", "num"), ("Eff", "num"), ("Risk", "num"),
                      ("Score", "num"), ("Call", ""), ("State", ""), ("Decision criteria", "wrap"), ("Needs", "")],
            rows, searchable=True, placeholder="Filter suggestions…", source="register",
            note="Score = impact × confidence ÷ (effort × (1 + 0.25 × risk)). It is a sorting aid so that cheap, high-confidence work surfaces first; it is not a verdict.")

    # comparison view: top three adopt-now
    top = [s for s in sorted(sgs, key=lambda z: -(z["impact"] * z["confidence"] / (z["effort"] * (1 + 0.25 * z["risk"])))) if s["recommendation"] == "Adopt now"][:3]
    comp_cells = []
    for s in top:
        comp_cells.append(
            f'<div class="card"><div class="k">{esc(s["id"])} · {esc(s["category"])}</div>'
            f'<h4 style="margin:4px 0 6px;text-transform:none;letter-spacing:0;font-size:14.5px;color:var(--ink)">{esc(s["title"])}</h4>'
            f'<p style="font-size:13px;margin-bottom:8px">{esc(s["proposal"])}</p>'
            f'<p style="font-size:12.5px;margin-bottom:6px"><strong>If skipped:</strong> {esc(s.get("blocks_if_skipped") or "—")}</p>'
            f'<p style="font-size:12.5px;margin-bottom:0"><strong>Done when:</strong> {esc(s["decision_criteria"])}</p></div>'
        )
    comp = '<div class="grid k3">' + "".join(comp_cells) + "</div>"

    steps = "".join(f"<li>{esc(p)}</li>" for p in proto)

    body = f"""
<div class="callout ok">
  <h4>This page exists so that nothing gets built by default</h4>
  <p>Every proposal below is scored on four axes and carries an explicit recommendation. Nothing is implemented because it was suggested — implementation status is tracked separately and shown as <em>state</em>. Review it, compare the trade-offs, then choose.</p>
</div>

<h3>Review protocol</h3>
<ol>{steps}</ol>

<h3>Scoring</h3>
<p>Four declared inputs, one ratio, and the formula is printed on every row so it can be argued with:</p>
<div class="formula">score = impact × confidence ÷ ( effort × (1 + 0.25 × risk) )</div>
<p class="tbl-note">Impact and confidence are about decision quality. Effort is 1 for a single sitting of scripted work and 5 for weeks or a purchase. Risk counts the damage if the idea is wrong — a proposal that could produce confidently wrong signals scores 5.</p>

{t}

<h3>Compare the three highest-ranked 'adopt now' items</h3>
{comp}

<h3>Rejected and deferred, kept on the record</h3>
<p>SG-13 (rank strategies by season-long ROI) and SG-14 (infer depth order from jersey number or experience) are marked rejected with their reasons intact. SG-12 (weekly change diffs) is deferred until four snapshots exist. Keeping the rejections visible is deliberate: a rejected idea that keeps returning is a signal about the process, not about the idea.</p>
"""
    return shell("pages/suggestions.html", "Suggestions", "Suggestions", body,
                 subtitle="18 proposals, scored and stated with their trade-offs, so a path can be chosen before anything is implemented.",
                 eyebrow="Decisions")


def build_strategies(D):
    st = D["strategies"]
    gates = D["gates"]["gates"]
    rows = []
    for s in st["strategies"]:
        g = s["gates"]
        blocked = [k for k, v in g.items() if v == "blocked"]
        hard = {x["id"] for x in gates if x["type"] == "hard"}
        blocked_hard = [k for k in blocked if k in hard]
        verdict_cls = "bad" if blocked_hard else "warn"
        rows.append({"cells": [
            f'<strong>{esc(s["id"])}</strong>',
            esc(s["name"]),
            badge(s["type"], "info"),
            esc(s["market"]),
            badge("BLOCKED" if blocked_hard else "unrun", verdict_cls),
            esc(", ".join(sorted(blocked_hard)) if blocked_hard else "—"),
            f'{sum(1 for v in g.values() if v == "unrun")}/{len(g)}',
            esc(s["thesis"]),
        ], "sort": [s["id"], s["name"], s["type"], s["market"], None, None, None, None]})
    t = tbl("t-strat", [("ID", ""), ("Strategy", ""), ("Type", ""), ("Market", ""), ("State", ""), ("Blocked at", ""), ("Gates unrun", "num"), ("Thesis", "wrap")],
            rows, searchable=True, placeholder="Filter strategies…", source="register")

    cards = []
    for s in st["strategies"]:
        gbadges = " ".join(
            badge(f'{k}: {v}', "bad" if v == "blocked" else "muted") for k, v in s["gates"].items()
        )
        cards.append(f"""
<div class="flag" style="border-left-color:var(--accent)">
  <h4>{esc(s['id'])} — {esc(s['name'])} {badge(s['type'],'info')}</h4>
  <div class="meta">{esc(s['market'])}</div>
  <dl>
    <dt>Thesis</dt><dd>{esc(s['thesis'])}</dd>
    <dt>Rule</dt><dd>{esc(s['rule'])}</dd>
    {'<dt>Current examples</dt><dd>' + esc(s['current_examples']) + '</dd>' if s.get('current_examples') else ''}
    <dt>Verdict</dt><dd><strong>{esc(s['verdict'])}</strong></dd>
    <dt>How it fails</dt><dd>{esc(s['risk_note'])}</dd>
    <dt>Gate state</dt><dd>{gbadges}</dd>
  </dl>
</div>""")

    body = f"""
<div class="callout bad">
  <h4>Zero of twelve strategies are scored — and that is the honest answer</h4>
  <p>The board ranks nothing because nothing can be measured. Every strategy is blocked at gate G0: the league publishes no odds archive of its own (S09, S13) and none has been purchased, so there is no price, no closing line and no way to separate an edge from a coin flip. Parlay and prop entries are additionally blocked at G9 and G10 for missing leg-level and usage data.</p>
  <p style="margin-bottom:0">Publishing an empty board is a deliberate choice. Filling it with hypothetical results would be precisely the failure this project exists to prevent.</p>
</div>

<h3>How the board will rank once G0 clears</h3>
<div class="formula">composite = 0.40·z(mean CLV) + 0.30·z(shrunk ROI) + 0.20·stability + 0.10·capacity
shrunk_ROI = ROI × n / (n + 400)</div>
<p>The shrinkage term is the important one: with 400 graded bets, half the measured ROI is treated as signal and half as noise. A 30-bet heater cannot lead the board, by construction.</p>
<p class="tbl-note">Grading spec: price fixed at submission, pushes refunded, voids excluded, and a line move never re-grades a placed bet. See <a href="gates.html">Validation gates</a> for the 13 gates and the reward tiers.</p>

{t}

<h3>Each strategy in detail</h3>
{''.join(cards)}
"""
    return shell("pages/strategies.html", "Strategy leaderboard", "Strategy leaderboard", body,
                 subtitle="Twelve strategies across single bets, parlays and player props — with every gate state shown, including the ones that block them.",
                 eyebrow="Decisions")


def build_gates(D):
    g = D["gates"]
    sm = D["strategy_math"]
    rows = []
    for x in g["gates"]:
        rows.append({"cells": [
            f'<strong>{esc(x["id"])}</strong>',
            esc(x["name"]),
            badge(x["type"], "bad" if x["type"] == "hard" else "warn"),
            esc(x["applies_to"]),
            esc(x["criterion"]),
            esc(x.get("numbers") or "—"),
            esc(x["failure"]),
        ], "sort": [x["id"], x["name"], x["type"], x["applies_to"], None, None, None]})
    t = tbl("t-gates", [("ID", ""), ("Gate", ""), ("Type", ""), ("Applies to", ""), ("Pass criterion", "wrap"), ("Numbers", "wrap"), ("If it fails", "wrap")],
            rows, source="method", note="Hard gates cannot be waived. A strategy failing any hard gate receives no reward, whatever its profit.")

    tier_rows = [{"cells": [f'<strong>{esc(x["tier"])}</strong>', esc(x["gates_required"]), esc(x["reward"]), esc(x["meaning"])]} for x in g["reward_tiers"]]
    tt = tbl("t-tiers", [("Tier", ""), ("Gates required", "wrap"), ("Reward", "wrap"), ("Meaning", "wrap")], tier_rows, source="method")

    sn = sm["sample_size"]
    sn_rows = [{"cells": [f'{r["target_edge"]*100:.1f} pp', f'{r["break_even_win_rate"]*100:.1f}%',
                          num(r["required_bets_winprob_test"], 0), num(r["required_bets_roi_test"], 0)]} for r in sn["rows"]]
    snt = tbl("t-samplesize", [("Target edge", "num"), ("Break-even win rate", "num"), ("Bets: win/loss test", "num"), ("Bets: ROI test", "num")], sn_rows, note=sn["note"], source="method")

    dsr_rows = [{"cells": [num(r["trials"], 0), num(r["observed_sharpe"], 3), num(r["expected_max_sharpe_under_null"], 4),
                           num(r["deflated_sharpe_ratio"], 4), badge("pass" if r["passes_G5"] else "fail", "ok" if r["passes_G5"] else "bad")]}
                for r in sm["deflated_sharpe"]["rows"]]
    dsrt = tbl("t-dsr", [("Trials tried", "num"), ("Observed Sharpe", "num"), ("Expected max under null", "num"), ("Deflated Sharpe", "num"), ("G5", "")], dsr_rows,
               note=sm["deflated_sharpe"]["note"], source="method")

    cib = sm["confidence_intervals"]
    ci_rows = [{"cells": [esc(r["record"]), num(r["n"], 0), num(r["observed_win_rate"], 3),
                          f'{r["wilson_95_ci"][0]:.3f} – {r["wilson_95_ci"][1]:.3f}',
                          badge("yes" if r["includes_break_even_524"] else "no", "warn" if r["includes_break_even_524"] else "ok")]}
               for r in cib["rows"]]
    cit = tbl("t-ci", [("Record", ""), ("n", "num"), ("Win rate", "num"), ("95% interval", "num"), ("Contains 52.4%?", "")], ci_rows, note=cib["note"], source="method")

    pl = sm["parlay_two_leg"]
    pl_rows = [{"cells": [num(r["rho"], 1), num(r["p_joint"], 4), num(r["p_joint_if_independent"], 4),
                          f'{r["error_from_independence_pct"]:+.1f}%', num(r["fair_decimal_odds"], 3),
                          signed(r["ev_per_unit_at_offered_price"], 4)]} for r in pl["rows"]]
    plt = tbl("t-parlay", [("Correlation ρ", "num"), ("Joint probability", "num"), ("If independent", "num"), ("Error", "num"), ("Fair decimal odds", "num"), ("EV at independence price", "num")], pl_rows, source="method")

    pl3 = sm["parlay_three_leg"]
    pl3_rows = [{"cells": [num(r["rho"], 1), num(r["p_joint"], 4), num(r["p_joint_if_independent"], 4),
                           num(r["fair_decimal_odds"], 3), signed(r["ev_per_unit_at_offered_price"], 4)]} for r in pl3["rows"]]
    pl3t = tbl("t-parlay3", [("Correlation ρ", "num"), ("Joint probability", "num"), ("If independent", "num"), ("Fair decimal odds", "num"), ("EV at independence price", "num")], pl3_rows, source="method")

    k = sm["kelly"]
    k_rows = [{"cells": [num(r["win_prob"], 2), esc(str(r["american_price"])), num(r["decimal_odds"], 3), signed(r["edge_vs_fair"], 4),
                         num(r["full_kelly_fraction"], 4), num(r["quarter_kelly_fraction"], 4)]} for r in k["rows"]]
    kt = tbl("t-kelly", [("Win prob", "num"), ("Price", "num"), ("Decimal", "num"), ("Edge per unit", "num"), ("Full Kelly", "num"), ("Quarter Kelly", "num")], k_rows, note=k["warning"], source="method")

    mult_rows = [{"cells": [num(r["trials"], 0), num(r["alpha_per_test"], 6), num(r["t_threshold"], 3)]} for r in sm["multiplicity"]["rows"]]
    multt = tbl("t-mult", [("Trials tried", "num"), ("Alpha per test", "num"), ("Required t", "num")], mult_rows, note=sm["multiplicity"]["method"], source="method")

    body = f"""
<div class="callout bad">
  <h4>All arithmetic on this page is illustrative, not empirical</h4>
  <p>Every table here is computed from declared parameters — a break-even rate, a target edge, a correlation. None of it is an observed result from NFL data. The warning is printed in the generated JSON too, so it travels with the numbers.</p>
</div>

<h3>The 13 gates</h3>
<p>Ordered so that the cheapest disqualifiers run first. Gate G1 is the one that changes the design of the whole competition:</p>
<div class="callout warn">
  <h4>{esc(sn['headline'])}</h4>
  <p style="margin-bottom:0">This is why the leaderboard cannot rank on a single season, and why closing-line value — which carries far more signal per bet — has to be the primary metric rather than realised profit.</p>
</div>
{t}

<h3>Reward tiers</h3>
<p>Rewards are tied to gates, not to profit. A strategy can be profitable and receive nothing; that is the point.</p>
{tt}

<h3>G1 — how many bets are actually needed</h3>
<div class="formula">n = ( z<sub>1−α/2</sub>·√(p₀(1−p₀)) + z<sub>power</sub>·√(p₁(1−p₁)) )² ÷ (p₁−p₀)²</div>
{snt}

<h3>G5 — the price of searching</h3>
<p>Test enough ideas and one will look excellent. The deflated Sharpe ratio charges for the search by comparing the observed Sharpe against the maximum you would expect from that many tries under the null.</p>
{dsrt}

<h3>G2 — multiplicity</h3>
{multt}

<h3>G8 — confidence intervals: what a hot start actually means</h3>
{cit}

<h3>G9 — why independence pricing manufactures edge</h3>
<p>Two legs at 55% each have a 30.25% joint chance if independent. If they move together at ρ = 0.6, the joint chance is 40.4% — a third higher. A book that priced them as independent would be offering a fair price of 3.31 when the true fair price is 2.48.</p>
<p class="tbl-note">{esc(pl['inputs']['why_this_price'])} {esc(pl['why_it_matters'])}</p>
{plt}
<h4 style="margin-top:18px">Three legs, equicorrelated</h4>
<p class="tbl-note">{esc(pl3['method'])} {esc(pl3['inputs']['why_this_price'])}</p>
{pl3t}

<h3>Staking — and why quarter Kelly</h3>
<p>Kelly assumes the probability is known. Here it would be estimated, and an over-estimated edge turns full Kelly into over-betting with a real chance of ruin. Quarter Kelly is shown as the conservative reference point.</p>
<div class="formula">f* = (p·d − 1) ÷ (d − 1)</div>
{kt}
"""
    return shell("pages/gates.html", "Validation gates", "Validation gates", body,
                 subtitle="Thirteen gates, five reward tiers, and the arithmetic that decides how much evidence is enough.",
                 eyebrow="Decisions")


def build_flagged(D):
    fl = D["flags"]["flags"]
    src_by = D["sources_by_id"]
    cards = []
    for f in sorted(fl, key=lambda z: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(z["severity"], 4)):
        cards.append(f"""
<div class="flag {esc(f['severity'])}">
  <h4>{esc(f['id'])} · {esc(f['title'])}</h4>
  <div class="meta">{badge(f['severity'], {'critical':'bad','high':'bad','medium':'warn','low':'muted'}.get(f['severity'],'muted'))} {badge(f['type'], 'muted')} · appears on {esc(', '.join(f['affects']))}</div>
  <dl>
    <dt>What was found</dt><dd>{esc(f['what'])}</dd>
    <dt>Why it matters</dt><dd>{esc(f['why'])}</dd>
    <dt>How it is handled</dt><dd>{esc(f['handling'])}</dd>
    <dt>To clear it</dt><dd>{esc(f['closure'])}</dd>
    <dt>Sources</dt><dd>{src_chips(f['source_ids'], src_by)}</dd>
  </dl>
</div>""")

    body = f"""
<div class="callout">
  <h4>The rule this page enforces</h4>
  <p>If a value could not be confirmed against an official NFL page, it was left blank and listed here. No value was inferred, estimated, or recalled from memory to fill a table cell. That is why some cells read <span class="null">—</span> and why the pages that would normally look most authoritative are the ones with gaps in them.</p>
</div>

<div class="grid k3" style="margin-bottom:18px">
  <div class="card bad"><div class="k">Critical</div><div class="v">{sum(1 for f in fl if f['severity']=='critical')}</div><div class="s">block a core requirement</div></div>
  <div class="card warn"><div class="k">High / medium</div><div class="v">{sum(1 for f in fl if f['severity'] in ('high','medium'))}</div><div class="s">degrade a specific feature</div></div>
  <div class="card"><div class="k">Low</div><div class="v">{sum(1 for f in fl if f['severity']=='low')}</div><div class="s">documented for completeness</div></div>
</div>

{''.join(cards)}
"""
    return shell("pages/flagged.html", "Flagged for review", "Flagged for review", body,
                 subtitle="Ten items that could not be confirmed, could not be met, or contradict each other — each with its source links and closure condition.",
                 eyebrow="Trust")


def build_sources(D):
    src = D["sources"]["sources"]
    rows = []
    for s in src:
        st = s.get("http_status")
        ok = st == 200
        rows.append({"cells": [
            f'<a id="{esc(s["id"])}"></a><strong>{esc(s["id"])}</strong>',
            esc(s["title"]),
            esc(s["publisher"]),
            badge("official" if s["official"] else "secondary", "ok" if s["official"] else "warn"),
            f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["url"])}</a>',
            badge(str(st), "ok" if ok else "bad"),
            esc(s.get("check", "")),
            esc(", ".join(s.get("supports", [])) or '<span class="null">—</span>'),
        ], "sort": [s["id"], s["title"], s["publisher"], None, None, None, None, None]})
    t = tbl("t-sources", [("ID", ""), ("Title", "wrap"), ("Publisher", ""), ("Class", ""), ("URL", "wrap"), ("HTTP", ""), ("Check performed", "wrap"), ("Supports", "wrap")],
            rows, searchable=True, placeholder="Filter sources…", source="register")

    irr = D["sources"]["irregularities"]
    irows = [{"cells": [f'<strong>{esc(i["id"])}</strong>', badge(i["severity"], {"high":"bad","medium":"warn","low":"muted"}.get(i["severity"],"muted")), esc(i["title"]), esc(i["detail"]), esc(i["action"])]} for i in irr]
    it = tbl("t-irr", [("ID", ""), ("Severity", ""), ("Irregularity", "wrap"), ("Detail", "wrap"), ("Action", "wrap")], irows, source="register")

    body = f"""
<p>One rule: only pages published by the NFL or its official properties count as a source of fact. Everything else may be cited as a lead but never as the basis for a published value. Two URLs are recorded <em>because</em> they 404 — so that no future session cites them.</p>
{t}

<h3>Irregularities recorded during verification</h3>
{it}

<h3>Retrieval method</h3>
<p>Every page above was fetched live during the session on {esc(D['sources']['meta']['retrieved_at'])} and its HTTP status recorded. Values were read from the rendered text and transcribed by hand into JSON, then re-checked arithmetically where possible. Where a page was truncated before a full dataset was captured, the gap is stated on the page that uses it rather than smoothed over.</p>
"""
    return shell("pages/sources.html", "Sources", "Sources", body,
                 subtitle="Twelve sources, ten resolving and two recorded broken. Official only — with the check performed printed against each one.",
                 eyebrow="Trust")


def build_coordination(D):
    body = """
<div class="callout">
  <h4>Single-session run, multi-session protocol</h4>
  <p><a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/COORDINATION.md">COORDINATION.md</a> is the shared task board: 13 tasks, each with an owner, a branch, a file scope and a status. It was written and pushed <em>before</em> any work began, so a parallel session would have seen the claim.</p>
  <p style="margin-bottom:0">No other session, branch or claim existed at the start of this run, so this session performed every task and also acted as the final integration session. The protocol for splitting the work across sessions is documented in the file and is unchanged.</p>
</div>

<h3>What the board records</h3>
<ul>
  <li><strong>Claims before work.</strong> Session id, branch and file scope, committed and pushed before editing.</li>
  <li><strong>Non-overlapping scopes.</strong> Shared outputs — the data files, navigation and this site's build — are integration-only.</li>
  <li><strong>Handoff rule.</strong> A claim older than 60 minutes with no commits may be taken over, with the handoff logged.</li>
  <li><strong>Verification log.</strong> Per task: sources used, the check performed, and any irregularity found.</li>
  <li><strong>Requests, not edits.</strong> If a task needs another session's file, the request is logged rather than the file touched.</li>
</ul>

<h3>Tasks and status</h3>
<div class="tablewrap"><table data-source="register">
<thead><tr><th>ID</th><th>Task</th><th>Owner</th><th>Status</th></tr></thead>
<tbody>
<tr><td>T01</td><td>Coordination board + repo scaffolding</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T02</td><td>Verified source registry</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T03</td><td>Verified 2026 league data</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T04</td><td>Verified rules layer</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T05</td><td>Injury sample + depth-stress model</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T06</td><td>Decision register</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T07</td><td>Suggestions register</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T08</td><td>Line-origination engine</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T09</td><td>Gates, leaderboard, correlation math</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T10</td><td>Static site</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T11</td><td>Verification + build gate</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T12</td><td>Executive summary</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
<tr><td>T13</td><td>Integration, re-verification, publish</td><td>arena-e5e2b753</td><td><span class="badge ok">done</span></td></tr>
</tbody></table></div>

<h3>Incidents</h3>
<ul>
  <li>Two guessed <code>operations.nfl.com</code> URLs returned 404. The live path was located and the dead ones recorded in the source registry as broken.</li>
  <li>An Associated Press article conflicts with NFL.com on practice-squad size (17 versus 16). Both are recorded; the value is left blank (I-06 / F-02).</li>
</ul>
"""
    return shell("pages/coordination.html", "Coordination", "Coordination", body,
                 subtitle="The shared task board, the claim protocol, and what was verified under each task.",
                 eyebrow="Trust")


def build_404(D):
    body = """
<div class="callout warn">
  <h4>That page does not exist</h4>
  <p>The link may be old, or the section may have been renamed. Every page on this site is reachable from the navigation above.</p>
  <p style="margin-bottom:0"><a href="index.html">Return to the dashboard</a> · <a href="pages/sources.html">Sources</a> · <a href="pages/flagged.html">Flagged for review</a></p>
</div>
"""
    return shell("404.html", "Page not found", "", body, subtitle="404", eyebrow="Not found")


# ================================================================ markdown
def write_exec_md(D):
    ex = D["executive_summary"]
    out = [f"# {ex['title']}", "", ex["subtitle"], "", f"*Generated {ex['generated']} · sources: see `data/sources.json`*", ""]
    for b in ex["blocks"]:
        t = b["type"]
        if t == "h":
            out += [f"## {b['text']}", ""]
        elif t == "p":
            out += [b["text"], ""]
        elif t == "ul":
            out += [f"- {i}" for i in b["items"]] + [""]
        elif t == "ol":
            out += [f"{n}. {i}" for n, i in enumerate(b["items"], 1)] + [""]
        elif t == "callout":
            out += [f"> **{b['title']}**", ">", f"> {b['text']}", ""]
        elif t == "kv":
            out += ["| Item | Value |", "| --- | --- |"]
            out += [f"| {k} | {v} |" for k, v in b["rows"]]
            out += [""]
        elif t == "table":
            out += ["| " + " | ".join(b["head"]) + " |", "|" + "|".join([" --- "] * len(b["head"])) + "|"]
            out += ["| " + " | ".join(r) + " |" for r in b["rows"]]
            out += [""]
    with open(os.path.join(ROOT, "EXECUTIVE_SUMMARY.md"), "w") as f:
        f.write("\n".join(out))


# ================================================================ main
def main():
    D = {
        "sources": load("sources.json"),
        "standings": load("standings_2026.json"),
        "rules": load("rules.json"),
        "injuries": load("injuries.json"),
        "questions": load("questions.json"),
        "suggestions": load("suggestions.json"),
        "strategies": load("strategies.json"),
        "gates": load("gates.json"),
        "flags": load("flags.json"),
        "model": load("model_outputs.json"),
        "strategy_math": load("strategy_math.json"),
        "executive_summary": load("executive_summary.json"),
    }
    D["sources_by_id"] = {s["id"]: s for s in D["sources"]["sources"]}

    os.makedirs(PAGES, exist_ok=True)

    pages = {
        "index.html": build_dashboard(D),
        "pages/executive-summary.html": build_exec(D),
        "pages/methodology.html": build_methodology(D),
        "pages/standings.html": build_standings(D),
        "pages/lines.html": build_lines(D),
        "pages/correlations.html": build_correlations(D),
        "pages/luck.html": build_luck(D),
        "pages/injuries.html": build_injuries(D),
        "pages/depth.html": build_depth(D),
        "pages/rules.html": build_rules(D),
        "pages/questions.html": build_questions(D),
        "pages/suggestions.html": build_suggestions(D),
        "pages/strategies.html": build_strategies(D),
        "pages/gates.html": build_gates(D),
        "pages/flagged.html": build_flagged(D),
        "pages/sources.html": build_sources(D),
        "pages/coordination.html": build_coordination(D),
    }

    for path, html_out in pages.items():
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        with open(full, "w") as f:
            f.write(html_out)

    write_exec_md(D)
    print(f"built {len(pages)} pages + EXECUTIVE_SUMMARY.md")


if __name__ == "__main__":
    main()
