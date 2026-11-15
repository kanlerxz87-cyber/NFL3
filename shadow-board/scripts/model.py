"""Frozen team-strength model for the Shadow Board.

Implements PREREGISTRATION.md §2 (features) and §3 (forecast) exactly. Pure standard library, no randomness,
so a build is reproducible from the repository alone. Nothing here reads a price, a depth chart or an injury
report: the pre-registration forbids it.

Run:  python3 shadow-board/scripts/model.py            # prints the Week 11 forecast table as JSON
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "decision-desk" / "data" / "games_2026.csv"

# Constants fixed by PREREGISTRATION.md §2-§3. Editing one of them without an amendment invalidates the run.
K_SHRINK = 2.0            # games of pseudo-play added by the shrinkage factor
SIGMA_FLOOR = 10.0        # lower bound on the margin sd used in the probability transform
SIGMA_CAP = 17.0           # upper bound on the same quantity
ROUND_TO = 0.5            # published line rounding
# The 2026 game log abbrevinates Arizona "AZ" while the schedule and standings pages print "ARI". Canonical here.
ALIASES = {"AZ": "ARI"}

TEAMS = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND",
         "JAX", "KC", "LA", "LAC", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF",
         "TB", "TEN", "WAS", "LV"]


def canon(code: str) -> str:
    return ALIASES.get(code.strip(), code.strip())


def load_corpus(path: Path = CORPUS) -> list[dict]:
    """Read the official 2026 game log. Rows without two published scores are returned flagged, never filled."""
    out = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            away_score, home_score = row["away_score"].strip(), row["home_score"].strip()
            complete = bool(away_score) and bool(home_score)
            out.append({
                "season": int(row["season"]),
                "week": int(row["week"]),
                "date": row["kickoff_date_et"],
                "slot": row["slot"],
                "away": canon(row["away_team"]),
                "home": canon(row["home_team"]),
                "away_score": int(away_score) if away_score else None,
                "home_score": int(home_score) if home_score else None,
                "source_url": row["source_url"],
                "complete": complete,
                "tie": complete and int(away_score) == int(home_score),
            })
    return out


def _shrink(values: dict, league_mean: float, games: dict) -> dict:
    return {t: league_mean + (games[t] / (games[t] + K_SHRINK)) * (values[t] - league_mean) if games[t] else league_mean
            for t in values}


def features(games: list[dict]) -> dict:
    """§2 feature build over the supplied (already as-of-filtered) games."""
    played = [g for g in games if g["complete"]]
    pf = {t: 0 for t in TEAMS}
    pa = {t: 0 for t in TEAMS}
    gp = {t: 0 for t in TEAMS}
    margins, home_pts, away_pts, home_wins = [], [], [], 0.0
    for g in played:
        pf[g["home"]] += g["home_score"]; pa[g["home"]] += g["away_score"]; gp[g["home"]] += 1
        pf[g["away"]] += g["away_score"]; pa[g["away"]] += g["home_score"]; gp[g["away"]] += 1
        margin = g["home_score"] - g["away_score"]
        margins.append(margin)
        home_pts.append(g["home_score"]); away_pts.append(g["away_score"])
        home_wins += 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
    n = len(played)
    net = {t: (pf[t] - pa[t]) / gp[t] if gp[t] else 0.0 for t in TEAMS}
    att = {t: pf[t] / gp[t] if gp[t] else 0.0 for t in TEAMS}
    defr = {t: pa[t] / gp[t] if gp[t] else 0.0 for t in TEAMS}
    seen = {g["home"] for g in played} | {g["away"] for g in played}
    if not seen <= set(TEAMS):
        raise SystemExit(f"corpus codes outside the declared team universe: {sorted(seen - set(TEAMS))}")
    mu_net = sum(net.values()) / len(TEAMS)
    mu_att = sum(att.values()) / len(TEAMS)
    mu_def = sum(defr.values()) / len(TEAMS)
    h_margin = sum(margins) / n if n else 0.0
    h_home_pts = sum(home_pts) / n if n else 0.0
    h_away_pts = sum(away_pts) / n if n else 0.0
    resid = [m - h_margin for m in margins]
    sd = math.sqrt(sum(r * r for r in resid) / (len(resid) - 1)) if len(resid) > 1 else SIGMA_CAP
    sigma = max(SIGMA_FLOOR, min(SIGMA_CAP, sd))
    return {
        "n_games": n,
        "weeks": sorted({g["week"] for g in games}),
        "games": {t: {"gp": gp[t], "pf": pf[t], "pa": pa[t],
                      "net": round(net[t], 4), "att": round(att[t], 4), "def": round(defr[t], 4),
                      "net_s": round(_shrink(net, mu_net, gp)[t], 4),
                      "att_s": round(_shrink(att, mu_att, gp)[t], 4),
                      "def_s": round(_shrink(defr, mu_def, gp)[t], 4),
                      "wins": sum(1 for g in played if g["home"] == t and g["home_score"] > g["away_score"])
                             + sum(1 for g in played if g["away"] == t and g["away_score"] > g["home_score"]),
                      "losses": sum(1 for g in played if g["home"] == t and g["home_score"] < g["away_score"])
                                + sum(1 for g in played if g["away"] == t and g["away_score"] < g["home_score"]),
                      "ties": sum(1 for g in played if (g["home"] == t or g["away"] == t) and g["tie"])}
                 for t in TEAMS},
        "league": {"mu_net": round(mu_net, 4), "mu_att": round(mu_att, 4), "mu_def": round(mu_def, 4),
                   "h_margin": round(h_margin, 4), "h_home_pts": round(h_home_pts, 4),
                   "h_away_pts": round(h_away_pts, 4), "home_rate": round(home_wins / n, 4) if n else None,
                   "sigma": round(sigma, 4), "sd_margin_raw": round(sd, 4)},
        "constants": {"K_SHRINK": K_SHRINK, "SIGMA_FLOOR": SIGMA_FLOOR, "SIGMA_CAP": SIGMA_CAP,
                      "ROUND_TO": ROUND_TO},
    }


def config_hash(feat: dict) -> str:
    """Canonical hash of everything that can change a forecast: constants + league terms + team rates."""
    blob = json.dumps({"constants": feat["constants"], "league": feat["league"],
                       "games": feat["games"], "n_games": feat["n_games"]}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def forecast(feat: dict, away: str, home: str) -> dict:
    """§3 forecast for one fixture. Returns probability, fair side, fair total and the inputs used.

    Two totals are produced. ``fair_total_primary`` is the estimator frozen in §3 and is the only one any gate
    may use. ``fair_total_secondary`` adds each club's own scoring rate to the pairing and is published beside
    it with a gap column, because requirement P4 asks for a second estimator to win a walk-forward comparison
    before the site collapses to one. Choosing between them is a future amendment, never an implicit switch.
    """
    g = feat["games"]
    lg = feat["league"]
    half = (lg["h_home_pts"] - (lg["h_home_pts"] + lg["h_away_pts"]) / 2.0)
    exp_home = lg["mu_att"] + (g[away]["def_s"] - lg["mu_def"]) + half
    exp_away = lg["mu_att"] + (g[home]["def_s"] - lg["mu_def"]) - half
    alt_home = (g[home]["att_s"] + g[away]["def_s"]) / 2.0 + half
    alt_away = (g[away]["att_s"] + g[home]["def_s"]) / 2.0 - half
    margin = lg["h_margin"] + (g[home]["net_s"] - g[away]["net_s"])
    p_home = _phi(margin / lg["sigma"])
    total = exp_home + exp_away
    return {
        "p_home": p_home,
        "p_away": 1.0 - p_home,
        "expected_margin_home": margin,
        "expected_home_points": exp_home,
        "expected_away_points": exp_away,
        "fair_total_secondary": round(alt_home + alt_away, 4),
        "secondary_home_points": alt_home,
        "secondary_away_points": alt_away,
        "fair_spread_home": -round(margin / ROUND_TO) * ROUND_TO,   # home team listed first; negative = home gives
        "fair_total": round(total / ROUND_TO) * ROUND_TO,
        "fair_price_home": 1.0 / p_home if p_home > 0 else None,     # vig-free, not an offer
        "fair_price_away": 1.0 / (1.0 - p_home) if p_home < 1 else None,
        "inputs": {"away": g[away], "home": g[home], "league": lg},
    }


if __name__ == "__main__":
    games = load_corpus()
    feat = features(games)
    print(json.dumps({"as_of_weeks": feat["weeks"], "n_games": feat["n_games"],
                      "league": feat["league"], "config_hash": config_hash(feat)}, indent=2))
