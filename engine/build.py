"""Build every page of the research desk from verified data + computed studies.

Run:  python3 engine/build.py     (writes site/ - published to GitHub Pages by CI)
If a data file is missing the page says so explicitly instead of inventing numbers.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))

import features
import gates
import loader
import report
import stats
import studies
from report import fmt, pct, table, esc, link, badge, unverified

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "site")
ASSETS = os.path.join(ROOT, "lab", "assets")
RESULTS = os.path.join(ROOT, "lab", "results")

RELEASE = {
    "games.csv": ("schedules", "games.csv", "schedule, results, closing lines, QB, rest, weather"),
    "injuries_2026.csv": ("injuries", "injuries_2026.csv", "official weekly injury report rows"),
    "depth_charts_2026.csv": ("depth_charts", "depth_charts_2026.csv", "weekly depth chart"),
    "depth_charts_2024.csv": ("depth_charts", "depth_charts_2024.csv", "weekly depth chart (depth_team)"),
    "snap_counts_2026.csv": ("snap_counts", "snap_counts_2026.csv", "offensive/defensive snap counts"),
    "stats_team_week_2026.csv": ("stats_team", "stats_team_week_2026.csv", "team weekly stats"),
    "roster_2026.csv": ("rosters", "roster_2026.csv", "roster status"),
}


def release_url(asset: str) -> str:
    meta = RELEASE.get(asset)
    if meta:
        return f"https://github.com/nflverse/nflverse-data/releases/tag/{meta[0]}"
    tag = asset.split("_")[0]
    return f"https://github.com/nflverse/nflverse-data/releases/tag/{tag}"


# --------------------------------------------------------------------------- data bootstrap
def load_everything() -> dict:
    man = loader.manifest()
    files = man.get("files", {})
    games = loader.games() if loader.available("games.csv") else []
    season_games = [g for g in games if g["season"] == 2026]
    inj = loader.injuries() if loader.available("injuries_2026.csv") else []
    depth = loader.depth_charts() if loader.available("depth_charts_2026.csv") else []
    depth24 = []
    for r in loader.rows("depth_charts_2024.csv"):
        if r.get("depth_team"):
            depth24.append(r)
    snaps = loader.snaps() if loader.available("snap_counts_2026.csv") else []
    team_week = loader.stats_team_week() if loader.available("stats_team_week_2026.csv") else []
    roster = loader.rosters() if loader.available("roster_2026.csv") else []
    return {"manifest": man, "files": files, "games": games, "season_games": season_games,
            "injuries": inj, "depth": depth, "depth2024": depth24, "snaps": snaps,
            "team_week": team_week, "roster": roster}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    if os.path.isdir(ASSETS):
        os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
        for name in os.listdir(ASSETS):
            shutil.copy(os.path.join(ASSETS, name), os.path.join(OUT, "assets", name))

    D = load_everything()
    page = report.Page()
    computed: dict = {}

    reg = [g for g in D["games"] if g["game_type"] == "REG" and g["home_score"] is not None]
    computed["n_games_total"] = len(reg)
    seasons = sorted({g["season"] for g in reg})
    computed["seasons"] = (seasons[0], seasons[-1]) if seasons else None

    # --- studies (each guarded so a missing file cannot produce an invented number)
    line = studies.line_study(reg) if len(seasons) >= 6 else {"ok": False, "reason": "need >= 6 seasons"}
    computed["line"] = line
    coefs = line.get("coefficients", []) if line.get("ok") else []
    preds = []
    if line.get("ok"):
        preds, _ = __import__("lines").build(reg)
        preds = [p for p in preds if p["season"] >= seasons[-1] - 12]
    computed["preds_n"] = len(preds)
    corr = studies.correlation_study(preds) if preds else {"rows": [], "stacked": {}, "n_games": 0}
    computed["corr"] = corr
    fam, fammeta = studies.strategy_family(preds) if preds else ([], {})
    computed["family"] = fam
    computed["fameta"] = fammeta
    clv = line.get("clv", {"ok": False}) if line.get("ok") else {"ok": False}
    computed["clv"] = clv
    inj = studies.injury_study(D["games"], D["injuries"], D["depth"], 2026) if D["injuries"] else {"ok": False, "reason": "injury file missing"}
    computed["injury"] = inj

    with open(os.path.join(RESULTS, "computed.json"), "w", encoding="utf-8") as f:
        json.dump(_jsonable(computed), f, indent=1, sort_keys=True, default=str)

    writers = [
        ("index.html", "Overview", "THE RESEARCH DESK", build_index),
        ("executive-summary.html", "Executive summary", "READ THIS FIRST", build_summary),
        ("lines.html", "Line origination", "MODEL vs MARKET", build_lines),
        ("strategies.html", "Strategy leaderboard", "PRE-REGISTERED FAMILY", build_strategies),
        ("correlation.html", "Correlation &amp; parlays", "JOINT OUTCOMES", build_correlation),
        ("availability.html", "Injuries &amp; backup depth", "POINT-IN-TIME AVAILABILITY", build_availability),
        ("questions.html", "Questions &amp; information gaps", "BEFORE ANY DECISION", build_questions),
        ("suggestions.html", "Suggestion board", "REVIEW AND CHOOSE", build_suggestions),
        ("sources.html", "Official sources", "VERIFICATION REGISTER", build_sources),
        ("flagged.html", "Flagged for review", "IRREGULARITIES", build_flagged),
        ("review.html", "Repository review", "LINE-BY-LINE", build_review),
    ]
    for slug, title, sub, fn in writers:
        body = fn(D, computed)
        with open(os.path.join(OUT, slug), "w", encoding="utf-8") as f:
            f.write(page.render(slug, title.replace("&amp;", "&"), sub, body))
        print(f"  wrote {slug}")
    with open(os.path.join(OUT, ".nojekyll"), "w") as f:
        f.write("")
    print(f"built {len(writers)} pages into {OUT}")
    return 0


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, float) and (o != o or math.isinf(o)):
        return None
    return o


# --------------------------------------------------------------------------- shared fragments
def status_banner(D: dict) -> str:
    files = D["files"]
    if not files:
        return ('<div class="notice warn"><b>No verified data snapshot yet.</b> The data refresh workflow '
                'has not produced <code>data/raw/manifest.json</code> on this branch. Every number below '
                'is therefore marked not established rather than estimated.</div>')
    newest = max(v.get("release_asset_updated_utc", "") for v in files.values())
    return (f'<div class="notice ok"><b>Data verified.</b> {len(files)} official release asset(s) matched '
            f'their GitHub-published SHA-256 digest; newest official asset timestamp {esc(newest)}. '
            f'{link("sources.html", "See the verification register →")}</div>')


def metrics_strip(computed: dict) -> str:
    line = computed.get("line", {})
    fam = computed.get("family", [])
    passing = [s for s in fam if s.get("status") == "passes all gates"]
    items = [
        ("OFFICIAL GAMES PARSED", fmt(computed.get("n_games_total"))),
        ("OUT-OF-SAMPLE GAMES", fmt(computed.get("preds_n"))),
        ("STRATEGIES TESTED", fmt(len(fam))),
        ("STRATEGIES PASSING ALL GATES", fmt(len(passing))),
    ]
    cells = "".join(f'<div><span>{esc(a)}</span><strong>{esc(b)}</strong></div>' for a, b in items)
    return f'<div class="metrics">{cells}</div>'


# --------------------------------------------------------------------------- pages
def build_index(D, C) -> str:
    line = C.get("line", {})
    fam = C.get("family", [])
    top = sorted([s for s in fam if s.get("n_bets")], key=lambda s: -(s["metrics"].get("z") or -99))[:3]
    rows = []
    for s in top:
        rows.append([esc(s["strategy"]), fmt(s["n_bets"]),
                     fmt(s["metrics"]["profit_per_unit"], 4),
                     fmt(s["metrics"]["ci95"][0], 4) + " to " + fmt(s["metrics"]["ci95"][1], 4),
                     badge(s["status"] == "passes all gates"),
                     link("strategies.html", "detail")])
    body = f"""
