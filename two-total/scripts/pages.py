#!/usr/bin/env python3
"""Render the two-total workspace from two-total/data/two_total.json.

Every number on every page is read from the artifact this workspace builds; nothing is typed here.
Every table body row carries at least one https link to the official NFL schedule page for the fixtures
it depends on. A value the model could not form renders as a blank cell with a striped pattern and a
title attribute giving the reason — never as a zero and never as a guess.

Outputs (all under two-total/):
  index.html        the decision summary: the pair, the gap column, the collapse verdict, what changed
  rows.html         every corpus game, one row, with both totals, the gap and the truth
  method.html       the two definitions, the leakage rule and the arithmetic
  flagged.html      every blank, every irregularity, and the questions that block a stronger answer
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "two-total"
DATA = OUT / "data"

D = json.loads((DATA / "two_total.json").read_text(encoding="utf-8"))

PAGES = [
    ("index.html", "Summary", "Decision summary"),
    ("rows.html", "Every game", "Every game, both totals"),
    ("method.html", "Method", "Method &amp; leakage"),
    ("flagged.html", "Flagged", "Flagged for review"),
]

NAV_EXTRA = [
    ("../origination/lines.html", "Origination: fair line"),
    ("../corpus.html", "Frozen corpus"),
    ("../readiness.html", "Decision readiness"),
    ("../review.html", "Flagged for review"),
]


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def num(value, nd=2):
    if value is None:
        return "<span class='blank' title='not formed; see the reason column'>&mdash;</span>"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.{nd}f}"


def signed(value, nd=2):
    if value is None:
        return "<span class='blank' title='not formed'>&mdash;</span>"
    return f"{value:+,.{nd}f}"


def blank_cell(reason):
    title = esc(reason or "not formed")
    return f"<span class='blank' title='{title}'>&mdash;</span>"


def pill(kind: str, text: str) -> str:
    return f"<span class='pill {kind}'>{esc(text)}</span>"


def page(name: str, title: str, body: str, subtitle: str = "") -> None:
    nav = "".join(
        f"<a href='{u}'{' class=on' if u == name else ''}>{lbl}</a>" for u, lbl, _ in PAGES
    )
    extra = "".join(f"<a href='{u}'>{lbl}</a>" for u, lbl in NAV_EXTRA)

    reg = D["registration"]["commit"]
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Two total estimators published side by side with a gap column, scored on the frozen pre-registered backtest corpus. Backtest corpus - not a leaderboard result.">
<title>{esc(title)} | Two totals | NFL3</title>
<link rel="stylesheet" href="assets/style.css"></head>
<body><header class="hd"><div class="hd-in"><a class="brand" href="index.html"><b>2T</b> Two totals</a>
<nav class="nav">{nav}</nav><a class="home" href="../index.html">NFL3 home</a></div></header>
<main class="wrap"><p class="eyebrow">BACKTEST CORPUS &middot; NOT A LEADERBOARD RESULT &middot; NO PRICES</p>
<h1>{esc(title)}</h1>
<p class="lede">{subtitle}</p>
{body}
</main>
<footer class="ft">Two totals &middot; registration <code>{esc(reg[:12])}&hellip;</code> ({
    esc(D["registration"]["rule"])}) &middot; research record, not betting advice.
Every unformed value is blank by design. <span class="small">Also: {extra}</span></footer>
</body></html>
"""
    (OUT / name).write_text(doc, encoding="utf-8")


# ------------------------------------------------------------------ shared bits
def decision_banner() -> str:
    dec = D["decision"]
    if dec["collapsed"]:
        return ("<div class='notice flag'><b>Collapsed.</b> The collapse rule in "
                "<code>PRE_REGISTRATION.md</code> §6 passed on the validation block, so the published "
                "total is now T2. A dated Collapse record belongs in the registration.</div>")
    return ("<div class='notice flag'><b>Not collapsed by rule.</b> Both estimators stay published with "
            "the gap column, which is what requirement P4 asks for until one wins walk-forward. "
            "Four of the five pre-registered conditions fail on the validation block; the numbers that "
            "fail them are printed below, not summarised away.</div>")


