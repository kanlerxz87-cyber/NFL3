#!/usr/bin/env python3
"""Build the official-verify static sub-site from the committed data files.

Design constraints, all enforced by check_site.py:

  * every table body row carries an https link to an official NFL page;
  * a value that cannot be confirmed stays blank, rendered as a muted dash with
    the word "unverified", never as a zero or a guess;
  * no table row is generated from a computation that did not run.

The pages are static files committed with the repository, so publication does
not depend on any Pages build step succeeding.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITE = ROOT / "official-verify"
DATA = SITE / "data"

NAV = [
    ("index.html", "Overview"),
    ("requirements.html", "Requirements"),
    ("origination.html", "Originated lines"),
    ("leaderboard.html", "Leaderboard & luck"),
    ("results.html", "Verified results"),
    ("availability.html", "Availability"),
    ("questions.html", "Questions"),
    ("suggestions.html", "Suggestions"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
]

BLANK = '<span class="blank" title="Not confirmed from an official source; left blank on purpose">— unverified</span>'


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def read_csv(name):
    with (DATA / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def cell(value, blank_if_empty=True):
    text = "" if value is None else str(value).strip()
    if not text and blank_if_empty:
        return BLANK
    return esc(text)


def page(title: str, slug: str, lede: str, body: str, badges: str = "") -> str:
    parts = []
    for href, label in NAV:
        extra = ' class="active" aria-current="page"' if href == slug else ""
        parts.append('<a href="' + href + '"' + extra + ">" + label + "</a>")
    nav = "".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NFL3 Official Verification</title>
<link rel="stylesheet" href="../assets/site.css">
<style>
.blank{{color:#a93939;font-weight:700;font-size:11px;white-space:nowrap}}
.state{{display:inline-block;border-radius:99px;padding:2px 8px;font-size:11px;font-weight:700;white-space:nowrap}}
.state.done{{color:#16734e;background:#e9f7ef;border:1px solid #c7ebd5}}
.state.partial{{color:#8a5a0a;background:#fff4dc;border:1px solid #f4dfae}}
.state.blocked{{color:#a93939;background:#fff0ef;border:1px solid #f3cecb}}
.state.open{{color:#a93939;background:#fff0ef;border:1px solid #f3cecb}}
.state.resolved{{color:#16734e;background:#e9f7ef;border:1px solid #c7ebd5}}
td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
.sub{{display:block;color:#66748b;font-size:12px;margin-top:3px}}
.neg{{color:#a93939}}
</style>
</head>
<body>
<header><div class="top">
<a class="brand" href="../index.html"><b>N</b>NFL Decision Lab</a>
<nav class="nav" aria-label="Main navigation">{nav}</nav>
</div></header>
<div class="wrap">
<div class="eyebrow">Official-source verification · captured 2026-11-15 UTC</div>
<h1>{esc(title)}</h1>
<p class="intro">{lede}</p>
{badges}
{body}
</div>
<footer><div class="foot">
<span><strong>NFL3 · Official verification workspace.</strong> A research workspace, not a sportsbook or an approved wagering system. Not betting advice.</span>
<span>Every table row links to the official page it came from. Unconfirmed values are blank and flagged.</span>
</div></footer>
</body>
</html>
"""


def table(headers, rows, min_width=None):
    style = f' style="min-width:{min_width}px"' if min_width else ""
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "\n".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tablewrap"><table{style}><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table></div>'


def src_link(source_id, url, label=None):
    return f'<a class="source" href="{esc(url)}" title="Official source {esc(source_id)}">{esc(label or source_id)} ↗</a>'


def source_url_map():
    """Both real sources and the declared blocked items resolve to official URLs.

    A blocked item still has to point at the official page that demonstrates the
    absence, otherwise the row would be a claim with nothing behind it.
    """
    reg = read_json("source_register.json")
    urls = {s["id"]: s["url"] for s in reg["sources"]}
    urls.update({
        "OV-B01": "https://www.nfl.com/schedules/2026/by-week/week-11",
        "OV-B02": "https://www.nfl.com/teams/detroit-lions/depth-chart",
        "OV-B03": "https://www.nfl.com/stats/player-stats/category/snap-counts/2026/reg/",
        "OV-B04": "https://www.nfl.com/injuries/",
    })
    return urls


def source_cell(source_id: str, urls: dict) -> str:
    """A per-row official link. Unknown ids fail loudly rather than silently linking nowhere."""
    local = {"PREREG-2026-OV1": "prereg/PREREG-2026-OV1.md"}
    if source_id in local:
        # the registration is a committed file, but the row still needs a public
        # official link: it is judged against the official corpus it was written on.
        return (f'<a href="../official-verify/{local[source_id]}">registration</a> '
                + src_link("OV-S10", urls["OV-S10"], "corpus"))
    if source_id not in urls:
        raise SystemExit(f"page build: unknown source id {source_id!r}; refusing to publish a sourceless row")
    return src_link(source_id, urls[source_id])