<h1>Original lines, measured honestly</h1>
<p class="lede">This desk originates its own NFL numbers from verified official data, then grades them
against the market's closing line. It is a measurement exercise: the leaderboard is designed to
reward skill and to reject luck, so most strategies are expected to fail.</p>
{status_banner(D)}
{metrics_strip(C)}
<div class="cards">
  <div class="card"><div class="kicker">LINE ORIGINATION</div><h3>Our number vs their number</h3>
    <p>Pre-game Elo and form, fitted only on prior seasons, produce an independent spread and total for
    every game. Both are compared with the closing line on mean absolute error, bias and correlation.</p>
    <a class="textlink" href="lines.html">Open line origination →</a></div>
  <div class="card"><div class="kicker">VALIDATION</div><h3>Seven gates before any claim</h3>
    <p>Sample size, profit confidence interval, multiple-testing control, selection-adjusted
    significance, season stability, closing-line value and a slippage stress test.</p>
    <a class="textlink" href="strategies.html">Open the leaderboard →</a></div>
  <div class="card"><div class="kicker">AVAILABILITY</div><h3>Starters and the men behind them</h3>
    <p>Official injury reports joined to that week's official depth chart show which starters are out
    and whether a 2nd, 3rd or 4th string player has to replace them.</p>
    <a class="textlink" href="availability.html">Open availability →</a></div>
  <div class="card"><div class="kicker">DECISIONS</div><h3>Questions before conclusions</h3>
    <p>A numbered register of what is known, what is missing, and what would have to be true before
    any change is implemented.</p>
    <a class="textlink" href="questions.html">Open the question register →</a></div>
