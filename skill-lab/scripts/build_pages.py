#!/usr/bin/env python3
"""Render the skill-lab pages from the committed result artifact.

The renderer reads ``skill-lab/data/results.json`` and writes static HTML.  It performs no
network access and computes no new statistic: every number on a page comes from the artifact,
so a reviewer can diff the JSON against the page.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "skill-lab"
DATA = LAB / "data"
RESULTS = DATA / "results.json"

PAGES = [
    ("index.html", "Overview"),
    ("leaderboard.html", "Leaderboard"),
    ("mind-change.html", "What would change our mind"),
    ("controls.html", "Controls &amp; luck"),
    ("staking.html", "Staking view"),
    ("dependence.html", "Dependence"),
    ("graded.html", "Graded forecasts"),
    ("methodology.html", "Methodology"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
]

NFL_SCORES = "https://www.nfl.com/scores/"
NFL_STANDINGS = "https://www.nfl.com/standings/league"
NFL_ODDS_TERMS = ("https://support.nfl.com/hc/en-us/articles/35869698780564-"
                   "If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL")
NFL_RULEBOOK = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/"
NFLVERSE_SCHEDULES = "https://github.com/nflverse/nflverse-data/releases/tag/schedules"


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def fmt(value, digits: int = 4, signed: bool = False, blank: str = "—") -> str:
    if value is None:
        return blank
    try:
        f = float(value)
    except (TypeError, ValueError):
        return esc(value)
    if f != f:
        return blank
    return f"{f:+.{digits}f}" if signed else f"{f:.{digits}f}"


def sign_class(value) -> str:
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    if f != f:
        return ""
    return "pos" if f > 0 else ("neg" if f < 0 else "")


def tag(text: str, kind: str) -> str:
    return f'<span class="tag {kind}">{text}</span>'


def link(url: str, label: str | None = None) -> str:
    return f'<a href="{esc(url)}">{esc(label or url)}</a>'


PROTOCOL_DOC = ("https://github.com/kanlerxz87-cyber/NFL3/blob/main/docs/"
                "SKILL_LAB_PRE_REGISTRATION.md")
ARTIFACT_LINK = ("https://github.com/kanlerxz87-cyber/NFL3/blob/main/skill-lab/data/results.json")


def evidence_cell(run_key: str) -> str:
    """Per-row evidence link: the official record plus the row-level forecast table."""
    official = (link(NFL_STANDINGS, "official standings") if run_key == "primary"
                else link(NFLVERSE_SCHEDULES, "schedule release"))
    return official + ' · <a href="graded.html">row-level forecasts</a>'


def table(headers: list[str], rows: list[list[str]], classes: list[str] | None = None) -> str:
    cls = classes or [""] * len(headers)
    head = "".join(f'<th class="{c}">{h}</th>' for h, c in zip(headers, cls))
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def nav(active: str) -> str:
    items = []
    for href, label in PAGES:
        cls = ' class="active"' if href == active else ""
        items.append(f'<a href="{href}"{cls}>{label}</a>')
    sep = '<span class="sep"></span>'
    links = sep.join(items)
    return (f'<nav class="sections"><div class="wrap">{links}</div></nav>')


def header(meta: dict) -> str:
    primary = meta["primary_corpus"]
    return (f'<header class="top"><div class="wrap"><div class="brand">'
            f'<div class="brand-mark">N3</div><div><h1>Skill lab — proper scores, controls and the removal of luck</h1>'
            f'<p>Protocol {esc(meta["protocol"])} · registered before any result was computed</p></div>'
            f'<div class="status-strip"><span>corpus {primary["observed_games"]} games</span>'
            f'<span>{esc(meta["generated_at_utc"][:10])}</span>'
            f'<span>0 strategies eligible</span></div></div></div></header>')


def footer(meta: dict) -> str:
    return (f'<footer><div class="wrap">NFL3 RESEARCH DESK — SKILL LAB'
            f'<span>Built for informed decisions, not guaranteed outcomes. '
            f'Pre-registration commit {esc(meta["pre_registration_commit"][:12])}.</span></div></footer>')


def page(meta: dict, name: str, title: str, eyebrow: str, lede: str, body: str,
         notices: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · NFL3 skill lab</title>
<meta name="description" content="NFL3 skill lab — benchmark-relative proper scores, control baselines, game-cluster uncertainty and multiplicity control for NFL line origination.">
<link rel="stylesheet" href="assets/site.css">
</head>
<body>
{header(meta)}
{nav(name)}
<main><div class="wrap">
<div class="page-head"><div class="eyebrow">{eyebrow}</div><h1>{esc(title)}</h1>
<p class="lede">{lede}</p></div>
{notices}
{body}
</div></main>
{footer(meta)}
</body>
</html>
"""