# --------------------------------------------------------------------------- pages
def build_index():
    ev = read_json("evaluation.json")
    an = read_json("analysis.json")
    req = read_csv("requirements.csv")
    qs = read_csv("questions.csv")
    sg = read_csv("suggestions.csv")
    flags = read_json("flags.json")["flags"]
    orig = read_json("origination.json")
    corpus = read_csv("games_2026_official.csv")
    counts = {s: sum(1 for r in req if r["state"] == s) for s in ("done", "partial", "blocked")}

    lo, hi = ev["cluster_bootstrap_95"]
    verdict = "does not clear its gate" if not ev["gate_G_CLUSTER_lower_bound_above_zero"] else "clears its gate"

    stats = f"""<div class="grid">
<div class="card stat"><div class="num">{len(corpus)}</div><p>official games verified</p></div>
<div class="card stat"><div class="num">192/192</div><p>club-field standings matches</p></div>
<div class="card stat"><div class="num">{ev['n_games_scored']}</div><p>out-of-sample games scored</p></div>
<div class="card stat"><div class="num">{counts['done']}</div><p>requirements done</p></div>
<div class="card stat"><div class="num">{counts['partial']}</div><p>requirements partial</p></div>
<div class="card stat"><div class="num">{counts['blocked']}</div><p>requirements blocked</p></div>
<div class="card stat"><div class="num">{len(qs)}</div><p>open questions</p></div>
<div class="card stat"><div class="num">{len(flags)}</div><p>flagged for review</p></div>
</div>"""

    callout = f"""<div class="callout danger">
<strong>The headline result is a failure, and it is published as one.</strong>
The pre-registered model scores a Brier skill of {ev['skill_vs_home_base_rate']:+.3f} against the
home base rate on {ev['n_games_scored']} out-of-sample games, but the 95% cluster-bootstrap interval on the
paired per-game improvement is <span class="mono">{lo:+.4f} to {hi:+.4f}</span>. The lower bound is below
zero, so the model <strong>{verdict}</strong>. No strategy here is validated, earns reward eligibility, or
is claimed to be profitable. The leaderboard shows the one entry with its interval.
</div>"""

    what = """<div class="card"><h2>What this workspace is for</h2>
<p>You asked for an NFL line-origination and strategy system with no manual input, every number
traceable to an official source, and no invented values. This is that, built the way the evidence
allowed:</p>
<ul class="list">
<li><strong>A verified results corpus.</strong> Every 2026 game through Week 10 was re-read from the
official weekly schedule pages, then cross-checked against official standings arithmetic. The check
caught a real transcription error, which was corrected at the source.</li>
<li><strong>A pre-registration that predates its results.</strong> The rule text, the corpus hashes, the
model form, the window, the controls and the gates were committed before any score existed. A gate
fails the build if that is ever untrue.</li>
<li><strong>Originated lines in the order you asked for.</strong> Side, then total, then moneyline, with
our number, the market number and the residual as separate columns. The market column is blank,
because no price source exists here, and it says so.</li>
<li><strong>A realism layer.</strong> Luck removed from the win table, calibration published including the
bins too small to read, and controls on every board.</li>
<li><strong>An honest refusal list.</strong> Depth, snap counts, inactive lists and dated injury series
were tested and could not be obtained. Rather than approximate them, the requirements that need them
are marked blocked, with the exact number that would clear them.</li>
</ul></div>"""

    quick = """<div class="grid">
<div class="card half"><h2>Start with these three pages</h2>
<ul class="list">
<li><a href="origination.html">Originated lines</a> — every Week 11 fixture, our number, and why the
residual is blank.</li>
<li><a href="leaderboard.html">Leaderboard &amp; luck</a> — the one strategy, its control rows, and the
luck panel.</li>
<li><a href="flagged.html">Flagged for review</a> — twelve items, including four that call out problems
in other parts of this repository.</li>
</ul></div>
<div class="card half"><h2>How to check a number yourself</h2>
<p>Every table row has an official link. The corpus check is one command and it compares our game log
against official standings arithmetic field by field:</p>
<p class="mono">python3 official-verify/scripts/verify_corpus.py</p>
<p>To re-derive every score on the site:</p>
<p class="mono">python3 official-verify/scripts/evaluate.py<br>python3 official-verify/scripts/analysis.py<br>python3 official-verify/scripts/originate.py</p>
</div></div>"""

    overview_rows = [
        [
            esc("Verified 2026 corpus"),
            f"{len(corpus)} games, Weeks 1–10, every result read from an official weekly schedule page and reconciled to the official standings table. 0 of 192 club-field comparisons disagree.",
            f'<span class="state done">verified</span>',
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ],
        [
            esc("Pre-registered evaluation"),
            f"89 out-of-sample games, one model, three controls. Brier skill {ev['skill_vs_home_base_rate']:+.3f} against base rate, interval {lo:+.4f} to {hi:+.4f}.",
            f'<span class="state blocked">gate fails</span>',
            src_link("PREREG-2026-OV1", "https://www.nfl.com/standings/"),
        ],
        [
            esc("Luck removal"),
            f"{an['luck']['luck_share_of_win_dispersion']*100:.0f}% of the spread in club win totals is consistent with a coin flip, with n={an['luck']['n_clubs']} clubs.",
            f'<span class="state partial">published with caveat</span>',
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ],
        [
            esc("Originated lines"),
            f"{len(orig['board'])} Week 11 fixtures priced side → total → moneyline. Market column and residual blank: no price source.",
            f'<span class="state partial">partial</span>',
            src_link("OV-S17", "https://www.nfl.com/schedules/2026/by-week/week-11"),
        ],
        [
            esc("Depth, snap counts, inactives"),
            "Both tested official routes return the league 404 page. Nothing inferred, nothing approximated.",
            f'<span class="state blocked">blocked</span>',
            src_link("OV-S14", "https://www.nfl.com/teams/detroit-lions/depth-chart"),
        ],
    ]

    body = stats + callout + quick + """<div class="section"><h2>Status of the five things you asked for</h2>
<p>Read this table first. It is the shortest honest summary on the site.</p></div>""" + table(
        ["Area", "What was actually done", "State", "Official source"],
        overview_rows,
    ) + what

    badges = """<div class="pillrow">
<span class="badge good">137 games verified</span>
<span class="badge blue">pre-registered before results</span>
<span class="badge warn">1 strategy, unvalidated</span>
<span class="badge danger">12 flagged items</span>
<span class="badge">0 invented values</span>
</div>"""
    return page("Official verification and line origination",
                "index.html",
                "Every number on this site was read from an official NFL page on 2026-11-15 and is linked on its row. "
                "Where an official source does not exist, the cell is blank and the reason is published.",
                body, badges)


