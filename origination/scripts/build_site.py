#!/usr/bin/env python3
"""Render the origination workspace from the committed artifacts.

Every number on every page is read from a JSON artifact this workspace builds; nothing is typed here.
Every table body row carries at least one link to an official or named source, and a value that could not
be confirmed renders as a blank with `unverified` rather than as a zero or a guess.
"""
from __future__ import annotations

import json

import common as C

OUT = C.OUT
DATA = C.DATA


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def f(value, nd=2, dash="—"):
    if value is None:
        return f"<span class='blank'>{dash}</span>"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{nd}f}"
    return C.esc(value)


def pct(value, nd=1, signed=False):
    if value is None:
        return "<span class='blank'>—</span>"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value * 100:.{nd}f}%"


def link(url, text, cls="source"):
    """Render a source link.

    A URL becomes an anchor. A repository path becomes a code reference, because linking to a file
    outside the published directory would be a broken link on the live site.
    """
    if not url:
        return C.esc(text)
    url = str(url)
    if url.startswith(("http://", "https://")):
        return (f"<a class='{cls}' href='{C.esc(url)}' target='_blank' rel='noopener noreferrer'>"
                f"{C.esc(text)} ↗</a>")
    return f"<code class='path'>{C.esc(url)}</code><small> (repository artifact, not a web page)</small>"


def badge(status):
    tone = {"pass": "ok", "fail": "danger", "blocked": "warn", "demoted": "danger",
            "published": "ok", "withheld": "warn", "unverified": "warn",
            "official": "ok", "community": "warn", "pre-kickoff": "ok", "post_hoc": "warn",
            "none": "danger", "partial": "warn"}.get(str(status).lower(), "warn")
    return f"<span class='pill {tone}'>{C.esc(status)}</span>"


BANNER = """
<div class="notice"><b>Read this first.</b> This workspace originates its own numbers and grades them
against a reconciled official results feed. It holds <b>one</b> community price observation, so no
opening-line edge, closing-line value or validated strategy exists yet — and the leaderboard says so on
every row. Prices are labelled <b>COMMUNITY</b>; standings and injury reports are labelled
<b>OFFICIAL</b>; anything that could not be confirmed is blank and sits on
<a href="flagged.html">Flagged for review</a>. Nothing here is betting advice.</div>
"""