</div>
<h2>Top of the leaderboard right now</h2>
<p class="sub">Ranked by the z-score of profit per unit over the out-of-sample window. A strategy is only
listed as passing when it clears all seven gates.</p>
{table(["Strategy", "Graded bets", "Profit / unit", "95% bootstrap CI", "All gates", "Detail"], rows,
       caption="Leaderboard extract · full family on the strategy page") if rows else
 '<p class="empty">No graded strategies yet — the data snapshot is missing.</p>'}
<div class="callout"><div><div class="kicker">BEFORE YOU READ A NUMBER</div>
<h2>What this desk will not do</h2>
<p>It will not claim an edge it cannot show, will not fill a blank to make a table look complete, and
will not treat a hot streak as skill. Every unconfirmed value is left blank and published on the
Flagged for Review page.</p></div>
<a class="button" href="executive-summary.html">Executive summary <span>↗</span></a></div>
"""
    return body


def build_summary(D, C) -> str:
    line = C.get("line", {})
    fam = C.get("family", [])
    corr = C.get("corr", {})
    passing = [s for s in fam if s.get("status") == "passes all gates"]
    best = max(fam, key=lambda s: (s["metrics"].get("z") if s["metrics"].get("z") == s["metrics"].get("z") else -99)) if fam else None
    eda = []
    if line.get("ok"):
        eda = [
            ("Games in the out-of-sample window", fmt(line["n_games"]),
             esc(f"{line['seasons'][0]}–{line['seasons'][1]}"), link(release_url("games.csv"), "games.csv")),
            ("Model spread MAE", fmt(line["model_mae_spread"]), "points, our number vs final margin",
             link(release_url("games.csv"), "games.csv")),
            ("Market spread MAE", fmt(line["market_mae_spread"]), "points, closing line vs final margin",
             link(release_url("games.csv"), "games.csv")),
            ("Model total MAE", fmt(line["model_mae_total"]), "points vs final total",
             link(release_url("games.csv"), "games.csv")),
            ("Market total MAE", fmt(line["market_mae_total"]), "points vs final total",
             link(release_url("games.csv"), "games.csv")),
            ("Correlation, our spread vs result", fmt(line["corr_model_result"], 3), "Pearson r",
             link(release_url("games.csv"), "games.csv")),
            ("Correlation, closing spread vs result", fmt(line["corr_market_result"], 3), "Pearson r",
             link(release_url("games.csv"), "games.csv")),
        ]
    body = f"""
<h1>Executive summary</h1>
<p class="lede">The state of the work in one page: what has been verified, what the numbers say, what
fails, and what must happen before any change is implemented.</p>
{status_banner(D)}
<h2>1 · What was built</h2>
<ul class="bullets">
<li><b>A verified data layer.</b> Official nflverse release assets are downloaded by CI and each file is
checked against the SHA-256 digest GitHub publishes for that asset. A digest mismatch stops the build.</li>
<li><b>An original-line engine.</b> A walk-forward model fits only on prior seasons, so every
out-of-sample prediction was made before the games it grades.</li>
<li><b>A validation regime.</b> Seven pre-registered gates, with multiple-testing and
selection-adjustment controls, applied to a fixed family of strategies.</li>
<li><b>An availability layer.</b> Official weekly injury reports joined to the same week's official
depth chart, so a starter listed Out is linked to the backup who replaced him.</li>
</ul>
<h2>2 · Headline findings</h2>
{table(["Finding", "Value", "Unit / definition", "Official source"], eda,
       caption="Computed from the verified snapshot. Blank cells are unverified, not zero.") if eda else
       '<p class="empty">No line study yet.</p>'}