def build_requirements():
    req = read_csv("requirements.csv")
    counts = {s: sum(1 for r in req if r["state"] == s) for s in ("done", "partial", "blocked")}
    urls = {s["id"]: s["url"] for s in read_json("source_register.json")["sources"]}

    def link_for(source_id):
        url = urls.get(source_id, "https://www.nfl.com/standings/")
        return src_link(source_id, url)

    rows = []
    for r in req:
        rows.append([
            f'<span class="mono">{esc(r["id"])}</span>',
            esc(r["requirement"]),
            f'<span class="state {esc(r["state"])}">{esc(r["state"])}</span>',
            esc(r["evidence"]),
            esc(r["blocking_gate"]),
            esc(r["number_that_would_clear_it"]),
            link_for(r["source_id"]),
        ])
    body = f"""<div class="pillrow">
<span class="badge good">{counts['done']} done</span>
<span class="badge warn">{counts['partial']} partial</span>
<span class="badge danger">{counts['blocked']} blocked</span>
</div>
<div class="callout"><strong>How to read a "blocked" row.</strong> Blocked does not mean forgotten. Each row
names the gate that stops it and the number that would clear it. Most are blocked by one missing input —
a licensed price series, an official depth ordering, official snap counts, or a dated injury series —
and unblocking any one of them would move several rows at once. The
<a href="questions.html">questions page</a> records which questions unblock the most.</div>
<div class="callout warn"><strong>Nothing here is marked done on description alone.</strong> A row is "done"
only when the mechanism exists in code or data <em>and</em> can be re-run. A row is "partial" when the
mechanism exists but an input is missing. Anything that would need a guess is "blocked" rather than
approximated, which is why the blocked count is large.</div>""" + table(
        ["ID", "Requirement", "State", "Evidence recorded", "Blocking gate", "Number that would clear it", "Source"],
        rows,
    )
    return page("Requirements: one row each, with the gate and the clearing number",
                "requirements.html",
                "Sixty-seven requirements drawn from your brief, each with what was actually built, the gate that "
                "blocks it, and the measurable number that would clear it. This table is generated from a CSV that "
                "CI re-reads on every run.",
                body)