def page_index(art):
    board, luck, gates, results = art["board"], art["luck"], art["gates"], art["results"]
    corr, avail, abl = art["corr"], art["avail"], art["ablation"]
    policies = art["ledger"]
    top = sorted(board["results"], key=lambda r: (r["summary"].get("bss") is None,
                                                  -(r["summary"].get("bss") or -9)))
    best = top[0] if top else None
    body = [BANNER]

    body.append(f"""
<div class="metrics">
  <div><span>PLAYED GAMES IN CORPUS</span><strong>{results['counts']['games_played']}</strong>
    <small>{len(results['counts']['weeks_covered'])} weeks · reconciled</small></div>
  <div><span>OFFICIAL RECONCILIATION</span><strong>{results['counts']['team_fields_matching']}/{results['counts']['team_fields_checked']}</strong>
    <small>club × field checks match</small></div>
  <div><span>PRICE SNAPSHOTS</span><strong>{policies['counts']['snapshots']}</strong>
    <small>{policies['counts']['with_pre_kickoff_opening']} pre-kickoff market cells</small></div>
  <div><span>STRATEGIES SCORED</span><strong>{len(board['results'])}</strong>
    <small>{len(gates['demoted'])} demoted by their own kill rule</small></div>
  <div><span>VALIDATED</span><strong>0</strong>
    <small>gates blocked: {', '.join(gates['blocking'])}</small></div>
  <div><span>CORRELATIONS WITH n</span><strong>{corr['counts']['published']}</strong>
    <small>{corr['counts']['withheld']} withheld with a reason</small></div>
</div>""")

    body.append("""
<div class="section-head"><div><div class="section-label">00 / THE SHORT VERSION</div>
<h2>What this workspace can and cannot say today</h2></div></div>
<div class="two">
<div class="card good"><h3>What is established</h3><ul>
<li>The results feed reproduces nfl.com's official standings for <b>all 32 clubs</b> on every field —
wins, losses, ties, points for, points against — over 137 played games.</li>
<li>The official depth pages describe <b>1,386 slots across 30 clubs</b>, and <b>149 rank-1 slots name
more than one player</b>. A single "starter" per slot would be a fabrication.</li>
<li>The injury report is captured with a hash and a clock time; every published availability row links
to it.</li>
<li>Every strategy is pre-registered with a content hash and scored with a proper score, an interval and
a control arm.</li>
</ul></div>
<div class="card bad"><h3>What is not</h3><ul>
<li><b>No price history.</b> One community observation exists. Weeks 1-9 kicked off before it, so their
numbers are post-hoc and cannot support a closing-line claim.</li>
<li><b>No validated strategy.</b> Every scored rule has a Brier-skill interval that includes zero or sits
below it. Two have already failed their own kill rule.</li>
<li><b>No measured injury effect.</b> The personnel ablation's holdout interval is
{lo} to {hi} points of MAE — it cannot distinguish an effect from noise.</li>
<li><b>No replacement certainty.</b> No official source names a replacement, so that column stays blank.</li>
</ul></div></div>""".replace("{lo}", f(abl["headline"]["holdout_lo"], 3))
       .replace("{hi}", f(abl["headline"]["holdout_hi"], 3)))

    body.append(f"""
<div class="section-head"><div><div class="section-label">01 / ORIGINATION ORDER</div>
<h2>Side first, then total, then moneyline</h2></div>
<p>Each market is originated separately, in that order, and each is graded on its own before the next is
trusted. The moneyline is a transform of the same margin model, so it is last by construction.</p></div>
<div class="table-wrap"><table><caption>Walk-forward origination (fit on prior seasons only). Market
comparison is shown wherever a stored price exists; the price class column says whether that number was
observed before kickoff.</caption>
<thead><tr><th>Market</th><th>Originated number</th><th>Market number</th><th>Difference</th>
<th>Error vs result (MAE)</th><th>Market error (MAE)</th><th>Price class</th><th>Source</th></tr></thead>
<tbody>""")
    wf = art["wf"]
    sd = wf["residual"]
    rows = wf["rows"]
    mae_m = C.mean([abs(r["model_margin"] - r["actual_margin"]) for r in rows])
    mae_mk = C.mean([abs(r["market_spread"] - r["actual_margin"]) for r in rows if r["market_spread"] is not None])
    mae_t = C.mean([abs(r["model_total"] - r["actual_total"]) for r in rows])
    mae_tk = C.mean([abs(r["market_total"] - r["actual_total"]) for r in rows if r["market_total"] is not None])
    body.append(f"""<tr><td><b>1 · Side</b><br><small>home margin</small></td>
<td>residual sd {f(sd['margin_sd'])} pts</td><td>stored spread</td>
<td>{f(C.mean([r['diff_spread'] for r in rows if r.get('diff_spread') is not None]))} pts mean</td>
<td>{f(mae_m)} pts</td><td>{f(mae_mk)} pts</td><td>{badge('post_hoc')} {badge('pre-kickoff')}</td>
<td>{link(C.G['schedules'], 'nflverse schedules')}<br>{link(C.S['standings'], 'NFL standings')}</td></tr>
<tr><td><b>2 · Total</b><br><small>combined points</small></td>
<td>residual sd {f(sd['total_sd'])} pts</td><td>stored total</td>
<td>{f(C.mean([r['diff_total'] for r in rows if r.get('diff_total') is not None]))} pts mean</td>
<td>{f(mae_t)} pts</td><td>{f(mae_tk)} pts</td><td>{badge('post_hoc')} {badge('pre-kickoff')}</td>
<td>{link(C.G['schedules'], 'nflverse schedules')}<br>{link(C.S['standings'], 'NFL standings')}</td></tr>
<tr><td><b>3 · Moneyline</b><br><small>home win probability</small></td>
<td>derived from the side model's residual sd</td><td>de-vigged stored moneyline</td>
<td>{f(art['elo']['residual']['margin_bias'], 2)} pt side bias carried in</td>
<td colspan="2">graded as a probability (Brier), not a point error</td>
<td>{badge('community')}</td><td>{link(C.G['schedules'], 'nflverse schedules')}</td></tr>
</tbody></table></div>
<div class="notice"><b>The model is worse than the market, and that is published.</b> On 137 games the
side model's mean absolute error is {f(mae_m)} points against the market's {f(mae_mk)}; the total model is
{f(mae_t)} against {f(mae_tk)}. A model that trails the number it is trying to beat is useful: it is a
working benchmark, and every strategy above it inherits the same handicap.</div>""")

    body.append(f"""
<div class="section-head"><div><div class="section-label">02 / LUCK</div>
<h2>Removing luck from the equation</h2></div>
<p>A win rate cannot separate skill from variance at this sample size. The panel below shows how much
sample a real edge needs, and what each scored strategy's interval actually covers.</p></div>
<div class="two">
<div class="card"><h3>Sample size needed (80% power, one-sided α=0.05)</h3>
<table><thead><tr><th>Edge over a coin</th><th>n needed</th><th>n held</th><th>Still needed</th></tr></thead><tbody>""")
    for row in luck["sample_size_table"]:
        body.append(f"""<tr><td>{pct(row['edge'], 0)}</td><td>{row['n_required_80pct']:,}</td>
<td>{row['n_available_now']}</td><td>{row['still_needed']:,}</td>
<td>{link(C.S['standings'], 'results')}</td></tr>""")
    body.append("""</tbody></table><p class="small">A 10% edge would need about 153 graded legs; a 2% edge
would need almost 4,000. This is why a 12-8 run is not evidence.</p></div>
<div class="card"><h3>What the leaderboard can distinguish</h3><ul>""")
    for row in luck["separations"][:5]:
        body.append(f"<li><b>{C.esc(row['id'])}</b> n={row['n']}, win rate "
                    f"{pct(row['win_rate'])} [{pct(row['wilson_lo'])}, {pct(row['wilson_hi'])}] — "
                    f"{C.esc(row['verdict'])}</li>")
    body.append(f"""</ul><p><a class="text-link" href="luck.html">Open the full removal-of-luck panel →</a></p></div>
</div>""")

    body.append(f"""
<div class="section-head"><div><div class="section-label">03 / AVAILABILITY</div>
<h2>Who was expected to start, and who actually played</h2></div>
<p>Depth is measured from playing time, never from jersey order. A slot is a group, not a person.</p></div>
<div class="metrics">
  <div><span>DEPTH SLOTS</span><strong>{avail['coverage']['depth_slots']:,}</strong><small>across {avail['coverage']['clubs_with_depth']} of 32 clubs</small></div>
  <div><span>RANK-1 SLOTS WITH ≥2 PLAYERS</span><strong>{avail['coverage']['slots_with_multiple_rank1']}</strong><small>a single starter would be invented</small></div>
  <div><span>REPORT ROWS WITH A GAME STATUS</span><strong>{avail['coverage']['games_on_report']}</strong><small>of {avail['coverage']['report_rows']} official rows</small></div>
  <div><span>RESERVE-LIST PLAYERS</span><strong>{avail['coverage']['reserve_players']}</strong><small>absent from the report by construction</small></div>
</div>
<div class="notice"><b>Snap-share leader vs published rank 1:</b> they agree in
{sum(1 for d in avail['depth_from_playing_time'] if d['leader_matches_rank1'])} of
{len(avail['depth_from_playing_time'])} position groups where both exist. Where they disagree, the
published order and the measured order are both shown; neither is declared right.
<a href="availability.html">Open the availability graph →</a></div>""")

    body.append(f"""
<div class="section-head"><div><div class="section-label">04 / WHAT WOULD CHANGE OUR MIND</div>
<h2>The gates that are blocking, and the number that would clear them</h2></div></div>
<div class="table-wrap"><table><caption>Gate status computed on this build. A blocked gate is not a
promise that the work is coming; it is a statement of what is missing.</caption>
<thead><tr><th>Gate</th><th>Question</th><th>Status</th><th>The number that decided it</th><th>Source</th></tr></thead>
<tbody>""")
    for g in gates["gates"]:
        body.append(f"""<tr><td><b>{g['id']}</b></td><td>{C.esc(g['question'])}</td><td>{badge(g['status'])}</td>
<td>{C.esc(g['number'])}<br><small>{C.esc(g['consequence'])}</small></td>
<td>{link(g['source'], 'source')}</td></tr>""")
    body.append("</tbody></table></div>")

    body.append("""
<div class="callout"><div><div class="section-label">NEXT</div><h2>What to read first</h2>
<p>Requirements first (what the brief asked for and what state each item is in), then the decisions the
gates are waiting on.</p></div>
<a class="button" href="requirements.html">Requirements →</a></div>""")
    return "\n".join(body), "Overview", "The origination workspace"