<p class="sub">{esc(_finding_sentence(line))}</p>
<h2>3 · Strategy verdicts</h2>
<p>Of <b>{len(fam)}</b> pre-registered strategies, <b>{len(passing)}</b> clear all seven gates.
{"The strongest is <b>" + esc(best["strategy"]) + "</b> with " + fmt(best["n_bets"]) + " graded bets and a profit of " + fmt(best["metrics"]["profit_per_unit"], 4) + " per unit, but it still fails at least one gate." if best else "No strategy has a gradeable sample yet."}</p>
{table(["Strategy", "Bets", "Profit/unit", "z", "Gates passed", "Verdict", "Graded against"],
       [[esc(s["strategy"]), fmt(s["n_bets"]), fmt(s["metrics"]["profit_per_unit"], 4),
         fmt(s["metrics"]["z"]), f'{s["gates_passed"]}/{s["gates_total"]}',
         badge(s["status"] == "passes all gates"), link(release_url("games.csv"), "games.csv")] for s in fam],
       caption="Full detail, per-season splits and gate-by-gate reasons on the strategy page") if fam else ""}
<h2>4 · Correlation</h2>
<p class="sub">{esc(_corr_sentence(corr))}</p>
<h2>5 · What is still unknown</h2>
<p>The desk cannot yet price player props or parlay combinations on real joint outcomes, because no
verified, licensed player-prop history or player-prop closing line is in the snapshot. That gap is
recorded as a question with a named owner and the exact data needed, not estimated. See
{link("questions.html", "Questions &amp; gaps")} and {link("flagged.html", "Flagged for review")}.</p>
<h2>6 · Decision requested</h2>
<p>Choose a path from the {link("suggestions.html", "suggestion board")}. Each suggestion lists the
evidence for it, what it costs, what would falsify it, and the gate it must pass before it ships.</p>
"""
    return body


def _finding_sentence(line: dict) -> str:
    if not line.get("ok"):
        return "Line study unavailable."
    better = "better" if line["model_mae_spread"] < line["market_mae_spread"] else "worse"
    gap = abs(line["market_mae_spread"] - line["model_mae_spread"])
    return (f"Our spread model is {better} than the closing line by {gap:.2f} points of MAE "
            f"({line['model_mae_spread']:.2f} vs {line['market_mae_spread']:.2f}). "
            f"Read this as a benchmark, not an edge: closing lines are the toughest public number "
            f"and a model that merely matches them does not beat the vig.")


def _corr_sentence(corr: dict) -> str:
    s = corr.get("stacked") or {}
    if not s:
        return "Correlation not established."
    return (f"Across {s['n']:,} games, home win + market-favourite cover + over all landed together "
            f"{pct(s['p_triple_observed'])} of the time versus {pct(s['p_triple_if_independent'])} if "
            f"the three legs were independent — a lift of {s['lift']:.2f}x. Same-game legs must be "
            f"priced with a joint probability, not a product.")


def build_lines(D, C) -> str:
    line = C.get("line", {})
    if not line.get("ok"):
        return f'<h1>Line origination</h1><p class="empty">Not established: {esc(line.get("reason","data missing"))}.</p>'
    rows = []
    for s in line["by_season"]:
        rows.append([fmt(s["season"]), fmt(s["n"]), fmt(s["model_mae_spread"]), fmt(s["market_mae_spread"]),
                     fmt(s["model_rmse_spread"]), fmt(s["model_mae_total"]), fmt(s["market_mae_total"]),
                     fmt(s["corr_model_result"], 3), fmt(s["corr_market_result"], 3),
                     link(release_url("games.csv"), "games.csv")])
    coef = []
    for c in line["coefficients"]:
        b = c["beta_spread"]
        coef.append([fmt(c["season"]), fmt(c["n_train_games"]), fmt(b[0], 4), fmt(b[1], 4),
                     fmt(b[2], 4), fmt(b[3], 4), fmt(c["league_total_train"]),
                     link(release_url("games.csv"), "games.csv")])
    ats = line.get("ats", {})
    ou = line.get("ou", {})
    grade_rows = []
    for st, lbl in ((ats, "Spread disagreement"), (ou, "Total disagreement")):
        if st.get("ok"):
            grade_rows.append([esc(lbl), fmt(st["n"]), fmt(st["profit_per_unit"], 4),
                               f'{fmt(st["ci95"][0], 4)} to {fmt(st["ci95"][1], 4)}',
                               pct(st["hit_rate"]), fmt(st["z"]), link(release_url("games.csv"), "games.csv")])
    body = f"""