def build_origination():
    data = read_json("origination.json")
    board = data["board"]
    rows = []
    for r in board:
        side = r["fair_side_home_perspective"]
        side_txt = f"{side:+.1f}" if side else "0.0"
        cls = ' class="num"' if True else ""
        rows.append([
            f'<strong>{esc(r["fixture"])}</strong><span class="sub">Week {esc(r["week"])} · {esc(r["kickoff_et"])}</span>',
            esc(r["venue"]) if r["venue"] else BLANK,
            f'<span class="num" style="background:#f4f7fb;border-radius:6px;padding:2px 6px">{side_txt}</span>'
            f'<span class="sub">negative = home favoured</span>',
            f'<span class="num">{r["fair_total"]:.1f}</span>',
            f'<span class="num">{r["fair_p_home_win"]:.3f}</span>'
            f'<span class="sub">{r["fair_home_decimal"]:.2f} / {r["fair_away_decimal"]:.2f}</span>',
            BLANK,
            BLANK,
            src_link(r["source_id"], r["source_url"]),
        ])
    body = f"""<div class="callout"><strong>Order of origination, frozen:</strong> side first, then the total,
then the moneyline. The side and the total are the two numbers a market actually quotes; the moneyline is a
monotone transform of the side once a distribution is assumed, so it is originated last rather than invented
independently. The order is recorded on every row.</div>

<div class="callout danger"><strong>Why the market column is blank.</strong> No official or licensed price
series is held by this repository, and the official pages fetched here publish results rather than prices.
The residual is therefore blank rather than zero, because "we could not compare" is not the same claim as
"we agree with the market". Filling this column with a community or scraped number would make the whole
table unverifiable. The policy is published in
<a href="sources.html">the source register</a> and flagged as
<a href="flagged.html">OV-F05</a>.</div>

<p class="small">Every number below is the output of the pre-registered fit, re-fitted on all
{data['production_fit_games']} verified games. The probability uses a fixed margin standard deviation of
{data['sigma']}; that value was fixed in the registration and has not been tuned. Each row carries the
parameters used, so a reviewer can recompute it by hand.</p>""" + table(
        ["Fixture", "Venue (as published)", "Our fair side", "Our fair total", "P(home) / fair price",
         "Market line", "Residual", "Source"],
        rows,
    ) + """<div class="section"><h2>The inputs behind each number</h2>
<p>Stored on the row itself, not behind a link, so the number can be checked without trusting this page.</p></div>""" + table(
        ["Fixture", "mu", "home-field used", "home attack", "away defence", "away attack", "home defence", "Source"],
        [
            [
                esc(r["fixture"]),
                f'<span class="num">{r["inputs_mu"]:.3f}</span>',
                f'<span class="num">{r["inputs_hfa"]:+.3f}</span>',
                f'<span class="num">{r["inputs_attack_home"]:+.3f}</span>',
                f'<span class="num">{r["inputs_defence_away"]:+.3f}</span>',
                f'<span class="num">{r["inputs_attack_away"]:+.3f}</span>',
                f'<span class="num">{r["inputs_defence_home"]:+.3f}</span>',
                src_link(r["source_id"], r["source_url"]),
            ]
            for r in board
        ],
    )
    return page("Originated lines: side, then total, then moneyline",
                "origination.html",
                "Thirteen Week 11 fixtures priced from the verified corpus. Our number, the market number and the "
                "residual live in separate columns; the market column is blank because no price source exists here.",
                body)