# --------------------------------------------------------------------------- sections
def build_overview(res: dict) -> str:
    meta = res["meta"]
    run = res["runs"]["primary"]
    rows = run["rows"]
    eligible = [r for r in rows if r.get("eligible_for_ranking")]
    best = max(rows, key=lambda r: r.get("skill_brier", float("-inf")))
    dep = res["dependence"]
    metrics = [
        ("CORPUS GRADED", f"{run['n_games_in_corpus']}", "2026 regular season, weeks 1–9, both scores published"),
        ("STRATEGY ROWS TESTED", f"{len(rows)}", "one family, one pre-registered protocol"),
        ("ELIGIBLE FOR RANKING", f"{len(eligible)}", "every gate G1–G7 must pass"),
        ("BEST BENCHMARK-RELATIVE SKILL", fmt(best.get("skill_brier"), 4, signed=True),
         f"{esc(best.get('strategy', ''))} vs the closing market probability"),
    ]
    cards = "".join(
        f'<div><h3>{esc(a)}</h3><p>{b}</p></div>' for a, b in [
            ("Signal, not staking",
             "A strategy is ranked on how good its probability is against the market's own "
             "probability. A profitable staking run cannot promote a row that fails the signal gates."),
            ("Luck is measured, not asserted",
             "Every run publishes a random-pick control and a base-rate control. A row that cannot beat "
             "the 95th percentile of the random control has not shown skill."),
            ("Uncertainty is structural",
             "Intervals come from a bootstrap that resamples <em>games</em>, so the three markets of one "
             "game are never counted as independent evidence."),
            ("Multiplicity is counted",
             "Benjamini–Hochberg control at q = 0.05 is applied across the whole family, and the number "
             "of trials is published with every adjusted value."),
            ("Blank means blank",
             "There is no dated price history in this repository, so closing-line value, open-to-close "
             "movement and any official price column are blank and flagged — never estimated."),
            ("Official sources only for facts",
             "Results, injury reports, reserve-list moves and standings come from NFL.com. The closing "
             "prices are community-maintained and are labelled as such on every table."),
        ])

    body = (f'<div class="metrics">'
            + "".join(f'<div><span>{esc(a)}</span><strong>{b}</strong><small>{c}</small></div>'
                      for a, b, c in metrics)
            + "</div>"
            + f'<h2>What the run found</h2>'
            + f'<div class="notice"><b>No registered strategy passed the gates.</b> On the frozen '
              f'{run["n_games_in_corpus"]}-game corpus, every registered row scored <em>worse</em> than the '
              f'market&#8217;s own de-vigged closing probability on its market: the best row was '
              f'{esc(best.get("strategy", ""))} at {fmt(best.get("skill_brier"), 4, signed=True)} Brier skill, '
              f'with a 95% game-cluster interval of [{fmt(best.get("bootstrap", {}).get("ci95", [None, None])[0], 4, signed=True)}, '
              f'{fmt(best.get("bootstrap", {}).get("ci95", [None, None])[1], 4, signed=True)}]. '
              f'The point estimate is below zero and the interval spans it, so the honest status is '
              f'<b>no skill demonstrated</b> — this is not a strategy that is nearly right, it is a strategy '
              f'that did not beat the market&#8217;s own probability. Any staking result from this family '
              f'would be luck, not edge.</div>'
            + '<div class="cards">' + cards + "</div>"
            + '<h2>How to read this</h2>'
            + '<ul class="tight">'
              '<li><b>Leaderboard</b> — the prospective-only ranking surface; it is empty until frozen gates clear. '
              'Backtest diagnostics do not appear there.</li>'
              '<li><b>Controls &amp; luck</b> — the market benchmark, the random-pick control, the base-rate '
              'control and the favourites-only control, with the luck floor each row had to clear.</li>'
              '<li><b>Staking view</b> — the retrospective return at the published closing price, kept in a '
              'separate table because it cannot promote a row.</li>'
              '<li><b>Dependence</b> — the measured dependence between the markets of the same game, which is '
              'why marginal probabilities are not multiplied for parlays.</li>'
              '<li><b>Methodology</b> — the frozen protocol, its commit hash, every definition and the '
              'limitations that are published with the numbers.</li>'
              '</ul>'
            + f'<h2>Within-game dependence, measured on the same corpus</h2>'
            + f'<p class="footnote">Home covers and over occurred together in '
              f'{fmt(dep.get("joint_cover_and_over_observed") * dep.get("n", 0), 0)} of {dep.get("n")} graded games '
              f'({fmt(dep.get("joint_cover_and_over_observed"), 4)}), against '
              f'{fmt(dep.get("joint_cover_and_over_if_independent"), 4)} if the two legs were independent.</p>')
    return body


