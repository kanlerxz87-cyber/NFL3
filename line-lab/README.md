# line-lab — line origination, validation gates and a decision register

**Live:** https://kanlerxz87-cyber.github.io/NFL3/line-lab/

Session `arena-e5e2b753`. This directory is self-contained: it does not touch the repository's root site,
`dashboard/` or `research-workspace/`, all of which belong to other sessions.

## What this is

A decision-support build for originating NFL lines, with three jobs:

1. **Collect and verify** NFL information from official sources only.
2. **Model** a line from those verified inputs, declaring every assumption where a value could not be sourced.
3. **Refuse to pretend.** Where the information a decision needs does not exist, the cell stays blank, the
   limitation is flagged, and the constraint is written down.

## The one thing to know first

**The NFL does not publish its own lines.** `https://www.nfl.com/odds/` returns HTTP 404, and NFL Support states
that odds shown in NFL widgets are "provided by official bookmaker partners of the NFL (FanDuel, Caesars, and
DraftKings)", with bets placed through a redirect to the bookmaker. Odds therefore appear on NFL surfaces, but
they are a licensed third-party feed with no historical archive.

Consequently:

- every number here is **model-implied**, never a market line;
- there is **no closing line**, so there is **no CLV, no ATS record and no backtest**;
- **zero strategies are scored.** The leaderboard is empty because the evidence is absent.

That is the finding, not an unfinished section.

## Contents

| Area | Pages | Status |
|---|---|---|
| League | Standings, Model lines, Correlations, Luck & regression | 32 clubs verified; four arithmetic checks pass |
| Availability | Injuries, Depth & availability, Rules | 108 injury rows verbatim; 12 of 15 rules verified; depth order **unavailable** |
| Decisions | Questions & gaps, Suggestions, Strategy leaderboard, Validation gates | 25 questions, 18 suggestions, 12 strategies, 13 gates |
| Trust | Flagged for review, Sources, Coordination | 10 flags, 13 sources |

```
index.html                 generated entry point for this sub-site
pages/*.html               generated category pages (17)
assets/site.css, app.js    hand-written; no framework, no external requests
data/*.json                all content — every table renders from here
scripts/model_ratings.py   ratings, correlations, luck, model lines
scripts/parlay_math.py     gate arithmetic, parlays, Kelly, confidence intervals
scripts/build_site.py      renders index.html, pages/*.html, EXECUTIVE_SUMMARY.md
scripts/verify.py          the build gate
EXECUTIVE_SUMMARY.md       generated from data/executive_summary.json
```

## Rebuild and verify

```bash
cd line-lab
python3 scripts/model_ratings.py   # data/model_outputs.json
python3 scripts/parlay_math.py     # data/strategy_math.json
python3 scripts/build_site.py      # all HTML
python3 scripts/verify.py          # must print PASS
```

Standard library only. Serve with `python3 -m http.server` from the repository root.

## What the gate enforces

`scripts/verify.py` fails the build on: a data table without a source column, a table without a declared source
class, a broken internal link or dead anchor, a row whose cell count does not match its header, a duplicate id,
a `TODO`/`TBD`/`NaN`/null leak, a standings arithmetic contradiction, an injury row without an official player
link, a verified rule without a source, a model output flagged as a market line, a neutral-site game varying with
home-field advantage, or a cross-reference to a flag/question/suggestion/strategy/gate that does not exist.

Current result: **PASS** — 13 checks, 0 warnings, 0 failures, 18 pages scanned.

## The four blocking gaps

| Flag | Missing | Why it cannot be worked around |
|---|---|---|
| **F-04** | An odds archive | The league publishes no lines of its own; the partner feed has no archive. Needs a purchase. |
| **F-08** | Depth order (1st/2nd/3rd string) | The official roster feed carries position and roster status, not rank. |
| **F-09** | Leg-level outcomes | Parlay correlation cannot be estimated, so no parlay is priced. |
| **F-02** | Roster sizes and the status deadline | Repeated everywhere, confirmed nowhere official — so left blank. |

## Method in one paragraph

An additive points model gives a margin of `r_A − r_B` where `r = (PF − PA)/G`, shrunk by `G/(G+k)`. Two totals
estimators are published side by side because they disagree by up to 12.2 points. The Pythagorean exponent is
fitted (k = 3.51) rather than borrowed, and luck is defined narrowly as `actual wins − expected wins` — a residual
that also contains real information, which the site says out loud. Correlations are Pearson r across 32 clubs with
n and p stated, and the one mechanically inflated correlation is labelled rather than quietly dropped.

## Scope notes

- No stakes, no money, no legal position (Q-05, Q-16). Analysis only, not betting advice.
- No player props priced; no usage data (F-06).
- Raw league data redistribution rights unverified (Q-01).
- Relationship to other sessions' work is recorded in `../COORDINATION.md`, including where this build overlaps
  and what it adds.