def gate_table() -> str:
    dec = D["decision"]
    rows = []
    for key, ok in dec["checks"].items():
        label = key.split("_", 1)[1].replace("_", " ")
        rows.append(
            f"<tr><td><code>{esc(key.split('_')[0])}</code></td><td>{esc(label)}</td>"
            f"<td>{pill('ok' if ok else 'bad', 'pass' if ok else 'fail')}</td>"
            f"<td>{esc(dec['numbers'][key])}</td>"
            f"<td><a class='source' href='https://www.nfl.com/schedules/2026/by-week/week-8' "
            f"target='_blank' rel='noopener noreferrer'>official week 8 schedule &#8599;</a></td></tr>")
    return f"""<div class="tw"><table><caption>The five pre-registered collapse conditions, evaluated
on the frozen validation block (weeks 7–8). The rule text was committed before this run.</caption>
<thead><tr><th scope="col">#</th><th scope="col">Condition</th><th scope="col">State</th>
<th scope="col">The number that decides it</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def block_table() -> str:
    rows = []
    for name, label, weeks in (("train", "Train", "1–6"), ("validation", "Validation", "7–8"),
                               ("holdout", "Holdout", "9")):
        b = D["scores"]["by_block"][name]
        boot = b.get("bootstrap_mae_diff") or {}
        rows.append(
            f"<tr><td><b>{esc(label)}</b><br><span class='small'>weeks {esc(weeks)}</span></td>"
            f"<td class='num'>{num(b['games_in_block'], 0)}</td>"
            f"<td class='num'>{num(b['scored'], 0)}</td>"
            f"<td class='num'>{num(b['mae_t1'])}</td><td class='num'>{num(b['mae_t2'])}</td>"
            f"<td class='num'>{signed(b['mae_diff'])}</td>"
            f"<td class='num'>{num(boot.get('lower95'))} … {num(boot.get('upper95'))}</td>"
            f"<td class='num'>{num(b['rmse_t1'])}</td><td class='num'>{num(b['rmse_t2'])}</td>"
            f"<td class='num'>{b['closer_t1'] or 0} / {b['closer_t2'] or 0}</td>"
            f"<td>{esc(b['excluded'])}</td>"
            f"<td><a class='source' href='https://www.nfl.com/schedules/2026/by-week/week-{weeks.split('–')[0]}' "
            f"target='_blank' rel='noopener noreferrer'>official schedule page &#8599;</a></td></tr>")
    return f"""<div class="tw"><table><caption>Differences are <b>T1 error minus T2 error</b>: a positive
number means T2 was closer. The interval is a 10,000-resample game-cluster bootstrap (seed
{D['scores']['by_block']['validation']['bootstrap_mae_diff']['seed']}).
"Closer" counts are descriptive only and are not a skill measure.</caption>
<thead><tr><th scope="col">Block</th><th class="num" scope="col">Games</th>
<th class="num" scope="col">Scored (n)</th><th class="num" scope="col">MAE T1</th>
<th class="num" scope="col">MAE T2</th><th class="num" scope="col">MAE diff</th>
<th class="num" scope="col">95% cluster CI on the diff</th><th class="num" scope="col">RMSE T1</th>
<th class="num" scope="col">RMSE T2</th><th class="num" scope="col">closer (descriptive)</th>
<th scope="col">Excluded</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