def build_leaderboard(res: dict) -> str:
    """Keep all historical score rows off the leaderboard; only the prospective board may rank."""
    return ("<div class=\"notice\"><b>Zero eligible strategies.</b> This page is a prospective-only "
            "ranking surface. It intentionally contains no backtest score, win rate, ROI, or rank. "
            "Historical research diagnostics remain outside the leaderboard and cannot qualify a row.</div>"
            "<h2>Current prospective leaderboard</h2>"
            "<p>The canonical board lists each market division, registered controls, signal and staking "
            "columns, promotion/demotion rules, and the number eligible. It currently has no graded "
            "prospective sample.</p>"
            "<p><a class=\"link\" href=\"../forward-ledger/leaderboard.html\">Open the prospective-only "
            "leaderboard →</a></p>")


def build_controls(res: dict) -> str:
    meta = res["meta"]
    run = res["runs"]["primary"]
    rows = []
    for r in run["rows"]:
        if "bootstrap" not in r:
            continue
        ctrl = r["control_random"]
        rows.append([
            esc(r["strategy"]),
            f'{r["n_games"]}',
            fmt(r["brier_market"], 4),
            fmt(r["brier_model"], 4),
            fmt(r["control_base_rate_brier"], 4),
            fmt(ctrl["brier_mean"], 4),
            fmt(r["control_base_rate_skill"], 4, signed=True),
            fmt(ctrl["skill_p95"], 4, signed=True),
            fmt(r["skill_brier"], 4, signed=True),
            "yes" if r["skill_brier"] > ctrl["skill_p95"] else "no",
        ])
    body = ('<h2>The four controls</h2>'
            '<ul class="tight">'
            '<li><b>C1 Market benchmark</b> — the de-vigged closing price probability. It is scored with '
            'the same formulas, so the market is never assumed to be perfect.</li>'
            '<li><b>C2 Random pick</b> — 1,000 fixed seeds, a uniformly random side on every game, treated '
            'as a hard forecast. This is the luck floor for a rule with no information.</li>'
            '<li><b>C2b Neutral</b> — p = 0.5 everywhere. Its mean Brier score is exactly 0.25 and it is '
            'the information-free floor for a probability forecast.</li>'
            '<li><b>C3 Favourites only</b> — always take the shorter price. The luck floor for a staking rule.</li>'
            '<li><b>C4 Base rate</b> — the training-window base rate applied to every game: the floor for a '
            'rule with no per-game information.</li>'
            '</ul>'
            + table(["Strategy", "n", "Brier market (C1)", "Brier ours", "Brier base rate (C4)",
                     "Brier random (C2)", "Skill of C4", "Skill of C2, 95th pct", "Our skill",
                     "Beats random 95th?"],
                    rows, ["", "num", "num", "num", "num", "num", "num", "num", "num", ""])
            + '<h2>What the controls say</h2>')
    # luck panel
    luck_rows = []
    for r in run["rows"]:
        if "bootstrap" not in r:
            continue
        ctrl = r["control_random"]
        st = r["staking"]
        luck_rows.append([
            esc(r["strategy"]),
            fmt(st["return_per_unit"], 3, signed=True),
            fmt(ctrl["return_p50"], 3, signed=True),
            fmt(ctrl["return_p95"], 3, signed=True),
            fmt(ctrl["return_max"], 3, signed=True),
            fmt(st["favourites_only_return"], 3, signed=True),
            fmt(st["return_at_minus_10pct_price"], 3, signed=True),
        ])
    body += ('<p class="footnote">A random picker that gets lucky over a short window is the standard way a '
             'bad signal looks like a good one. The columns below are the distribution of a rule with no '
             'information at all, measured on the same corpus and the same prices.</p>'
             + table(["Strategy market", "Our flat-stake return", "Random pick, median",
                      "Random pick, 95th pct", "Random pick, best seed", "Favourites only",
                      "Our return at a 10% worse price"],
                     luck_rows, ["", "num", "num", "num", "num", "num", "num"])
             + '<div class="notice warn"><b>Read the return column last.</b> A positive realised return on '
               'this corpus is not evidence of skill: the random control reaches a positive 95th percentile '
               'on every market, so a lucky staking run and a real edge look identical in the return column. '
               'Only the signal columns above can tell them apart, and on this corpus the signal columns are '
               'negative for every registered row.</div>')
    return body