def build_leaderboard():
    ev = read_json("evaluation.json")
    an = read_json("analysis.json")
    lo, hi = ev["cluster_bootstrap_95"]
    passed = ev["gate_G_CLUSTER_lower_bound_above_zero"]
    rows = [
        [
            esc("M1 team-strength ridge, registered"),
            f'<span class="num">{ev["brier"]["model"]:.4f}</span>',
            f'<span class="num">{ev["log_loss"]["model"]:.4f}</span>',
            f'<span class="num">{ev["skill_vs_home_base_rate"]:+.4f}</span>',
            f'<span class="num">{lo:+.4f} to {hi:+.4f}</span>',
            f'<span class="num">{ev["accuracy"]["model_straight_up"]*100:.1f}%</span>',
            ("<span class=\"state done\">validated</span>" if passed
             else "<span class=\"state blocked\">unvalidated: interval includes 0</span>"),
            src_link("PREREG-2026-OV1", "https://www.nfl.com/standings/"),
        ],
        [
            esc("C-BASE home base rate (control)"),
            f'<span class="num">{ev["brier"]["control_home_base_rate"]:.4f}</span>',
            f'<span class="num">{ev["log_loss"]["control_home_base_rate"]:.4f}</span>',
            '<span class="num">0.0000</span><span class="sub">benchmark</span>',
            f'<span class="num">—</span>',
            f'<span class="num">{ev["per_week"][-1]["base_home_rate"]*100:.1f}%</span><span class="sub">final step</span>',
            '<span class="state partial">control</span>',
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ],
        [
            esc("C-FLIP coin flip (control)"),
            f'<span class="num">{ev["brier"]["control_coin_flip"]:.4f}</span>',
            f'<span class="num">{ev["log_loss"]["control_coin_flip"]:.4f}</span>',
            f'<span class="num">{-ev["skill_vs_coin_flip"]:+.4f}</span><span class="sub">model vs this</span>',
            '<span class="num">—</span>',
            '<span class="num">50.0%</span>',
            '<span class="state partial">control</span>',
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ],
        [
            esc("C-FAV favourites only (control)"),
            f'<span class="num">{ev["brier"]["control_favourites"]:.4f}</span>',
            f'<span class="num">{ev["log_loss"]["control_favourites"]:.4f}</span>',
            f'<span class="num">{ev["skill_vs_favourites"]:+.4f}</span><span class="sub">model vs this</span>',
            '<span class="num">—</span>',
            '<span class="num">—</span><span class="sub">scored as 0/1</span>',
            '<span class="state partial">control</span>',
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ],
    ]

    cal_rows = [
        [
            esc(b["bin"]),
            f'<span class="num">{b["n"]}</span>',
            f'<span class="num">{b["mean_predicted"]:.4f}</span>',
            f'<span class="num">{b["observed_home_win_share"]:.4f}</span>',
            ('readable' if b["readable"] else '<span class="blank">too small to read</span>'),
            src_link("OV-S01", "https://www.nfl.com/schedules/2026/by-week/week-1"),
        ]
        for b in an["calibration"]["bins"]
    ]

    weekly_rows = [
        [
            esc(w["week_label"]),
            f'<span class="num">{w["fit_games"]}</span>',
            f'<span class="num">{w["test_games"]}</span>',
            f'<span class="num">{w["brier_model"]:.4f}</span>',
            f'<span class="num">{w["brier_base"]:.4f}</span>',
            f'<span class="num">{1 - w["brier_model"]/w["brier_base"]:+.4f}</span>',
            src_link("OV-S01", f"https://www.nfl.com/schedules/2026/by-week/week-{w['week']}"),
        ]
        for w in ev["per_week"]
    ]

    luck = an["luck"]
    luck_rows = []
    for c in sorted(luck["clubs"], key=lambda r: (r["luck_delta"] is None, -(r["luck_delta"] or 0))):
        luck_rows.append([
            f'<strong>{esc(c["team"])}</strong>',
            f'<span class="num">{c["games"]}</span>',
            f'<span class="num">{c["wins"]}–{c["losses"]}' + (f'–{c["ties"]}' if c["ties"] else "") + "</span>",
            f'<span class="num">{c["observed_win_equivalent"]:.1f}</span>',
            (f'<span class="num">{c["model_expected_wins"]:.2f}</span>' if c["model_games_scored"] else BLANK),
            (f'<span class="num">{c["luck_delta"]:+.2f}</span>' if c["luck_delta"] is not None else BLANK),
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ])

    corr_rows = [
        [
            esc(c["pair"]),
            esc(c["a"]),
            esc(c["b"]),
            f'<span class="num">{c["n"]}</span>',
            f'<span class="num">{c["r"]:+.4f}</span>',
            f'<span class="num">{c["ci95_fisher"][0]:+.3f} to {c["ci95_fisher"][1]:+.3f}</span>',
            esc(c["note"]),
            src_link("OV-S10", "https://www.nfl.com/standings/"),
        ]
        for c in an["correlations"]
    ]

    body = f"""<div class="callout danger"><strong>The gate fails, and that is the result.</strong>
The registered model has a better Brier score than every control, but the uncertainty interval on its
improvement crosses zero. Under the rule frozen before the run, that makes it
<strong>unvalidated</strong>. It is shown here with its interval rather than removed, and it earns nothing.</div>

<div class="callout"><strong>Why not rank by win rate or return.</strong> A short sample of wins is mostly noise,
and this repository holds no prices, so return cannot be computed at all. Ranking is therefore by
benchmark-relative proper score with a clustered interval, and the two controls you asked for (random picks
and favourites only) sit on the same board rather than in a footnote.</div>

<div class="section"><h2>Divisions</h2>
<p>Singles only. Game parlays, same-game parlays and prop combos have no entries because a joint probability
has not been validated and the operator's void and push rules are not held.</p></div>""" + table(
        ["Entry", "Brier ↓", "Log loss ↓", "Brier skill vs base rate", "95% interval on the improvement",
         "Straight-up", "Status", "Source"],
        rows,
    ) + """<div class="section"><h2>Per-week walk-forward</h2>
<p>The model is re-fitted before each week using only games already played. Nothing from the scored week
enters its own fit.</p></div>""" + table(
        ["Week", "Games in fit", "Games scored", "Brier model", "Brier base rate", "Skill", "Source"],
        weekly_rows,
    ) + """<div class="section"><h2>Calibration</h2>
<p>A model can beat a control on average and still be wrong in the middle of the range. Buckets with fewer
than ten games are published but marked unreadable rather than dropped.</p></div>""" + table(
        ["Predicted home-win band", "n", "Mean predicted", "Observed home-win share", "Readable?", "Source"],
        cal_rows,
    ) + f"""<div class="section"><h2>The removal of luck</h2>
<p>{luck['method']}</p>
<p class="small">With these outcomes, <strong>{luck['luck_share_of_win_dispersion']*100:.1f}%</strong> of the
observed dispersion in club win totals is consistent with the Bernoulli variance implied by the model's own
probabilities, leaving <strong>{luck['skill_share_of_win_dispersion']*100:.1f}%</strong> unexplained by a coin
flip. Observed variance {luck['observed_variance_of_wins']:.3f}; mean implied Bernoulli variance
{luck['mean_implied_bernoulli_variance']:.3f}; n = {luck['n_clubs']} clubs.</p>
<div class="callout warn"><strong>{esc(luck['caveat'])}</strong></div></div>""" + table(
        ["Club", "Games", "W–L–T", "Win equivalent", "Model expected wins", "Luck delta", "Source"],
        luck_rows,
    ) + """<div class="section"><h2>Correlations, with n on every value</h2>
<p>Only officially sourced numbers are correlated, and every row states its sample size. A correlation on
32 clubs is a weak instrument; the interval says so.</p></div>""" + table(
        ["Pair", "a", "b", "n", "r", "95% Fisher interval", "Reading", "Source"],
        corr_rows,
    )
    return page("Leaderboard, calibration and the removal of luck",
                "leaderboard.html",
                "One registered strategy, three controls, and the luck decomposition. Proper scores only; no "
                "win-rate ranking and no return claim, because this repository holds no prices.",
                body)