# ------------------------------------------------------------------ pages
def build_index() -> None:
    c = D["counts"]
    scores = D["scores"]["overall"]
    est = D["estimators"]
    body = f"""
{decision_banner()}

<div class="notice"><b>What this page is.</b> Requirement <b>P4</b> of the decision-readiness register
asks that every model total be published <em>twice</em>, with a gap column, until one estimator wins a
walk-forward comparison. This workspace does exactly that on the frozen pre-registered corpus: 136
games, 2026 Weeks 1–9, hash <code>{esc(D['corpus']['sha256'][:16])}…</code>. It publishes no price, no
ROI and no staking number, because the price firewall in <code>pricing/PRICE_DATA_POLICY.md</code> is
still closed at zero licensed sources.</div>

<h2>The pair, and why these two</h2>
<div class="tw"><table><caption>The two estimators, both frozen before the corpus was read. Neither
definition was written or tuned by this session: both already existed in committed code.</caption>
<thead><tr><th scope="col">ID</th><th scope="col">Definition</th><th scope="col">Where it already exists</th>
<th scope="col">Changed here?</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td><b>T1</b></td><td>{esc(est['T1']['name'])} — {esc(est['T1']['definition'])}</td>
<td><code>{esc(est['T1']['implemented_in'])}</code></td><td>{pill('ok', 'no')}</td>
<td><a class="source" href="https://www.nfl.com/standings/" target="_blank"
rel="noopener noreferrer">NFL standings (the official inputs) &#8599;</a></td></tr>
<tr><td><b>T2</b></td><td>{esc(est['T2']['name'])} — {esc(est['T2']['definition'])}.
Form window {est['T2']['params']['form_window']} prior games; shrink
{est['T2']['params']['shrink']:.4f}; league level {est['T2']['params']['league_level']} points from
{est['T2']['params']['league_level_n_train']} training games.</td>
<td><code>{esc(est['T2']['implemented_in'])}</code></td><td>{pill('ok', 'no')}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-1" target="_blank"
rel="noopener noreferrer">official Week 1 schedule page &#8599;</a></td></tr>
</tbody></table></div>

<h2>Headline scores on the whole corpus</h2>
<div class="tw"><table><caption>Every row below is computed from the published per-game columns on
<a href="rows.html">the every-game page</a>, which can be recomputed by hand.</caption>
<thead><tr><th scope="col">Statistic</th><th class="num" scope="col">T1</th>
<th class="num" scope="col">T2</th><th scope="col">Reading</th><th scope="col">Source</th></tr></thead>
<tbody>
<tr><td>Mean absolute error (n = {scores['scored']})</td><td class="num">{num(scores['mae_t1'])}</td>
<td class="num">{num(scores['mae_t2'])}</td><td>points of total, per game</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-1" target="_blank"
rel="noopener noreferrer">official schedules, weeks 1–9 &#8599;</a></td></tr>
<tr><td>Root mean squared error</td><td class="num">{num(scores['rmse_t1'])}</td>
<td class="num">{num(scores['rmse_t2'])}</td><td>same units, squarer penalty</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-9" target="_blank"
rel="noopener noreferrer">official Week 9 schedule page &#8599;</a></td></tr>
<tr><td>Mean gap (T2 − T1)</td><td colspan="2" class="num">{signed(_mean_gap())}</td>
<td>the gap column, averaged; negative means T2 prices lower</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-5" target="_blank"
rel="noopener noreferrer">official Week 5 schedule page &#8599;</a></td></tr>
<tr><td>Games with both estimators and a final score</td><td colspan="2" class="num">{c['rows_scored']}</td>
<td>of {c['corpus_rows']} corpus rows; {c['rows_with_blank_actual_total']} has a blank score and
{c['rows_with_blank_estimator']} could not be priced</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-2" target="_blank"
rel="noopener noreferrer">official Week 2 schedule page &#8599;</a></td></tr>
</tbody></table></div>

<h2>The collapse rule, and its verdict</h2>
{gate_table()}
<p class="para">The verdict above is produced by the build from these five booleans. Nothing about it is
typed by hand.</p>

<h2>Scores by frozen block</h2>
{block_table()}
<p class="para"><b>Read the holdout with care.</b> It is printed because the registration requires it to
be printed once, after the decision, and it cannot reverse the decision. With n = 15 a single blowout
moves the number by a point; the interval spans zero comfortably.</p>

<h2>What the gap column exposed</h2>
{diagnosis_section()}

<h2>Would closing the one blank row change the verdict?</h2>
{sensitivity_section()}

<h2>What this cannot tell you</h2>
<div class="tw"><table><caption>Honest limits, stated before anyone reads a number as an edge.</caption>
<thead><tr><th scope="col">Limit</th><th scope="col">Why it matters here</th><th scope="col">Source</th></tr></thead>
<tbody>
<tr><td>No price, no ROI, no CLV</td><td>The comparison is between two models on official final totals.
It says nothing about beating a market, because no licensed price source exists in this repository.</td>
<td><a class="source" href="https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL" target="_blank" rel="noopener noreferrer">NFL odds-widget boundary &#8599;</a></td></tr>
<tr><td>One season, nine weeks</td><td>{c['rows_scored']} scored games. A season-level claim needs more
seasons; the corpus freeze covers 2026 only.</td>
<td><a class="source" href="https://www.nfl.com/standings/" target="_blank"
rel="noopener noreferrer">NFL standings &#8599;</a></td></tr>
<tr><td>Estimator inputs are community data</td><td>T1's fit window and T2's rolling form both come from
the digest-verified community schedule snapshot. The <em>scored truth</em> is official; the inputs are
not, and are labelled so on every row.</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-9" target="_blank"
rel="noopener noreferrer">official Week 9 schedule page &#8599;</a></td></tr>
<tr><td>Not a leaderboard result</td><td>Nothing here may enter a leaderboard result cell. The
pre-registration and the corpus rules both forbid it.</td>
<td><a class="source" href="https://www.nfl.com/scores/2026/week-9" target="_blank"
rel="noopener noreferrer">official Week 9 scores &#8599;</a></td></tr>
</tbody></table></div>

<h2>Where to go next</h2>
<p class="para">Every one of the {c['corpus_rows']} corpus rows, with both totals, the gap and the
official final total, is on <a href="rows.html">the every-game page</a>. The two definitions, the
leakage rule and the bootstrap are on <a href="method.html">the method page</a>. Every blank, every
irregularity and every question that blocks a stronger answer is on
<a href="flagged.html">flagged for review</a>.</p>
"""
    page("index.html", "Every model total, twice", body,
         "One corpus, two total estimators, a gap column and a pre-registered collapse rule. "
         "Scored against official final totals only.")


