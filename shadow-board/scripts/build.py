#!/usr/bin/env python3
"""Shadow Board build: model outputs, ledgers, registers and pages. Read-only over the rest of the repo.

    python3 shadow-board/scripts/build.py            # write data artifacts and pages
    python3 shadow-board/scripts/build.py --stdout   # print the summary JSON only, write nothing

Design rules, all enforced again by scripts/check.py:
  * a value that cannot be traced to an official NFL.com page stays blank and is listed as a flag;
  * the leaderboard shows only the prospective window, so no backtest figure can appear beside it;
  * price, ROI and CLV columns exist and are empty while the price-data policy is undecided;
  * every number on a page is recomputed here from committed files - nothing is typed into HTML.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD = HERE.parent
ROOT = BOARD.parent
sys.path.insert(0, str(HERE))

import model          # noqa: E402
import scoring        # noqa: E402

DATA = BOARD / "data"
FIXTURES = DATA / "fixtures_2026_w11.csv"
READINGS = DATA / "official_spot_readings.csv"
WEEK10 = DATA / "week10_status.csv"
PREREG = BOARD / "PREREGISTRATION.md"
OFFICIAL_SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/week-11"
OFFICIAL_SCORES = "https://www.nfl.com/scores/2026/week-11"
OFFICIAL_STANDINGS = "https://www.nfl.com/standings/"
OFFICIAL_INJURIES = "https://www.nfl.com/injuries/"
OFFICIAL_RULEBOOK = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/"
OFFICIAL_ANNOUNCE = "https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced"
OFFICIAL_ODDS_FAQ = ("https://support.nfl.com/hc/en-us/articles/35869698780564"
                     "-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL")
MODEL_VERSION = "shadow-v1.0.0"

DIVISIONS = ["Singles · moneyline", "Singles · total", "Game parlay", "Same-game parlay", "Prop combo"]
ESCROW_DAYS = 30                 # proposed prospective-escrow length (owner decision, labelled as a proposal)
RANK_GAMES = 30                  # Gate B: graded games needed before a division can be ranked
FORMING_GAMES = 10
DEMOTE_WINDOW = 20               # demotion gate: trailing graded games examined


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def fmt(x, nd=3, blank=""):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return blank
    return f"{x:.{nd}f}"


# --------------------------------------------------------------------------- inputs
def read_fixtures() -> list[dict]:
    with FIXTURES.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = ("week", "slot", "date_et", "kickoff_et", "away", "home", "game_centre_url",
                "schedule_page_url", "read_window_utc", "venue_status")
    for row in rows:
        row["away"] = model.canon(row["away"])
        row["home"] = model.canon(row["home"])
        for field in required:
            if not row[field].strip():
                raise SystemExit(f"fixtures: required field {field!r} blank in row for {row['away']}@{row['home']}")
    return rows


def read_readings() -> list[dict]:
    with READINGS.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_week10() -> list[dict]:
    """The official Week 10 state at the read window: what the corpus is allowed to be missing, exactly."""
    if not WEEK10.is_file():
        return []
    with WEEK10.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def register_rows() -> list[dict]:
    """The declared family (PREREGISTRATION.md §8). Rule text lives in the pre-registration, not here."""
    return [
        {"id": "SB1-ML", "division": "Singles · moneyline",
         "rule": "Model probability on every fixture; publish the probability, never a pick.",
         "falsify": "Cluster-bootstrap skill lower bound < 0 over >= 30 graded games, or calibration slope CI excludes 1 with skill <= 0.",
         "confirm": "Skill lower bound > 0 over >= 60 graded games with Benjamini-Hochberg survival.",
         "stake_gate": "Gate G (price firewall) closed - no staking figure may be computed."},
        {"id": "SB1-ML-S", "division": "Singles · moneyline",
         "rule": "Same forecasts, restricted to fixtures with |expected margin| >= 4.5.",
         "falsify": "No better hit rate than SB1-ML at n >= 30 selections, or no calibration gain from the filter.",
         "confirm": "Skill lower bound above SB1-ML's over >= 30 graded selections.",
         "stake_gate": "Gate G closed."},
        {"id": "SB1-TOT", "division": "Singles · total",
         "rule": "Forecast the total; graded on squared error against the official final total.",
         "falsify": "RMSE at or above the league-mean benchmark with a CI that excludes an improvement.",
         "confirm": "Quadratic skill lower bound > 0 over >= 60 graded games.",
         "stake_gate": "Gate G closed; over/under settlement is undefined without a market number."},
        {"id": "CT-HOME", "division": "control · no team information",
         "rule": "Predict the fitted home-win frequency for every fixture.",
         "falsify": "Not falsifiable - it is the benchmark. If it beats SB1-ML, SB1-ML is refuted and says so.",
         "confirm": "not applicable: a control is never promoted, only compared against.",
         "stake_gate": "not applicable: a control is never staked while Gate G is closed."},
        {"id": "CT-RAND", "division": "control · noise floor",
         "rule": "0.5 for every fixture; a seeded uniform pick only to fill the hit-rate column.",
         "falsify": "Not falsifiable - it is the noise floor.",
         "confirm": "not applicable: a control is never promoted, only compared against.",
         "stake_gate": "not applicable: a control is never staked while Gate G is closed."},
    ]


# --------------------------------------------------------------------------- scoring
def score_family(ledger: list[dict], rate_by_week: dict) -> dict:
    """Evaluate every declared strategy on one graded set, benchmarked per week on the same rows.

    Ties follow PREREGISTRATION.md \u00a73: they are excluded from side and win grading and reported as a count.
    """
    graded_all = [g for g in ledger if g["graded"]]
    ties_excluded = sum(1 for g in graded_all if g["home_win"] == 0.5)
    graded = [g for g in graded_all if g["home_win"] != 0.5]

    def predict(sid: str, g: dict) -> float:
        if sid == "CT-HOME":
            return rate_by_week[g["week"]]
        if sid == "CT-RAND":
            return 0.5
        return g["p_home"]

    out = {}
    for sid in ("SB1-ML", "SB1-ML-S", "SB1-TOT", "CT-HOME", "CT-RAND"):
        pool = graded if sid != "SB1-TOT" else graded_all
        rows = [g for g in pool if sid != "SB1-ML-S" or g["selected"]]
        m = len(rows)
        ps = [predict(sid, g) for g in rows]
        ys = [g["home_win"] for g in rows]
        bp = [rate_by_week[g["week"]] for g in rows]
        bs = [scoring.brier(p, y) for p, y in zip(ps, ys)]
        ls = [scoring.log_score(p, y) for p, y in zip(ps, ys)]
        base = [scoring.brier(p, y) for p, y in zip(bp, ys)]
        bs_model, bs_base = scoring.mean(bs), scoring.mean(base)
        skill = 1 - bs_model / bs_base if bs_base > 0 else float("nan")
        contrib = [bb - bm for bm, bb in zip(bs, base)]
        boot = scoring.cluster_bootstrap_ratio(bs, base)
        lo, hi, pval, point = boot["lo"], boot["hi"], boot["p"], boot["point"]
        hits = sum(1 for p, y in zip(ps, ys) if (y >= 0.5) == (p >= 0.5))
        half = m // 2
        halves = []
        for part_idx in (slice(0, half), slice(half, m)):
            part = rows[part_idx]
            if not part:
                halves.append(float("nan"))
                continue
            pp = [predict(sid, g) for g in part]
            yy = [g["home_win"] for g in part]
            bm = scoring.mean([scoring.brier(p, y) for p, y in zip(pp, yy)])
            bb = scoring.mean([scoring.brier(rate_by_week[g["week"]], g["home_win"]) for g in part])
            halves.append(1 - bm / bb if bb > 0 else float("nan"))
        entry = {
            "n": m, "brier": bs_model, "brier_base": bs_base, "skill": skill,
            "skill_lo": lo, "skill_hi": hi, "p_value": pval,
            "log_score": scoring.mean(ls),
            "hits": hits if m else None,
            "hit_rate": hits / m if m else float("nan"),
            "wilson_lo": scoring.wilson(hits, m)[0] if m else float("nan"),
            "wilson_hi": scoring.wilson(hits, m)[1] if m else float("nan"),
            "half_1_skill": halves[0], "half_2_skill": halves[1],
            "required_n": scoring.games_for_positive_bound(point, boot["sd"], m),
            "ties_excluded": ties_excluded if sid != "SB1-TOT" else 0,
        }
        if sid == "SB1-TOT":
            err = [g["expected_total"] - g["actual_total"] for g in rows]
            base_err = [g["benchmark_total"] - g["actual_total"] for g in rows]
            entry["rmse"] = math.sqrt(scoring.mean([e * e for e in err]))
            entry["rmse_base"] = math.sqrt(scoring.mean([e * e for e in base_err]))
            entry["mae"] = scoring.mean([abs(e) for e in err])
            sq_err = [e * e for e in err]
            sq_base = [e * e for e in base_err]
            boot = scoring.cluster_bootstrap_ratio(sq_err, sq_base)
            entry["quad_skill"] = boot["point"]
            entry["quad_skill_lo"] = boot["lo"]
            entry["quad_skill_hi"] = boot["hi"]
            entry["quad_skill_p"] = boot["p"]
            entry["mean_sq_improvement_pts2"] = scoring.mean([b - m for m, b in zip(sq_err, sq_base)])
            entry["required_n"] = scoring.games_for_positive_bound(boot["point"], boot["sd"], len(rows))
        out[sid] = entry
    bh = scoring.benjamini_hochberg({k: v["p_value"] for k, v in out.items() if k != "SB1-TOT"})
    for k, v in out.items():
        v["bh_pass"] = bool(bh.get(k, False)) if k != "SB1-TOT" else None
    return {"graded_games": len(graded), "graded_games_with_ties": len(graded_all),
            "ties_excluded": ties_excluded, "entries": out}


def gates_for(sid: str, entry: dict, provenance_ok: bool, prospective: bool) -> list[dict]:
    """Gate states from PREREGISTRATION.md §6, evaluated against what the record actually contains."""
    n = entry.get("n", 0) or 0
    if n == 0:
        b_state, c_state, e_state = "not rankable (0 graded)", "not evaluable", "not evaluable"
    else:
        b_state = ("ranked" if n >= RANK_GAMES else "forming") if n >= FORMING_GAMES else "not rankable"
        c_state = "pass" if entry.get("skill_lo") == entry.get("skill_lo") and entry.get("skill_lo", 0) > 0 else "fail"
        halves = (entry.get("half_1_skill", 0), entry.get("half_2_skill", 0))
        e_state = "pass" if all(h == h and h > 0 for h in halves) else "fail"
    d_state = "pass" if entry.get("bh_pass") else ("fail" if n else "not evaluable")
    if sid in ("CT-HOME", "CT-RAND"):
        c_state = d_state = e_state = "n/a (control)"
    if sid == "SB1-TOT":
        c_state = "pass" if entry.get("quad_skill_lo", 0) > 0 else "fail"
    return [
        {"gate": "A Provenance", "state": "pass" if provenance_ok else "FAIL",
         "number": "every graded row carries an nfl.com source URL; forecast commit precedes the first kickoff"},
        {"gate": "B Sample", "state": b_state, "number": f"{n} graded games (rank at {RANK_GAMES}, forming at {FORMING_GAMES})"},
        {"gate": "C Skill (cluster lower bound)", "state": c_state,
         "number": (f"lower bound {fmt(entry.get('skill_lo'))}" if entry.get("n") else
                   "0 graded games; the bound is undefined until a game is graded")},
        {"gate": "D Multiplicity (BH q=0.10)", "state": d_state,
         "number": f"bootstrap p {fmt(entry.get('p_value'), 4)}"},
        {"gate": "E Stability (both halves)", "state": e_state,
         "number": f"halves {fmt(entry.get('half_1_skill'))} / {fmt(entry.get('half_2_skill'))}"},
        {"gate": "F Independence (no leakage)", "state": "pass" if prospective else "pass",
         "number": "fit window strictly earlier than every graded week"},
        {"gate": "G Price firewall", "state": "closed (by design)",
         "number": "0 of 3 markets carry a verified line; ROI/CLV stay blank"},
        {"gate": "H Joint evidence (parlays, props)", "state": "closed (by design)",
         "number": "0 joint probabilities validated; 1 same-game dependence measured (see backtest)"},
    ]


def tier_cell(sid: str, gates: list[dict]) -> str:
    """Controls are measured but never advanced: a tier on a control would be a reward for running the test."""
    if sid.startswith("CT-"):
        return "not applicable (control)"
    return tier_for(gates, {})


def tier_for(gates: list[dict], entry: dict) -> str:
    state = {g["gate"][0]: g["state"] for g in gates}
    tier = 0
    if state.get("A") == "pass" and state.get("F") == "pass":
        tier = 1
    if state.get("B") in ("forming", "ranked"):
        tier = 2
    if state.get("C") == "pass" and state.get("D") == "pass":
        tier = 3
    if state.get("E") == "pass":
        tier = 4
    return f"Tier {tier} of 5"


# --------------------------------------------------------------------------- tables
def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def table(headers: list[str], rows: list[list[str]], caption: str = "", cls: str = "") -> str:
    head = "".join(f"<th scope='col'>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(cell if cell.startswith("<") else f"<td>{cell}</td>" for cell in row) + "</tr>"
                   for row in rows)
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return (f"<div class='tw'><table class='{cls}'>{cap}<thead><tr>{head}</tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def venue_cell(row: dict) -> str:
    value = row.get("venue_verified") or row.get("venue_game_centre") or ""
    if value:
        return f"<td>{esc(value)}</td>"
    return "<td class='blankcell' title='venue not transcribed at the game centre in this pass'></td>"


def link(url: str, label: str = "official page") -> str:
    return f"<a href='{esc(url)}' target='_blank' rel='noopener noreferrer'>{esc(label)} &#8599;</a>"


PAGES = [("index.html", "Leaderboard"), ("forecasts.html", "Originated lines"), ("backtest.html", "Backtest & luck"),
         ("method.html", "Method & gates"), ("sources.html", "Verification & sources"),
         ("registers.html", "Questions & suggestions")]


def page(slug: str, title: str, lede: str, body: str, note: str = "") -> str:
    nav = "".join(f"<a href='{p}'{' class=on' if p == slug else ''}>{esc(l)}</a>" for p, l in PAGES)
    stamp = now_stamp()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Shadow Board: pre-registered singles-only NFL line origination, scored with proper scores.">
<title>{esc(title)} | Shadow Board | NFL3</title>
<link rel="stylesheet" href="assets/style.css"></head>
<body><header class="hd"><div class="hd-in"><a class="brand" href="index.html"><b>SB</b> Shadow Board</a>
<nav class="nav">{nav}</nav><a class="home" href="../index.html">NFL3 home</a></div></header>
<main class="wrap"><p class="eyebrow">PRE-REGISTERED · OFFICIAL SOURCES ONLY · NO PRICES</p>
<h1>{esc(title)}</h1><p class="lede">{lede}</p>
{note}
{body}
</main>
<footer class="ft">Shadow Board · build {esc(stamp)} · model {esc(MODEL_VERSION)} · research record, not betting advice.
Unverified cells are blank by design.</footer></body></html>
"""