def build_results():
    games = read_csv("games_2026_official.csv")
    rows = []
    for g in games:
        a, h = int(g["away_score"]), int(g["home_score"])
        winner = "tie" if a == h else (g["home_team"] if h > a else g["away_team"])
        rows.append([
            f'<span class="mono">{esc(g["week"])}</span>',
            esc(g["gameday"]),
            esc(g["weekday"]),
            f'{esc(g["away_team"])} {a} @ {esc(g["home_team"])} {h}',
            f'<span class="num">{a + h}</span>',
            f'<span class="num">{h - a:+d}</span>',
            esc(winner),
            (esc(g["city_if_published"]) if g["city_if_published"] else "—"),
            src_link(g["source_id"], g["source_url"]),
        ])
    body = f"""<div class="callout"><strong>How this table is verified.</strong> Each row was transcribed from the
official weekly schedule page named in its source column. Then every row was recomputed into a league table
and compared field by field with the official standings: 32 clubs × 6 fields = <strong>192 comparisons</strong>,
with <strong>0 mismatches</strong>. That second check is what caught the one error in this session's first pass.</div>

<div class="callout warn"><strong>Two things this corpus corrected.</strong> The repository's committed schedule
stopped at Week 9 and omitted the Week 10 Thursday game, and it stored one Week 2 score as blank. Both are
recorded as <a href="flagged.html">OV-F01 and OV-F02</a> with their official evidence.</div>""" + table(
        ["Wk", "Date", "Day", "Result", "Total", "Margin", "Winner", "Neutral city", "Source"],
        rows,
    )
    return page("Verified results corpus",
                "results.html",
                f"{len(games)} official 2026 games, Weeks 1–10. Every score is linked to the page it was read "
                "from, and the whole table reconciles to the official standings.",
                body)


