# Executive summary

What was built, what is verified, what is blocked, and what to decide next. Every number below is reproducible from the scripts in this repository.

*Generated 2026-11-12 · sources: see `data/sources.json`*

> **The one finding that governs everything else**
>
> The NFL does not publish its own lines. nfl.com/odds/ returns 404, and NFL Support confirms that the odds shown in NFL widgets are supplied by partner bookmakers (FanDuel, Caesars, DraftKings) with bets placed through a redirect. So odds appear on NFL surfaces, but they are a licensed third-party feed — there is no NFL-authored, historical, machine-readable line archive. The consequence is unavoidable: no strategy in this project can be validated, ranked, or paid a reward until an odds archive is bought. Every model output here is a model-implied number and is labelled as such, never a line.

## 1. What exists now

The repository contained a single file with the word 'NFL' in it. It now contains a verifiable data layer, an analytical engine, a validation framework, a site that renders all of it, and a build gate that refuses to publish a row without a source. Nothing in the site is hand-typed into HTML: every table is generated from JSON, and every JSON value traces to a source id.

| Item | Value |
| --- | --- |
| Official sources registered | 12 (10 resolving, 2 recorded as broken so they are never cited) |
| Clubs with verified 2026 records | 32 of 32 |
| Injury rows transcribed verbatim | 108, across 10 complete club reports |
| Rules verified against an official page | 12 of 15 (3 left blank and flagged, see F-02) |
| Model-generated matchups | 8 verified Week 10 games |
| Questions in the decision register | 25 |
| Ranked suggestions | 18 |
| Strategies on the leaderboard | 12 — of which 0 are scored |

## 2. What the verified data actually says

These are computed from the official 2026 standings snapshot, not asserted. The generators are scripts/model_ratings.py and scripts/parlay_math.py.

| Finding | Value | What it means |
| --- | --- | --- |
| Scoring margin explains most of the table | r = +0.876, R² = 0.767 | 76.7% of between-club win-pct variance is explained by net points per game. The remaining 23.3% is the pool holding one-score games, opponent quality and chance — i.e. where luck lives and where any claimed edge must be proven, not assumed. |
| Offence and defence are nearly independent | r = -0.206, p = 0.26 | A club's offence tells you little about its defence, which is why scoring margin carries information that either side alone does not. |
| Division form is weak as a standalone signal | r = +0.328, p = 0.066 | Intra-division results carry some information but not enough to support a strategy on their own. |
| Recent form is largely quality, not momentum | r = +0.424, p = 0.015 | Two disjoint blocks of the same season correlate positively — but both measure club quality, so this is reliability, not momentum. Reading it as momentum would be a category error. |
| Fitted Pythagorean exponent | k = 3.51 | Fitted on 32 clubs at one snapshot. High relative to the publicly quoted value, which is itself a warning about small-sample fitting. Do not treat it as a law. |
| Most over-performing clubs | DEN +2.01, CLE +1.99 wins | Their records run ahead of their scoring margin — the natural fade candidates if the market has not already priced the regression. |
| Most under-performing club | TB -2.48 wins | Tampa Bay's margin is far better than its 3-6 record. This is the other side of the same coin. |
| The two totals estimators disagree | up to 12.2 points | Minnesota at Green Bay: 39.0 by average-of-game-totals versus 51.2 by the additive model. Both are published. A 12-point disagreement is not a rounding issue and it is why no total is offered as a recommendation. |

## 3. The requirement that cannot be met yet

The brief asks the system to know when a 2nd, 3rd or 4th string player must replace a starter, on offence and on defence. That is a depth-order question, and depth order is the one thing the official feed does not publish. The official NFL.com club roster page exposes position and roster status (ACT) and nothing about rank. It was read in full to confirm the absence rather than assumed.

Rather than invent 'starter' labels, this build ships a DepthStress index that measures what is verified: how much availability is degraded at each position, weighted by a declared position-value table. It explicitly does not claim who replaces whom, and its own definition says so. Two routes could close the gap — per-club official depth charts, or official snap counts — and both need verification club by club before anything is published (Q-09, SG-05).

## 4. The arithmetic that should shape the competition design

> **A season cannot validate a two-point edge**
>
> Detecting a 2-percentage-point edge over a 52.4% break-even, at 80% power and 5% significance, needs about 4,887 graded bets on the win/loss test, or 19,623 on the ROI test. A 17-game season cannot do it. This single calculation dictates the design: the leaderboard must rank on closing-line value (which has far more signal per bet), must run over multiple seasons, and must apply a multiplicity correction for every variant tried.

Two further numbers make the point concrete. A 12-3 record has a 95% confidence interval of 54.8% to 92.9% — it survives break-even. A 55-45 record does not: 45.2% to 64.4% comfortably contains it. A 300-200 record does exclude it. That is the sample at which a claim becomes possible, and it is why the reward rule pays nothing for any strategy that fails a hard gate, regardless of profit.

## 5. What to do next, in order

1. Buy a historical odds archive with closing lines, and write down the closing-line snapshot rule before the first backtest (SG-01). Nothing downstream is measurable without it.
2. Ingest game-level results so the rating becomes opponent-adjusted and the home-field parameter is estimated instead of assumed (SG-02). This removes three declared assumptions at once.
3. Make closing-line value the headline metric and realised ROI a diagnostic (SG-03).
4. Resolve the depth-order source before building the backup-deficiency feature (SG-05). Do not let the requirement be met with invented labels.
5. Read the data terms before publishing raw rows long-term (SG-09) and obtain a legal opinion on the reward structure (Q-05) before any money is attached.
6. Keep logging every rejected idea and every trial count (SG-07). The multiplicity correction is only honest if the count is honest.

## 6. What is explicitly not claimed

- No published number is a betting line. There is no market price anywhere in this project, and none can be obtained from an official source.
- No strategy is scored, ranked or rewarded. The leaderboard is empty by design and says so on every row.
- No player prop is priced. There is no usage data and no leg-level outcome data.
- No starting or backup designation is asserted for any player. The official feed does not carry one.
- No probability is attached to Out, Doubtful or Questionable. That calibration has not been measured.
- No legal, licensing or tax position is taken. Those are open questions with named owners.

## 7. Where to review

Ten items are on the Flagged for Review page, each with its source links and the exact condition that would clear it. Three are blocking: no odds source (F-04), no depth order (F-08), and no leg-level correlation data (F-09). The Questions page carries 25 decision items with current answers and the cheapest action that closes each one. The Suggestions page ranks 18 proposals and is built to be reviewed before anything is implemented.