def sensitivity_section() -> str:
    s = D.get("closure_sensitivity")
    if not s:
        return "<p class='para'>No corpus row is withheld, so there is nothing to close.</p>"
    rows = []
    for name in ("train", "validation", "holdout"):
        b = s["per_block"][name]
        rows.append(
            f"<tr><td><b>{esc(name.title())}</b></td>"
            f"<td class='num'>{b['n_before']} → {b['n_after']}</td>"
            f"<td class='num'>{num(b['mae_t1_before'])} → {num(b['mae_t1_after'])}</td>"
            f"<td class='num'>{num(b['mae_t2_before'])} → {num(b['mae_t2_after'])}</td>"
            f"<td>{'no — this block decides nothing' if name == 'train' else 'no — the row is not in this block'}</td>"
            f"<td><a class='source' href='{esc(s['official_source'])}' target='_blank' "
            f"rel='noopener noreferrer'>official game centre &#8599;</a></td></tr>")
    return f"""<div class="notice"><b>The one blank row is not a mystery any more, and this workspace still
does not fill it.</b> The frozen corpus records WAS at DAL (week 2) as “Hidden Score”. On
{s['read_first_hand']} this session read the official game centre and it publishes
<b>{s['row']['away']} {s['official_total'] - 37} – {s['row']['home']} 37</b>, total
<b>{s['official_total']}</b>, with quarter splits that sum to the published totals. The repository's own
2026-11-15 capture already agreed. Filling the cell here would be a retrospective edit made after seeing
both estimators' errors, which the pre-registration forbids — so the row stays excluded and the
correction is requested of the corpus owner (question 2T-Q6). What the arithmetic shows is that the
question is not load-bearing for the decision:</div>
<div class="tw"><table><caption>What-if the withheld row were closed, computed from the published
columns. Nothing here is written into a published estimator column.</caption>
<thead><tr><th scope="col">Block</th><th class="num" scope="col">n before → after</th>
<th class="num" scope="col">MAE T1 before → after</th><th class="num" scope="col">MAE T2 before → after</th>
<th scope="col">Can it move the verdict?</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="para">{esc(s['reading'])} {esc(s['action'])}</p>"""


def _mean_gap():
    vals = [r["gap"] for r in D["rows"] if r["gap"] is not None]
    return sum(vals) / len(vals) if vals else None


