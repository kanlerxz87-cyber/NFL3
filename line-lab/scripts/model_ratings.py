#!/usr/bin/env python3
"""
model_ratings.py — line-origination engine (v0 baseline).

Every number this script prints is reproducible from data/standings_2026.json,
which was transcribed verbatim from the official NFL.com standings page (S01).

Design notes
------------
The rating is a classic additive points model:

    points_A = mu + off_A - def_B
    margin_A = (off_A + def_A) - (off_B + def_B) = r_A - r_B

where off_i = PF_i/G, def_i = PA_i/G and r_i = (PF_i - PA_i)/G.

That identity is exact within the model, so the model margin is r_A - r_B and the
model total is L + r_A + r_B, with L the league average total points per game.

Known limitations (deliberate, documented, flagged on the site):
  * No opponent adjustment: r_i credits a team for playing weak opponents. Fixing
    this needs a game-level log (F-04).
  * Home-field advantage and game-margin sigma cannot be estimated without a
    game log, so they are treated as *parameters* with a sensitivity table
    rather than invented constants (A-01, A-02).
  * Shrinkage k is an explicit assumption (A-03).

Output: data/model_outputs.json
"""

import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ----------------------------------------------------------------------------
# Parameters that CANNOT be verified from an official source. Declared once,
# published on the site, and varied in the sensitivity table. Never hidden.
# ----------------------------------------------------------------------------
SHRINK_K = 2.0          # A-03: r' = r * G/(G+k)
SIGMA_MARGIN = 13.5     # A-02: assumed sd of NFL game margin, points
HFA_SENSITIVITY = [0.0, 1.5, 2.5, 3.5]   # A-01: home-field advantage, points


def load():
    with open(os.path.join(DATA, "standings_2026.json")) as f:
        return json.load(f)


def norm_cdf(x, mu=0.0, sigma=1.0):
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fisher_p(r, n):
    """Two-sided p-value via Fisher z. Approximation, adequate for n=32."""
    if r is None or abs(r) >= 1.0:
        return None
    z = math.atanh(r) * math.sqrt(n - 3)
    return math.erfc(abs(z) / math.sqrt(2.0))


def fit_pythagorean_exponent(teams):
    """Pick k minimising squared error between PF^k/(PF^k+PA^k) and actual win pct.

    No external constant is assumed; k is estimated from the 32-team snapshot.
    """
    actual = [(t["w"] + 0.5 * t["t"]) / (t["w"] + t["l"] + t["t"]) for t in teams]
    best_k, best_sse = None, None
    k = 0.50
    while k <= 6.0001:
        sse = 0.0
        for t, a in zip(teams, actual):
            pf, pa = float(t["pf"]), float(t["pa"])
            p = (pf ** k) / (pf ** k + pa ** k)
            sse += (p - a) ** 2
        if best_sse is None or sse < best_sse:
            best_k, best_sse = k, sse
        k += 0.01
    return round(best_k, 2), best_sse