def page_requirements(art):
    reqs = art["requirements"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">TRACEABILITY</div>
<h2>One row per requirement, with the gate that blocks it and the number that would clear it</h2></div>
<p>{reqs['summary']['total']} requirements tracked: {reqs['summary']['implemented']} implemented,
{reqs['summary']['partial']} partial, {reqs['summary']['blocked']} blocked, {reqs['summary']['validated']} validated.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>State is computed from the artifacts in this
workspace, not asserted. A requirement is only 'implemented' when the artifact that satisfies it exists
and is reproducible on this build.</caption>
<thead><tr><th>ID</th><th>Requirement</th><th>State</th><th>What exists (evidence)</th>
<th>Gate that blocks it</th><th>The number that would clear it</th><th>Source</th></tr></thead><tbody>""")
    for r in reqs["rows"]:
        body.append(f"""<tr><td><b>{r['id']}</b></td><td>{C.esc(r['text'])}</td><td>{badge(r['state'])}</td>
<td>{C.esc(r['evidence'])}</td><td>{C.esc(r['gate'])}</td><td>{C.esc(r['number'])}</td>
<td>{link(r['source'], r['source_label'])}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="notice"><b>How to read 'blocked'.</b> A blocked requirement has a working
subset but cannot be called done: {', '.join(reqs['blocked_ids']) or 'none'}. Each one names the gate and
the measurable condition that would clear it, so a decision can be made against it rather than around it.</div>""")
    return "\n".join(body), "Requirements", "Decision readiness"


def page_decisions(art):
    qs = art["questions"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">THE QUESTIONS</div>
<h2>{len(qs['rows'])} questions that must be answered before a decision is reasonable</h2></div>
<p>Each question names what we know, what we do not know, how to find it out, and who or what it blocks.
An answer is only written when a source supplied it.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Questions grouped by the decision they block.
Discovery action is the cheapest way to close the gap, not a commitment.</caption>
<thead><tr><th>ID</th><th>Area</th><th>Question</th><th>What we know</th><th>What we do not know</th>
<th>Discovery action</th><th>Blocks</th><th>Source</th></tr></thead><tbody>""")
    for q in qs["rows"]:
        body.append(f"""<tr><td><b>{q['id']}</b></td><td>{C.esc(q['area'])}</td><td>{C.esc(q['question'])}</td>
<td>{C.esc(q['known'])}</td><td>{C.esc(q['unknown'])}</td><td>{C.esc(q['discovery'])}</td>
<td>{C.esc(q['blocks'])}</td><td>{link(q['source'], q['source_label'])}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="notice"><b>Why these questions and not others.</b> Every question below blocks
a number that is currently blank on this site. A question that blocks nothing is not on this page —
it is on the suggestions page, where it can be argued about without holding up a decision.</div>""")
    return "\n".join(body), "Decisions & questions", "What must be resolved first"