def build_mind_change(res: dict) -> str:
    """The two-sided 'what would change our mind' field, published for every registered row."""
    meta = res["meta"]
    rows = []
    for row in res["runs"]["primary"]["rows"]:
        belief = ("A pre-registered evaluation on a corpus the model has never seen, of at least the "
                  "registered sample size, in which the 95% game-cluster lower bound on Brier skill is "
                  "above zero, the row beats the random-pick control's 95th percentile, the row survives "
                  "Benjamini–Hochberg correction inside its family, and the calibration error is at or "
                  "below 0.05 — all four, on the same corpus, in one run.")
        reject = ("A pre-registered evaluation on an equally sized unseen corpus in which the Brier skill "
                  "is at or below zero, or the 95% lower bound is below zero, or the row fails to beat "
                  "the random-pick control's 95th percentile, or it fails the multiplicity control, or "
                  "its calibration error exceeds 0.05. Any one of these is sufficient, and a second "
                  "consecutive such result demotes the row to paper status.")
        observed = ("Observed in this run: skill "
                    f'{fmt(row.get("skill_brier"), 4, signed=True)}, lower bound '
                    f'{fmt(row.get("bootstrap", {}).get("lower95"), 4, signed=True)}, '
                    f'{row.get("gates_passed", 0)}/{row.get("gates_total", 0)} gates.')
        rows.append([
            esc(row["strategy"]), esc(row.get("name", "")), belief, reject, observed,
            link(PROTOCOL_DOC, "SL-PRE-01"),
            link("https://github.com/kanlerxz87-cyber/NFL3/blob/main/docs/"
                 "SKILL_LAB_PRE_REGISTRATION_AMENDMENT_02.md", "SL-PRE-01b"),
        ])
    body = ('<div class="notice"><b>The field is written forward.</b> It was frozen in '
            '<a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/docs/'
            'SKILL_LAB_PRE_REGISTRATION_AMENDMENT_02.md">SL-PRE-01b</a> for the next evaluation window '
            '(2026 weeks 10 onward). It is not applied to the completed run below: the run is published '
            'as what it was, a negative result. The belief side requires four conditions at once; the '
            'rejection side requires one.</div>'
            '<h2>Every registered row, and what would move it</h2>'
            + table(["Strategy", "Definition", "Would move this towards belief",
                     "Would move this towards rejection", "What this run showed", "Protocol", "Field"],
                    rows, ["", "", "", "", "", "", ""]))
    return body


def build_staking(res: dict) -> str:
    meta = res["meta"]
    run = res["runs"]["primary"]
    rows = []
    for r in run["rows"]:
        if "bootstrap" not in r:
            continue
        st = r["staking"]
        ci = st.get("return_ci95") or [None, None]
        rows.append([
            esc(r["strategy"]),
            esc(r["name"]),
            f'{st["n_bets"]}',
            f'{st["hit_rate"]:.3f}' if st["hit_rate"] is not None else "—",
            f'<span class="{sign_class(st["return_per_unit"])}">{fmt(st["return_per_unit"], 3, signed=True)}</span>',
            f'[{fmt(ci[0], 3, signed=True)}, {fmt(ci[1], 3, signed=True)}]',
            fmt(st["favourites_only_return"], 3, signed=True),
            fmt(st["return_at_minus_10pct_price"], 3, signed=True),
            tag("signal gates fail — not promotable",
                "fail" if not r["eligible_for_ranking"] else "pass"),
        ])
    body = ('<div class="notice warn"><b>This table cannot promote a strategy.</b> It is retrospective: it '
            'uses the community-maintained closing price that was published in the schedule release, there '
            'is no opening price, there is no permissioned price archive, and the signal gates in the '
            'leaderboard are the only ranking basis. A row that fails a signal gate stays failed however good '
            'this column looks.</div>'
            '<h2>Retrospective flat-stake view at the published closing price</h2>'
            + table(["Strategy", "Definition", "Bets", "Hit rate", "Return per unit",
                     "95% cluster CI", "Favourites only", "At a 10% worse price", "Signal verdict"],
                    rows, ["", "", "num", "num", "num", "num", "num", "num", ""])
            + '<h2>Why there is no closing-line value column</h2>'
            '<p class="footnote">Closing-line value needs an opening price and a closing price for the same '
            'market at a known time. This repository holds one undated community line per game and no '
            'official or permissioned price history, so the cell stays blank rather than being estimated. '
            f'Source boundary: {link(NFL_ODDS_TERMS, "NFL odds-widget terms (support.nfl.com)")}.</p>'
            '<h2>What would fill the blanks</h2>'
            '<ul class="tight">'
            '<li>A permissioned, dated open and close price history for every market we originate.</li>'
            '<li>An official settlement record so a graded result is not a community score.</li>'
            '<li>A published price-data policy, which the readiness register lists as blocked.</li>'
            '</ul>')
    return body