def build_ratings(doc):
    teams = doc["teams"]
    total_pf = sum(t["pf"] for t in teams)
    total_games = sum(t["w"] + t["l"] + t["t"] for t in teams)
    league_ppg = total_pf / total_games          # points per team per game
    league_total = 2 * league_ppg

    k_pyth, sse = fit_pythagorean_exponent(teams)

    out = []
    for t in teams:
        g = t["w"] + t["l"] + t["t"]
        wp = (t["w"] + 0.5 * t["t"]) / g
        off = t["pf"] / g
        dfn = t["pa"] / g
        r = (t["pf"] - t["pa"]) / g
        r_shrunk = r * g / (g + SHRINK_K)
        pyth = (t["pf"] ** k_pyth) / (t["pf"] ** k_pyth + t["pa"] ** k_pyth)
        exp_wins = pyth * g
        luck = (t["w"] + 0.5 * t["t"]) - exp_wins
        out.append({
            "abbr": t["abbr"],
            "name": t["name"],
            "conference": t["conference"],
            "division": t["division"],
            "team_url": t["team_url"],
            "games": g,
            "w": t["w"], "l": t["l"], "t": t["t"],
            "win_pct": round(wp, 4),
            "pf": t["pf"], "pa": t["pa"], "net": t["net"],
            "off_ppg": round(off, 2),
            "def_ppg": round(dfn, 2),
            "net_ppg": round(r, 2),
            "rating_shrunk": round(r_shrunk, 3),
            "pythag_win_pct": round(pyth, 4),
            "expected_wins": round(exp_wins, 2),
            "luck_wins": round(luck, 2),
            "src": "S01",
        })

    corr = compute_correlations(out, k_pyth)
    return out, {
        "league_ppg_per_team": round(league_ppg, 3),
        "league_total_points": round(league_total, 3),
        "total_team_games": total_games,
        "pythagorean_exponent_fitted": k_pyth,
        "pythagorean_sse": round(sse, 5),
    }, corr


def compute_correlations(rows, k_pyth):
    n = len(rows)

    def series(key):
        return [r[key] for r in rows]

    # division_record / last5 live on the raw standings document, in the same
    # club order as the derived rows, so index alignment is exact.
    with open(os.path.join(DATA, "standings_2026.json")) as f:
        src = json.load(f)["teams"]
    assert [t["abbr"] for t in src] == [r["abbr"] for r in rows], "club order must match"
    last5 = [_rec_pct(t["last5"]) for t in src]
    divrec = [_rec_pct(t["division_record"]) for t in src]

    def _prior_pct(t):
        """Record in the games BEFORE the last five, by subtracting the published
        last-five record from the published season record. Pure arithmetic on two
        official numbers; nothing is inferred."""
        w, l, tt = int(t["w"]), int(t["l"]), int(t["t"])
        gw, gl, gt = [int(x) for x in t["last5"].split("-")]
        pw, pl, pt = w - gw, l - gl, tt - gt
        if pw < 0 or pl < 0 or pt < 0:
            return None
        g = pw + pl + pt
        return (pw + 0.5 * pt) / g if g else None

    prior = [_prior_pct(t) for t in src]

    pairs = [
        ("C1", "net points per game", "win pct", series("net_ppg"), series("win_pct"),
         "The core skill signal: how much of a club's record its scoring margin explains."),
        ("C2", "points for per game", "win pct", series("off_ppg"), series("win_pct"),
         "Offence-only signal strength."),
        ("C3", "points against per game", "win pct", series("def_ppg"), series("win_pct"),
         "Defence-only signal strength."),
        ("C4", "points for per game", "points against per game", series("off_ppg"), series("def_ppg"),
         "Cross-sectional pairing of offence and defence; near-zero means a club's offence and defence are unrelated, so scoring margin carries both."),
        ("C5", "Pythagorean win pct (fitted)", "actual win pct", series("pythag_win_pct"), series("win_pct"),
         "Model calibration: how much of the table the scoring model reproduces."),
        ("C6", "division win pct", "overall win pct", divrec, series("win_pct"),
         "Does intra-division form track overall form? Low values argue against 'division form' as a standalone signal."),
        ("C7", "last five games win pct", "season win pct", last5, series("win_pct"),
         "PART-WHOLE CAUTION: the last five games are a subset of the season record, so this r is "
         "mechanically inflated and is NOT evidence of momentum. Reported only to show the size of "
         "the artefact; use C8 for the real test."),
        ("C8", "win pct in games before the last five", "win pct in the last five",
         prior, last5,
         "Split-half reliability, NOT a momentum effect. Two disjoint blocks of the same season, but both "
         "measure the same underlying club quality, so a positive r is expected even with zero momentum. "
         "Read it as an upper bound on how much a 3-4 game block is worth; a true momentum test must "
         "control for quality (needs a game log, F-04)."),
    ]

    res = []
    for cid, ax, ay, xs, ys, note in pairs:
        r = pearson(xs, ys)
        p = fisher_p(r, n)
        res.append({
            "id": cid, "x": ax, "y": ay,
            "r": None if r is None else round(r, 4),
            "r2": None if r is None else round(r * r, 4),
            "p_value": None if p is None else round(p, 6),
            "n": n,
            "note": note,
            "mechanical": note.startswith("PART-WHOLE"),
            "src": "S01",
            "provenance": "derived",
        })

    # R^2 of the margin->win relation, stated separately because it is the
    # number the whole 'skill vs luck' split rests on.
    r_net = pearson(series("net_ppg"), series("win_pct"))
    share = {
        "r": round(r_net, 4),
        "r2": round(r_net * r_net, 4),
        "pct_of_win_variance_explained_by_margin": round(100 * r_net * r_net, 1),
        "pct_residual": round(100 * (1 - r_net * r_net), 1),
        "note": ("The share of between-club win-pct variance that scoring margin explains. "
                 "The complement is what one-score games, opponent quality and chance left over "
                 "— i.e. the size of the luck pool that any strategy must avoid claiming."),
    }
    return {"pairs": res, "variance_decomposition": share}


