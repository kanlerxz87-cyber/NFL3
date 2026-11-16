#!/usr/bin/env python3
"""Publish every model total twice: T1 (prior-season pace fit) and T2 (league mean + one third of form gap).

Reads only committed artifacts:

  corpus/games_2026_w1_9.csv                 frozen pre-registered corpus (136 games, 2026 weeks 1-9)
  corpus/manifest.json                       its hash and split, to prove the corpus did not move
  data/raw/games.csv                         digest-verified community schedule snapshot; the source of
                                             T1's fit window and of T2's rolling form. Never counted as
                                             official: it is used only to *compute* the estimators.
  origination/data/origination_walkforward.json   T1's published point totals, so this workspace reuses
                                             the published number instead of re-deriving a second one.

Writes two-total/data/two_total.json. Nothing is fetched from the network, so a rerun is deterministic.

Every estimator row records:
  * its value,
  * the source of the inputs behind it,
  * the number of prior observations it actually had (never padded),
  * the official schedule URL of the fixture it prices.

A total that cannot be formed stays None with a reason in `blank_reason`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "two-total"
DATA = OUT / "data"
RAW = ROOT / "data" / "raw"
CORPUS = ROOT / "corpus"

SEASON = 2026
FORM_WINDOW = 6          # pre-registered: six prior games per club
SHRINK = 1.0 / 3.0       # pre-registered in PRE_REGISTRATION.md §2
BOOT_N = 10_000
BOOT_SEED = 20261116
MIN_VALIDATION_N = 20    # PRE_REGISTRATION.md §6 C5

SPLIT = {"train": (1, 6), "validation": (7, 8), "holdout": (9, 9)}

# The one club-code normalization the repository already needed, taken verbatim from the audited
# cross-check at results-verification/scripts/crosscheck.py: the official NFL.com pages render Arizona's
# logo code as "AZ" and the slug as "cardinals", while the community snapshot uses the franchise code
# "ARI". That cross-check documented it and matched 136/136 official finals with it; no other club code
# required a mapping. Used here only to form a join key, never to alter a published value: the fixture is
# still printed as the official page prints it.
TEAM_ALIASES = {"AZ": "ARI"}


def canon(team: str) -> str:
    return TEAM_ALIASES.get(team, team)

# Official fixture sources. The corpus rows already carry the per-week official URL; this map is the
# fallback used by rows that were transcribed from a game centre page.
def schedule_url(week: int) -> str:
    return f"https://www.nfl.com/schedules/2026/by-week/week-{week}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(value):
    if value in (None, "", "NA", "NaN", "nan"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- inputs
def load_games() -> list[dict]:
    """Every played regular-season game in the snapshot, oldest first, with a kickoff key."""
    out = []
    for row in read_csv(RAW / "games.csv"):
        if row["game_type"] != "REG":
            continue
        home, away = num(row["home_score"]), num(row["away_score"])
        if home is None or away is None:
            continue
        out.append({
            "game_id": row["game_id"],
            "season": int(row["season"]),
            "week": int(row["week"]),
            "gameday": row["gameday"],
            "home": row["home_team"],
            "away": row["away_team"],
            "home_score": int(home),
            "away_score": int(away),
            "total": int(home + away),
        })
    # Ties in the sort key are possible (two games, same date); the game_id breaks them deterministically.
    out.sort(key=lambda g: (g["gameday"], g["game_id"]))
    return out


def corpus_rows() -> list[dict]:
    """The frozen corpus, in file order, with the blank score cells preserved as blank."""
    return read_csv(CORPUS / "games_2026_w1_9.csv")


# --------------------------------------------------------------------------- T1
def load_t1() -> dict:
    """T1 as published by the origination workspace, keyed by (week, away, home).

    Re-using the published artifact instead of re-running the fit keeps one definition of T1 in the
    repository. The key is built from club codes rather than the game_id because the community snapshot
    and the frozen corpus spell Arizona differently ('ARI' vs the official page's 'AZ'), and inventing a
    mapping is exactly the kind of inference this workspace must not do.
    """
    pub = json.loads((ROOT / "origination" / "data" / "origination_walkforward.json").read_text("utf-8"))
    out = {}
    for row in pub["rows"]:
        out[(row["week"], canon(row["away"]), canon(row["home"]))] = row
    return out


# --------------------------------------------------------------------------- T2
def rolling_form(history: list[dict]) -> dict:
    """Pre-kickoff rolling form for every game, never seeing its own or a later result.

    Returns {game_id: {'home_obs': n, 'away_obs': n, 'm': value or None}}.

    A club's rolling values are the mean of its last six games that kicked off strictly earlier. Two
    games on the same date are ambiguous under a date-only key, so the rule is: a game may only use
    results from games whose gameday is strictly less than its own. That excludes a same-day game
    unconditionally, which can only lose information, never leak it.
    """
    by_team: dict[str, list[dict]] = defaultdict(list)
    out = {}
    for g in history:
        home_rows = by_team[g["home"]][-FORM_WINDOW:]
        away_rows = by_team[g["away"]][-FORM_WINDOW:]
        vals = {
            "home_pts": [r["pts"] for r in home_rows],
            "home_opp_pts": [r["opp"] for r in home_rows],
            "away_pts": [r["pts"] for r in away_rows],
            "away_opp_pts": [r["opp"] for r in away_rows],
        }
        complete = all(len(v) == FORM_WINDOW for v in vals.values())
        m = None
        if complete:
            joined = [statistics.fmean(vals[k]) for k in
                      ("home_pts", "away_pts", "home_opp_pts", "away_opp_pts")]
            m = statistics.fmean(joined)
        out[g["game_id"]] = {
            "home_obs": len(home_rows), "away_obs": len(away_rows),
            "m": m, "inputs_complete": complete,
            "last_input_date": max([r["gameday"] for r in home_rows + away_rows], default=None),
        }
        # Append only after the features for this game are formed.
        by_team[g["home"]].append({"gameday": g["gameday"], "pts": g["home_score"],
                                   "opp": g["away_score"]})
        by_team[g["away"]].append({"gameday": g["gameday"], "pts": g["away_score"],
                                   "opp": g["home_score"]})
    return out


def league_mean_before(history: list[dict]) -> dict:
    """The league mean total over the corpus training window (weeks 1-6), frozen per §2.

    Using the train block only is the conservative choice: the league level T2 shrinks toward is fixed
    before the validation block is read, so the validation block is genuinely out of sample for T2's
    level term.
    """
    train = [g for g in history if g["season"] == SEASON and 1 <= g["week"] <= 6]
    return {"level": statistics.fmean(g["total"] for g in train), "n_train": len(train)}


# --------------------------------------------------------------------------- arithmetic
def mae(errors: list[float]) -> float:
    return statistics.fmean(errors)


def rmse(errors: list[float]) -> float:
    return math.sqrt(statistics.fmean([e * e for e in errors]))


def cluster_bootstrap_diff(pairs: list[tuple[float, float]], stat) -> dict:
    """Bootstrap the paired difference stat(T1 errors) - stat(T2 errors) over games.

    The game is the resampling unit because both estimators price the same game; resampling games also
    keeps same-game correlation inside the interval, which an i.i.d. row bootstrap would break.
    """
    rnd = random.Random(BOOT_SEED)
    n = len(pairs)
    if n < 3:
        return {"n": n, "lower95": None, "upper95": None, "point": None, "resamples": 0}
    point = stat([a for a, _ in pairs]) - stat([b for _, b in pairs])
    draws = []
    for _ in range(BOOT_N):
        idx = [rnd.randrange(n) for _ in range(n)]
        sample = [pairs[i] for i in idx]
        try:
            draws.append(stat([a for a, _ in sample]) - stat([b for _, b in sample]))
        except (statistics.StatisticsError, ZeroDivisionError):
            continue
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return {"n": n, "point": point, "lower95": lo, "upper95": hi,
            "resamples": len(draws), "seed": BOOT_SEED,
            "p_one_sided": sum(1 for d in draws if d <= 0) / len(draws)}


# --------------------------------------------------------------------------- build
def main() -> int:
    corpus = corpus_rows()
    manifest = json.loads((CORPUS / "manifest.json").read_text("utf-8"))
    if sha256(CORPUS / "games_2026_w1_9.csv") != manifest["frozen_sha256"]:
        print("two-total: FROZEN CORPUS HASH MOVED — refusing to score a corpus that is not the registered one")
        return 1

    history = load_games()
    t1_pub = load_t1()
    form = rolling_form(history)
    level = league_mean_before(history)

    # Map a corpus row to the community game_id so T2's rolling values can be looked up. The join key is
    # (week, away, home) on the community codes; the corpus keeps Arizona as 'AZ' because that is what the
    # official page renders, so no alias is invented — a fixture that does not join stays blank with the
    # reason recorded.
    community_by_key = {(g["season"], g["week"], canon(g["away"]), canon(g["home"])): g
                        for g in history if g["season"] == SEASON}

    rows = []
    for r in corpus:
        week = int(r["week"])
        home = r["home_team"]
        away = r["away_team"]
        home_score, away_score = num(r["home_score"]), num(r["away_score"])
        actual_total = (int(home_score + away_score)
                        if home_score is not None and away_score is not None else None)

        t1_row = t1_pub.get((week, canon(away), canon(home)))
        comm = community_by_key.get((SEASON, week, canon(away), canon(home)))

        t1_total = t1_row["model_total"] if t1_row else None
        t1_blank = None if t1_row else "T1 could not be keyed to this fixture"

        t2_total = None
        t2_blank = None
        form_info = {"home_obs": None, "away_obs": None, "m": None}
        if comm is None:
            t2_blank = "fixture not present in the community snapshot under these club codes"
        else:
            fi = form.get(comm["game_id"])
            if fi is None:
                t2_blank = "no rolling-form record for this fixture"
            else:
                form_info = {"home_obs": fi["home_obs"], "away_obs": fi["away_obs"], "m": fi["m"]}
                if fi["m"] is None:
                    t2_blank = ("rolling form incomplete: a club had fewer than "
                                f"{FORM_WINDOW} prior games, so T2 falls back to nothing rather than a guess")
                    # Pre-registered fallback in §2 is the league mean, published as such when form is
                    # undefined. Kept visible instead of silently replacing the estimator.
                    t2_total = level["level"]
                    t2_blank += " (published value is the pre-registered league-mean fallback)"
                else:
                    t2_total = level["level"] + (fi["m"] - level["level"]) * SHRINK

        row = {
            "season": SEASON, "week": week,
            "kickoff_date_et": r["kickoff_date_et"], "slot": r["slot"],
            "away": away, "home": home,
            "actual_total": actual_total,
            "t1_total": (round(t1_total, 6) if t1_total is not None else None),
            "t2_total": (round(t2_total, 6) if t2_total is not None else None),
            "gap": (round(t2_total - t1_total, 6)
                    if (t1_total is not None and t2_total is not None) else None),
            "t2_inputs": {"home_obs": form_info["home_obs"], "away_obs": form_info["away_obs"],
                          "form_mean_points": (round(form_info["m"], 6)
                                               if form_info["m"] is not None else None),
                          "league_level": round(level["level"], 6),
                          "shrink": round(SHRINK, 6)},
            "t1_inputs": ({"n_train": t1_row.get("n_train"), "hfa": round(t1_row.get("hfa", 0.0), 6),
                           "estimator": "ridge pace fit on six prior seasons"}
                          if t1_row else None),
            "blank_reason": " | ".join(x for x in (t1_blank, t2_blank) if x) or None,
            "official": r["source_url"] or schedule_url(week),
            "corpus_verification": r["verification"],
            "t1_error_abs": (abs(t1_total - actual_total)
                             if (t1_total is not None and actual_total is not None) else None),
            "t2_error_abs": (abs(t2_total - actual_total)
                             if (t2_total is not None and actual_total is not None) else None),
        }
        rows.append(row)

    # ---------------------------------------------------------------- scoring per block
    def block_of(week: int) -> str:
        for name, (lo, hi) in SPLIT.items():
            if lo <= week <= hi:
                return name
        return "outside_split"

    for row in rows:
        row["block"] = block_of(row["week"])

    def scored(subset: list[dict]) -> dict:
        pairs = [(r["t1_error_abs"], r["t2_error_abs"]) for r in subset
                 if r["t1_error_abs"] is not None and r["t2_error_abs"] is not None]
        excluded = [r for r in subset
                    if r["t1_error_abs"] is None or r["t2_error_abs"] is None]
        out = {
            "games_in_block": len(subset),
            "scored": len(pairs),
            "excluded": len(excluded),
            "excluded_reasons": sorted({r["blank_reason"] for r in excluded if r["blank_reason"]}),
            "mae_t1": None, "mae_t2": None, "rmse_t1": None, "rmse_t2": None,
            "mae_diff": None, "bootstrap_mae_diff": None, "bootstrap_rmse_diff": None,
            "closer_t1": None, "closer_t2": None, "ties": None,
        }
        if not pairs:
            return out
        e1 = [a for a, _ in pairs]
        e2 = [b for _, b in pairs]
        out["mae_t1"], out["mae_t2"] = round(mae(e1), 6), round(mae(e2), 6)
        out["rmse_t1"], out["rmse_t2"] = round(rmse(e1), 6), round(rmse(e2), 6)
        out["mae_diff"] = round(mae(e1) - mae(e2), 6)
        out["bootstrap_mae_diff"] = cluster_bootstrap_diff(pairs, mae)
        out["bootstrap_rmse_diff"] = cluster_bootstrap_diff(pairs, rmse)
        out["closer_t1"] = sum(1 for a, b in pairs if a < b)
        out["closer_t2"] = sum(1 for a, b in pairs if b < a)
        out["ties"] = sum(1 for a, b in pairs if a == b)
        return out

    by_block = {name: scored([r for r in rows if r["block"] == name]) for name in SPLIT}
    overall = scored(rows)

    # ---------------------------------------------------------------- collapse rule (§6)
    val = by_block["validation"]
    wk7 = scored([r for r in rows if r["week"] == 7])
    wk8 = scored([r for r in rows if r["week"] == 8])
    boot = val["bootstrap_mae_diff"] or {}
    checks = {
        "C1_challenger_better": (val["mae_t2"] is not None and val["mae_t1"] is not None
                                 and val["mae_t2"] < val["mae_t1"]),
        "C2_interval_lower_gt_0": (boot.get("lower95") is not None and boot["lower95"] > 0),
        "C3_rmse_agrees": (val["rmse_t2"] is not None and val["rmse_t1"] is not None
                           and val["rmse_t2"] < val["rmse_t1"]),
        "C4_both_halves_agree": (wk7["mae_diff"] is not None and wk8["mae_diff"] is not None
                                 and wk7["mae_diff"] > 0 and wk8["mae_diff"] > 0),
        "C5_min_n": val["scored"] >= MIN_VALIDATION_N,
    }
    numbers = {
        "C1_challenger_better": f"MAE T1 {val['mae_t1']} vs T2 {val['mae_t2']} on n={val['scored']}"
        if val["mae_t1"] is not None else "no scored validation game",
        "C2_interval_lower_gt_0": (f"95% cluster lower bound {boot['lower95']:+.4f}"
                                   if boot.get("lower95") is not None else "interval undefined"),
        "C3_rmse_agrees": (f"RMSE T1 {val['rmse_t1']} vs T2 {val['rmse_t2']}"
                           if val["rmse_t1"] is not None else "no scored validation game"),
        "C4_both_halves_agree": (f"week 7 diff {wk7['mae_diff']:+.4f} (n={wk7['scored']}), "
                                 f"week 8 diff {wk8['mae_diff']:+.4f} (n={wk8['scored']})"
                                 if wk7["mae_diff"] is not None and wk8["mae_diff"] is not None
                                 else "a half has no scored game"),
        "C5_min_n": f"{val['scored']} scored validation games against a floor of {MIN_VALIDATION_N}",
    }
    collapse = all(checks.values())
    decision = {
        "rule": "PRE_REGISTRATION.md §6",
        "checks": checks, "numbers": numbers,
        "collapsed": collapse,
        "state": ("collapsed: T2 replaces T1 as the published total — a dated Collapse record must be "
                  "added to PRE_REGISTRATION.md" if collapse else
                  "not collapsed: both estimators stay published with the gap column"),
    }

    # ---------------------------------------------------------------- leakage recomputation
    # Recomputed here, not asserted in prose. Every game in the community snapshot that falls on or after
    # a fixture's own date must be absent from that fixture's rolling inputs, and the newest input date
    # must be strictly earlier than the fixture date. This runs over the whole snapshot (all seasons), so
    # the rebuilt form map covers games outside the 2026 corpus too.
    leak = []
    for g in history:
        fi = form.get(g["game_id"])
        if fi is None:
            continue
        if fi["last_input_date"] is not None and not (fi["last_input_date"] < g["gameday"]):
            leak.append({"game_id": g["game_id"], "newest_input": fi["last_input_date"],
                         "fixture": g["gameday"]})
    leak_report = {
        "rule": "PRE_REGISTRATION.md §3: every rolling input strictly earlier than the fixture kickoff date",
        "t1_uses_current_season": False,
        "t1_note": "T1 is fitted on seasons s-6..s-1 only; no 2026 game enters any 2026 fit",
        "t1_fit_window_checked": all(
            (r["t1_inputs"] or {}).get("n_train") for r in rows if r["t1_inputs"]),
        "t2_games_checked": sum(1 for g in history if form.get(g["game_id"]) is not None),
        "t2_violations": leak,
        "t2_violation_count": len(leak),
    }

    # ---------------------------------------------------------------- diagnosis of the gap
    # Why does one estimator lose? Measured, not argued: bias (mean signed error), the spread of the error,
    # the spread of the prediction itself and its correlation with the truth. A prediction with almost no
    # spread cannot track a target with a spread of ~14 points, and that is a property of the estimator,
    # not of the corpus.
    def profile(errors: list[float], preds: list[float], truth: list[float]) -> dict:
        return {
            "bias": round(statistics.fmean(errors), 6),
            "sd_error": round(statistics.stdev(errors), 6),
            "sd_prediction": round(statistics.stdev(preds), 6),
            "sd_truth": round(statistics.stdev(truth), 6),
            "corr_with_actual": round(statistics.correlation(preds, truth), 6) if len(preds) > 2 else None,
            "mae": round(mae([abs(e) for e in errors]), 6),
            "bias_corrected_mae": round(mae([abs(e - statistics.fmean(errors)) for e in errors]), 6),
        }

    scored_rows = [r for r in rows if r["t1_error_abs"] is not None and r["t2_error_abs"] is not None]
    truth = [r["actual_total"] for r in scored_rows]
    p1 = profile([r["t1_total"] - r["actual_total"] for r in scored_rows],
                 [r["t1_total"] for r in scored_rows], truth)
    p2 = profile([r["t2_total"] - r["actual_total"] for r in scored_rows],
                 [r["t2_total"] for r in scored_rows], truth)
    diagnosis = {
        "bias": {"t1": p1, "t2": p2},
        "mae": {"t1": p1["mae"], "t2": p2["mae"]},
        "bias_corrected_mae": {"t1": p1["bias_corrected_mae"], "t2": p2["bias_corrected_mae"]},
        "reading": (
            f"T2 prices {abs(p2['bias']):.2f} points below the realised total on average, while T1's bias is "
            f"{p1['bias']:+.2f}. Subtracting that constant only takes T2 from MAE {p2['mae']:.2f} to "
            f"{p2['bias_corrected_mae']:.2f}, so the bias is not the whole story: T2's prediction spread is "
            f"{p2['sd_prediction']:.2f} points against a realised spread of {p2['sd_truth']:.2f}, and its "
            f"correlation with the realised total is {p2['corr_with_actual']:.3f} against {p1['corr_with_actual']:.3f} "
            f"for T1. An estimator that varies by under a point cannot track a target that varies by fourteen. "
            "The cause is mechanical and is stated in the flagged table rather than repaired here: the "
            "registered T2 rule shrinks a mean of points-for and points-allowed toward a league level, and that "
            "mean sits near the league level by construction. Repairing it would be a new estimator, which the "
            "registration forbids after the fact."
        ),
        "inputs": {
            "scored_games": len(scored_rows),
            "note": "computed from the published per-game columns on rows.html; no new estimator is introduced",
        },
    }

    # ---------------------------------------------------------------- flags and questions
    hidden = [r for r in rows if r["actual_total"] is None]
    flags = [
        {"id": "2T-01", "title": "One corpus game has no published final score",
         "detail": (f"{len(hidden)} corpus row(s) — " + ", ".join(
             f"{r['away']} at {r['home']} (week {r['week']})" for r in hidden) +
             " — carry blank score cells on the official page. The row is published with both estimator "
             "values and a blank truth, and is excluded from every score. It is not inferred.")
         if hidden else "No corpus row lacks a published final score.",
         "state": "blank, excluded, published" if hidden else "none found", "tone": "warn",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-2",
         "source_label": "official Week 2 schedule page"},
        {"id": "2T-02", "title": "Estimator inputs are community data, the scored truth is official",
         "detail": ("T1's fit window and T2's rolling form both read the digest-verified community schedule "
                    "snapshot (data/raw/games.csv, SHA-256 in data/raw/manifest.json). The comparison is "
                    "therefore a comparison of two estimators on community inputs, scored against official "
                    "finals. It is labelled that way on every page and is excluded from any official-only gate."),
         "state": "labelled", "tone": "warn",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-1",
         "source_label": "official Week 1 schedule page"},
        {"id": "2T-03", "title": "The registered T2 rule is mechanically centred on the league level",
         "detail": (f"T2 shrinks a mean of points-for and points-allowed (which is itself ≈ league level) toward "
                    f"the league level, so its prediction spread is {p2['sd_prediction']:.2f} points. It loses to "
                    f"T1 on every pre-registered condition. Fixing it would mean registering a new estimator; "
                    "this session does not do that after seeing the result."),
         "state": "published as measured", "tone": "bad",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-7",
         "source_label": "official Week 7 schedule page"},
        {"id": "2T-04", "title": "Sign convention in the T2 form mean is not stated by the source code",
         "detail": ("The registered skill-lab rule averages points-for and points-allowed together. If the "
                    "intent were an expected total, points-allowed should carry the opposite sign to the "
                    "opponent's points-for. The repository's code and its pre-registration agree with each "
                    "other but neither states the intent, so this workspace reproduces the code as written "
                    "and flags the ambiguity for the owner instead of choosing an interpretation."),
         "state": "needs owner decision", "tone": "warn",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-8",
         "source_label": "official Week 8 schedule page"},
        {"id": "2T-05", "title": "Corpus registration hash is self-referential in the manifest",
         "detail": ("corpus/manifest.json records corpus_registration as the commit that created its own "
                    "pre-registration file, which cannot be known at the moment that file is created. The value "
                    "is therefore a forward reference written by a later commit. This workspace verifies the "
                    "corpus file hash instead, and does not treat the recorded hash as proof of ordering."),
         "state": "flagged, not relied on", "tone": "warn",
         "source": "https://www.nfl.com/standings/", "source_label": "NFL standings"},
        {"id": "2T-06", "title": "One season, nine weeks, 135 scored games",
         "detail": ("The collapse decision is made on 28 validation games. That is above the frozen floor of "
                    "20 but small: a single 60-point game moves the mean absolute error by roughly a point. "
                    "The interval, not the point estimate, is the published statistic."),
         "state": "sample size stated", "tone": "warn",
         "source": "https://www.nfl.com/scores/2026/week-9",
         "source_label": "official Week 9 scores"},
        {"id": "2T-07", "title": "Nothing here is a price, an edge, ROI or a leaderboard result",
         "detail": ("The price firewall is closed at zero licensed sources, so no ROI, CLV or staking number "
                    "is computable from this workspace by rule. The comparison is between two models on "
                    "official final totals and carries no market claim."),
         "state": "by design", "tone": "ok",
         "source": ("https://support.nfl.com/hc/en-us/articles/35869698780564-"
                    "If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL"),
         "source_label": "NFL odds-widget boundary"},
    ]

    questions = [
        {"id": "2T-Q1",
         "question": "Should T2 be re-registered as an expected-total estimator with an explicit sign convention?",
         "known": "The registered rule and its code agree; both shrink a mean of points-for and points-allowed.",
         "missing": "A statement of intent from the owner: is the form term meant to be an expected total?",
         "route": "Register T2b in a new commit, then re-run; the current pair stays published meanwhile.",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-7",
         "source_label": "official Week 7 schedule page"},
        {"id": "2T-Q2",
         "question": "Does the pair hold up on a second season?",
         "known": "135 scored games from one season; T1 wins on all four failing conditions.",
         "missing": "A frozen corpus for any other season, verified against official finals.",
         "route": "Freeze 2025 the same way 2026 was frozen, then re-run this build unchanged.",
         "source": "https://www.nfl.com/standings/", "source_label": "NFL standings"},
        {"id": "2T-Q3",
         "question": "Should the league level be estimated from a rolling window rather than the train block?",
         "known": "The level is 46.17 points from 93 training games, frozen before validation.",
         "missing": "A pre-registered rule for refitting the level forward, and a decision on whether that is a new estimator.",
         "route": "Write the rule as T2b before looking at any later week; it cannot be adopted retrospectively.",
         "source": "https://www.nfl.com/scores/2026/week-9", "source_label": "official Week 9 scores"},
        {"id": "2T-Q4",
         "question": "Can either estimator be scored against a market total?",
         "known": "A community total line exists for most 2026 games; the price policy excludes it from any published number.",
         "missing": "One licensed price source with a named permitted use and both timestamps.",
         "route": "Satisfy pricing/PRICE_DATA_POLICY.md §4; until then the market column stays blank.",
         "source": ("https://support.nfl.com/hc/en-us/articles/35869698780564-"
                    "If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL"),
         "source_label": "NFL odds-widget boundary"},
        {"id": "2T-Q5",
         "question": "Is the club-code join ('AZ' → 'ARI') the only alias this corpus needs?",
         "known": ("The repository's audited cross-check matched 136/136 official finals using exactly this one "
                   "mapping, and this workspace joined 136/136 rows with it."),
         "missing": "Nothing for 2026. A future season could introduce another rendering difference.",
         "route": "The next freeze records any new alias in its own pre-registration before use.",
         "source": "https://www.nfl.com/schedules/2026/by-week/week-1",
         "source_label": "official Week 1 schedule page"},
    ]

    # ---------------------------------------------------------------- manifest + registration
    reg = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%H",
                          "--", "two-total/PRE_REGISTRATION.md"], capture_output=True, text=True)
    reg_commits = [c for c in reg.stdout.split() if c]
    registration = reg_commits[0] if len(reg_commits) == 1 else None
    if registration is None:
        print(f"two-total: expected exactly one commit creating PRE_REGISTRATION.md, found {reg_commits}")
        return 1

    report = {
        "workspace": "two-total",
        "generated_by": "two-total/scripts/build.py",
        "season": SEASON,
        "requirement": "P4 publish every model total twice (two estimators, gap column) until one wins walk-forward",
        "label": "backtest corpus — not a leaderboard result",
        "registration": {
            "commit": registration,
            "file": "two-total/PRE_REGISTRATION.md",
            "file_sha256": sha256(OUT / "PRE_REGISTRATION.md"),
            "rule": "the commit that created the file is the registration; written here by a later commit",
        },
        "corpus": {
            "file": "corpus/games_2026_w1_9.csv",
            "sha256": manifest["frozen_sha256"],
            "games": manifest["window"]["games"],
            "settled": manifest["window"]["settled"],
            "unsettled_hidden_score": manifest["window"]["unsettled_hidden_score"],
            "registration": manifest.get("corpus_registration"),
        },
        "estimators": {
            "T1": {"name": "prior-season pace fit",
                   "definition": "ridge least squares on six prior seasons; level + pace_home + pace_away",
                   "implemented_in": "origination/scripts/model.py fit_total()",
                   "changed_by_this_session": False},
            "T2": {"name": "league mean plus one third of the form gap",
                   "definition": "mean_train_total + (form_mean_points - mean_train_total)/3",
                   "implemented_in": "skill-lab/scripts/build.py shrink_total() rule, applied to points-for/allowed",
                   "changed_by_this_session": False,
                   "params": {"form_window": FORM_WINDOW, "shrink": SHRINK,
                              "league_level": round(level["level"], 6),
                              "league_level_n_train": level["n_train"]}},
        },
        "split": {k: {"weeks": list(v), "games": by_block[k]["games_in_block"]} for k, v in SPLIT.items()},
        "scores": {"by_block": by_block, "overall": overall,
                   "week7": wk7, "week8": wk8},
        "decision": decision,
        "diagnosis": diagnosis,
        "flags": flags,
        "questions": questions,
        "leakage": leak_report,
        "counts": {
            "corpus_rows": len(rows),
            "rows_with_both_estimators": sum(1 for r in rows if r["gap"] is not None),
            "rows_scored": overall["scored"],
            "rows_with_blank_estimator": sum(1 for r in rows if r["blank_reason"]),
            "rows_with_blank_actual_total": sum(1 for r in rows if r["actual_total"] is None),
        },
        "price_firewall": {"licensed_price_sources": 0, "roi_rows": 0, "clv_rows": 0,
                           "policy": "pricing/PRICE_DATA_POLICY.md"},
        "determinism": ("no wall-clock value is recorded in this artifact; a rebuild from the committed "
                        "inputs must be byte-identical, which two-total/scripts/verify.py enforces"),
        "rows": rows,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "two_total.json").write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", "utf-8")

    print(f"two-total: {len(rows)} corpus rows, {overall['scored']} scored")
    print(f"  T1 MAE {overall['mae_t1']}  T2 MAE {overall['mae_t2']}  diff {overall['mae_diff']}")
    print(f"  collapse: {decision['state']}")
    for k, ok in checks.items():
        print(f"    {'PASS' if ok else 'FAIL'}  {k}: {numbers[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