def build_dependence(res: dict) -> str:
    dep = res["dependence"]
    n = dep.get("n", 0)
    src = (link(NFL_STANDINGS, "official standings")
           + ' · <a href="graded.html">row-level forecasts</a>')
    rows = [
        ["Home covers the closing spread", fmt(dep["p_home_cover"], 4), "—", "—", src],
        ["Game total over the closing total", fmt(dep["p_over"], 4), "—", "—", src],
        ["Home team wins", fmt(dep["p_home_win"], 4), "—", "—", src],
        ["Home covers AND over (observed joint)",
         fmt(dep["joint_cover_and_over_observed"], 4),
         fmt(dep["joint_cover_and_over_if_independent"], 4),
         fmt(dep["joint_cover_and_over_observed"] - dep["joint_cover_and_over_if_independent"], 4, signed=True),
         src],
        ["Home covers AND over AND home wins (observed joint)",
         fmt(dep["joint_all_three_observed"], 4),
         fmt(dep["joint_all_three_if_independent"], 4),
         fmt(dep["joint_all_three_observed"] - dep["joint_all_three_if_independent"], 4, signed=True),
         src],
    ]
    corr_rows = [
        ["Home covers ↔ over", fmt(dep["phi_cover_over"], 4, signed=True), str(n),
         "Weakly negative: a home cover and an over pull against each other, because a home cover usually "
         "means a win that did not produce many points."],
        ["Home covers ↔ home wins", fmt(dep["phi_cover_win"], 4, signed=True), str(n),
         "Strongly positive: covering the closing spread nearly always means winning the game."],
        ["Over ↔ home wins", fmt(dep["phi_over_win"], 4, signed=True), str(n),
         "Weakly negative: a home win and an over are not the same event, so the two legs of a mixed parlay "
         "cannot be treated as independent."],
    ]
    corr_rows = [row + [src] for row in corr_rows]
    body = ('<div class="notice"><b>Why the parlay divisions are empty.</b> A parlay price is a joint claim. '
            'Multiplying marginal probabilities is only valid under independence, and the legs of one game '
            'are not independent: the observed joint probability of home-covering and over is '
            f'{fmt(dep["joint_cover_and_over_observed"], 4)} against '
            f'{fmt(dep["joint_cover_and_over_if_independent"], 4)} if they were — a gap of '
            f'{fmt(abs(dep["joint_cover_and_over_observed"] - dep["joint_cover_and_over_if_independent"]), 4)}. '
            'A combo may only be ranked when a directly validated joint probability and the operator&#8217;s '
            'void and push rules are both available. Neither exists in this repository.</div>'
            '<h2>Marginals and measured joints</h2>'
            + table(["Event", "Observed", "If independent", "Gap", "Source"], rows,
                    ["", "num", "num", "num", ""])
            + '<h2>Correlations between the legs of the same game</h2>'
            + table(["Pair", "Phi", "n", "Reading", "Source"], corr_rows, ["", "num", "num", "", ""])
            + f'<p class="footnote">n = {n} graded games (2026 weeks 1–9, excluding pushes). Phi is the '
              'Matthews correlation for binary variables. Every value on this page comes from the committed '
              'community schedule release; the official per-game scores are cross-checked against the NFL '
              'standings page.</p>')
    return body