def _rec_pct(rec):
    try:
        w, l, t = [int(x) for x in rec.split("-")]
    except Exception:
        return None
    g = w + l + t
    return (w + 0.5 * t) / g if g else None


def build_lines(ratings, league, matchups):
    by = {r["abbr"]: r for r in ratings}
    L = league["league_total_points"]
    out = []
    for m in matchups:
        a, h = by[m["away"]], by[m["home"]]
        ra, rh = a["rating_shrunk"], h["rating_shrunk"]
        neutral_home_margin = rh - ra
        # Two totals estimators, deliberately both published.
        total_additive = L + rh + ra                     # implied by the additive points model
        total_average = ((a["pf"] + a["pa"]) / a["games"] + (h["pf"] + h["pa"]) / h["games"]) / 2
        model_total = total_average
        is_neutral = bool(m.get("neutral_site"))
        rows = []
        for hfa in HFA_SENSITIVITY:
            hm = neutral_home_margin + (0.0 if is_neutral else hfa)
            wp_home = norm_cdf(hm, 0.0, SIGMA_MARGIN)
            rows.append({
                "hfa": hfa,
                "home_margin": round(hm, 2),
                "home_spread": round(-hm, 2),
                "model_total": round(model_total, 2),
                "home_spread_rounded": round(round(-hm * 2) / 2, 1),
                "home_win_prob": round(wp_home, 4),
                "away_win_prob": round(1 - wp_home, 4),
            })
        out.append({
            "id": m["id"],
            "away": m["away"], "home": m["home"],
            "away_name": a["name"], "home_name": h["name"],
            "kickoff_et": m["kickoff_et"],
            "network": m["network"],
            "note": m["note"],
            "away_rating": ra, "home_rating": rh,
            "away_games": a["games"], "home_games": h["games"],
            "neutral_site": is_neutral,
            "neutral_home_margin": round(neutral_home_margin, 2),
            "model_total": round(model_total, 2),
            "model_total_additive": round(total_additive, 2),
            "model_total_average": round(total_average, 2),
            "variants": rows,
            "src": m["source_id"],
            "provenance": "derived",
            "is_market_line": False,
        })
    return out