<h1>Line origination: our number versus the market</h1>
<p class="lede">Every game gets an independent spread and total from a transparent model. The model is
refitted each season on earlier seasons only, so the numbers below are genuinely out of sample.</p>
<div class="notice ok">Definition of our spread: positive means the <b>home team is favoured</b>, matching
the official schedule schema. Model inputs: pre-game Elo, prior-six-game scoring-margin form, rest
differential and a home-field term. Totals: prior-six-game points for and against on both sides of
the ball, blended with the league's scoring level.</div>
<h2>Accuracy by season</h2>
{table(["Season", "Games", "Our spread MAE", "Closing spread MAE", "Our spread RMSE",
        "Our total MAE", "Closing total MAE", "r(our, result)", "r(closing, result)", "Source"],
       rows, caption="MAE and RMSE in points. r is Pearson correlation with the actual result.")}
<h2>Overall, out of sample</h2>
{table(["Metric", "Our model", "Closing market", "Source"],
       [["Mean absolute error, spread", fmt(line["model_mae_spread"]), fmt(line["market_mae_spread"]), link(release_url("games.csv"), "games.csv")],
        ["Root mean square error, spread", fmt(line["model_rmse_spread"]), fmt(line["market_rmse_spread"]), link(release_url("games.csv"), "games.csv")],
        ["Mean absolute error, total", fmt(line["model_mae_total"]), fmt(line["market_mae_total"]), link(release_url("games.csv"), "games.csv")],
        ["Mean signed bias, spread", fmt(line["model_bias_spread"]), fmt(line["market_bias_spread"]), link(release_url("games.csv"), "games.csv")],
        ["Mean signed bias, total", fmt(line["model_bias_total"]), fmt(line["market_bias_total"]), link(release_url("games.csv"), "games.csv")],
        ["Pearson r with result", fmt(line["corr_model_result"], 3), fmt(line["corr_market_result"], 3), link(release_url("games.csv"), "games.csv")]],
       caption="A lower MAE is better. The closing market is the benchmark to beat.")}
<h2>What the model coefficients look like</h2>
<p class="sub">Published so the model can be audited rather than trusted. Coefficients are in points per
unit of the feature (Elo difference divided by 100, form difference divided by 7 points).</p>
{table(["Season fitted", "Training games", "Intercept", "Elo diff", "Form diff", "Rest diff",
        "Training league total", "Source"], coef,
       caption="Walk-forward refits: each row was fitted only on seasons before it")}
<h2>Grading the disagreements at the market's own price</h2>
<p class="sub">A bet is only taken when our number is more than 0.5 points away from the closing line.
Profit is per unit staked, graded at the market's actual price for that side, pushes excluded from
the win rate but kept at zero profit.</p>
{table(["Signal", "Graded bets", "Profit / unit", "95% bootstrap CI", "Cover/win rate", "z", "Source"],
       grade_rows, caption="Out-of-sample graded results. This is a measurement, not a recommendation.")}
<p class="sub">{esc(_line_verdict(line))}</p>
"""
    return body


def _line_verdict(line: dict) -> str:
    ats = line.get("ats", {})
    if not ats.get("ok"):
        return "No graded disagreements."
    m = ats["profit_per_unit"]
    ci = ats["ci95"]
    if ci[0] > 0:
        return f"Positive profit of {m:.4f} per unit with a confidence interval above zero: this clears gate G2 and continues to the family-wide tests."
    return (f"Profit of {m:.4f} per unit with a 95% interval of {ci[0]:.4f} to {ci[1]:.4f}, which "
            f"straddles zero. The signal is not distinguishable from luck at this sample size — the "
            f"correct action is to keep testing, not to bet.")


def build_strategies(D, C) -> str:
    fam = C.get("family", [])
    if not fam:
        return '<h1>Strategy leaderboard</h1><p class="empty">Not established: no gradable strategies yet.</p>'
    rows = []
    for s in sorted(fam, key=lambda x: -(x["metrics"].get("z") if x["metrics"].get("z") == x["metrics"].get("z") else -99)):
        m = s["metrics"]
        rows.append([esc(s["strategy"]), esc(s["family"]), fmt(s["n_bets"]), fmt(m["profit_per_unit"], 4),
                     f'{fmt(m["ci95"][0], 4)} to {fmt(m["ci95"][1], 4)}', fmt(m["z"]),
                     fmt(m.get("bh_adjusted_p")), fmt(m["deflated_threshold_z"]),
                     f'{s["gates_passed"]}/{s["gates_total"]}', badge(s["status"] == "passes all gates"),
                     link(release_url("games.csv"), "games.csv")])
    detail = []
    for s in fam:
        g = s["gates"]
        gates_html = "".join(
            f'<li><b>{k}</b> {badge(v)} <span class="dim">{esc(GATE_TEXT.get(k.split("_")[0], ""))}</span></li>'
            for k, v in g.items())
        detail.append(f"""