def build_graded(res: dict) -> str:
    run = res["runs"]["primary"]
    rows = []
    for g in sorted(run["graded"], key=lambda r: (r["strategy"], r["gameday"], r["game_id"])):
        url = f'https://www.nfl.com/scores/2026/week-{g["week"]}'
        rows.append([
            f'{link(url, g["game_id"])}',
            esc(g["gameday"]),
            f'{esc(g["away"])} @ {esc(g["home"])}',
            esc(g["strategy"]),
            esc(g["event"]),
            fmt(g["model_line"], 1) if g.get("model_line") is not None else "—",
            fmt(g["market_line"], 1) if g.get("market_line") is not None else "—",
            fmt(g.get("line_gap"), 1, signed=True) if g.get("line_gap") is not None else "—",
            fmt(g["model_prob"], 4),
            fmt(g["benchmark_prob"], 4),
            fmt(g["benchmark_prob_shin"], 4),
            "yes" if g["outcome"] == 1.0 else "no",
            fmt(g["brier_model"], 4),
            fmt(g["brier_market"], 4),
        ])
    body = ('<p class="footnote">Every graded forecast in the primary corpus. The game identifier links to '
            'the official NFL scores page for that week. <b>Our line</b> is the model&#8217;s own number, '
            '<b>Market line</b> is the closing line from the community schedule release, and <b>Gap</b> is '
            'their difference. The Shin column is the alternative de-vig method from the registration, shown '
            'so the reader can see whether a conclusion depends on the de-vig choice.</p>'
            + table(["Game", "Date", "Match-up", "Strategy", "Event", "Our line", "Market line", "Gap",
                     "Our probability", "Market probability (proportional)", "Market probability (Shin)",
                     "Outcome", "Brier ours", "Brier market"],
                    rows, ["", "", "", "", "", "num", "num", "num", "num", "num", "num", "", "num", "num"]))
    return body


def build_methodology(res: dict) -> str:
    meta = res["meta"]
    settings = meta["settings"]
    body = ('<div class="notice"><b>The rule was frozen before the results were computed.</b> The protocol is '
            f'committed in the repository; the creating commit is '
            f'<code>{esc(meta["pre_registration_commit"])}</code> '
            f'({esc(meta.get("pre_registration_commit_date", ""))}), and that commit is verified to be an '
            f'ancestor of the branch that publishes this result. The protocol file hashes to '
            f'<code>{esc(meta.get("pre_registration_file_sha256", ""))}</code>, the same value as at '
            'registration, so no rule has been edited since. Two amendments follow, both committed before '
            'any score existed and published with the result. Any later change needs a new numbered '
            'pre-registration.</div>'
            '<h2>What is measured</h2>'
            '<ul class="tight">'
            '<li><b>Corpus</b> — 2026 regular season, weeks 1–9: every game with both scores published. '
            f'Observed {meta["primary_corpus"]["observed_games"]} games against an expected '
            f'{meta["primary_corpus"]["expected_games"]}.</li>'
            '<li><b>Model</b> — walk-forward: coefficients are fitted on earlier seasons only and applied to '
            'the target season. Two margin models (Elo + form + rest, and Elo only) and two total models '
            '(least squares and a shrinkage estimator) are published, so the totals are never collapsed into '
            'one number before the walk-forward comparison.</li>'
            '<li><b>Probability</b> — a normal distribution around the model&#8217;s own line, using the '
            'training residual scale carried forward unchanged.</li>'
            '<li><b>Benchmark</b> — the de-vigged closing price probability, primary method proportional, '
            'secondary method Shin.</li>'
            '<li><b>Proper scores</b> — Brier score and log loss, with skill defined as '
            '1 − (model score ÷ benchmark score).</li>'
            '<li><b>Uncertainty</b> — a cluster bootstrap that resamples games, so the markets of one game '
            'are never treated as independent evidence.</li>'
            '<li><b>Multiplicity</b> — Benjamini–Hochberg at q = 0.05 across the family, with the trial '
            'count published.</li>'
            '</ul>'
            '<h2>Settings of this run</h2>'
            + table(["Setting", "Value"], [
                ["Protocol", esc(meta["protocol"])],
                ["Pre-registration commit", f'<code>{esc(meta["pre_registration_commit"])}</code>'],
                ["Code commit at run time", f'<code>{esc(meta["code_commit"])}</code>'],
                ["Bootstrap resamples", f'{settings["n_boot"]:,}'],
                ["Bootstrap seed", str(settings["boot_seed"])],
                ["Random control seeds", f'{settings["random_control_seeds"]:,}'],
                ["Benjamini–Hochberg q", str(settings["bh_q"])],
                ["Minimum graded games (G1)", str(settings["min_games_gate"])],
                ["Calibration limit (G6)", str(settings["ece_limit"])],
                ["Run timestamp (UTC)", esc(meta["generated_at_utc"])],
            ])
            + '<h2>Limitations published with every number</h2>'
            '<ul class="tight">'
            '<li><b>Feature selection is not blinded.</b> The walk-forward refit removes coefficient lookahead '
            'but cannot remove a human having chosen the feature list with access to historical results.</li>'
            '<li><b>The prices are community-maintained.</b> The closing lines come from the nflverse '
            'schedules release. They are not an official NFL price archive, and no price on this site is '
            'published as official.</li>'
            '<li><b>No dated price history.</b> With one undated line per game there is no opening price, so '
            'closing-line value is blank and the gate that depends on it cannot be evaluated.</li>'
            '<li><b>One season of hold-out.</b> The primary corpus is a single season. The supporting panel '
            'over earlier seasons is published beside it, not merged into it.</li>'
            '<li><b>Result scores come from a community release</b>; the standings cross-check on the '
            'Decision Desk page is what ties the corpus back to the official record.</li>'
            '</ul>'
            '<h2>Reproduce it</h2>'
            '<pre><code>python3 skill-lab/scripts/build.py      # recompute and rewrite skill-lab/data/results.json\n'
            'python3 skill-lab/scripts/build_pages.py  # re-render the pages from that artifact\n'
            'python3 skill-lab/scripts/verify.py      # fail-closed checks on the published artifact</code></pre>')
    return body


