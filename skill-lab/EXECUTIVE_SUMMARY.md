# Skill lab — executive summary

**Written:** 2026-11-15 UTC · **Protocol:** SL-PRE-01 (+ SL-PRE-01a, SL-PRE-01b)
**Registration commit:** `0d94a177dc399e1c5ea5c4c0e03968e6adba4fb1` (committed before any result existed; verified reachable from the published branch, with the protocol file hashing to the same SHA-256 as at registration)
**Artifact:** `skill-lab/data/results.json` · **Pages:** `skill-lab/index.html`

---

## The one-paragraph version

We asked a single, falsifiable question: does our own line, turned into a probability, beat the
market's own de-vigged probability on a proper score, by enough to be told apart from noise? We
frozen the corpus, the model, the metrics, the controls, the uncertainty method, the multiplicity
control and the pass/fail gates **before** we computed anything, and we answered the question on
the frozen 2026 weeks 1–9 corpus. The answer is no. Every one of the six registered rows scored
**worse** than the market's own probability, every gate interval included zero, and no row
qualified. Nothing is promoted, no staking result is presented as an edge, and the family is
published as a negative result with its controls attached.

## What was measured

| | |
|---|---|
| Corpus | 2026 regular season, weeks 1–9 — 136 games with both scores published (the registered size) |
| Supporting panel | every earlier regular season, walk-forward, 5,967 games — published beside the primary corpus, never pooled into it |
| Rows | 6 registered strategy rows: two margin models (Elo + form + rest, and Elo only) × spread and moneyline, plus two total estimators (least squares, shrinkage) |
| Benchmark | the de-vigged closing price probability (proportional primary, Shin secondary) |
| Metrics | Brier score and log loss; skill = 1 − (model ÷ benchmark) |
| Uncertainty | game-cluster bootstrap, 10,000 resamples, seed 20260101 — the three markets of one game are never counted as independent evidence |
| Multiplicity | Benjamini–Hochberg at q = 0.05 across the family, with the trial count published |
| Controls | market benchmark, random hard pick over 1,000 seeds, favourites only, base rate, neutral p = 0.5 |

## The result

| Row | Market | n | Brier skill | 95% cluster interval | Lower bound | BH q | Gates |
|---|---|---|---|---|---|---|---|
| spread_full | spread | 130 | −0.0294 | [−0.0961, +0.0345] | −0.0961 | 1.0000 | 2/7 |
| spread_elo | spread | 130 | −0.0404 | [−0.1077, +0.0239] | −0.1077 | 1.0000 | 2/7 |
| total_ls | total | 136 | −0.1172 | [−0.1867, −0.0489] | −0.1867 | 0.9999 | 2/7 |
| total_shrink | total | 136 | −0.3029 | [−0.4653, −0.1382] | −0.4653 | 0.9999 | 2/7 |
| ml_full | moneyline | 135 | −0.0346 | [−0.1204, +0.0387] | −0.1204 | 0.9999 | 3/7 |
| ml_elo | moneyline | 135 | −0.0547 | [−0.1443, +0.0202] | −0.1443 | 0.9999 | 3/7 |

**0 of 6 rows qualified for ranking.** The supporting panel over 23 earlier seasons agrees: every
row is negative there too, with intervals below zero.

## How to read this honestly

- **A negative point estimate is not the same as proof of harm.** The intervals are wide and span
  zero. The correct claim is *no skill demonstrated*, not *the model is worse than the market*.
- **The two total estimators differ sharply.** The least-squares total (−0.117) is much closer to
  the market than the shrinkage total (−0.303). That gap is a finding about the estimators, and it
  is why both totals stay published rather than one being collapsed into a single number.
- **The retrospective staking table is on its own page** (`staking.html`) because a profitable
  staking run and a real edge look identical in a return column. The random control reaches a
  positive 95th percentile on every market in this corpus, which is the proof of that point.
- **The parlay and prop divisions are published empty.** The legs of one game are measurably
  dependent (home-cover and over co-occur at 0.177 against 0.219 if independent, n = 130), so
  multiplying marginal probabilities is invalid, and no operator void/push rule set or permissioned
  parlay price exists in this repository.

## What is blank, and why

There is no dated price history in this repository — one undated community closing line per game.
So closing-line value, open-to-close movement and any official price column are **blank**, not
estimated. This is the same boundary the NFL itself draws at
[the odds-widget terms](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL).
Until a permissioned, dated open-and-close archive exists, the honest reading of this lab is
*exploratory*.

## What would change our mind

Frozen forward in
[SL-PRE-01b](https://github.com/kanlerxz87-cyber/NFL3/blob/main/docs/SKILL_LAB_PRE_REGISTRATION_AMENDMENT_02.md)
for the next evaluation window (2026 weeks 10 onward), every row carries a two-sided field:
**belief** requires four conditions at once (lower bound above zero, beating the random control's
95th percentile, surviving multiplicity, calibration error ≤ 0.05); **rejection** requires one
(skill ≤ 0, lower bound below zero, failing the control, failing multiplicity, or calibration error
> 0.05). The field is written forward and does not reinterpret the run above.

## The limits, stated once

- Feature selection was not blinded. The walk-forward refit removes coefficient lookahead; it
  cannot remove a human having chosen the feature list with access to history.
- The prices are community-maintained. The scores are cross-checked against the official standings
  page at the team-aggregate level, not at each official game centre.
- One season of hold-out. The supporting panel is published beside the primary corpus, not merged
  into it.

## Reproduce it

```
python3 skill-lab/scripts/build.py      # recompute and rewrite skill-lab/data/results.json
python3 skill-lab/scripts/build_pages.py  # re-render the pages from that artifact
python3 skill-lab/scripts/verify.py      # fail-closed checks on the published artifact
python3 tests/test_skill_lab.py          # regression tests (protocol, scores, pages)
```