<div class="strategy">
  <h3>{esc(s["strategy"])} <span class="dim">· {esc(s["family"])} family · {fmt(s["n_bets"])} bets</span></h3>
  <div class="stratgrid">
    <div><span>Profit / unit</span><strong>{fmt(s["metrics"]["profit_per_unit"], 4)}</strong></div>
    <div><span>z-score</span><strong>{fmt(s["metrics"]["z"])}</strong></div>
    <div><span>Required z</span><strong>{fmt(s["metrics"]["deflated_threshold_z"])}</strong></div>
    <div><span>Positive seasons</span><strong>{pct(s["metrics"]["positive_season_share"])}</strong></div>
    <div><span>1st half / 2nd half</span><strong>{fmt(s["metrics"]["half_profit"].get("H1"), 4)} / {fmt(s["metrics"]["half_profit"].get("H2"), 4)}</strong></div>
    <div><span>Stress (−10% price)</span><strong>{fmt(s["metrics"]["stress10_profit_per_unit"], 4)}</strong></div>
  </div>
  <ul class="gate-list">{gates_html}</ul>
  <p class="verdict">{esc(_verdict_text(s))}</p>
</div>""")
    body = f"""
<h1>Strategy leaderboard</h1>
<p class="lede">A fixed family of strategies, pre-registered before results were inspected, graded on the
same out-of-sample games. Rewards are proposed to follow gate completion, not headline profit.</p>
<div class="notice warn"><b>How to read this.</b> The leaderboard exists to reject strategies. A
strategy is only "passing" when all seven gates clear; everything else is a candidate in testing and
is not a betting recommendation.</div>
{table(["Strategy", "Family", "Bets", "Profit/unit", "95% CI", "z", "BH-adj p",
        "Required z", "Gates", "Verdict", "Source"], rows,
       caption="Sorted by z-score. Required z is the deflated-Sharpe threshold for the number of attempts.")}
<h2>Gate-by-gate detail</h2>
{"".join(detail)}
<h2>Reward design</h2>
<p class="sub">Rewards are tied to gate completion, never to raw profit, so a lucky streak earns nothing:</p>
{table(["Reward tier", "Requirement", "Why this cannot be gamed by luck"],
       [["Candidate", "G1 sample size met", "A small sample cannot pass, so a hot start earns nothing."],
        ["Qualified", "G2 profit CI above zero", "The interval must exclude zero, not just the point estimate."],
        ["Verified", "G3 + G4 multiple-testing and selection gates", "Corrects for how many strategies were tried; a lucky winner from a large search does not qualify."],
        ["Durable", "G5 stability + G6 closing-line value", "Requires repeatability across seasons and halves, and beating the closing number."],
        ["Deployable", "G7 slippage stress", "Must survive a 10% worse price, so thin edges are filtered out."],
        ["Champion", "All seven, sustained next season", "Out-of-sample survival in a season it never saw."]],
       cls="data method",
       caption="Proposal - requires a decision on the suggestion board before any reward is paid")}
"""
    return body


GATE_TEXT = {
    "G1": "minimum sample of graded bets from digest-verified data",
    "G2": "mean profit > 0 with a 95% block-bootstrap CI above zero",
    "G3": "survives Benjamini-Hochberg control across the strategy family",
    "G4": "z exceeds the deflated-Sharpe threshold for the number of attempts",
    "G5": "positive in >= 60% of seasons and in both halves",
    "G6": "positive closing-line value with a CI above zero",
    "G7": "survives a 10% worse average price",
}


def _verdict_text(s: dict) -> str:
    failed = [k for k, v in s["gates"].items() if not v]
    if not failed:
        return "Passes every gate. Eligible for the reward tier ladder."
    names = ", ".join(GATE_TEXT.get(k.split("_")[0], k).split(",")[0] for k in failed)
    return f"Fails {len(failed)} gate(s): {names}. Not eligible for a reward or a real stake."


def build_correlation(D, C) -> str:
    corr = C.get("corr", {})
    if not corr.get("rows"):
        return '<h1>Correlation</h1><p class="empty">Not established: no graded games yet.</p>'
    rows = []
    for r in corr["rows"]:
        rows.append([esc(r["pair"]), fmt(r["n"]), fmt(r["phi"], 4),
                     f'{fmt(r["ci95"][0], 4)} to {fmt(r["ci95"][1], 4)}', fmt(r["p_value"], 4),
                     fmt(r["n_both"]), fmt(r["n_a_only"]), fmt(r["n_b_only"]), fmt(r["n_neither"]),
                     link(release_url("games.csv"), "games.csv")])
    s = corr.get("stacked") or {}
    stack_rows = []
    if s:
        src = link(release_url("games.csv"), "games.csv")
        stack_rows = [
            ["Home win, favourite cover and over all landed", pct(s["p_triple_observed"]), "observed joint rate", src],
            ["If the three legs were independent", pct(s["p_triple_if_independent"]), "p(win) × p(cover) × p(over)", src],
            ["Overstatement from naive multiplication", pct(s["overstatement"]), "absolute percentage points", src],
            ["Lift factor", fmt(s["lift"], 3), "observed ÷ independent", src],
            ["Home win rate", pct(s["p_home_win"]), "single leg", src],
            ["Market-favourite cover rate", pct(s["p_fav_cover"]), "single leg", src],
            ["Over rate", pct(s["p_over"]), "single leg", src],
        ]
    body = f"""