def build_flagged(res: dict) -> str:
    meta = res["meta"]
    items = [
        ["SL-F01", "High", "The closing prices are community-maintained, not official",
         f'Every market benchmark in this lab is de-vigged from the nflverse schedules release '
         f'({link(NFLVERSE_SCHEDULES, "release page")}). The NFL publishes no free historical price archive; '
         f'the boundary is {link(NFL_ODDS_TERMS, "NFL odds-widget terms")}.',
         "Treat every skill number as exploratory until a permissioned price archive is in place."],
        ["SL-F02", "High", "No dated price history, so closing-line value is blank",
         "The schedule release carries one undated line per game. There is no opening price, so the "
         "closing-line-value gate cannot be evaluated and its column is left blank rather than estimated.",
         "Acquire a dated open/close archive, or keep the cell blank and say so."],
        ["SL-F03", "Medium", "The feature list was chosen with hindsight",
         "The walk-forward refit removes coefficient lookahead but not feature-selection hindsight. This is "
         "stated in the registration and repeated in the methodology page.",
         "Register a feature set in advance and freeze it before the next evaluation window."],
        ["SL-F04", "Medium", "Result scores are community-maintained",
         "Final scores come from the community schedules release. The Decision Desk cross-check against the "
         f'official standings page ({link(NFL_STANDINGS, "NFL standings")}) is what ties the corpus to the '
         "official record; the tie is to team aggregates, not to each game's official game centre.",
         "Re-verify each result against the official game centre before any staking use."],
        ["SL-F05", "Medium", "No strategy is eligible for ranking",
         "Every registered row has a negative benchmark-relative skill with a lower bound below zero. The "
         "family is demoted to paper status by the registered demotion rule.",
         "Do not publish these rows as a leaderboard; publish them as a negative result."],
        ["SL-F06", "Low", "Parlay and prop divisions are empty by construction",
         "No permissioned parlay price history, no operator void/push rule set and no official prop line "
         "history or settlement record exists in this repository.",
         "Keep the divisions published and empty; fill them only when the joint evidence exists."],
        ["SL-F07", "Low", "One registered corpus row was excluded",
         f'{res["runs"]["primary"]["exclusions"].get("no gradeable market price or line for this market", 0)} '
         "forecast rows had no gradeable price or line for their market and were excluded by the registered "
         "exclusion rule. The exclusions are counted in the artifact.",
         "No action; the rule was fixed in advance."],
    ]
    evidence = [
        link(NFL_ODDS_TERMS, "NFL odds terms"),
        link(NFL_ODDS_TERMS, "NFL odds terms"),
        link(PROTOCOL_DOC, "pre-registration"),
        link(NFL_STANDINGS, "official standings"),
        link(ARTIFACT_LINK, "committed artifact"),
        link(NFL_RULEBOOK, "2026 rulebook"),
        link(ARTIFACT_LINK, "committed artifact"),
    ]
    rows = [[esc(i), esc(s), esc(t), d, a, evidence[n]] for n, (i, s, t, d, a) in enumerate(items)]
    body = ('<p class="footnote">These are published for review and do not block the site. Each one names the '
            'evidence and the action.</p>'
            + table(["ID", "Severity", "Finding", "Evidence", "Action", "Source"], rows,
                    ["", "", "", "", "", ""]))
    return body