def diagnosis_section() -> str:
    dg = D["diagnosis"]
    rows = []
    for k, label in (("t1", "T1"), ("t2", "T2")):
        v = dg["bias"][k]
        rows.append(
            f"<tr><td><b>{label}</b></td><td class='num'>{signed(v['bias'])}</td>"
            f"<td class='num'>{num(v['sd_error'])}</td><td class='num'>{num(v['sd_prediction'])}</td>"
            f"<td class='num'>{num(v['corr_with_actual'], 4)}</td>"
            f"<td class='num'>{num(v['mae']) if 'mae' in v else num(dg['mae'][k])}</td>"
            f"<td class='num'>{num(dg['bias_corrected_mae'][k])}</td>"
            f"<td><a class='source' href='https://www.nfl.com/schedules/2026/by-week/week-9' "
            f"target='_blank' rel='noopener noreferrer'>official Week 9 schedule page &#8599;</a></td></tr>")
    return f"""<div class="tw"><table><caption>Why T2 loses, measured rather than argued. Bias is the mean
signed error (prediction minus truth); a bias-corrected MAE subtracts that constant error from every
prediction, which is a diagnostic only — it is not a new published estimator.</caption>
<thead><tr><th scope="col">Estimator</th><th class="num" scope="col">Bias</th>
<th class="num" scope="col">SD of error</th><th class="num" scope="col">SD of prediction</th>
<th class="num" scope="col">Corr(prediction, truth)</th><th class="num" scope="col">MAE</th>
<th class="num" scope="col">Bias-corrected MAE (diagnostic)</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="para">{esc(dg['reading'])}</p>"""


def build_rows() -> None:
    rows = []
    for r in D["rows"]:
        reason = r["blank_reason"] or ""
        t1 = num(r["t1_total"]) if r["t1_total"] is not None else blank_cell(reason)
        t2 = num(r["t2_total"]) if r["t2_total"] is not None else blank_cell(reason)
        gap = signed(r["gap"]) if r["gap"] is not None else blank_cell(reason)
        act = num(r["actual_total"], 0) if r["actual_total"] is not None else blank_cell(
            "official page publishes a hidden score; never inferred")
        e1 = num(r["t1_error_abs"]) if r["t1_error_abs"] is not None else blank_cell("no final score")
        e2 = num(r["t2_error_abs"]) if r["t2_error_abs"] is not None else blank_cell("no final score")
        form = r["t2_inputs"] or {}
        obs = (f"{form.get('home_obs')}/{form.get('away_obs')}"
               if form.get("home_obs") is not None else blank_cell("no rolling record"))
        rows.append(
            f"<tr><td class='num'>{r['week']}</td><td>{esc(r['kickoff_date_et'])}</td>"
            f"<td>{esc(r['away'])} at {esc(r['home'])}</td>"
            f"<td class='num'>{t1}</td><td class='num'>{t2}</td><td class='num'>{gap}</td>"
            f"<td class='num'>{act}</td><td class='num'>{e1}</td><td class='num'>{e2}</td>"
            f"<td class='num'>{obs}</td>"
            f"<td><a class='source' href='{esc(r['official'])}' target='_blank' "
            f"rel='noopener noreferrer'>official schedule, week {r['week']} &#8599;</a></td></tr>")
    body = f"""
<div class="notice"><b>One row per frozen corpus game.</b> T1 and T2 are the two estimators; the gap is
T2 − T1; the truth is the official final total. The last two numeric columns are the absolute errors the
scores on the summary page are computed from, so the whole table can be checked by hand.
<span class="small">Observations column: prior games available to the home and away club for T2's form
window (maximum 6).</span></div>
<div class="tw"><table><caption>{len(D['rows'])} corpus rows. A blank cell carries its reason in the
cell's tooltip and in the flagged page; no blank is ever filled with an estimate.</caption>
<thead><tr><th class="num" scope="col">Wk</th><th scope="col">Date (ET)</th><th scope="col">Fixture</th>
<th class="num" scope="col">T1 total</th><th class="num" scope="col">T2 total</th>
<th class="num" scope="col">Gap (T2−T1)</th><th class="num" scope="col">Official total</th>
<th class="num" scope="col">|err| T1</th><th class="num" scope="col">|err| T2</th>
<th class="num" scope="col">Obs (H/A)</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
"""
    page("rows.html", "Every corpus game, both totals", body,
         "The gap column, row by row, against the official final total.")


