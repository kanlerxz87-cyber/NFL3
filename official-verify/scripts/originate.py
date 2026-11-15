#!/usr/bin/env python3
"""Originate a line for every published fixture, then publish the residual.

Order of origination (frozen for this script): **side first, then the total,
then the moneyline**. The side and total are the two numbers a market quotes;
the moneyline is a monotone transform of the side once a distribution is
assumed, so it is originated last and never invented independently.

What is published, as separate columns and never merged:

  * our fair side (a signed number, home perspective, with the sign convention
    stated on the page);
  * our fair total;
  * our fair moneyline, as a probability and as a decimal price;
  * the market line, **blank** when no official/verified price exists;
  * the residual (our number minus the market), blank whenever the market
    column is blank.

The residual is not fudged to zero. A blank market means "not obtained", which
is different from "no disagreement", and the page says so.

Inputs are the pre-registered fits (see PREREG-2026-OV1). Parameters for the
current production fit are produced by `evaluate.py`'s design matrix but fitted
on **every** game in the corpus, which is the only defensible basis for a
forward number; the walk-forward fits remain the *evaluation*.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import design, load_games, norm_cdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "official-verify" / "data"
OUT = DATA / "origination.json"
SIGMA = 13.5
SIGMA_TOTAL = 13.5


def read_fixtures(name):
    with (DATA / name).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    games = {}
    for row in rows:
        key = (row["week"], row["location"], row["team"], row["opponent"])
        games[key] = row
    fixtures = {}
    for row in rows:
        if row["location"] != "home":
            continue
        away = next(
            r for r in rows
            if r["week"] == row["week"]
            and r["location"] == "away"
            and r["opponent"] == row["team"]
        )
        fixtures[row["week"] + "_" + away["team"] + "_" + row["team"]] = {
            "week": int(row["week"]),
            "home": row["team"],
            "away": away["team"],
            "weekday": row["weekday"],
            "date_et": row["date_et"],
            "kickoff_et": row["kickoff_et"],
            "venue": row["venue_as_published"],
            "neutral": row["neutral_site"] == "yes",
            "source_id": row["source_id"],
            "source_url": row["source_url"],
        }
    return fixtures


def main() -> int:
    games = load_games()
    teams = sorted({g["home"] for g in games} | {g["away"] for g in games})
    mu, hfa, attack, defence = design(games, teams)
    idx = {t: i for i, t in enumerate(teams)}

    # Only fixtures that had not kicked off at capture time are originated.
    # Week 10 games were being played on the capture date, so originating them
    # would be a look-ahead forecast wearing a forecast's clothes.
    fixtures = read_fixtures("week11_fixtures_official.csv")

    board = []
    for key, fx in sorted(fixtures.items(), key=lambda kv: (kv[1]["week"], kv[1]["date_et"])):
        h, a = idx[fx["home"]], idx[fx["away"]]
        # neutral-site fixtures carry no home-field term: the gate is the venue
        # the league published, not our assumption about it.
        venue_hfa = 0.0 if fx["neutral"] else hfa
        exp_home = mu + venue_hfa / 2 + attack[h] - defence[a]
        exp_away = mu - venue_hfa / 2 + attack[a] - defence[h]
        margin = exp_home - exp_away          # positive = home favoured
        total = exp_home + exp_away
        # The published probability is rounded to four decimals; prices are
        # derived from that published value so a reviewer recomputing 1/p from
        # the page reproduces the price exactly rather than approximately.
        p_home = round(norm_cdf(margin / SIGMA), 4)
        fair_home_price = round(1 / p_home, 2) if p_home > 0 else None
        fair_away_price = round(1 / (1 - p_home), 2) if p_home < 1 else None
        board.append(
            {
                "fixture": f"{fx['away']} @ {fx['home']}",
                "week": fx["week"],
                "kickoff_et": f"{fx['weekday']} {fx['date_et']} {fx['kickoff_et']}",
                "venue": fx["venue"] or "",
                "neutral_site": "yes" if fx["neutral"] else "no",
                "origination_order": "side -> total -> moneyline",
                "fair_side_home_perspective": round(-margin, 2),
                "side_sign_convention": "negative = home favoured (the number added to the home margin to settle)",
                "fair_total": round(total, 2),
                "fair_p_home_win": p_home,
                "fair_home_decimal": fair_home_price,
                "fair_away_decimal": fair_away_price,
                "market_side": "",
                "market_total": "",
                "market_p_home": "",
                "residual_side": "",
                "residual_total": "",
                "residual_note": "market not obtained: no licensed or official price series is held (OV-B01)",
                "inputs_attack_home": round(attack[h], 3),
                "inputs_defence_away": round(defence[a], 3),
                "inputs_attack_away": round(attack[a], 3),
                "inputs_defence_home": round(defence[h], 3),
                "inputs_mu": round(mu, 3),
                "inputs_hfa": round(venue_hfa, 3),
                "source_id": fx["source_id"],
                "source_url": fx["source_url"],
            }
        )

    payload = {
        "generated_by": "official-verify/scripts/originate.py",
        "production_fit_games": len(games),
        "sigma": SIGMA,
        "sigma_total": SIGMA_TOTAL,
        "board": board,
        "price_policy": {
            "status": "DECIDED: no market price is published until a licensed or official series is obtained",
            "consequence": (
                "Each market column stays blank and each residual stays blank. A blank is "
                "published as a blank and flagged; it is never filled with a community or "
                "scraped price, and it is never rendered as zero disagreement."
            ),
            "what_would_clear_it": (
                "A documented price source with a reuse grant, plus a dated capture of the "
                "closing number for each fixture, would let the residual be computed."
            ),
        },
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Originated {len(board)} fixtures from {len(games)} official games.")
    for row in board[:5]:
        print(f"  {row['fixture']:12s} side {row['fair_side_home_perspective']:+.1f} "
              f"total {row['fair_total']:.1f} P(home) {row['fair_p_home_win']:.3f}")
    print("  ...")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