<h1>Correlation between legs</h1>
<p class="lede">Parlays and same-game combinations are only worth pricing when the joint outcome is
measured, not assumed. Every number here comes from {fmt(corr.get("n_games"))} settled games.</p>
<div class="notice ok">Method: each leg is graded as a settled binary outcome (cover, over/under,
moneyline win). Dependence is the phi coefficient — Pearson correlation between the two 0/1 legs —
with a 95% Fisher-z interval. Pushes are excluded from that pair.</div>
<h2>Measured dependence between legs</h2>
{table(["Leg pair", "Games", "Phi", "95% CI", "p-value", "Both win", "A only", "B only",
        "Neither", "Source"], rows,
       caption="Phi of 0 means the legs behaved independently in this sample")}
<h2>The specific case that breaks naive parlay maths</h2>
<p class="sub">A same-game parlay of home moneyline + home spread + over is the standard product
offered on a game. Multiply the three single-leg probabilities and the combined chance is overstated.
This table measures the first two legs directly.</p>
{table(["Quantity", "Value", "Definition", "Source"], stack_rows)}
<h2>What this means for pricing</h2>
<ul class="bullets">
<li>Two legs in the <b>same game</b> must be priced with a joint probability, not a product. The lift
factor above is the size of the correction found in this sample.</li>
<li>Legs in <b>different games</b> can be treated as independent for pricing, but the sportsbook's own
parlay multiplier still applies its hold on top.</li>
<li>Player-prop combinations need player-level joint outcomes that are <b>not in this snapshot</b>.
That is an open question with a named data requirement, published on the Questions page.</li>
</ul>
"""
    return body


def build_availability(D, C) -> str:
    inj = C.get("injury", {})
    if not inj.get("ok"):
        return f'<h1>Injuries &amp; backup depth</h1><p class="empty">Not established: {esc(inj.get("reason","no report"))}.</p>'
    snap_rows = []
    for r in inj.get("snapshot", []):
        snap_rows.append([
            fmt(r["week"]), esc(r["gameday"]), f'{esc(r["away"])} @ {esc(r["home"])}',
            fmt(r["spread_line"]), fmt(r["total_line"]),
            fmt(r["home_out_off"]), fmt(r["home_out_def"]), fmt(r["away_out_off"]), fmt(r["away_out_def"]),
            f'{fmt(r["home_q_def"])} / {fmt(r["away_q_def"])}',
            link("https://www.nfl.com/injuries/", "NFL injury report"),
            link(release_url("depth_charts_2026.csv"), "depth chart")])
    stats_rows = []
    for key, label in (("market_vs_def_injuries", "Market spread vs defensive starters out"),
                       ("market_vs_off_injuries", "Market spread vs offensive starters out"),
                       ("result_vs_def_injuries", "Result vs market vs defensive starters out"),
                       ("result_vs_off_injuries", "Result vs market vs offensive starters out"),
                       ("total_vs_off_injuries", "Game total vs combined offensive starters out")):
        v = inj.get(key)
        if v:
            stats_rows.append([esc(label), fmt(v["n"]), fmt(v["r"], 4),
                               f'{fmt(v["ci95"][0], 4)} to {fmt(v["ci95"][1], 4)}',
                               link("https://www.nfl.com/injuries/", "NFL injury report")])
    body = f"""