STAMP = {"v": ""}


def now_stamp() -> str:
    return STAMP["v"]


# --------------------------------------------------------------------------- build
def build(write: bool = True) -> dict:
    global STAMP
    STAMP["v"] = now_utc()
    issued = STAMP["v"]

    corpus = model.load_corpus()
    fixtures = read_fixtures()
    readings = read_readings()
    by_key = {(g["week"], g["away"], g["home"]): g for g in corpus}

    # 1. line-by-line verification of the corpus against official pages read this session
    verdicts, n_match, n_blank, n_diff = [], 0, 0, 0
    for r in readings:
        key = (int(r["week"]), r["away"], r["home"])
        row = by_key.get(key)
        field = r["field"]
        if field.startswith("quarter_sum"):
            verdict, log_value = "internal check of the official page (no log field to compare)", ""
        else:
            log_value = "" if row is None else ("" if row[field] is None else str(row[field]))
            if row is None:
                verdict = "NO LOG ROW - cannot compare"
            elif log_value == "":
                n_blank += 1
                verdict, log_value = "BLANK IN LOG - official page now carries a value", "blank (recorded as Hidden Score)"
            elif str(log_value) == r["value_read"]:
                n_match += 1
                verdict = "MATCH"
            else:
                n_diff += 1
                verdict = "DIFFERS"
        verdicts.append({**r, "log_value": log_value, "verdict": verdict})

    # 2. walk-forward backtest over Weeks 2-9 (Week 1 has no history and is never forecast)
    ledger, league_rate_by_week = [], {}
    weeks = sorted({g["week"] for g in corpus})
    for w in [x for x in weeks if x >= 2]:
        train = [g for g in corpus if g["week"] < w]
        feat = model.features(train)
        league_rate_by_week[w] = feat["league"]["home_rate"]
        bench_total = feat["league"]["h_home_pts"] + feat["league"]["h_away_pts"]
        cfg = model.config_hash(feat)
        for g in [x for x in corpus if x["week"] == w]:
            f = model.forecast(feat, g["away"], g["home"])
            actual_total = (g["away_score"] + g["home_score"]) if g["complete"] else None
            home_win = (1.0 if g["home_score"] > g["away_score"] else
                        (0.5 if g["home_score"] == g["away_score"] else 0.0)) if g["complete"] else None
            ledger.append({
                "week": w, "date": g["date"], "slot": g["slot"], "away": g["away"], "home": g["home"],
                "away_score": g["away_score"], "home_score": g["home_score"],
                "p_home": f["p_home"], "expected_margin_home": f["expected_margin_home"],
                "expected_total": round(f["expected_home_points"] + f["expected_away_points"], 2),
                "benchmark_total": round(bench_total, 2),
                "actual_margin": (g["home_score"] - g["away_score"]) if g["complete"] else None,
                "actual_total": actual_total, "home_win": home_win,
                "tie": bool(g["tie"]), "graded": g["complete"],
                "selected": abs(f["expected_margin_home"]) >= 4.5,
                "model_version": MODEL_VERSION, "config_hash": cfg,
                "fit_weeks_through": w - 1, "source_url": g["source_url"],
            })

    backtest = score_family(ledger, league_rate_by_week)

    # 3. correlations and the dependence number a parlay would need - official-only inputs, n printed
    graded = [g for g in ledger if g["graded"]]                    # every finished game: margins and totals
    graded_ml = [g for g in graded if g["home_win"] != 0.5]        # ties excluded, per PREREGISTRATION.md 3
    pairs_em = ([g["expected_margin_home"] for g in graded], [g["actual_margin"] for g in graded])
    pairs_et = ([g["expected_total"] for g in graded], [g["actual_total"] for g in graded])
    pairs_mag = ([abs(g["expected_margin_home"]) for g in graded], [abs(g["actual_margin"]) for g in graded])
    corr_rows = []
    for label, (xs, ys) in (("expected margin vs actual margin", pairs_em),
                            ("expected total vs actual total", pairs_et),
                            ("confidence |margin| vs realised |margin|", pairs_mag)):
        r = scoring.pearson(xs, ys)
        lo, hi = scoring.fisher_ci(r, len(xs))
        corr_rows.append({"measure": label, "r": r, "n": len(xs), "ci": (lo, hi)})
    home_win_b = [1 if g["home_win"] == 1.0 else 0 for g in graded]
    over_b = [1 if (g["actual_total"] or 0) > g["expected_total"] else 0 for g in graded]
    phi = scoring.phi(home_win_b, over_b)
    phi_lo, phi_hi = scoring.fisher_ci(phi, len(graded))
    corr_rows.append({"measure": "same-game dependence: home win vs total above our number (phi)",
                      "r": phi, "n": len(graded), "ci": (phi_lo, phi_hi)})

    # 4. removal-of-luck panel
    luck = {"moneyline": scoring.simulate_record([g["p_home"] for g in graded_ml],
                                                  [g["home_win"] for g in graded_ml]),
            "selective": scoring.simulate_record([g["p_home"] for g in graded_ml if g["selected"]],
                                                 [g["home_win"] for g in graded_ml if g["selected"]])}
    var_act = scoring.stdev([g["actual_margin"] for g in graded]) ** 2
    var_exp = scoring.stdev([g["expected_margin_home"] for g in graded]) ** 2
    var_res = scoring.stdev([g["actual_margin"] - g["expected_margin_home"] for g in graded]) ** 2
    luck["variance"] = {"var_actual": var_act, "var_expected": var_exp, "var_residual": var_res,
                        "share_explained": var_exp / var_act if var_act else float("nan")}

    # 5. ratings snapshot now, and the same rule applied one week earlier, for the weekly diff
    snap_now = model.features([g for g in corpus if g["week"] <= weeks[-1]])
    snap_prev = model.features([g for g in corpus if g["week"] <= weeks[-1] - 1])

    def ranked(feat):
        items = sorted(((t, v["net_s"]) for t, v in feat["games"].items()), key=lambda kv: -kv[1])
        return {t: {"rank": i + 1, "net": net, "att": feat["games"][t]["att_s"],
                    "def": feat["games"][t]["def_s"], "w": feat["games"][t]["wins"],
                    "l": feat["games"][t]["losses"], "t": feat["games"][t]["ties"]}
                for i, (t, net) in enumerate(items)}
    rank_now, rank_prev = ranked(snap_now), ranked(snap_prev)

    # 6. prospective forecasts for Week 11 (fitted through Week 9, issued before the first kickoff)
    feat_fwd = model.features([g for g in corpus if g["week"] <= weeks[-1]])
    cfg_fwd = model.config_hash(feat_fwd)
    as_of_last = max(g["date"] for g in corpus if g["week"] <= weeks[-1] and g["complete"])
    forecasts, records = [], []
    for fx in fixtures:
        f = model.forecast(feat_fwd, fx["away"], fx["home"])
        fixture_kickoff = f"{fx['date_et']}T{fx['kickoff_et']}:00-05:00"
        row = {
            "week": fx["week"], "slot": fx["slot"], "date_et": fx["date_et"], "kickoff_et": fx["kickoff_et"],
            "away": fx["away"], "home": fx["home"], "p_home": f["p_home"], "p_away": f["p_away"],
            "fair_spread_home": f["fair_spread_home"], "fair_total_primary": round(
                f["expected_home_points"] + f["expected_away_points"], 2),
            "fair_total_secondary": f["fair_total_secondary"],
            "gap": round(f["fair_total_secondary"] - (f["expected_home_points"] + f["expected_away_points"]), 2),
            "market_line": "", "residual": "",
            "fair_price_home": round(f["fair_price_home"], 3), "fair_price_away": round(f["fair_price_away"], 3),
            "corpus_gap_days": (dt.date.fromisoformat(fx["date_et"]) - dt.date.fromisoformat(as_of_last)).days,
            "venue_verified": fx["venue_game_centre"], "venue_status": fx["venue_status"],
            "neutral_site": fx["neutral_site"], "network": fx["network"],
            "issued_at_utc": issued, "as_of_data": f"2026 week {weeks[-1]} (through {as_of_last})",
            "model_version": MODEL_VERSION, "config_hash": cfg_fwd,
            "source_url": fx["game_centre_url"], "schedule_url": fx["schedule_page_url"],
            "kickoff_iso": fixture_kickoff,
        }
        forecasts.append(row)
        for sid, div in (("SB1-ML", "Singles · moneyline"), ("SB1-ML-S", "Singles · moneyline (selective)"),
                         ("SB1-TOT", "Singles · total"), ("CT-HOME", "control"), ("CT-RAND", "control")):
            records.append({
                "forecast_id": f"W11-{fx['away']}-{fx['home']}-{sid}", "strategy": sid, "division": div,
                "issued_at_utc": issued, "as_of_data": row["as_of_data"], "season": 2026, "week": 11,
                "slot": fx["slot"], "away": fx["away"], "home": fx["home"],
                "p_home": round(f["p_home"], 4), "p_away": round(f["p_away"], 4),
                "fair_spread_home": f["fair_spread_home"], "fair_total_primary": row["fair_total_primary"],
                "fair_total_secondary": f["fair_total_secondary"],
                "selected": abs(f["expected_margin_home"]) >= 4.5,
                "inputs": {"away_net": f["inputs"]["away"]["net_s"], "home_net": f["inputs"]["home"]["net_s"],
                           "away_gp": f["inputs"]["away"]["gp"], "home_gp": f["inputs"]["home"]["gp"],
                           "home_rate": f["inputs"]["league"]["home_rate"], "sigma": f["inputs"]["league"]["sigma"],
                           "h_margin": f["inputs"]["league"]["h_margin"], "mu_att": f["inputs"]["league"]["mu_att"],
                           "mu_def": f["inputs"]["league"]["mu_def"]},
                "model_version": MODEL_VERSION, "config_hash": cfg_fwd,
                "market_line": "", "residual": "",
                "source_urls": [fx["game_centre_url"], fx["schedule_page_url"]],
                "registration": "PREREGISTRATION.md §1-§8 (frozen)", "supersedes": "",
            })
    first_kickoff = dt.datetime.fromisoformat(
        min(f"{fx['date_et']}T{fx['kickoff_et']}:00" for fx in fixtures) + "-05:00")
    issued_before_first = dt.datetime.fromisoformat(issued) < first_kickoff
    kickoff_iso = first_kickoff.isoformat()

    # 7. prospective leaderboard: only games forecast before kickoff may ever appear here
    prospective = [r for r in records if r["week"] >= 11]

    result = {
        "built_at_utc": issued, "model_version": MODEL_VERSION, "config_hash": cfg_fwd,
        "corpus": {"rows": len(corpus), "with_scores": sum(1 for g in corpus if g["complete"]),
                   "blank_scores": sum(1 for g in corpus if not g["complete"]),
                   "weeks": weeks, "ties": sum(1 for g in corpus if g["tie"])},
        "verification": {"readings": len(readings), "match": n_match, "blank_in_log": n_blank,
                         "differs": n_diff, "rows": verdicts},
        "backtest": backtest, "correlations": corr_rows, "luck": luck,
        "graded_for_win_grading": len(graded_ml),
        "fixtures": len(forecasts), "forecast_records": len(records),
        "week10": read_week10(),
        "prospective_graded": 0, "issued_before_first_kickoff": bool(issued_before_first),
        "first_kickoff_iso": kickoff_iso,
        "as_of_data": f"2026 weeks 1-{weeks[-1]}", "last_verified_game_date": as_of_last,
        "rank_now": rank_now, "rank_prev": rank_prev,
    }
    result["fair_lines"] = forecasts
    result["records"] = records
    result["ledger"] = ledger

    if write:
        DATA.mkdir(parents=True, exist_ok=True)
        write_json(DATA / "summary.json", result_without_blob(result))
        write_csv(DATA / "fair_lines_2026_w11.csv", forecasts,
                  ["week", "slot", "date_et", "kickoff_et", "away", "home", "p_home", "p_away",
                   "fair_spread_home", "fair_total_primary", "fair_total_secondary", "gap", "market_line",
                   "residual", "fair_price_home", "fair_price_away", "corpus_gap_days", "venue_verified",
                   "venue_status", "neutral_site", "network", "issued_at_utc", "as_of_data", "model_version",
                   "config_hash", "source_url", "schedule_url"])
        write_jsonl(DATA / "forecast_records.jsonl", result["records"])
        write_csv(DATA / "backtest_ledger.csv", ledger,
                  ["week", "date", "slot", "away", "home", "away_score", "home_score", "p_home",
                   "expected_margin_home", "expected_total", "benchmark_total", "actual_margin", "actual_total",
                   "home_win", "tie", "graded", "selected", "fit_weeks_through", "model_version",
                   "config_hash", "source_url"])
        write_csv(DATA / "verification_rows.csv", verdicts,
                  ["id", "week", "away", "home", "field", "value_read", "log_value", "verdict",
                   "official_url", "read_window_utc", "note"])
        write_json(DATA / "ratings_snapshot.json",
                   {"built_at_utc": issued, "as_of": f"2026 weeks 1-{weeks[-1]}",
                    "as_of_previous": f"2026 weeks 1-{weeks[-1] - 1}",
                    "note": "Recomputed with the frozen rule on logs truncated at Week 9 and Week 8. This is an "
                            "as-of comparison, not an archived immutable capture; the snapshot ledger "
                            "(requirement A5/L10) is still not in place.",
                    "now": rank_now, "previous": rank_prev, "league": snap_now["league"],
                    "league_previous": snap_prev["league"]})
        pages = render(result, fixtures, readings, ledger, graded, graded_ml)
        for name, html_text in pages.items():
            (BOARD / name).write_text(html_text)
    return result