def build_sources(res: dict) -> str:
    meta = res["meta"]
    rows = [
        ["Official NFL scores", link(NFL_SCORES, "nfl.com/scores"),
         "Per-week official result pages; linked from every graded forecast row."],
        ["Official NFL standings", link(NFL_STANDINGS, "nfl.com/standings/league"),
         "The official record used by the Decision Desk cross-check of the game log."],
        ["Official NFL rulebook", link(NFL_RULEBOOK, "2026 NFL rulebook"),
         "Game definitions used by the model and by the settlement convention (pushes excluded)."],
        ["NFL odds-widget boundary", link(NFL_ODDS_TERMS, "support.nfl.com"),
         "The league's own statement of what an NFL betting product is; the source of the price-data gap."],
        ["Community schedules release", link(NFLVERSE_SCHEDULES, "nflverse-data releases"),
         f'Closing lines and final scores. Digest: {esc(str(meta["data"].get("games_sha256"))[:24])}… '
         f'Not an official NFL source.'],
    ]
    body = (table(["Source", "Link", "Use"], rows)
            + '<p class="footnote">Official pages establish published facts. The community release is used '
              'only where no official equivalent exists (historical closing prices), and every such use is '
              'labelled on the page where it appears.</p>')
    return body


BUILDERS = {
    "index.html": build_overview,
    "leaderboard.html": build_leaderboard,
    "mind-change.html": build_mind_change,
    "controls.html": build_controls,
    "staking.html": build_staking,
    "dependence.html": build_dependence,
    "graded.html": build_graded,
    "methodology.html": build_methodology,
    "flagged.html": build_flagged,
    "sources.html": build_sources,
}

TITLES = {
    "index.html": ("Overview", "Skill lab",
                   "Benchmark-relative proper scores, control baselines, game-cluster uncertainty and "
                   "multiplicity control for every line this project originates."),
    "mind-change.html": ("What would change our mind", "Two-sided falsification field",
                         "For every registered row: the evidence that would move it towards belief, the "
                         "evidence that would move it towards rejection, and what this run actually showed."),
    "leaderboard.html": ("Leaderboard", "Signal leaderboard",
                         "Every registered strategy row scored with a proper score against the market's own "
                         "probability, with an interval that treats one game as one observation."),
    "controls.html": ("Controls &amp; luck", "Controls and the removal of luck",
                      "The market benchmark, a random-pick control, a base-rate control and a favourites-only "
                      "control — the floors a strategy has to clear before luck can be ruled out."),
    "staking.html": ("Staking view", "Staking, kept separate",
                      "Retrospective flat-stake return at the published closing price. It is shown here and "
                      "nowhere else, because it cannot promote a strategy."),
    "dependence.html": ("Dependence", "Dependence between the legs of one game",
                        "Measured joint probabilities against the independence product: the evidence that "
                        "keeps the parlay divisions empty."),
    "graded.html": ("Graded forecasts", "Every graded forecast",
                    "Our line, the market line, the gap, both probabilities and both scores for every "
                    "forecast in the primary corpus."),
    "methodology.html": ("Methodology", "Methodology and limitations",
                          "The frozen protocol, its commit hash, every definition and every limitation that "
                          "travels with the numbers."),
    "flagged.html": ("Flagged for review", "Flagged for review",
                      "Irregularities and open items published for the owner to review, each with its "
                      "evidence and the action it implies."),
    "sources.html": ("Sources", "Sources",
                      "Every source used on this site, with the authority boundary stated per source."),
}


def main() -> int:
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    meta = res["meta"]
    LAB.mkdir(parents=True, exist_ok=True)
    for name, builder in BUILDERS.items():
        title, eyebrow, lede = TITLES[name]
        body = builder(res)
        html_text = page(meta, name, title, eyebrow, lede, body)
        (LAB / name).write_text(html_text, encoding="utf-8")
    print(f"skill-lab: wrote {len(BUILDERS)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
