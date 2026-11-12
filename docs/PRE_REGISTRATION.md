# Pre-registration: strategy family and validation gates

Written before the out-of-sample results were inspected. Any change to a gate or to the family after
looking at results invalidates the run, and the change must be recorded here with a date and a reason.

## The strategy family (fixed)

Nine strategies, each graded on every out-of-sample game in the same window. Adding a strategy to
this list is a decision that must be recorded **before** its results are computed.

| ID | Strategy | Side | Rule |
|---|---|---|---|
| S1 | ATS model edge > 0.5 pt | Spread | Take the side our number favours when it differs from the closing line by more than 0.5 points |
| S2 | O/U model edge > 0.5 pt | Total | Take over or under on the same rule |
| S3 | ATS model edge > 2 pts | Spread | Selectivity test: does being pickier help? |
| S4 | O/U model edge > 2 pts | Total | Selectivity test on totals |
| S5 | ATS model edge > 3 pts | Spread | Stronger selectivity test |
| S6 | O/U model edge > 3 pts | Total | Stronger selectivity test on totals |
| S7 | Elo-gap fade > 2 pts | Spread | Bet the side a pure Elo rating says is mispriced, ignoring recent form |
| S8 | Rest advantage ≥ 3 days | Spread | Bet the side coming off materially more rest |
| S9 | Fade big favourites, line ≥ 7 | Spread | Contrarian test of the public-bias hypothesis |

Reward tiers are tied to gate completion, not to raw profit, so a lucky streak earns nothing.

## Gates (fixed)

| Gate | Test | Threshold |
|---|---|---|
| G1 | Sample size | ≥ 100 graded bets from digest-verified data |
| G2 | Profit | Mean profit per unit > 0 **and** 95% moving-block bootstrap CI lower bound > 0 |
| G3 | Multiple testing | Survives Benjamini-Hochberg at q = 0.05 across the whole family |
| G4 | Selection / luck | z exceeds the deflated-Sharpe threshold (Bailey & Lopez de Prado) for the number of attempts, and z > 2 |
| G5 | Stability | Positive in ≥ 60% of seasons **and** in both halves of the window |
| G6 | Closing-line value | Mean CLV > 0 with a 95% CI lower bound > 0 |
| G7 | Cost realism | Still profitable with a 10% worse average price |

A strategy is called `passing` only when all seven clear. Everything else is a candidate in testing
and is never described as an edge.

## Out-of-sample protocol

1. Seasons are processed in ascending order.
2. For season *s*, the model is fitted on all seasons before *s* only, with at least four training
   seasons required before any prediction is made.
3. Predictions for *s* are graded after the fact; no result from *s* or later enters any coefficient
   used for *s*.
4. The site reports the most recent 12 predicted seasons, and separately the walk-forward coefficient
   table so the protocol can be audited.

## Statistics used, and why

| Purpose | Method | Reason |
|---|---|---|
| Confidence interval on profit | Moving-block bootstrap, block = 20 bets | Bets within a season are not independent; a naive interval would be too narrow |
| Hit rate interval | Wilson score interval | Correct coverage at small samples and near 0/1 |
| Multiple testing | Benjamini-Hochberg | Controls the false discovery rate across the family |
| Selection adjustment | Deflated-Sharpe threshold | A leaderboard of *k* strategies is expected to produce a large z by chance alone |
| Correlation of legs | Phi coefficient with Fisher-z CI | Both legs are binary outcomes |

## What is explicitly not claimed

- No strategy is claimed to be profitable.
- No line is claimed to beat the closing market; the market is the benchmark.
- No player-prop or parlay product is priced, because the verified prop data is not in the snapshot.
- No injury-severity estimate is made, because the official report has no such field.

## Amendments

None. The gates above are the ones the published run used.