def main():
    doc = load()
    ratings, league, corr = build_ratings(doc)
    lines = build_lines(ratings, league, doc["verified_matchups_week10"])

    payload = {
        "meta": {
            "title": "Line-origination engine v0 — model outputs",
            "generated": "2026-11-12",
            "generator": "scripts/model_ratings.py",
            "inputs": "data/standings_2026.json (S01, official NFL.com standings, 2026 REG)",
            "warning": ("These are MODEL-IMPLIED numbers, not market lines. No official NFL odds source "
                        "exists (I-04), so no comparison with a market price, no closing-line value and no "
                        "backtest could be computed. Do not treat any number here as a price."),
            "assumptions": [
                {"id": "A-01", "name": "Home-field advantage", "value": "0.0 baseline; 1.5 / 2.5 / 3.5 in sensitivity",
                 "why": "Cannot be estimated without a game-level log; no official NFL source publishes a league HFA constant."},
                {"id": "A-02", "name": "Game-margin sigma", "value": SIGMA_MARGIN,
                 "why": "Used only to convert a margin into a win probability. Not estimated from data in this build."},
                {"id": "A-05", "name": "Totals specification", "value": "average-of-club-game-totals published as the headline; additive-model total published alongside",
                 "why": ("The additive points model forces total = league_total + r_A + r_B, which mechanically "
                         "drives totals down when two weak clubs meet. The average-of-club-game-totals estimator "
                         "is the more defensible headline. Both are shown; they disagree, and that disagreement "
                         "is itself the signal that totals need a dedicated model (F-04).")},
                {"id": "A-06", "name": "Neutral-site treatment", "value": "home-field term forced to 0 for the Munich game",
                 "why": "No official NFL source publishes a neutral-site adjustment; forcing 0 is a stated choice, not a measurement."},
                {"id": "A-03", "name": "Shrinkage k", "value": SHRINK_K,
                 "why": "r' = r*G/(G+k) pulls small samples toward league average. k=2 with 8-9 game samples shrinks ~20%."},
            ],
        },
        "league": league,
        "ratings": ratings,
        "correlations": corr,
        "lines": lines,
    }

    # depth / availability stress model
    payload["depth_stress"] = build_depth_stress()
    payload["luck_table"] = build_luck(ratings)

    with open(os.path.join(DATA, "model_outputs.json"), "w") as f:
        json.dump(payload, f, indent=1)

    print("league total  :", league["league_total_points"])
    print("pythag k      :", league["pythagorean_exponent_fitted"])
    for c in corr["pairs"]:
        print(f'{c["id"]}  r={c["r"]:+.3f}  r2={c["r2"]:.3f}  p={c["p_value"]:.4g}  {c["x"]} vs {c["y"]}')
    print("margin->wins r2:", corr["variance_decomposition"])
    print("lines:", len(lines))
    print("luck table rows:", len(payload["luck_table"]))


# ---------------------------------------------------------------------------
# Availability / depth-stress
# ---------------------------------------------------------------------------
POSITION_GROUP = {
    "QB": "offense", "RB": "offense", "FB": "offense", "WR": "offense", "TE": "offense",
    "T": "offense", "G": "offense", "C": "offense", "OT": "offense",
    "DE": "defense", "DT": "defense", "LB": "defense", "CB": "defense", "S": "defense",
    "SAF": "defense", "DB": "defense",
    "K": "special", "P": "special", "LS": "special",
}

# Weight = how much a single unavailable body at that position is assumed to move
# a team's scoring margin, in points. ASSUMPTION (A-04): no official source
# publishes position value weights. Published as an editable parameter, never
# presented as measured.
POSITION_WEIGHT = {
    "QB": 2.0, "T": 0.6, "G": 0.5, "C": 0.5, "OT": 0.6,
    "WR": 0.5, "TE": 0.4, "RB": 0.4, "FB": 0.1,
    "DE": 0.6, "DT": 0.5, "LB": 0.5, "CB": 0.7, "S": 0.6, "SAF": 0.6, "DB": 0.7,
    "K": 0.5, "P": 0.2, "LS": 0.05,
}

PRACTICE_WEIGHT = {"Did Not Participate": 1.0, "Limited Participation": 0.5, "Full Participation": 0.0}