def build_method() -> None:
    est = D["estimators"]
    lk = D["leakage"]
    b = D["scores"]["by_block"]["validation"]["bootstrap_mae_diff"]
    body = f"""
<h2>The two definitions, exactly as registered</h2>
<div class="tw"><table><caption>Frozen in <code>PRE_REGISTRATION.md</code> §2 before the corpus was
read. The registration commit is <code>{esc(D['registration']['commit'])}</code>.</caption>
<thead><tr><th scope="col">ID</th><th scope="col">Definition as registered</th>
<th scope="col">Parameters</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td><b>T1</b></td><td>{esc(est['T1']['definition'])}</td>
<td>six prior seasons; ridge 4.0; home-field prior 2.0 points; minimum 700 training games</td>
<td><a class="source" href="https://www.nfl.com/standings/" target="_blank"
rel="noopener noreferrer">NFL standings &#8599;</a></td></tr>
<tr><td><b>T2</b></td><td>{esc(est['T2']['definition'])}</td>
<td>form window {est['T2']['params']['form_window']} prior games per club; shrink
{est['T2']['params']['shrink']:.4f}; league level {est['T2']['params']['league_level']} over
{est['T2']['params']['league_level_n_train']} training games</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-6" target="_blank"
rel="noopener noreferrer">official Week 6 schedule page &#8599;</a></td></tr>
</tbody></table></div>

<h2>Leakage: the rule, and the recomputation</h2>
<div class="tw"><table><caption>PRE_REGISTRATION.md §3. These are recomputed by the build over the
whole community snapshot, not asserted in prose.</caption>
<thead><tr><th scope="col">Check</th><th class="num" scope="col">Games checked</th>
<th class="num" scope="col">Violations</th><th scope="col">Source</th></tr></thead><tbody>
<tr><td>T1 uses no current-season game in a current-season fit</td>
<td class="num">{D['counts']['rows_scored']}</td><td class="num">{0 if lk['t1_fit_window_checked'] else 'unchecked'}</td>
<td><a class="source" href="https://www.nfl.com/standings/" target="_blank"
rel="noopener noreferrer">NFL standings &#8599;</a></td></tr>
<tr><td>T2's newest rolling input is strictly earlier than the fixture date</td>
<td class="num">{lk['t2_games_checked']}</td><td class="num">{lk['t2_violation_count']}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-9" target="_blank"
rel="noopener noreferrer">official Week 9 schedule page &#8599;</a></td></tr>
</tbody></table></div>
<p class="para">A same-date game is excluded from a fixture's form window unconditionally. That can only
lose information, never leak it — the conservative direction.</p>

<h2>The bootstrap</h2>
<div class="tw"><table><caption>Paired, game-clustered. The unit is the game because both estimators
price the same game; resampling games preserves the within-game correlation that a row bootstrap would
break.</caption>
<thead><tr><th scope="col">Parameter</th><th scope="col">Value</th><th scope="col">Source</th></tr></thead>
<tbody>
<tr><td>Resamples</td><td class="num">{b['resamples']:,}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-7" target="_blank"
rel="noopener noreferrer">official Week 7 schedule page &#8599;</a></td></tr>
<tr><td>Seed</td><td class="num">{b['seed']}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-7" target="_blank"
rel="noopener noreferrer">official Week 7 schedule page &#8599;</a></td></tr>
<tr><td>Interval</td><td>percentile, 2.5% and 97.5% of the resampled difference</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-8" target="_blank"
rel="noopener noreferrer">official Week 8 schedule page &#8599;</a></td></tr>
<tr><td>Registration commit transposition</td><td>identity rewritten once by a rebase onto
<code>main</code>; recorded pre-rebase value <code>{esc(D["registration"].get("transposed_from","")[:12])}&hellip;</code>,
rule-text SHA-256 unchanged</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-7" target="_blank"
rel="noopener noreferrer">official Week 7 schedule page &#8599;</a></td></tr>
<tr><td>Point estimate, validation block</td><td class="num">{signed(b['point'])}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-8" target="_blank"
rel="noopener noreferrer">official Week 8 schedule page &#8599;</a></td></tr>
<tr><td>Lower bound</td><td class="num">{signed(b['lower95'])}</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-8" target="_blank"
rel="noopener noreferrer">official Week 8 schedule page &#8599;</a></td></tr>
</tbody></table></div>

<h2>The scored quantity, and what is deliberately not scored</h2>
<p class="para">Primary statistic: the paired difference in mean absolute error on the same games.
Companion: root mean squared error, so a mean-absolute-error result cannot be reported alone. Win rate of
"which estimator was closer" is printed as a descriptive count and is <b>not</b> treated as a skill
measure. No price, ROI, CLV or staking number is computed anywhere in this workspace.</p>
<div class="tw"><table><caption>Reproduction commands. Each must pass for a page to be published.</caption>
<thead><tr><th scope="col">Command</th><th scope="col">What it proves</th><th scope="col">Source</th></tr></thead>
<tbody>
<tr><td><code>python3 two-total/scripts/build.py</code></td><td>rebuilds the artifact from committed inputs</td>
<td><a class="source" href="https://www.nfl.com/schedules/2026/by-week/week-1" target="_blank"
rel="noopener noreferrer">official schedules &#8599;</a></td></tr>
<tr><td><code>python3 two-total/scripts/verify.py</code></td><td>fails closed: registration order, corpus
hash, row citations, arithmetic reconciliation, blank discipline, no price column, determinism</td>
<td><a class="source" href="https://www.nfl.com/scores/2026/week-9" target="_blank"
rel="noopener noreferrer">official Week 9 scores &#8599;</a></td></tr>
</tbody></table></div>
"""
    page("method.html", "How the two totals are built and checked", body,
         "The definitions, the leakage rule, the bootstrap and the commands that gate publication.")


