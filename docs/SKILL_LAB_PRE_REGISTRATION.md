# Pre-registration — skill-lab evaluation protocol (SL-PRE-01)

**Status:** registered before any result in this protocol was computed.
**Registered on:** 2026-11-15 UTC.
**Registration commit:** the commit that adds this file to the repository. The hash is published on
`skill-lab/methodology.html` and in `skill-lab/data/registry.json` by a later commit that only
records the hash; the later commit changes no rule in this document.
**Scope of the registration:** the rule text, the sample window, the gates, the scoring
definitions, the controls and the publication rules below are frozen at registration. Any change
after registration requires a new, numbered pre-registration (SL-PRE-02, …) and must be published.

Nothing here is betting advice, a sportsbook, or an approved wagering system.

---

## 1. Question being answered

> When our own line and the market's line are both turned into probabilities and both scored with a
> proper scoring rule, does our probability carry information the market's does not — and is any
> apparent advantage larger than what luck alone would produce?

Three claims are tested separately and must never be merged:

| Claim | Metric | Price-dependent? |
|---|---|---|
| **Signal** — our probability is better calibrated than the market's | benchmark-relative Brier skill and log-loss skill | No |
| **Luck** — the observed gap is inside the range a random or naive rule would produce | comparison against pre-registered controls | No |
| **Staking** — betting the edge would have made money | flat-stake return at the published closing price | Yes |

A strategy may only be **ranked** on the signal claim. A staking result never promotes a strategy
and never overrules a failed signal gate.

## 2. Corpus (frozen)

- **Primary corpus:** 2026 NFL regular season, weeks 1–9 — every game in that window that has a
  published final score for both teams in the schedule release used (`data/raw/games.csv`,
  nflverse `schedules` release). Expected size: **136 games**; the exact count is published, and any
  difference from 136 is reported rather than silently accepted.
- **Supporting panel:** the same walk-forward model evaluated over every earlier regular season in
  the same file (2003–2025). This panel is reported separately and never pooled into the primary
  corpus for a headline number.
- **Exclusions, applied before scoring:** a game is dropped if either final score is missing; if the
  closing spread line, closing total line, closing moneyline or the matching closing price is
  missing for the market being graded; or if the model cannot produce a probability for it
  (non-finite inputs). Every exclusion is counted and listed.
- **No re-selection:** the corpus is not re-cut after results are seen. If the count differs from
  the expected 136 the difference is published with the reason.

## 3. The model (frozen)

- **Estimand:** a home-team point margin and a game total, both expressed in the sign convention of
  the schedule release (`result` = home score − away score; `total` = home score + away score;
  `spread_line` positive = home favoured).
- **Features, frozen at registration:** pre-game Elo difference, difference in rolling points
  differential (window 6 games), difference in rest days, home-field constant — for the margin
  model; rolling points scored, rolling points allowed, and each opponent's rolling points scored
  and allowed — for the total model. The feature set is **not** re-selected after scoring.
- **Fitting:** walk-forward. For each target season the coefficients are estimated by ordinary
  least squares on **earlier seasons only** (minimum four training seasons), then applied to that
  season. No game is scored with coefficients that saw that game or a later game.
- **Residual scale:** the standard deviation of the training-set residuals for the target season's
  fit is carried forward unchanged and used to turn a margin or total into a probability. It is not
  re-estimated on the evaluated season.
- **Probability mapping:** a normal distribution with the fitted point estimate and the training
  residual scale. Home covers a spread line when `model_margin − spread_line` is positive; the over
  wins when `model_total − total_line` is positive; the home side wins a moneyline when the
  modelled margin is positive.
- **Second total estimator (registered as a pair, per the "publish every model total twice" rule):**
  a fixed, unfitted shrinkage estimator — the league mean total plus one third of the difference
  between the mean of the four form terms and the league mean. Both estimators are published with
  the gap between them, and neither is dropped before the walk-forward comparison is published.

**Known limitation, registered in advance:** the *feature list* was chosen by a human with access to
historical results. The walk-forward refit removes coefficient lookahead but it cannot remove
feature-selection hindsight. This limitation is published with every skill number.

## 4. The benchmark (frozen)

- **Market probability:** the closing price implied probability, de-vigged.
  - Spread: `home_spread_odds` / `away_spread_odds`; moneyline: `home_moneyline` /
    `away_moneyline`; total: `over_odds` / `under_odds`.
  - **Primary de-vig method: proportional** (normalise the two implied probabilities so they sum to
    one). **Secondary: Shin** — reported alongside so the reader can see whether the conclusion
    depends on the de-vig choice. If the two methods disagree about the sign of a skill score, the
    skill score is published as *method-dependent*.
- **Prices are community-maintained.** The schedule release used here is the nflverse `schedules`
  GitHub release. It is **not** an official NFL price archive. No price in this repository is
  published as an official market price, and no staking decision is made from it. The official
  boundary is the NFL's own odds-widget terms page.
- Because the price archive is community-maintained and undated, **closing-line value cannot be
  computed**: there is no dated opening price to compare against. Any cell that would need one stays
  blank and is flagged.

## 5. Proper scores (frozen)

For a binary forecast with probability `p` and outcome `y ∈ {0,1}`:

- **Brier score** `BS = (p − y)²`. Lower is better.
- **Log loss** `LL = −[y·ln p + (1−y)·ln(1−p)]`, with `p` clipped to `[1e-4, 1−1e-4]`. Lower is
  better.
- **Brier skill score against the benchmark**: `BSS = 1 − BS_model / BS_benchmark`. Positive means
  the model scored better than the market's own probability.
- **Log-loss skill score**: `1 − LL_model / LL_benchmark`, same reading.
- Skill is reported as a mean over the graded games together with the number of graded games `n`.

A market probability is itself a forecast and is scored with the same formulas, so the benchmark is
never assumed to be perfect.

## 6. Controls (frozen)

Every leaderboard run publishes these three controls next to the strategies:

| Control | Definition | Purpose |
|---|---|---|
| **C1 Market benchmark** | the de-vigged closing price probability | the reference; its own skill against itself is zero by construction |
| **C2 Random** | `p = 0.5` on both sides, 1,000 fixed seeds, the distribution of the statistic reported | the luck floor for a rule with no information |
| **C3 Favourites only** | at every price, take the market's favourite (the side with the shorter price); reported for the return and the hit rate | the luck floor for a *staking* rule |
| **C4 Base rate** | the training-window base rate (home win rate; league mean total; home cover rate) applied to every game | the floor for a rule with no per-game information |

C2 and C4 are probability forecasters and are compared on proper scores; C3 is a staking rule and
is compared on flat-stake return and hit rate. A strategy that cannot beat C2 and C4 on proper
scores has not shown skill; a strategy that cannot beat C3 on return has not shown a staking edge.

## 7. Uncertainty (frozen)

- **Cluster bootstrap.** Games are the unit of resampling, because several markets of the same game
  are not independent. The resampler draws `n_games` game identifiers with replacement and takes
  **all** graded forecasts attached to each drawn game, so within-game dependence is preserved.
- **10,000 resamples, seed 20260101, percentile method**, two-sided 95% interval.
- The **lower bound** of that interval is the value the gates test. The point estimate alone never
  passes a gate.
- The one-sided bootstrap p-value used for the multiplicity step is the share of resamples whose
  statistic is ≤ 0.

## 8. Multiplicity (frozen)

- All strategy × market rows graded in one run form **one family**.
- Benjamini–Hochberg false-discovery-rate control at **q = 0.05**, applied to the one-sided
  bootstrap p-values.
- The **number of trials** in the family is published next to the adjusted value. A row that passes
  every other gate but fails the multiplicity control is reported as *not distinguishable from
  chance after correcting for the number of strategies tried*.

## 9. Promotion gates (frozen, fail-closed)

A row is **eligible for ranking** only if every gate below passes. A failing gate is named on the
row; no row is described as passing when any gate fails.

| Gate | Test |
|---|---|
| **G1 Sample** | at least 100 graded games in the primary corpus for the row |
| **G2 Skill** | mean Brier skill against the benchmark > 0 |
| **G3 Uncertainty** | the 95% cluster-bootstrap lower bound of the mean skill > 0 |
| **G4 Multiplicity** | survives Benjamini–Hochberg at q = 0.05 within the family |
| **G5 Control** | mean skill > the 95th percentile of the random control (C2) and > the base-rate control (C4) |
| **G6 Calibration** | mean absolute calibration error ≤ 0.05 across five probability bins, measured on the primary corpus |
| **G7 Price realism** | the signal verdict is unchanged when the closing price is worsened by 10% (staking view only) |

**Demotion rule.** A strategy that has been eligible for ranking and later fails G2, G3 or G4 on a
rolling re-run returns to *paper* status and its published rank is withdrawn until it passes again.
The published demotion state is part of the register.

## 10. Signal and staking are separated (frozen)

- The leaderboard is sorted by **signal** (mean Brier skill), never by realised return.
- The return column is published in a separate, clearly labelled table, is computed at the
  community closing price, is explicitly retrospective, and carries the statement that it is not a
  basis for a staking decision.
- A row whose signal gates fail cannot be promoted by a positive return. The published table states
  this next to the return.

## 11. Divisions (frozen)

- **Division 1 — singles (spread, total, moneyline).** Admissible.
- **Division 2 — game parlays (legs from different games).** Not admissible in this registration:
  a parlay needs a *joint* probability and the operator's void/push rules. No permissioned parlay
  price history exists in this repository, so no joint evidence can be validated.
- **Division 3 — same-game parlays.** Not admissible for the same reason, plus the measured
  dependence between legs in the same game.
- **Division 4 — player-prop combinations.** Not admissible: no official prop line history and no
  official settlement record exists in this repository.

Non-admissible divisions are published as empty with the reason, not omitted.

## 12. What is published

- Every graded row: the game identifier, the market, the model probability, the benchmark
  probability, the outcome, both proper scores, the skill, `n`, the bootstrap interval, the
  adjusted p-value, the gate outcomes and the source link.
- The control results, the trial count, the excluded games and the reason for each exclusion.
- The registry: protocol version, pre-registration commit hash, code commit hash, data release
  URLs and digests, and the timestamp of the run.
- Every value that cannot be produced from a committed source stays blank and is flagged. Nothing is
  estimated, back-filled or inferred.