def build_depth_stress():
    with open(os.path.join(DATA, "injuries.json")) as f:
        inj = json.load(f)
    rows = inj["rows"]
    by_team = {}
    for r in rows:
        t = by_team.setdefault(r["team"], {"team": r["team"], "listed": 0, "dnp": 0, "limited": 0,
                                           "offense": 0, "defense": 0, "special": 0,
                                           "out": 0, "doubtful": 0, "questionable": 0,
                                           "raw_stress": 0.0, "positions": {}})
        t["listed"] += 1
        t["positions"][r["pos"]] = t["positions"].get(r["pos"], 0) + 1
        grp = POSITION_GROUP.get(r["pos"], "unknown")
        if grp in ("offense", "defense", "special"):
            t[grp] += 1
        pw = PRACTICE_WEIGHT.get(r["pr"], 0.0)
        if r["pr"] == "Did Not Participate":
            t["dnp"] += 1
        elif r["pr"] == "Limited Participation":
            t["limited"] += 1
        gs = (r["gs"] or "").lower()
        if gs == "out":
            t["out"] += 1
        elif gs == "doubtful":
            t["doubtful"] += 1
        elif gs == "questionable":
            t["questionable"] += 1
        # game status overrides practice weight: Out is certain
        status_mult = {"out": 1.0, "doubtful": 0.9, "questionable": 0.6}.get(gs, pw)
        t["raw_stress"] += POSITION_WEIGHT.get(r["pos"], 0.25) * status_mult
    teams = []
    for t in by_team.values():
        teams.append({
            "team": t["team"],
            "listed": t["listed"],
            "dnp": t["dnp"], "limited": t["limited"],
            "offense_listed": t["offense"], "defense_listed": t["defense"], "special_listed": t["special"],
            "out": t["out"], "doubtful": t["doubtful"], "questionable": t["questionable"],
            "positions": t["positions"],
            "raw_stress": round(t["raw_stress"], 2),
            "src": "S05",
        })
    teams.sort(key=lambda x: -x["raw_stress"])
    # normalise to a 0-100 index against the max in this snapshot
    mx = max((t["raw_stress"] for t in teams), default=0) or 1
    for i, t in enumerate(teams):
        t["depth_stress_index"] = round(100 * t["raw_stress"] / mx, 1)
        t["rank"] = i + 1
    return {
        "meta": {
            "definition": ("DepthStress = sum over listed players of "
                           "position_weight x availability_weight, where availability_weight is "
                           "1.0 for Out / Did Not Participate, 0.9 for Doubtful, 0.6 for Questionable, "
                           "0.5 for Limited Participation, 0 for Full Participation."),
            "what_it_is_not": ("It is NOT a depth-chart measure. It says how much verified availability "
                               "is degraded at a position, not who replaces whom. The official NFL.com "
                               "roster feed exposes position and roster status but no depth order (R14), "
                               "so '2nd/3rd/4th string' attribution cannot be verified and is left out."),
            "weights_are_assumptions": True,
            "assumption_id": "A-04",
            "coverage": inj["meta"]["coverage"],
            "teams_covered": len(teams),
            "source_id": "S05",
        },
        "teams": teams,
    }


def build_luck(ratings):
    rows = sorted(ratings, key=lambda r: r["luck_wins"])
    out = []
    for r in rows:
        out.append({
            "abbr": r["abbr"], "name": r["name"],
            "w": r["w"], "l": r["l"], "t": r["t"],
            "games": r["games"],
            "win_pct": r["win_pct"],
            "pythag_win_pct": r["pythag_win_pct"],
            "expected_wins": r["expected_wins"],
            "luck_wins": r["luck_wins"],
            "direction": "over-performing" if r["luck_wins"] > 0 else ("under-performing" if r["luck_wins"] < 0 else "as expected"),
            "team_url": r["team_url"],
            "src": "S01",
            "provenance": "derived",
        })
    return out


if __name__ == "__main__":
    main()