<h1>Injuries and backup depth</h1>
<p class="lede">Which starters are out, who is behind them on the official depth chart, and whether the
market already knows.</p>
<div class="notice ok"><b>How availability is measured.</b> The official weekly injury report gives each
player's game status (Out, Doubtful, Questionable). The same week's official depth chart gives each
player's depth slot (1 = starter, 2/3/4 = backups). Joining them on player name and team-week produces
"starters listed Out" per side of the ball — the input a replacement-quality model needs.</div>
<h2>Current week at a glance</h2>
{table(["Week", "Date", "Matchup", "Closing spread", "Closing total", "Home OFF starters out",
        "Home DEF starters out", "Away OFF starters out", "Away DEF starters out",
        "Questionable DEF (home / away)", "Injury source", "Depth source"], snap_rows,
       caption="Starters = players at depth slot 1 on that week's official chart who are listed Out or Doubtful")}
<h2>Does the market already price starter absences?</h2>
<p class="sub">A correlation between the availability differential and the market's deviation from the
pre-game Elo expectation. A large, correctly-signed value means the market already moves for injuries;
a near-zero value would mean the information is not priced — the signal worth chasing.</p>
{table(["Relationship", "Games", "Pearson r", "95% CI", "Official source"], stats_rows,
       caption="Single-season sample; treat as a first look, not a validated signal")}
<h2>Backup-depth watchlist</h2>
<p class="sub">Starters listed Out, with the next man up from the same official depth chart. A blank
backup means the depth chart does not list a replacement at that slot — recorded as unverified rather
than inferred.</p>
{_backup_watchlist(D, inj)}
<h2>What is missing</h2>
<ul class="bullets">
<li>Historical <b>snap-share</b> evidence for backups is fetched (2026 snap counts) but joining it to
replacement performance needs a player-level graded dataset that is not in this snapshot.</li>
<li>Injury <b>severity</b> and expected games missed is not a field in the official report. Any estimate
would be a model output and must be labelled as such.</li>
</ul>
"""
    return body


def _backup_watchlist(D, inj) -> str:
    depth = D.get("depth")
    inj_rows = D.get("injuries") or []
    if not depth or not inj_rows:
        return '<p class="empty">Depth chart or injury report not in the snapshot.</p>'
    week = inj.get("current_week", 0)
    # build (team, position) -> ordered depth slots for the week
    chart = collections.defaultdict(list)
    for r in depth:
        chart[(features.canon(r.get("team", "")), r.get("pos", ""))].append(r)
    out_rows = []
    seen = set()
    for r in inj_rows:
        if int(r["week"]) != week or r["report_status"] not in ("Out", "Doubtful"):
            continue
        team = features.canon(r["team"])
        pos = (r.get("position") or "").upper()
        key = (team, pos, r["name"])
        if key in seen:
            continue
        seen.add(key)
        # find the player's own depth rank
        mine = None
        for rec in depth:
            if features.canon(rec.get("team", "")) == team and (rec.get("name") or "").lower() == (r["name"] or "").lower() and rec.get("pos") == pos:
                mine = rec
                break
        rank = mine.get("rank") if mine else None
        backup = None
        if rank is not None and rank == mine.get("rank"):
            candidates = [c for c in chart.get((team, pos), [])
                          if c.get("rank") is not None and c["rank"] > (rank or 0)]
            candidates.sort(key=lambda c: (c["rank"], c.get("name") or ""))
            if candidates:
                backup = candidates[0].get("name")
        out_rows.append([esc(team), esc(pos), esc(r["name"]), esc(r.get("report_injury") or "—"),
                         fmt(rank), esc(backup) if backup else unverified("depth chart lists no replacement"),
                         link("https://www.nfl.com/injuries/", "NFL injury report"),
                         link(release_url("depth_charts_2026.csv"), "depth chart")])
    if not out_rows:
        return '<p class="empty">No starters listed Out or Doubtful on the current week\'s report.</p>'
    return table(["Team", "Pos", "Starter listed out", "Injury", "Depth slot", "Next man up",
                  "Injury source", "Depth source"], out_rows[:80],
                 caption="Depth slot 1 is the starter. Next man up is the next player at the same position on the official chart.")




# --------------------------------------------------------------------------- pages 07-11
import _pages_tail
build_questions = _pages_tail.build_questions
build_suggestions = _pages_tail.build_suggestions
build_sources = _pages_tail.build_sources
build_flagged = _pages_tail.build_flagged
build_review = _pages_tail.build_review


if __name__ == "__main__":
    sys.exit(main())