def result_without_blob(result: dict) -> dict:
    out = {k: v for k, v in result.items() if k not in ("ledger", "records", "fair_lines")}
    return out


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n" for r in rows))


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in cols})


# --------------------------------------------------------------------------- pages
def render(res: dict, fixtures, readings, ledger, graded, graded_ml) -> dict[str, str]:
    ent = res["backtest"]["entries"]
    pages = {}
    notice = ("<div class='notice'><b>What this is.</b> A pre-registered singles-only shadow baseline. It prices "
              "nothing against a market, because no permissioned price source exists in this repository, so the "
              "market and residual columns are blank on purpose. Nothing here is betting advice.</div>")

    # ---- index: leaderboard (prospective only) + gates + tier
    lb_rows = []
    for reg in register_rows():
        e = ent.get(reg["id"], {"n": 0})
        gates = gates_for(reg["id"], {"n": 0}, provenance_ok=res["issued_before_first_kickoff"], prospective=True)
        lb_rows.append([
            f"<td>{esc(reg['id'])}</td>", f"<td>{esc(reg['division'])}</td>",
            f"<td>{esc(reg['rule'])}</td>",
            f"<td class='num'>{esc('0')}</td>",
            "<td class='num blankcell' title='no graded prospective game yet'></td>",
            "<td class='num blankcell' title='price firewall (Gate G) closed'></td>",
            f"<td>{esc(tier_cell(reg['id'], gates))}</td>",
            f"<td>not rankable (0 of {RANK_GAMES} graded games)</td>",
            f"<td>{link(OFFICIAL_SCORES, 'official Week 11 slate')}</td>",
        ])
    lb = table(["Strategy", "Division", "Signal rule", "Graded games", "Brier skill (cluster lower bound)",
                "Staking / ROI", "Reward tier", "Leaderboard state", "Source"], lb_rows,
               "Prospective leaderboard. Only fixtures forecast after the registration commit and before kickoff "
               "may appear; every graded cell is empty because Week 11 starts 2026-11-19.")
    demote = table(["Rule", "Threshold", "Observed now", "State", "Source"], [
        ["Live strategy returns to paper", f"trailing {DEMOTE_WINDOW} graded games, cluster-bootstrap skill lower "
         "bound < 0 in two consecutive weekly evaluations", "0 of 20 graded games recorded; evaluation 1 not due",
         "not evaluable", link("https://www.nfl.com/scores/", "official scores") + " &#183; <a href='../readiness.html'>readiness register</a>"],
        ["Immediate suspension", "any Gate A provenance failure (missing official URL, forecast issued after "
         "kickoff, silent imputation)", "0 failures; the Week 11 issue time precedes the first kickoff", "armed",
         link(OFFICIAL_SCHEDULE, "official Week 11 schedule page")],
        ["Escrow (stage B) opening condition", f"stage-A qualification in the division (>= {RANK_GAMES} graded "
         f"games, skill lower bound > 0, BH survival)", "not opened - no division is qualified", "closed",
         link("https://www.nfl.com/schedules/2026/by-week/week-11", "official Week 11 page") + " &#183; <a href='../review.html'>flagged for review</a>"],
    ], caption=f"Demotion and escrow counters. The {ESCROW_DAYS}-day escrow length is a proposal for the owner, "
               "not a measured figure.")
    gates_index = table(["Gate", "State on the prospective record", "Number", "Source"],
                        [[f"<td>{esc(g['gate'])}</td>", f"<td>{esc(g['state'])}</td>", f"<td>{esc(g['number'])}</td>",
                          link("https://www.nfl.com/scores/", "official scores") + " &#183; " +
                          "<a href='PREREGISTRATION.md'>pre-registration</a>"]
                         for g in gates_for("SB1-ML", {"n": 0}, res["issued_before_first_kickoff"], True)],
                        "Gate states for SB1-ML on the prospective window. The same eight gates are applied to "
                        "every declared strategy at every weekly evaluation.")
    facts = table(["Item", "Value", "How it was checked", "Source"], [
        ["Registration commit", "<code>PREREGISTRATION.md</code> committed before any artifact of this workspace",
         "the file is frozen; check.py refuses a build whose artifacts predate it",
         link("https://www.nfl.com/schedules/2026/by-week/week-11", "fixture source") + " &#183; <a href='PREREGISTRATION.md'>pre-registration</a>"],
        ["Corpus", f"{res['corpus']['rows']} games (2026 Weeks 1-{max(res['corpus']['weeks'])}), "
                   f"{res['corpus']['with_scores']} with two published scores, "
                   f"{res['corpus']['blank_scores']} blank and excluded",
         "row count recomputed from the committed log at build time",
         link("https://www.nfl.com/schedules/2026/by-week/week-1", "official Week 1 schedule page")],
        ["Line-by-line checks this pass",
         f"{res['verification']['readings']} values read off official pages: "
         f"{res['verification']['match']} match, {res['verification']['blank_in_log']} fill a blank in the log, "
         f"{res['verification']['differs']} differ",
         "each value compared with the committed log field by field",
         link("https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2", "official game centre") + " &#183; <a href='sources.html'>verification table</a>"],
        ["Backtest (not leaderboard)", f"walk-forward over Weeks 2-{max(res['corpus']['weeks'])}, "
         f"{res['backtest']['graded_games']} graded games; skill and its interval on the backtest page",
         "printed only on backtest.html so it cannot be read as a leaderboard result",
         link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 page") + " &#183; <a href='backtest.html'>backtest page</a>"],
    ], caption="Verified inputs behind the board.")
    pages["index.html"] = page("index.html", "Shadow Board - pre-registered singles baseline",
                               "One model, five declared entries, no prices, no manual input. The leaderboard shows "
                               "only what was forecast before kickoff; everything computed from past games is on the "
                               "backtest page and never beside a ranking.", notice +
                               "<h2>Prospective leaderboard (Week 11 onward)</h2>" + lb +
                               "<h2>Readiness of the board</h2>" + facts +
                               "<h2>Validation gates on the prospective record</h2>" + gates_index +
                               "<h2>Demotion gate and two-stage escrow</h2>" + demote)

    # ---- forecasts page
    fl_rows = [[f"<td>{esc(r['week'])}</td>", f"<td>{esc(r['slot'])}</td>",
                f"<td>{esc(r['date_et'])} {esc(r['kickoff_et'])} ET</td>",
                f"<td>{esc(r['away'])} at {esc(r['home'])}</td>",
                f"<td class='num'>{fmt(r['p_home'], 4)}</td>", f"<td class='num'>{fmt(r['p_away'], 4)}</td>",
                f"<td class='num'>{fmt(r['fair_spread_home'], 1)}</td>",
                f"<td class='num'>{fmt(r['fair_total_primary'], 2)}</td>",
                f"<td class='num'>{fmt(r['fair_total_secondary'], 2)}</td>",
                f"<td class='num'>{fmt(r['gap'], 2)}</td>",
                "<td class='blankcell' title='no permissioned price source - requirement P7 undecided'></td>",
                "<td class='blankcell' title='residual needs a verified market line'></td>",
                f"<td class='num'>{fmt(r['fair_price_home'], 2)}</td>",
                f"<td class='num'>{fmt(r['corpus_gap_days'], 0)}</td>",
                venue_cell(r),
                f"<td>{link(r['source_url'], 'game centre')}</td>"] for r in res["fair_lines"]]
    fair = table(["Wk", "Slot", "Date / kickoff (ET)", "Fixture", "P(home)", "P(away)", "Fair side (home)",
                  "Fair total (primary)", "Fair total (secondary)", "Gap between estimators", "Market line",
                  "Residual vs market", "Fair price home (vig-free)", "Corpus staleness (days)", "Venue (game centre)",
                  "Source"], fl_rows,
                 "Originated numbers for the whole Week 11 slate, published as probability plus its inputs. "
                 "Side first, then total, then moneyline-equivalent price, in that column order. The two market "
                 "columns are empty by design: there is no verified price to differ from.")
    neg = table(["Field", "Value", "Reading", "Source"], [
        ["Issued at (UTC)", esc(res["built_at_utc"]), "written before the first Week 11 kickoff ("
         + esc(res["first_kickoff_iso"]) + "), "
         + ("confirmed" if res["issued_before_first_kickoff"] else "NOT confirmed"),
         link("https://www.nfl.com/schedules/2026/by-week/week-11", "Week 11 slate")],
        ["Data as of", esc(res["as_of_data"]), "the model may not see a game after this date, so Week 10 games "
         "are deliberately absent and staleness is printed per fixture",
         link("https://www.nfl.com/schedules/2026/by-week/week-11", "Week 11 slate")],
        ["Config hash", f"<code>{esc(res['config_hash'])}</code>",
         "sha-256 prefix of the constants, league terms and team rates that produced these numbers",
         link("https://www.nfl.com/scores/2026/week-11", "official scores page")],
        ["Model version", esc(MODEL_VERSION), "frozen by PREREGISTRATION.md; a change is an amendment, not a tweak",
         link("https://www.nfl.com/standings/", "official standings")],
    ])
    pages["forecasts.html"] = page("forecasts.html", "Originated lines - Week 11 slate",
                                   "Every row is a probability plus the inputs that produced it, stored in "
                                   "<code>data/forecast_records.jsonl</code> as an immutable record. Picks are not "
                                   "published: a pick without a probability cannot be scored properly.",
                                   "<h2>Fair lines</h2>" + neg + fair +
                                   "<h2>Fixture context, from published schedule facts only</h2>" +
                                   table(["Fixture", "Slot", "Neutral / international", "Venue at game centre",
                                          "Venue named on the schedule page", "Status", "Source"],
                                         [[f"{esc(f['away'])} at {esc(f['home'])}", esc(f["slot"]),
                                           esc(f["neutral_site"]),
                                           esc(f["venue_game_centre"]) or "<span class='blank'>blank</span>",
                                           esc(f["venue_schedule_page"]) or "<span class='blank'>blank</span>",
                                           esc(f["venue_status"]), link(f["game_centre_url"], "game centre")]
                                          for f in fixtures]))

    # ---- backtest page
    def metric_row(sid, label):
        e = ent[sid]
        return [esc(label), f"{e['n']}", fmt(e["brier"], 4), fmt(e["brier_base"], 4), fmt(e["skill"], 4),
                fmt(e["skill_lo"], 4), fmt(e["skill_hi"], 4), fmt(e["p_value"], 4),
                "yes" if e["bh_pass"] else "no", fmt(e["log_score"], 4),
                (fmt(e["hit_rate"], 3) + f" ({fmt(e['wilson_lo'], 2)}-{fmt(e['wilson_hi'], 2)})") if e["n"] else "",
                (f"{e['hits']}/{e['n']}") if e["n"] else "", fmt(e["required_n"], 0),
                link("https://www.nfl.com/schedules/2026/by-week/week-1", "official results")]
    mrows = [metric_row(k, k) for k in ("SB1-ML", "SB1-ML-S", "CT-HOME", "CT-RAND")]
    t_ = ent["SB1-TOT"]
    trow = ["SB1-TOT", f"{t_['n']}", fmt(t_["rmse"], 2), fmt(t_["rmse_base"], 2), fmt(t_["mae"], 2),
            fmt(t_["mean_sq_improvement_pts2"], 2), fmt(t_["quad_skill"], 4), fmt(t_["quad_skill_lo"], 4),
            fmt(t_["quad_skill_hi"], 4), fmt(t_["quad_skill_p"], 4), fmt(t_["required_n"], 0),
            link("https://www.nfl.com/schedules/2026/by-week/week-1", "official results")]
    metrics = table(["Entry", "n", "Mean Brier", "Benchmark mean Brier", "Brier skill", "Skill lower bound",
                     "Skill upper", "Bootstrap p", "Survives BH", "Log score", "Hit rate (Wilson)", "Hits",
                     "Games for the bound to clear 0", "Source"], mrows,
                    f"Walk-forward over 2026 Weeks 2-{max(res['corpus']['weeks'])} on the "
                    f"{res['graded_for_win_grading']} games that decided a side; "
                    f"{res['backtest']['ties_excluded']} tied game in the window is excluded from win grading per the "
                    "pre-registration and is reported as a count. Backtest evidence, never a leaderboard result.")
    totals_tbl = table(["Entry", "n", "RMSE (pts)", "Benchmark RMSE (pts)", "MAE (pts)",
                        "Mean squared-error gain (pts\u00b2)", "Skill", "Skill lower bound", "Skill upper",
                        "Bootstrap p", "Games for the bound to clear 0", "Source"], [trow],
                       "Totals are graded on squared error against the official final total and benchmarked on the "
                       "fitted league mean total for the same week. A negative skill means the originated total was "
                       "worse than naming the league average - which is what this corpus shows.")
    corr = table(["Association (officially sourced numbers only)", "r", "n", "95% interval (Fisher z)", "Source"],
                 [[esc(c["measure"]), fmt(c["r"], 3), f"{c['n']}",
                   f"{fmt(c['ci'][0], 3)} to {fmt(c['ci'][1], 3)}",
                   link("https://www.nfl.com/schedules/2026/by-week/week-1", "official schedule pages")]
                  for c in res["correlations"]],
                 "Every correlation prints n. The last row is the same-game dependence a parlay would have to "
                 "respect: it is measured here from outcomes only, which is not the same as a validated joint "
                 "probability, so the joint-evidence gate stays closed.")
    lk = res["luck"]
    luck_tbl = table(["Luck measure", "Value", "Interpretation", "Source"], [
        ["Observed hits vs model's own distribution",
         f"{lk['moneyline']['observed_hits']} of {lk['moneyline']['n']} (simulated mean "
         f"{fmt(lk['moneyline']['expected_hits_mean'], 1)} ± {fmt(lk['moneyline']['expected_hits_sd'], 1)})",
         f"the record sits at the {fmt(lk['moneyline']['hits_percentile'] * 100, 0)}th percentile of seasons the "
         "model itself would produce, so that share of the record is not evidence of anything",
         link("https://www.nfl.com/scores/", "official scores")],
        ["Observed mean Brier against the model's own distribution",
         f"{fmt(lk['moneyline']['observed_brier'], 4)} observed vs {fmt(lk['moneyline']['simulated_brier_mean'], 4)} "
         f"simulated mean (2.5-97.5 pct: {fmt(lk['moneyline']['simulated_brier_p025'], 4)} to "
         f"{fmt(lk['moneyline']['simulated_brier_p975'], 4)}); the real season scored better than "
         f"{fmt(lk['moneyline']['brier_percentile'] * 100, 1)}% of the {lk['moneyline']['draws']:,} seasons the model "
         "would have produced from these same probabilities",
         "how lucky or unlucky the scored outcomes were relative to the model's own probabilities",
         link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 results")],
        ["Variance explained by the expectation",
         f"{fmt(lk['variance']['share_explained'] * 100, 1)}%",
         "variance of the model's expected margin over variance of the realised margin: the ceiling on what any "
         "single-game forecast can explain, independent of luck",
         link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 results")],
        ["Games needed for a positive lower bound at the observed effect",
         f"{fmt(ent['SB1-ML']['required_n'], 0)}", "a sample-size target, not a promise of significance",
         link("https://www.nfl.com/schedules/2026/by-week/week-8", "official Week 8 results")],
    ])
    cal = table(["Forecast probability bin", "n", "Mean forecast", "Observed home-win rate", "Gap", "Source"],
                [[esc(c["bin"]), f"{c['n']}", fmt(c["mean_p"], 3), fmt(c["observed"], 3),
                  fmt((c["observed"] - c["mean_p"]) if c["n"] else float("nan"), 3),
                  link("https://www.nfl.com/schedules/2026/by-week/week-2", "official results")]
                 for c in scoring.calibration([(g["p_home"], g["home_win"]) for g in graded_ml])],
                "Calibration on the backtest window. Small bins are printed with their n because a smooth curve at "
                "n=119 is not evidence.")
    snap = json.loads((DATA / "ratings_snapshot.json").read_text()) if (DATA / "ratings_snapshot.json").exists() else \
        {"now": res["rank_now"], "previous": res["rank_prev"]}
    diff_rows = []
    for team, v in sorted(snap["now"].items(), key=lambda kv: kv[1]["rank"]):
        prev = snap["previous"].get(team, {"rank": v["rank"], "net": v["net"]})
        diff_rows.append([f"{v['rank']}", esc(team), f"<span class='mono'>{esc(v['w'])}-{esc(v['l'])}"
                          f"{'-T' if v['t'] else ''}</span>", fmt(v["net"], 3), fmt(prev["net"], 3),
                          fmt(v["net"] - prev["net"], 3), f"{prev['rank'] - v['rank']:+d}",
                          link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 page")])
    diff = table(["Rank now", "Team", "Record (Weeks 1-9)", "Rating now", "Rating a week earlier",
                  "Change", "Rank change", "Source"], diff_rows,
                 "Weekly 'what changed' view produced by the same frozen rule at two as-of points. Recomputed, "
                 "not archived: the immutable snapshot ledger is still open work.")
    pages["backtest.html"] = page("backtest.html", "Backtest, correlations, luck and the weekly diff",
                                  "Everything on this page was computed from games that had already finished. It "
                                  "exists to show whether the machinery separates skill from noise - it is not a "
                                  "leaderboard result and is never quoted as one.",
                                  "<h2>Proper-score metrics</h2>"
                                  + "<p class='para'>Read the lower bound, not the point estimate. "
                                    "CT-RAND - a coin flip - reaches a bootstrap p of "
                                    + fmt(res['backtest']['entries']['CT-RAND']['p_value'], 3)
                                    + " on this window while its skill interval still covers zero: that is what a "
                                      "leaderboard looks like when it is scored on a point estimate. No entry here "
                                      "has a positive lower bound, so nothing on this page is evidence of skill, and "
                                      "the sample-size column says how far away the corpus is from being able to say "
                                      "anything else.</p>" + metrics +
                                  "<h2>Totals, on the squared-error scale</h2>" + totals_tbl +
                                  "<h2>Correlations with n</h2>" + corr +
                                  "<h2>Removal of luck</h2>"
                                  + "<p class='para'>A hit count that matches the model's own expectation says "
                                    "nothing about whether the probabilities were good: the scoring detail says more. "
                                    "Here the realised outcomes were less predictable than the model's probabilities "
                                    "anticipated, which the calibration table below shows as over-confidence in the "
                                    "0.6-0.8 band rather than as bad luck.</p>" + luck_tbl +
                                  "<h2>Calibration</h2>" + cal +
                                  "<h2>What changed, Week 8 to Week 9</h2>" + diff)

    # ---- method page
    strat_rows = [[f"<td>{esc(r['id'])}</td>", f"<td>{esc(r['division'])}</td>", f"<td>{esc(r['rule'])}</td>",
                   f"<td>{esc(r['falsify'])}</td>", f"<td>{esc(r['confirm'])}</td>",
                   f"<td>{esc(r['stake_gate'])}</td>",
                   f"<td>{link('https://www.nfl.com/schedules/2026/by-week/week-11', 'fixture source')} &#183; <a href='PREREGISTRATION.md'>registered rule</a></td>"]
                  for r in register_rows()]
    strat = table(["Entry", "Division", "Rule (frozen)", "What would change our mind", "What would confirm it",
                   "Staking gate", "Registration"], strat_rows,
                  "Two-sided falsification fields for every declared strategy, as required: each entry states both "
                  "the result that would kill it and the result that would establish it, in numbers.")
    div_rows = []
    for d in DIVISIONS:
        eligible = 3 if d == "Singles · moneyline" else (1 if d == "Singles · total" else 0)
        blocker = ("none - singles only, per the shadow-baseline decision" if d.startswith("Singles")
                   else "joint-evidence gate: no validated joint probability and no operator void/push rules")
        div_rows.append([esc(d), f"{eligible}", "0 graded games in the prospective window", esc(blocker),
                         ("a directly validated joint probability with its n, plus documented settlement rules"
                          if not d.startswith("Singles") else f"{RANK_GAMES} graded games forecast before kickoff"),
                         link(OFFICIAL_RULEBOOK, "official 2026 rulebook")])
    divisions = table(["Division", "Eligible entries", "Graded record", "Blocking condition",
                       "Number that clears it", "Source"], div_rows,
                      "Divisions are ranked separately and by benchmark-relative skill, not by win rate; a parlay "
                      "division with no joint evidence stays empty rather than being filled by multiplying marginals.")
    para = ("<p class='para'>The full rule text is in <a href='PREREGISTRATION.md'>PREREGISTRATION.md</a>. It is "
            "the only place a threshold is decided: this page restates numbers, it does not invent them.</p>")
    stats_tbl = table(["Statistic", "Why this one", "Where it can mislead", "Reference"], [
        ["Brier score, benchmark-relative", "proper scoring rule; a vague forecast cannot hide in it",
         "at small n a good mean score can be a lucky window", link("https://itl.nist.gov/", "NIST/SEMATECH e-Handbook")],
        ["Game-cluster bootstrap", "two events in one game are not independent samples",
         "resampling games still assumes independence between weeks",
         link("https://scikit-learn.org/stable/modules/cross_validation.html", "cross-validation practice")],
        ["Benjamini-Hochberg across the family", "five entries tested at once produces a champion by luck",
         "controls the false-discovery rate, not the false-omission rate",
         link("https://itl.nist.gov/", "multiple-comparison practice")],
        ["Wilson interval on a hit rate", "correct coverage near 0 and 1, where a normal band fails",
         "a hit rate ignores price, so it can never be a staking claim",
         link("https://www.nfl.com/standings/", "official standings")],
        ["Fisher z on correlations", "the interval is defined for a correlation, unlike a bare r",
         "normality of the underlying pairs is not checked at the n printed above",
         link("https://itl.nist.gov/", "NIST reference")],
    ])
    other = table(["Item", "This workspace", "official-verify/ (registered separately, on main)", "Source"], [
        ["Model", "Shrunken net-points-per-game, margin sd fitted from the corpus and clipped to 10.0-17.0",
         "Ridge attack/defence on the sum-to-zero constraint, sigma fixed at 13.5 in advance",
         link("https://www.nfl.com/schedules/2026/by-week/week-1", "official Week 1 schedule page")
         + " &#183; <a href='../official-verify/prereg/PREREG-2026-OV1.md'>their registration</a>"],
        ["Backtest window", f"2026 Weeks 2-{max(res['corpus']['weeks'])}, every game with a prior",
         "2026 Weeks 4-10 evaluation, Weeks 1-3 warm-up",
         link("https://www.nfl.com/schedules/2026/by-week/week-4", "official Week 4 schedule page")
         + " &#183; <a href='../official-verify/index.html'>official-verify overview</a>"],
        ["Controls", "Home-win-rate benchmark and a coin flip",
         "Coin flip, home base rate and a favourites-only control",
         link("https://www.nfl.com/standings/", "official standings")
         + " &#183; <a href='../official-verify/data/evaluation.json'>their evaluation artifact</a>"],
        ["Prospective board", "Yes - Week 11 onward, and only that window is ranked", "No prospective leaderboard",
         link(OFFICIAL_SCHEDULE, "official Week 11 schedule page")
         + " &#183; <a href='../official-verify/leaderboard.html'>their leaderboard page</a>"],
        ["Result on the shared weeks", "Skill +0.068, cluster lower bound -0.052 (see the backtest page)",
         "Skill +0.119 against the home base-rate control on 89 scored games, intervals as they publish them",
         link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 schedule page")
         + " &#183; <a href='../official-verify/data/evaluation.json'>their evaluation artifact</a>"],
    ])
    pages["method.html"] = page("method.html", "Method, gates and the strategy register",
                                "What is frozen, what is measured, and what would change each entry's mind. The "
                                "gates are fail-closed: the default state of a strategy is not ranked.",
                                para + "<h2>Declared strategies</h2>" + strat +
                                "<h2>The same question is registered twice in this repository</h2>"
                                + "<p class='para'>A second session registered a comparable evaluation on the same "
                                  "official corpus while this one was being built. The two are not corrections of each "
                                  "other and neither is a replication of the other: they differ in model form, window "
                                  "and sigma treatment, so their numbers must not be pooled or averaged. This table "
                                  "exists so a reader can see which claim comes from which registration. The one thing "
                                  "the two registrations do agree on is the verdict that matters: neither model's "
                                  "skill clears a game-cluster lower bound above zero on the 2026 corpus, so a claim "
                                  "of selective skill from either workspace would be premature regardless of which "
                                  "formula is used.</p>" + other +
                                "<h2>Leaderboard divisions</h2>" + divisions +
                                "<h2>Scoring rules and their failure modes</h2>" + stats_tbl +
                                "<h2>Rejected shortcuts (recorded so they are not re-proposed silently)</h2>" +
                                table(["Rejected", "Why", "Source"], [
                                    ["Deriving depth order from jersey number, experience or salary",
                                     "an attribute is not a roster decision; the club's published list is the record",
                                     link(OFFICIAL_INJURIES, "official injury report")],
                                    ["A fixed points penalty for a missing starter",
                                     "the effect of an absence is a property of the replacement, not of the label; "
                                     "it must be ablated, with uncertainty", link(OFFICIAL_INJURIES, "official report")],
                                    ["Ranking strategies by season-long ROI or by a win rate",
                                     "both reward a short lucky run and neither needs a forecast to be good",
                                     link(OFFICIAL_ODDS_FAQ, "NFL odds-widget boundary")],
                                    ["Publishing a parlay from multiplied marginal probabilities",
                                     "dependence is measured above at r = "
                                     + fmt(res["correlations"][-1]["r"], 2) + " on this corpus, so multiplication "
                                       "is invalid until a joint estimate exists",
                                     link("https://www.nfl.com/scores/", "official scores")],
                                ]))

    # ---- sources page: verification + source register + flags
    v_rows = [[f"<td>{esc(v['id'])}</td>", f"<td>{esc(v['week'])}</td>",
               f"<td>{esc(v['away'])} at {esc(v['home'])}</td>", f"<td>{esc(v['field'])}</td>",
               f"<td class='mono'>{esc(v['value_read'])}</td>", f"<td class='mono'>{esc(v['log_value'])}</td>",
               f"<td>{esc(v['verdict'])}</td>", f"<td>{link(v['official_url'], 'official page')}</td>",
               f"<td class='mono'>{esc(v['read_window_utc'])}</td>"] for v in res["verification"]["rows"]]
    ver = table(["ID", "Wk", "Fixture", "Field", "Read from official page", "Committed log value", "Verdict",
                 "Source", "Read window (UTC)"], v_rows,
                "Line-by-line verification of the corpus against a second official page, with the clock window the "
                "read was taken in.")
    src_rows = [
        ["2026 Week 11 schedule page (slate, kickoff slots, published records)", link(OFFICIAL_SCHEDULE, "nfl.com"),
         "fixture list, times, bye list", "records printed beside fixtures include Week 10 for some clubs and not "
         "others; not used as a model input"],
        ["2026 Week 11 scores page (same slate, second official view)", link(OFFICIAL_SCORES, "nfl.com"),
         "independent confirmation of the 13-game slate", "shows no venues"],
        ["Week 2 game centre, Washington at Dallas", link("https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2", "nfl.com"),
         "final score and quarter scores that the committed log leaves blank", "published after the log was captured"],
        ["Week 11 game centre, Minnesota at San Francisco", link("https://www.nfl.com/games/vikings-at-49ers-2026-reg-11", "nfl.com"),
         "venue and location fields; the team results strip used for the row checks",
         "the strip is a secondary presentation of past games, not an archived page"],
        ["Week 11 game centre, Indianapolis at Houston", link("https://www.nfl.com/games/colts-at-texans-2026-reg-11", "nfl.com"),
         "venue field; team rate snapshot fields", "stadium field disagrees with the schedule page travel link"],
        ["2026 schedule announcement, dated 14 May 2026", link(OFFICIAL_ANNOUNCE, "media.nfl.com"),
         "18 weeks, 272 games, kickoff Wednesday 9 September, nine international games, Week 11 Mexico City",
         "a dated press release: it establishes what was announced, not what was later flexed"],
        ["Official injury report page", link(OFFICIAL_INJURIES, "nfl.com"),
         "the weekly report the availability work reads", "mutable; no percentages attached to any designation"],
        ["Historical injury report URL pattern", link("https://www.nfl.com/injuries/league/2024/REG4", "nfl.com"),
         "past-season weekly reports render (season and week selector)",
         "the records printed beside a past-week report are end-of-season values, so the page is not point-in-time "
         "safe; using it for a backtest requires a dated contemporaneous capture (flagged)"],
        ["2026 NFL rulebook", link(OFFICIAL_RULEBOOK, "operations.nfl.com"),
         "playing rules behind any totals/comeback prior", "playing rules are not settlement rules"],
        ["NFL odds-widget boundary", link(OFFICIAL_ODDS_FAQ, "support.nfl.com"),
         "the league's own statement that odds come from partner books and bets settle there",
         "no NFL-authored price archive is implied, which is why the price columns are blank"],
    ]
    srcs = table(["Source", "Link", "What it establishes here", "What it does not establish"],
                 [[f"<td>{esc(a)}</td>", b, f"<td>{esc(c)}</td>", f"<td>{esc(d)}</td>"] for a, b, c, d in src_rows])
    flags = table(["Flag", "Observation", "Why it matters", "Source"], [
        ["SB-F01", "The committed 2026 log has one game with no score (Week 2, Washington at Dallas); the official "
         "game centre published 20-37 when read on 2026-11-15, and the quarter scores sum to it.", "the corpus is "
         "excluded from fitting and grading rather than filled here, because the log file belongs to another owner.",
         link("https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2", "game centre")],
        ["SB-F02", "The log covers Weeks 1-9, so a Week 11 forecast is 12-14 days stale and every club's Week 10 "
         "result is missing.", "rest-day and form features are unavailable, and staleness is printed per fixture "
         "instead of being silently ignored.", link(OFFICIAL_SCHEDULE, "schedule page")],
        ["SB-F03", "For Indianapolis at Houston the game centre says RELIANT STADIUM while the schedule page's club "
         "travel link says NRG Stadium.", "venue provenance is contested between two official pages, so the venue "
         "field for the other 11 fixtures stays blank rather than being guessed from either.",
         link("https://www.nfl.com/games/colts-at-texans-2026-reg-11", "game centre")],
        ["SB-F04", "The Cincinnati at Washington fixture shows FedEx Field on the schedule page's travel link and no "
         "game-centre read this pass.", "an unverified venue name would be exactly the kind of inferred value this "
         "project forbids; the cell is blank and the check is queued.", link(OFFICIAL_SCORES, "scores page")],
        ["SB-F05", "nfl.com/injuries/league/{season}/REG{week} renders past seasons, but the win-loss records "
         "printed beside those tables are end-of-season values.", "the archive exists and would let the "
         "designation-reliability study run, but its point-in-time integrity is unproven; a backtest on it must be "
         "labelled with lookahead risk.", link("https://www.nfl.com/injuries/league/2024/REG4", "2024 Week 4 report")],
        ["SB-F06", "The Week 10 injury report page titled 'Week 10 of the 2026 Season' prints 'Injuries - WEEK 9' in "
         "the body; the same mismatch appears on 2024 Week 4 ('Week 10' title, 'WEEK 4' body).",
         "a scraper keyed on the title would mislabel captures by a week; parsers must read the body header.",
         link("https://www.nfl.com/injuries/league/2024/REG4", "example page")],
        ["SB-F07", "No price source of any kind is available under the current policy, so opening/closing snapshots, "
         "CLV, ROI and vig-free consensus cannot be computed.", "every market column on this board is blank and no "
         "strategy can move past Tier 4 until the owner decides the price-data policy.",
         link(OFFICIAL_ODDS_FAQ, "NFL odds-widget boundary")],
    ])
    w10 = res.get("week10", [])
    if w10:
        boundary = table(["Wk", "Slot", "Date / kickoff (ET)", "Fixture", "Pregame records", "Status at read time",
                          "Score read", "Source"],
                         [[f"<td>{esc(r['week'])}</td>", f"<td>{esc(r['slot'])}</td>",
                           f"<td>{esc(r['date_et'])} {esc(r['kickoff_et'])}</td>",
                           f"<td>{esc(r['away'])} at {esc(r['home'])}</td>",
                           f"<td class='mono'>{esc(r['away_record_pregame'])} / {esc(r['home_record_pregame'])}</td>",
                           f"<td>{esc(r['official_status_at_read'])}</td>",
                           (f"<td class='mono'>{esc(r['away_score'])}-{esc(r['home_score'])}</td>"
                            if r["away_score"] else
                            "<td class='blankcell' title='no score on the page at the read window'></td>"),
                           f"<td>{link(r['game_centre_url'], 'game centre')} &#183; "
                           f"{link(r['schedule_page_url'], 'Week 10 schedule')}</td>"]
                          for r in w10],
                         "The corpus boundary, stated exactly. The verified log ends with the Week 9 Monday game "
                         "(2026-11-09). Of Week 10, the Thursday game is final and is the one completed result the log "
                         "is missing; the Sunday games had not been played inside the read window, so they are not "
                         "missing data. No count of Week 10 fixtures is claimed here because the page read stopped "
                         "part-way through the slate.")
    else:
        boundary = ""
    pages["sources.html"] = page("sources.html", "Verification, sources and flags",
                                 "The reads that check this workspace, what each source is allowed to establish, and "
                                 "the irregularities that are published instead of quietly corrected.",
                                 "<h2>Line-by-line checks</h2>" + ver +
                                 "<h2>What the corpus is missing, exactly</h2>" + boundary +
                                 "<h2>Source register</h2>" + srcs + "<h2>Flagged for review</h2>" + flags)

    # ---- registers page
    q_rows = [
        ["SB-Q01", "Price data", "Which price source may this repository read, at what timing, under what terms?",
         "Owner decision; nothing else unblocks P1/P3/P5/P6 and the reward ladder's top tier.",
         link(OFFICIAL_ODDS_FAQ, "the league's own odds boundary")],
        ["SB-Q02", "Corpus refresh", "Should the verified log be extended week by week and committed with a hash so "
         "as-of features stop being stale?", "Blocks rest-day, form and availability features on the prospective window.",
         link(OFFICIAL_SCHEDULE, "official schedule page")],
        ["SB-Q03", "Venue authority", "Which official page is authoritative for venue when the game centre and the "
         "schedule page disagree?", "Roof/surface and travel features cannot be built before the answer.",
         link("https://www.nfl.com/games/colts-at-texans-2026-reg-11", "game centre example")],
        ["SB-Q04", "Historical reports", "May the past-season injury archive be used for a designation-reliability "
         "study knowing its printed context is end-of-season?", "Decides whether the Q06 study is a flagged "
         "approximation or waits for dated captures.",
         link("https://www.nfl.com/injuries/league/2024/REG4", "2024 Week 4 report")],
        ["SB-Q05", "Rewards", "What does a tier actually pay, and who funds it?",
         "Tiers are eligibility states; without a funded rule the ladder is a scoreboard with no reward.",
         link("https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL", "odds boundary") + " &#183; <a href='../readiness.html'>readiness register</a>"],
        ["SB-Q06", "Sample policy", "Is a 30-game minimum to rank acceptable when a single week grades 13 fixtures?",
         "It sets how many weeks a strategy must sit unranked before its skill bound means anything.",
         link("https://www.nfl.com/schedules/2026/by-week/week-11", "one week grades 13 fixtures") + " &#183; <a href='PREREGISTRATION.md'>pre-registration</a>"],
    ]
    s_rows = [
        ["SB-S01", "Extend the verified log every week and store it with its own hash",
         "unblocks rest, form, availability deltas and the backtest corpus growth; 13 fixtures per week of graded "
         "record instead of a frozen 135-game sample", "one scheduled capture job", "P1 stays blocked",
         "high", link(OFFICIAL_SCHEDULE, "official schedule page")],
        ["SB-S02", "Move the forecast issuance into the weekly CI run so a forecast cannot be written after kickoff",
         "makes Gate A self-enforcing rather than a statement in a page", "small workflow step",
         "needs a runner with network egress", "high",
         link("https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages",
              "GitHub Pages workflows")],
        ["SB-S03", "Publish the removal-of-luck panel next to any future reward decision",
         "a reward paid on a record at the 60th percentile of a lucky draw is a payment for noise", "already built here",
         "none", "high", link("https://www.nfl.com/schedules/2026/by-week/week-9", "official Week 9 results")
         + " &#183; <a href='backtest.html'>luck panel</a>"],
        ["SB-S04", "Keep the parlay and prop divisions empty until a joint probability is estimated directly",
         "multiplying marginals at a measured same-game dependence of r = "
         + fmt(res["correlations"][-1]["r"], 2) + " would overstate every combo", "no work needed; a discipline",
         "costs short-term content", "medium", link(OFFICIAL_RULEBOOK, "official rulebook")],
        ["SB-S05", "Add the availability ablation as a second pre-registered entry once the log refresh exists",
         "tests whether injury/depth features help instead of assuming a fixed penalty", "one amendment, then a "
         "chronological holdout with and without the features", "blocked on SB-S01 and SB-Q04", "medium",
         link(OFFICIAL_INJURIES, "official report")],
        ["SB-S06", "Record the owner's decision on price data as a commit, the same way the rules are registered",
         "the price policy is the single gate that most requirements wait on; a recorded decision is auditable",
         "one decision row", "none", "high", link(OFFICIAL_ODDS_FAQ, "odds boundary")],
    ]
    pages["registers.html"] = page("registers.html", "Questions that block decisions, and suggestions to review",
                                   "One row per question with the decision it gates, and one per suggestion with its "
                                   "cost, benefit and blocker. Nothing on this page has been implemented as a change "
                                   "to another workspace.",
                                   "<h2>Questions</h2>" + table(["ID", "Area", "Question", "What it unblocks", "Source"],
                                                                [[f"<td>{esc(a)}</td>", f"<td>{esc(b)}</td>",
                                                                  f"<td>{esc(c)}</td>", f"<td>{esc(d)}</td>", e]
                                                                 for a, b, c, d, e in q_rows]) +
                                   "<h2>Suggestions</h2>" + table(["ID", "Suggestion", "Benefit", "Cost", "Blocker",
                                                                    "Priority", "Source"],
                                                                   [[f"<td>{esc(a)}</td>", f"<td>{esc(b)}</td>",
                                                                     f"<td>{esc(c)}</td>", f"<td>{esc(d)}</td>",
                                                                     f"<td>{esc(e)}</td>", f"<td>{esc(f)}</td>", g]
                                                                    for a, b, c, d, e, f, g in s_rows]))
    return pages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true", help="print the summary without writing artifacts")
    args = ap.parse_args()
    res = build(write=not args.stdout)
    ent = res["backtest"]["entries"]
    print(json.dumps({"built_at_utc": res["built_at_utc"], "corpus": res["corpus"],
                      "verification": {k: v for k, v in res["verification"].items() if k != "rows"},
                      "backtest_graded": res["backtest"]["graded_games"],
                      "skills": {k: {"n": e["n"], "skill": round(e["skill"], 4) if e["skill"] == e["skill"] else None,
                                    "lo": round(e["skill_lo"], 4) if e["skill_lo"] == e["skill_lo"] else None,
                                    "p": round(e["p_value"], 4) if e["p_value"] == e["p_value"] else None}
                                 for k, e in ent.items()},
                      "fixtures": res["fixtures"], "forecast_records": res["forecast_records"],
                      "issued_before_first_kickoff": res["issued_before_first_kickoff"],
                      "correlations": [{k: (round(v, 4) if isinstance(v, float) and v == v else v)
                                        for k, v in c.items() if k != "ci"} for c in res["correlations"]],
                      "config_hash": res["config_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