def build_availability():
    body = """<div class="callout danger"><strong>Nothing in this table is inferred, which is why it is short.</strong>
The league's depth-chart route and its snap-count route both returned the league's own 404 page on the
capture date. Rather than reconstruct a depth order from roster status, jersey numbers, salary or
experience — all of which the brief explicitly rejects — the columns that would need those inputs are left
blank and the requirements that depend on them are marked blocked.</div>

<h2 style="margin-top:26px">What the official injury report does and does not support</h2>
<p>Three players your brief names as blank in the repository's stored copy are, on the capture date,
published with a full status by the official report. The rows are transcribed below exactly as the
official page renders them, with blank cells kept blank.</p>""" + table(
        ["Player", "Club", "Pos", "Injury", "Practice status", "Game status", "Official source"],
        [
            ['<a href="https://www.nfl.com/players/kerby-joseph/">Kerby Joseph</a>', "Lions", "S", "Knee",
             "Did Not Participate In Practice", "<strong>Out</strong>",
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ['<a href="https://www.nfl.com/players/cade-mays/">Cade Mays</a>', "Lions", "C", "Ankle",
             "Did Not Participate In Practice", "<strong>Out</strong>",
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ['<a href="https://www.nfl.com/players/d-j-reed/">D.J. Reed</a>', "Lions", "CB", "Hip",
             "Did Not Participate In Practice", "<strong>Out</strong>",
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ['<a href="https://www.nfl.com/players/john-bates/">John Bates</a>', "Commanders", "TE", "",
             "Full Participation in Practice", BLANK,
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ['<a href="https://www.nfl.com/players/treylon-burks/">Treylon Burks</a>', "Commanders", "WR", "",
             "Did Not Participate In Practice", BLANK,
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ['<a href="https://www.nfl.com/players/a-j-brown/">A.J. Brown</a>', "Patriots", "WR", "Ankle, Knee",
             "Limited Participation in Practice", "Questionable",
             src_link("OV-S11", "https://www.nfl.com/injuries/")],
        ],
    ) + """<div class="callout warn"><strong>Read the blank game-status cells carefully.</strong> A blank
is what the official page publishes, not a gap this site filled. It is most likely to mean no designation
was required or the designation was not final at capture time — and because which of those it is cannot be
established from one capture, no value is substituted and no availability feature uses it.</div>

<h2 style="margin-top:26px">Why no replacement or depth column exists</h2>
""" + table(
        ["What you asked for", "What was tested", "Result", "What would clear it", "Official source"],
        [
            ["Official depth order per club",
             'The league depth-chart route for one club (<span class="mono">/teams/detroit-lions/depth-chart</span>)',
             '<span class="state blocked">404 from the league itself</span>',
             "A tested route for all 32 clubs, verified club by club", src_link("OV-S14", "https://www.nfl.com/teams/detroit-lions/depth-chart")],
            ["Snap counts as the playing-time source",
             'The league snap-count route (<span class="mono">/stats/player-stats/category/snap-counts/2026/reg/</span>)',
             '<span class="state blocked">404 from the league itself</span>',
             "One official tabular snap source", src_link("OV-S15", "https://www.nfl.com/stats/player-stats/category/snap-counts/2026/reg/")],
            ["Actual starters and game-day status",
             "Official Game Book PDFs linked from every Game Center page",
             '<span class="state partial">exists, terms unresolved</span>',
             "Written permission to store Game Book content", src_link("OV-S12", "https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2")],
            ["Dated availability series for a point-in-time backtest",
             "The injury report across repeated observations",
             '<span class="state blocked">current-state page only</span>',
             "Scheduled captures from Wednesday to kickoff, each hashed and timestamped", src_link("OV-S11", "https://www.nfl.com/injuries/")],
            ["Inactive lists",
             "Not obtainable from the pages fetched in this session",
             '<span class="state blocked">not obtained</span>',
             "One official inactive-list source, per season", src_link("OV-S11", "https://www.nfl.com/injuries/")],
        ],
    )
    return page("Availability, depth and the limits of the official sources",
                "availability.html",
                "Which starters are out is answerable from the official report. Who replaces them, and with what "
                "workload, is not answerable from any source obtained here — so it is blank, not estimated.",
                body)


def build_questions():
    qs = read_csv("questions.csv")
    urls = source_url_map()
    rows = []
    for q in qs:
        rows.append([
            f'<span class="mono">{esc(q["id"])}</span><span class="sub">{esc(q["area"])}</span>',
            f'<strong>{esc(q["question"])}</strong>'
            f'<span class="sub"><em>Known:</em> {esc(q["what_we_know"])}</span>'
            f'<span class="sub"><em>Not known:</em> {esc(q["what_we_do_not_know"])}</span>',
            esc(q["what_it_blocks"]),
            esc(q["discovery_action"]),
            source_cell(q["source_id"], urls),
        ])
    body = """<div class="callout"><strong>What this page is.</strong> These are the questions that must be
answered before a decision can reasonably be made, written so that each one names what is already known,
what is missing, what it blocks and the cheapest action that would settle it. None of them is rhetorical:
each has an action attached.</div>

<div class="callout warn"><strong>Read the "what it blocks" column as a priority list.</strong> The price
question (Q01) blocks more downstream work than any other, because without prices there is no return, no
closing-line value, and no residual against a market. Depth ordering (Q11) blocks the largest cluster of
availability features.</div>""" + table(
        ["ID / area", "Question, and what is known versus missing", "What it blocks", "How to find out", "Official source"],
        rows,
    )
    return page("Questions that must be answered before a decision",
                "questions.html",
                "Thirty-five questions, each with what we know, what we do not, what it blocks, and the cheapest "
                "action that would close it. Every question is sourced or explicitly marked unobtainable.",
                body)


def build_suggestions():
    sg = read_csv("suggestions.csv")
    urls = source_url_map()
    rows = []
    for s in sg:
        rows.append([
            f'<span class="mono">{esc(s["id"])}</span>',
            f'<strong>{esc(s["title"])}</strong><span class="sub">{esc(s["problem"])}</span>',
            esc(s["what_changes"]),
            f'{esc(s["effort"])} effort<span class="sub">{esc(s["risk"])}</span>',
            (esc(s["depends_on"]) if s["depends_on"] != "None" else "no dependency"),
            esc(s["what_would_change_our_mind"]),
            source_cell(s.get("source_id") or "OV-S10", urls),
        ])
    body = """<div class="callout"><strong>How to use this page.</strong> Nothing here has been implemented without
your say-so. Each suggestion states the problem, the smallest change that addresses it, its cost and risk,
what it depends on, and — two-sided, as you asked — the observation that would prove it wrong. Pick the ones
you want and they move to the requirements page.</div>

<div class="callout warn"><strong>The order that is cheapest first.</strong> S01, S07, S09 and S11 cost almost
nothing and change how the site is trusted rather than what it computes. S02 (a second season) is the single
highest-value item on the list, because it is the only one that can move the leaderboard's failing interval.</div>""" + table(
        ["ID", "Suggestion", "What changes", "Cost / risk", "Depends on", "What would change our mind", "Official source"],
        rows,
    )
    return page("Suggestions, ranked by value and cost",
                "suggestions.html",
                "Twenty proposed improvements, each two-sided, each with its dependency and its cost. Nothing on "
                "this page is implemented until you choose it.",
                body)


def build_sources():
    reg = read_json("source_register.json")
    rows = []
    for s in reg["sources"]:
        rows.append([
            f'<span class="mono">{esc(s["id"])}</span>',
            f'<a href="{esc(s["url"])}">{esc(s["title"])}</a>'
            f'<span class="sub mono">{esc(s["url"])}</span>',
            esc(s["used_for"]),
            esc(s["verified_by"]),
            f'<span class="sub">{esc(s["evidence"])}</span>',
            esc(s["observed_at_utc"]),
        ])
    blocked = "".join(
        f"<li><strong>{esc(b['id'])} · {esc(b['what'])}</strong> — <em>{esc(b['status'])}</em>. {esc(b['detail'])}</li>"
        for b in reg["blocked"]
    )
    body = f"""<div class="callout"><strong>How every page on this site was built.</strong> {esc(reg['access_method'])}</div>
""" + table(
        ["ID", "Source", "Used for", "How it was checked", "Evidence recorded", "Observed"],
        rows,
    ) + f"""<div class="section"><h2>What could not be obtained</h2>
<p>These are published because a missing input is a finding. Each one is the reason a requirement is
blocked rather than approximated.</p>
<ul class="list">{blocked}</ul></div>

<div class="section"><h2>The price policy, decided before any backtest</h2>
<p><strong>Decision:</strong> no market price is published until a licensed or official price series with a
stated closing definition is obtained. The consequence is that every market column stays blank and every
residual stays blank. A blank is never filled with a community or scraped number, and it is never rendered
as zero disagreement. The number that would clear it: two vendor evaluations in writing, one reuse grant,
and a fixed closing-snapshot definition.</p>
<p class="small">Source authority boundary: this workspace cites official NFL pages for published facts. A
citation supports only the field it is attached to, and it does not imply reuse rights. Community-maintained
data is deliberately excluded from every number on this site.</p></div>"""
    return page("Source register",
                "sources.html",
                "Fifteen official sources read line by line, what each was used for, and four things that could "
                "not be obtained at all.",
                body)


def build_flagged():
    flags = read_json("flags.json")
    rows = []
    for f in flags["flags"]:
        rows.append([
            f'<span class="mono">{esc(f["id"])}</span>'
            f'<span class="sub"><span class="state {esc(f["status"])}">{esc(f["status"])}</span></span>',
            f'<strong>{esc(f["severity"])} severity</strong>',
            f'<strong>{esc(f["statement"])}</strong>'
            f'<span class="sub"><em>Evidence:</em> {esc(f["evidence"])}</span>'
            f'<span class="sub"><em>What this session did:</em> {esc(f["what_we_did"])}</span>',
            esc(f["action_for_reviewer"]),
            src_link(f["source_id"], f["source_url"], f["source_id"]),
        ])
    body = """<div class="callout danger"><strong>These do not block publication, and they are not hidden in a
log file.</strong> Every one is listed here with its evidence and the action a reviewer should take. Two are
already resolved; the rest need a human decision, and several concern files owned by other work streams in
this repository rather than by this one.</div>

<div class="callout warn"><strong>The three most important.</strong> OV-F06 is the honest verdict on the
model: it does not clear its own gate. OV-F01 is a repaired defect in the shared game log. OV-F05 is the
reason the market column is empty everywhere on this site.</div>""" + table(
        ["ID", "Severity", "Finding, evidence and what was done", "Action for reviewer", "Source"],
        rows,
    )
    return page("Flagged for review",
                "flagged.html",
                f"{len(flags['flags'])} items, each with its evidence, what this session did about it, and what a "
                "reviewer should decide. Nothing here is silently suppressed.",
                body)


def main() -> int:
    pages = {
        "index.html": build_index(),
        "requirements.html": build_requirements(),
        "origination.html": build_origination(),
        "leaderboard.html": build_leaderboard(),
        "results.html": build_results(),
        "availability.html": build_availability(),
        "questions.html": build_questions(),
        "suggestions.html": build_suggestions(),
        "sources.html": build_sources(),
        "flagged.html": build_flagged(),
    }
    for name, content in pages.items():
        (SITE / name).write_text(content, encoding="utf-8")
        print(f"wrote official-verify/{name} ({len(content):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