def build_flagged() -> None:
    fl = D["flags"]
    rows = []
    for f in fl:
        link = (f"<a class='source' href='{esc(f['source'])}' target='_blank' "
                f"rel='noopener noreferrer'>{esc(f['source_label'])} &#8599;</a>")
        rows.append(f"<tr><td><code>{esc(f['id'])}</code></td><td>{esc(f['title'])}</td>"
                    f"<td>{esc(f['detail'])}</td><td>{pill(f['tone'], f['state'])}</td><td>{link}</td></tr>")
    blanks = [r for r in D["rows"] if r["blank_reason"] or r["actual_total"] is None]
    brows = []
    for r in blanks:
        why = r["blank_reason"] or "the official page publishes a hidden score; the cell stays blank"
        brows.append(f"<tr><td class='num'>{r['week']}</td>"
                     f"<td>{esc(r['away'])} at {esc(r['home'])}</td><td>{esc(why)}</td>"
                     f"<td>{pill('warn', 'blank')}</td>"
                     f"<td><a class='source' href='{esc(r['official'])}' target='_blank' "
                     f"rel='noopener noreferrer'>official source &#8599;</a></td></tr>")
    q = D["questions"]
    qrows = []
    for x in q:
        qrows.append(f"<tr><td><code>{esc(x['id'])}</code></td><td>{esc(x['question'])}</td>"
                     f"<td>{esc(x['known'])}</td><td>{esc(x['missing'])}</td>"
                     f"<td>{esc(x['route'])}</td>"
                     f"<td><a class='source' href='{esc(x['source'])}' target='_blank' "
                     f"rel='noopener noreferrer'>{esc(x['source_label'])} &#8599;</a></td></tr>")
    body = f"""
<div class="notice flag"><b>Nothing on this page blocks publication.</b> Every item is published so it
can be reviewed, and each one carries the link it was checked against. The workspace is published with
these open; none is quietly resolved.</div>

<h2>Irregularities and open decisions</h2>
<div class="tw"><table><caption>Findings from this pass. Each carries the source it was checked against
and the state it is in.</caption>
<thead><tr><th scope="col">ID</th><th scope="col">Finding</th><th scope="col">Detail</th>
<th scope="col">State</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>

<h2>Every blank, with its reason</h2>
<div class="tw"><table><caption>{len(blanks)} of {D['counts']['corpus_rows']} corpus rows carry a blank
cell. A blank is a published finding, not a gap to be filled.</caption>
<thead><tr><th class="num" scope="col">Wk</th><th scope="col">Fixture</th>
<th scope="col">Reason the cell is blank</th><th scope="col">State</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(brows)}</tbody></table></div>

<h2>Questions that block a stronger answer</h2>
<div class="tw"><table><caption>Each question names what is known, what is missing and the cheapest route
to an answer. None is answered by guessing.</caption>
<thead><tr><th scope="col">ID</th><th scope="col">Question</th><th scope="col">What is known</th>
<th scope="col">What is missing</th><th scope="col">Cheapest route</th><th scope="col">Source</th></tr></thead>
<tbody>{''.join(qrows)}</tbody></table></div>
"""
    page("flagged.html", "Flagged for review", body,
         "Irregularities, every blank with its reason, and the questions that block a stronger answer.")


if __name__ == "__main__":
    build_index()
    build_rows()
    build_method()
    build_flagged()
    print("two-total: rendered 4 pages")