def page_strategies(art):
    board = art["board"]
    reg = art["registry"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">PRE-REGISTRATION</div>
<h2>Every strategy is frozen before it sees a result</h2></div>
<p>{len(reg['strategies'])} rules registered at version <code>{C.esc(reg['version'])}</code>. The hash is
a digest of the rule text, so an edit produces a different registration rather than a quiet change.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Two-sided 'what would change our mind' on every
row: the condition that would promote it and the condition that would kill it. A blocked row is not
scored anywhere.</caption>
<thead><tr><th>ID</th><th>Strategy</th><th>Family</th><th>Frozen rule</th><th>Registration</th>
<th>Promote if</th><th>Kill if</th><th>Status</th><th>Source</th></tr></thead><tbody>""")
    demoted = set(art["gates"]["demoted"])
    for s in reg["strategies"]:
        if s.get("gate_status") == "blocked":
            status = badge("blocked") + f"<br><small>{C.esc(s.get('blocked_by',''))}</small>"
        elif s["id"] in demoted:
            status = badge("demoted")
        else:
            status = badge("scored")
        body.append(f"""<tr><td><b>{s['id']}</b></td><td>{C.esc(s['name'])}</td>
<td>{C.esc(s['family'])}</td><td>{C.esc(s['rule'])}</td>
<td><code>{C.esc(s['registration'])}</code></td><td>{C.esc(s['promote'])}</td>
<td>{C.esc(s['kill'])}</td><td>{status}</td>
<td>{link(C.S['standings'] if s['market'] != 'prop-combo' else C.S['odds_faq'],
         'rules on file')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="notice"><b>Demotion is a feature, not a failure.</b> {len(demoted)} of the
scored rules have a Brier-skill interval entirely below zero and are labelled demoted. They keep their
numbers so the demotion can be checked. <a href="leaderboard.html">See the leaderboard →</a></div>""")
    return "\n".join(body), "Strategy registry", "Frozen rules and their kill conditions"


def page_leaderboard(art):
    board = art["board"]
    gates = art["gates"]
    luck = art["luck"]
    body = [BANNER]
    m = board["multiplicity"]
    body.append(f"""<div class="section-head"><div><div class="section-label">PROPER SCORES</div>
<h2>Ranked by benchmark-relative Brier skill, with an interval and a control on every row</h2></div>
<p>Benchmark: {C.esc(board['benchmark'])}. Multiplicity: {m['trials']} strategies, family-wise α=0.05,
so a per-test level of {m['alpha_per_test']:.5f}. <b>No row is validated</b>: promotion needs n ≥
{gates['floors']['promote_min_n']} and an interval above zero.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Brier skill score (BSS): positive means the
strategy beat the benchmark on the same rows. The interval is a paired game-cluster bootstrap. A control
arm's BSS is exactly zero by construction, which is what makes it a control.</caption>
<thead><tr><th>#</th><th>Strategy</th><th>Family</th><th>Market</th><th>n</th><th>Brier skill</th>
<th>95% interval</th><th>Win rate</th><th>Wilson 95%</th><th>Verdict</th><th>Source</th></tr></thead><tbody>""")
    ranked = sorted(board["results"], key=lambda r: (r["summary"].get("bss") is None,
                                                     -(r["summary"].get("bss") or -9)))
    verdict_by_id = {row["id"]: row["verdict"] for row in luck["separations"]}
    for i, r in enumerate(ranked, 1):
        s = r["summary"]
        lo, hi = s.get("lo"), s.get("hi")
        interval = f"[{f(lo)}, {f(hi)}]" if lo is not None else "—"
        wlo, whi = s.get("wilson", (None, None))
        body.append(f"""<tr><td>{i}</td><td><b>{C.esc(r['id'])}</b> {C.esc(r['name'])}</td>
<td>{C.esc(r['family'])}</td><td>{C.esc(r['market'])}</td><td>{s.get('n') or 0}</td>
<td>{f(s.get('bss'), 3)}</td><td>{interval}</td><td>{pct(s.get('accuracy'))}</td>
<td>[{pct(wlo)}, {pct(whi)}]</td><td>{badge(verdict_by_id.get(r['id'], 'unverified').split(':')[0])}
<br><small>{C.esc(verdict_by_id.get(r['id'], ''))}</small></td>
<td>{link(C.S['standings'], 'NFL standings')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="notice"><b>Why there is no 'ranking by ROI' anywhere on this page.</b>
Return over a season is a single draw from a very wide distribution. At {luck['corpus']['games_played']}
played games, an 11-9 record is unremarkable for a coin. Ranking on realised return would let one good
week outrank twenty weeks of calibrated work, which is the exact failure the brief asks us to prevent.
<a href="luck.html">See the arithmetic →</a></div>""")
    body.append("""<div class="section-head"><div><div class="section-label">BLOCKED</div>
<h2>What cannot be ranked, and why</h2></div></div>
<div class="table-wrap"><table><caption>A blocked strategy stays visible with its blocking condition. It
is not 'promising'; it has no evidence path yet.</caption>
<thead><tr><th>ID</th><th>Strategy</th><th>Family</th><th>Blocked by</th><th>Source</th></tr></thead><tbody>""")
    for s in board["blocked"]:
        body.append(f"""<tr><td><b>{C.esc(s['id'])}</b></td><td>{C.esc(s['name'])}</td>
<td>{C.esc(s['family'])}</td><td>{C.esc(s['blocked_by'])}</td>
<td>{link(C.S['odds_faq'], 'NFL betting FAQ')}</td></tr>""")
    body.append("</tbody></table></div>")
    return "\n".join(body), "Leaderboard", "Proper scores, controls and uncertainty"


def page_lines(art):
    wf, elo = art["wf"], art["elo"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">ORIGINATED LINES</div>
<h2>Our fair line, the market line, and the difference — as three separate columns</h2></div>
<p>Walk-forward: the model pricing a game was fitted on strictly earlier games. Parameters are
pre-registered and not tuned: {C.esc(str(wf['params']))}.</p></div>""")
    body.append(f"""<div class="notice"><b>Price class.</b> {wf['counts']['price_pre_kickoff']} of
{wf['counts']['games']} games have a price that was observed <b>before kickoff</b>; the rest are
<b>post-hoc</b> — recorded after the game had started, so they can be shown but never counted as an
opening or a closing line. Policy P02 in the price store makes this a hard rule.</div>""")
    body.append(f"""<div class="table-wrap"><table><caption>Every played game with a stored price. Model
spread is positive when the home side is favoured, matching the stored spread's sign convention.</caption>
<thead><tr><th>Wk</th><th>Matchup</th><th>Model spread</th><th>Market spread</th><th>Difference</th>
<th>Model total</th><th>Market total</th><th>Difference</th><th>Result</th><th>Price class</th>
<th>Source</th></tr></thead><tbody>""")
    for r in sorted(wf["rows"], key=lambda x: (x["week"], x["gameday"] or "", x["game_id"])):
        cls = r.get("price_class", "none")
        body.append(f"""<tr><td>{r['week']}</td>
<td>{C.esc(C.FULL_NAME.get(r['away'], r['away']))} @ {C.esc(C.FULL_NAME.get(r['home'], r['home']))}</td>
<td>{f(r['model_margin'], 1, '+')}</td><td>{f(r.get('market_spread'), 1, '') if r.get('market_spread') is not None else "<span class='blank'>unverified</span>"}</td>
<td>{f(r.get('diff_spread'), 1, '+') if r.get('diff_spread') is not None else "<span class='blank'>—</span>"}</td>
<td>{f(r['model_total'], 1)}</td>
<td>{f(r.get('market_total'), 1) if r.get('market_total') is not None else "<span class='blank'>unverified</span>"}</td>
<td>{f(r.get('diff_total'), 1, '+') if r.get('diff_total') is not None else "<span class='blank'>—</span>"}</td>
<td>{r['actual_away']}–{r['actual_home']}</td><td>{badge(cls)}</td>
<td>{link(C.S['standings'], 'official result')}<br>{link(C.G['schedules'], 'price')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="section-head"><div><div class="section-label">SECOND ESTIMATOR</div>
<h2>Elo, so a claimed signal can be checked against another model family</h2></div>
<p>Leak-free: each game is priced from ratings before that game was played. Parameters
pre-registered: {C.esc(str(elo['params']))}.</p></div>
<div class="table-wrap"><table><caption>Elo is published as an independent check, not as a better model.
A signal that appears in one estimator and not the other is not a signal.</caption>
<thead><tr><th>Matchup</th><th>Elo margin</th><th>Ridge margin</th><th>Market spread</th>
<th>Actual margin</th><th>Source</th></tr></thead><tbody>""")
    ridge = {r["game_id"]: r for r in wf["rows"]}
    for r in sorted(elo["rows"], key=lambda x: (x["week"], x["game_id"]))[:40]:
        base = ridge.get(r["game_id"], {})
        body.append(f"""<tr><td>{C.esc(C.FULL_NAME.get(r['away'], r['away']))} @ {C.esc(C.FULL_NAME.get(r['home'], r['home']))}</td>
<td>{f(r['model_margin'], 1, '+')}</td><td>{f(base.get('model_margin'), 1, '+')}</td>
<td>{f(base.get('market_spread'), 1, '') if base.get('market_spread') is not None else "<span class='blank'>—</span>"}</td>
<td>{r['actual_margin']:+d}</td><td>{link(C.S['standings'], 'official')}</td></tr>""")
    body.append("</tbody></table><p class='small'>First 40 rows shown; the full set is in "
                "<code>origination/data/origination_elo.json</code>.</p></div>")
    return "\n".join(body), "Originated lines", "Fair line, market line, difference"


def page_prices(art):
    ledger = art["ledger"]
    policy = (C.DATA / "prices" / "POLICY.md").read_text(encoding="utf-8")
    body = [BANNER]
    c = ledger["counts"]
    body.append(f"""<div class="section-head"><div><div class="section-label">PRICE STORE</div>
<h2>Opening and closing numbers for every market we originate — recorded, not estimated</h2></div>
<p>One immutable snapshot per observation, each with its own hash and the upstream release digest.
A market with no pre-kickoff observation keeps a blank opening and closing.</p></div>""")
    body.append(f"""<div class="metrics">
<div><span>SNAPSHOTS</span><strong>{c['snapshots']}</strong><small>immutable, hashed</small></div>
<div><span>EVENT × MARKET CELLS</span><strong>{c['market_cells']}</strong><small>272 events × 3 markets</small></div>
<div><span>WITH PRE-KICKOFF OPENING</span><strong>{c['with_pre_kickoff_opening']}</strong><small>the only usable cell set</small></div>
<div><span>POST-HOC ONLY</span><strong>{c['post_hoc_only']}</strong><small>shown, never graded as a close</small></div>
<div><span>NO OBSERVATION</span><strong>{c['no_observation_at_all']}</strong><small>blank, by rule</small></div>
</div>""")
    body.append(f"""<div class="notice"><b>The honest state of the store.</b> Week 10's unplayed games are
the first genuine pre-kickoff numbers this repository owns. For them the opening and the closing are
<b>the same number</b> because only one capture exists — the ledger says so on every such cell. This is
the day-one baseline, and it is the reason no closing-line-value claim appears anywhere on this site.</div>""")
    body.append("""<div class="table-wrap"><table><caption>Snapshot register. A new observation is a new
file; nothing is overwritten in place.</caption>
<thead><tr><th>Snapshot</th><th>Observed at</th><th>SHA-256</th><th>Source class</th><th>Source</th></tr></thead><tbody>""")
    for snap in ledger["snapshot_files"]:
        body.append(f"""<tr><td><code>{C.esc(snap['path'])}</code></td><td>{C.esc(snap['observed_at'])}</td>
<td><code>{C.esc(snap['sha256'][:32])}…</code></td><td>{badge('community')}</td>
<td>{link(C.G['schedules'], 'nflverse release')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="table-wrap"><table><caption>Per-event ledger, Week 10 and the played
Week 10 game. Opening/closing are blank wherever no pre-kickoff observation exists.</caption>
<thead><tr><th>Event</th><th>Kickoff (approx UTC)</th><th>Market</th><th>Opening</th><th>Closing</th>
<th>Observations pre / post</th><th>Source</th></tr></thead><tbody>""")
    shown = 0
    for event in ledger["events"]:
        if event["week"] != 10:
            continue
        for market in ("spread", "total", "moneyline"):
            cell = event["markets"][market]
            opening = cell.get("opening") or {}
            closing = cell.get("closing") or {}
            if not opening and not closing and not cell.get("post_hoc"):
                continue
            def fmt(payload):
                if not payload:
                    return "<span class='blank'>unverified</span>"
                return " / ".join(f"{C.esc(k)} {f(v, 1)}" for k, v in payload.items() if v is not None)
            body.append(f"""<tr><td>{C.esc(event['away'])} @ {C.esc(event['home'])}</td>
<td>{C.esc((event.get('kickoff_utc_approx') or '')[:16])}</td><td>{C.esc(market)}</td>
<td>{fmt(opening)}</td><td>{fmt(closing)}</td>
<td>{cell.get('n_pre_kickoff', 0)} / {cell.get('n_post_kickoff', 0)}</td>
<td>{link(C.G['schedules'], 'price')}</td></tr>""")
            shown += 1
    body.append("</tbody></table></div>")
    body.append(f"""<div class="section-head"><div><div class="section-label">POLICY</div>
<h2>Decided before any backtest was published</h2></div>
<p>Policy hash <code>{C.esc((ledger.get('policy_sha256') or '')[:32])}…</code> is written into the ledger,
so a later edit is visible as a changed hash rather than a silent change.</p>
<pre class="policy">{C.esc(policy)}</pre></div>""")
    return "\n".join(body), "Price store", "Opening, closing and the policy that governs them"


def page_availability(art):
    avail = art["avail"]
    abl = art["ablation"]
    c = avail["coverage"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">AVAILABILITY GRAPH</div>
<h2>Expected starters, actual participants, and the depth between them</h2></div>
<p>Nodes: {avail['graph']['nodes']['club']} clubs, {avail['graph']['nodes']['slot']:,} published slots,
{avail['graph']['nodes']['player_named_in_slot']:,} named players, {avail['graph']['nodes']['report_row']}
report rows, {avail['graph']['nodes']['reserve_row']} reserve rows,
{avail['graph']['nodes']['playing_time_row']:,} playing-time rows.</p></div>""")
    body.append(f"""<div class="metrics">
<div><span>CLUBS WITH A PARSED DEPTH PAGE</span><strong>{c['clubs_with_depth']}/32</strong>
<small>two clubs publish no parseable chart</small></div>
<div><span>SLOTS NAMING ≥2 RANK-1 PLAYERS</span><strong>{c['slots_rank1_with_two_or_more']}</strong>
<small>kept as groups</small></div>
<div><span>GAME DESIGNATIONS PUBLISHED</span><strong>{c['games_on_report']}/{c['report_rows']}</strong>
<small>of official report rows</small></div>
<div><span>CLUBS WITH NO REPORT SECTION</span><strong>{c['no_injury_sections']}</strong>
<small>not the same as injury-free</small></div>
</div>""")
    body.append("<div class='notice'><b>Rules this graph enforces.</b><ul>")
    for rule in avail["rules"]:
        body.append(f"<li>{C.esc(rule)}</li>")
    body.append("</ul></div>")
    body.append("""<div class="section-head"><div><div class="section-label">DEPTH FROM PLAYING TIME</div>
<h2>Measured order versus published order</h2></div>
<p>For every club/unit/position where playing time exists, the player with the largest measured snap share
is compared with the club's published rank 1. Neither is declared correct; the disagreement is the datum.</p></div>
<div class="table-wrap"><table><caption>Disagreements first. A rank-1 group holding several players can
show a measured leader who is not the first name on the page.</caption>
<thead><tr><th>Club</th><th>Unit</th><th>Pos</th><th>Measured leader</th><th>Share</th>
<th>Published rank</th><th>Agrees?</th><th>Source</th></tr></thead><tbody>""")
    checks = sorted(avail["depth_from_playing_time"], key=lambda d: d["leader_matches_rank1"])
    for d in checks[:60]:
        body.append(f"""<tr><td>{C.esc(d['club'])}</td><td>{C.esc(d['unit'])}</td>
<td>{C.esc(d['position'])}</td><td>{C.esc(d['snap_leader'])}</td>
<td>{pct(d['snap_leader_share'])}</td><td>{d['snap_leader_published_rank']}</td>
<td>{badge('pass') if d['leader_matches_rank1'] else badge('partial')}</td>
<td>{link(C.G['snaps'], 'playing time')}</td></tr>""")
    body.append("</tbody></table><p class='small'>First 60 of "
                f"{len(checks)} groups shown.</p></div>")
    body.append("""<div class="section-head"><div><div class="section-label">WEEK 10 DEFICIENCIES</div>
<h2>Where a rank-1 slot is officially unavailable</h2></div>
<p>Only official designations (Out / Doubtful) create a deficiency. The backup shown is the club's own
next published name — evidence of order, never a claim of assignment.</p></div>
<div class="table-wrap"><table><caption>Empty where the club publishes no chart or the report names no
unavailable rank-1 player. A blank means the source does not say, not that the slot is healthy.</caption>
<thead><tr><th>Fixture</th><th>Club</th><th>Pos</th><th>Unavailable</th><th>Designation</th>
<th>Next published name</th><th>His status</th><th>Source</th></tr></thead><tbody>""")
    for m in avail["matchups"]:
        for side, data in m["sides"].items():
            for d in data["deficits"]:
                next_name = ", ".join(d["published_backup"] or []) or None
                body.append(f"""<tr><td>{C.esc(C.FULL_NAME.get(m['away'], m['away']))} @ {C.esc(C.FULL_NAME.get(m['home'], m['home']))}</td>
<td>{C.esc(data['club_name'])}</td><td>{C.esc(d['position'])}</td>
<td>{C.esc(', '.join(d['unavailable']))}</td><td>{badge(d['designation'])}</td>
<td>{C.esc(next_name) if next_name else "<span class='blank'>not published</span>"}</td>
<td>{C.esc(', '.join(x or 'blank' for x in (d['backup_game_status'] or [])) or 'blank')}</td>
<td>{link(d['report_source'], 'NFL report')}<br>{link(d['chart_source'], 'club chart')}</td></tr>""")
    if not any(d["deficits"] for m in avail["matchups"] for d in m["sides"].values()):
        body.append("<tr><td colspan='8'><span class='blank'>No rank-1 slot with an official Out/Doubtful "
                    "designation and a parsed chart was found on the captured snapshot.</span></td></tr>")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="section-head"><div><div class="section-label">ABLATION</div>
<h2>Injury and personnel: tested, not penalised</h2></div>
<p>Same model, with and without the personnel term, on a chronological holdout. λ is a pre-registered
conversion and the whole grid is published so no reader has to trust a single number.</p></div>
<div class="table-wrap"><table><caption>MAE improvement is (without personnel) − (with personnel), so a
positive number means the personnel term helped. The interval is a paired game-cluster bootstrap.</caption>
<thead><tr><th>λ (points per lost snap share)</th><th>n</th><th>MAE without</th><th>MAE with</th>
<th>Improvement</th><th>95% interval</th><th>Source</th></tr></thead><tbody>""")
    for entry in abl["grid"]:
        b = entry["buckets"]["holdout"]
        body.append(f"""<tr><td>{entry['lambda']}</td><td>{b['n']}</td><td>{f(b['base_mae'], 3)}</td>
<td>{f(b['personnel_mae'], 3)}</td><td>{f(b['mae_improvement'], 3, '+')}</td>
<td>[{f(b['mae_improvement_lo'], 3, '+')}, {f(b['mae_improvement_hi'], 3, '+')}]</td>
<td>{link(C.S['injuries'], 'report')} · {link(C.G['snaps'], 'snaps')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("<div class='notice'><b>Verdict.</b> <ul>")
    for limit in abl["limits"]:
        body.append(f"<li>{C.esc(limit)}</li>")
    body.append("</ul></div>")
    return "\n".join(body), "Availability & depth", "Who was expected, who actually played"


def page_correlations(art):
    corr = art["corr"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">CORRELATIONS</div>
<h2>Computed only from officially sourced numbers, each with n and an interval</h2></div>
<p>{C.esc(corr['rule'])}</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Every row names the source class of both inputs.
A COMMUNITY + OFFICIAL row is published for transparency and is excluded from every official-only gate.
n &lt; 30 is marked not estimable.</caption>
<thead><tr><th>ID</th><th>Relationship</th><th>Inputs</th><th>n</th><th>r</th><th>95% interval</th>
<th>Estimable?</th><th>Source A</th><th>Source B</th></tr></thead><tbody>""")
    for row in corr["rows"]:
        body.append(f"""<tr><td><b>{row['key']}</b></td><td>{C.esc(row['label'])}<br>
<small>{C.esc(row['scope'])}</small></td>
<td>{badge(row['class_a'])} {badge(row['class_b'])}</td><td>{row['n']}</td><td>{f(row['r'], 3)}</td>
<td>[{f(row['lo'], 3)}, {f(row['hi'], 3)}]</td>
<td>{badge('pass') if row['estimable'] else badge('unverified')}</td>
<td>{link(row['source_a'], 'input A')}</td><td>{link(row['source_b'], 'input B')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="section-head"><div><div class="section-label">WITHHELD</div>
<h2>Relationships we refuse to publish, and the reason</h2></div>
<div class="table-wrap"><table><caption>A withheld correlation is a decision about evidence, not a gap in
effort. Publishing any of these would require relabelling a community input as a market fact.</caption>
<thead><tr><th>ID</th><th>Relationship</th><th>Why it is withheld</th><th>Source</th></tr></thead><tbody>""")
    for row in corr["not_published"]:
        body.append(f"""<tr><td><b>{C.esc(row['key'])}</b></td><td>{C.esc(row['label'])}</td>
<td>{C.esc(row['why'])}</td><td>{link(row['source'], 'source')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append(f"""<div class="notice"><b>What a correlation would buy us.</b> Parlays and prop combos are
ranked only when a directly validated <i>joint</i> probability exists (gate G07). A marginal correlation
between two legs is necessary but nowhere near sufficient: the joint probability also depends on the
conditional structure inside a game. That is why the withheld list has four entries and the published
list has {corr['counts']['published']}.</div>""")
    return "\n".join(body), "Correlations", "Official inputs only, with n on every value"


def page_luck(art):
    luck = art["luck"]
    body = [BANNER]
    c = luck["corpus"]
    body.append(f"""<div class="section-head"><div><div class="section-label">REMOVAL OF LUCK</div>
<h2>Separating signal from staking, on {c['games_played']} played games</h2></div>
<p>{C.esc(luck['panel_statement'])}</p></div>""")
    body.append(f"""<div class="metrics">
<div><span>GAMES IN CORPUS</span><strong>{c['games_played']}</strong><small>weeks {c['weeks'][0]}–{c['weeks'][-1]}</small></div>
<div><span>SETTLEMENT</span><strong>official</strong><small>{C.esc(c['reconciliation'])}</small></div>
<div><span>STRATEGIES SEPARATED</span><strong>{len(luck['separations'])}</strong><small>each with an interval</small></div>
<div><span>WITH AN INTERVAL ABOVE ZERO</span><strong>{sum(1 for s in luck['separations'] if s['bss_lo'] and s['bss_lo'] > 0)}</strong>
<small>none is validated at this n</small></div>
</div>""")
    body.append("""<div class="section-head"><div><div class="section-label">SAMPLE ARITHMETIC</div>
<h2>How much evidence a real edge needs</h2></div>
<div class="table-wrap"><table><caption>Normal-approximation sample size for a one-sided win/loss test.
The 'still needed' column is the honest distance between this corpus and a decision.</caption>
<thead><tr><th>True edge over a coin</th><th>Win probability</th><th>n at 80% power</th><th>n at 90% power</th>
<th>n held</th><th>Still needed</th><th>Source</th></tr></thead><tbody>""")
    for row in luck["sample_size_table"]:
        body.append(f"""<tr><td>{pct(row['edge'], 0)}</td><td>{row['win_probability']:.2f}</td>
<td>{row['n_required_80pct']:,}</td><td>{row['n_required_90pct']:,}</td>
<td>{row['n_available_now']}</td><td>{row['still_needed']:,}</td>
<td>{link(C.S['standings'], 'results feed')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="section-head"><div><div class="section-label">SIGNAL vs STAKING</div>
<h2>What each scored rule actually demonstrated</h2></div>
<div class="table-wrap"><table><caption>Three separate columns on purpose. The win-rate interval can be
wide while the Brier-skill interval is decisive, or the reverse. Neither one is money.</caption>
<thead><tr><th>Strategy</th><th>Family</th><th>n</th><th>Wins</th><th>Win rate</th><th>Wilson 95%</th>
<th>Brier skill</th><th>Skill 95%</th><th>Verdict</th><th>Source</th></tr></thead><tbody>""")
    for row in luck["separations"]:
        body.append(f"""<tr><td><b>{C.esc(row['id'])}</b> {C.esc(row['name'])}</td>
<td>{C.esc(row['family'])}</td><td>{row['n']}</td><td>{row['wins']}</td>
<td>{pct(row['win_rate'])}</td><td>[{pct(row['wilson_lo'])}, {pct(row['wilson_hi'])}]</td>
<td>{f(row['bss'], 3)}</td><td>[{f(row['bss_lo'], 3)}, {f(row['bss_hi'], 3)}]</td>
<td>{C.esc(row['verdict'])}</td><td>{link(C.S['standings'], 'official results')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="section-head"><div><div class="section-label">FLUKES</div>
<h2>Could a coin have done this?</h2></div>
<div class="table-wrap"><table><caption>Exact binomial tail probability of at least this many wins out of
n under p=0.5. Look at the largest win rate on the page and compare it with the sample it was earned on.
</caption><thead><tr><th>Strategy</th><th>n</th><th>Wins</th><th>P(at least this many by chance)</th>
<th>Source</th></tr></thead><tbody>""")
    for row in luck["fluke_probability"]:
        body.append(f"""<tr><td><b>{C.esc(row['id'])}</b></td><td>{row['n']}</td><td>{row['wins']}</td>
<td>{f(row['p_at_least_this_many_by_chance'], 3)}</td>
<td>{link(C.S['standings'], 'results')}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="notice"><b>The rule this page exists to enforce.</b> A strategy is never
described as profitable, unlucky or promising here. It is described by what its interval covers. Staking
and reward decisions sit behind the gates on <a href="leaderboard.html">the leaderboard</a> and cannot be
made from a win rate.</div>""")
    return "\n".join(body), "Luck removal", "Signal, staking and chance, kept apart"


def page_suggestions(art):
    sug = art["suggestions"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">REVIEW BEFORE BUILD</div>
<h2>{len(sug['rows'])} suggestions, ranked by what they unblock</h2></div>
<p>This page is a review surface, not a build queue. Pick a path; nothing here changes a file until it is
chosen. Each suggestion names what it unblocks, its cost, its risk and the decision it is waiting on.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Ranked by (blocked requirements unblocked) then by
cost. A suggestion with no blocked requirement behind it is an improvement, not a priority.</caption>
<thead><tr><th>#</th><th>Suggestion</th><th>Unblocks</th><th>Cost / effort</th><th>Risk if done wrong</th>
<th>The decision it needs</th><th>Source</th></tr></thead><tbody>""")
    for i, s in enumerate(sorted(sug["rows"], key=lambda x: (-len(x["unblocks"]), x["cost"])), 1):
        body.append(f"""<tr><td>{i}</td><td><b>{C.esc(s['title'])}</b><br><small>{C.esc(s['detail'])}</small></td>
<td>{C.esc(', '.join(s['unblocks']) or '—')}</td><td>{C.esc(s['cost'])}</td>
<td>{C.esc(s['risk'])}</td><td>{C.esc(s['decision'])}</td>
<td>{link(s['source'], s['source_label'])}</td></tr>""")
    body.append("</tbody></table></div>")
    body.append("""<div class="notice"><b>How to choose.</b> Start at the top. The two highest-value items
are price capture and a second dated injury capture, because almost every blocked number on this site
depends on one or both. Everything else can be deferred without making an existing number wrong.</div>""")
    return "\n".join(body), "Suggestions", "Proposals awaiting a decision"


def page_flagged(art):
    flagged = art["flagged"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">FLAGGED FOR REVIEW</div>
<h2>{len(flagged['rows'])} irregularities, each with its source</h2></div>
<p>None of these block publication. Each one is a place where the honest answer is 'we do not know' or
'this conflicts'. They are listed so the owner can review them after the site is live.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>Severity is about consequence for a decision, not
about effort. Every row carries the source that shows the issue.</caption>
<thead><tr><th>ID</th><th>Severity</th><th>Item</th><th>What is irregular</th><th>What would resolve it</th>
<th>Source</th></tr></thead><tbody>""")
    for row in flagged["rows"]:
        body.append(f"""<tr><td><b>{C.esc(row['id'])}</b></td><td>{badge(row['severity'])}</td>
<td>{C.esc(row['title'])}</td><td>{C.esc(row['issue'])}</td>
<td>{C.esc(row['resolve'])}</td><td>{link(row['source'], row['source_label'])}</td></tr>""")
    body.append("</tbody></table></div>")
    return "\n".join(body), "Flagged for review", "Open irregularities and unverified items"


def page_sources(art):
    src = art["sources"]
    body = [BANNER]
    body.append(f"""<div class="section-head"><div><div class="section-label">SOURCES</div>
<h2>Every source, what it covers, and what it does not</h2></div>
<p>{src['counts']['official']} official and {src['counts']['community']} community sources. A capture hash
proves byte integrity, never authority to reuse.</p></div>""")
    body.append("""<div class="table-wrap"><table><caption>The 'limit' column matters as much as the scope:
a source that does not establish depth order cannot be used to establish depth order.</caption>
<thead><tr><th>ID</th><th>Class</th><th>Source</th><th>What it covers</th><th>What it does not establish</th>
<th>Observed</th></tr></thead><tbody>""")
    for s in src["rows"]:
        body.append(f"""<tr><td><b>{C.esc(s['id'])}</b></td><td>{badge(s['class'])}</td>
<td>{link(s['url'], s['name'])}</td><td>{C.esc(s['covers'])}</td><td>{C.esc(s['limit'])}</td>
<td>{C.esc(s['observed'])}</td></tr>""")
    body.append("</tbody></table></div>")
    return "\n".join(body), "Sources", "Official and community inputs"


PAGES = {
    "index.html": page_index,
    "requirements.html": page_requirements,
    "decisions.html": page_decisions,
    "strategies.html": page_strategies,
    "leaderboard.html": page_leaderboard,
    "lines.html": page_lines,
    "prices.html": page_prices,
    "availability.html": page_availability,
    "correlations.html": page_correlations,
    "luck.html": page_luck,
    "suggestions.html": page_suggestions,
    "flagged.html": page_flagged,
    "sources.html": page_sources,
}


def build() -> int:
    art = {
        "board": load("leaderboard.json"),
        "luck": load("luck.json"),
        "gates": load("gates.json"),
        "results": load("results.json"),
        "corr": load("correlations.json"),
        "avail": load("availability_graph.json"),
        "ablation": load("ablation.json"),
        "ledger": load("prices/ledger.json"),
        "registry": load("strategies.json"),
        "requirements": load("requirements.json"),
        "questions": load("questions.json"),
        "suggestions": load("suggestions.json"),
        "flagged": load("flagged.json"),
        "sources": load("sources.json"),
        "wf": load("origination_walkforward.json"),
        "elo": load("origination_elo.json"),
    }
    written = 0
    for filename, renderer in PAGES.items():
        content, title, subtitle = renderer(art)
        C.HERE["page"] = filename
        html = C.page(title, subtitle, content)
        (OUT / filename).write_text(html, encoding="utf-8")
        written += 1
    print(f"Built {written} origination pages into origination/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
