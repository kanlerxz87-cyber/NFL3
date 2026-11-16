# Pre-registration: two total estimators, a gap column and the collapse rule

**Status:** registered. **Registered:** 2026-11-16 UTC by session `arena/ca175be6-nfl3`.
**Registration rule** (same rule as `docs/PRE_REGISTRATION.md`): the commit that created this file **is**
the registration. Its SHA-1 is written into `two-total/manifest.json` by the commit immediately
following creation, and `two-total/scripts/verify.py` fails if the artifact names a commit that does not
contain this file. Every evaluation on `two-total/evaluation.html` runs **after** that commit.

This file is rule text. It contains no performance number, no price, and no outcome estimate. Nothing in
it was chosen by looking at a result.

---

## 1. The requirement this registration answers

> *"Publish every model total twice until one wins — keep both estimators visible with the gap column, and
> only collapse to one after a walk-forward comparison."*

Today the repository publishes **one** point total (`origination`, estimator `T1`) and compares two total
models only as over/under Brier scores against a market line built from a **community** price file
(`skill-lab` `total_ls` / `total_shrink`). There is no per-game point-total pair, no gap column, and no
collapse rule. The decision-readiness register records this requirement as `P4`, *Not started*, current
value *0 estimators compared*. This registration starts that record at its true value.

## 2. The two estimators (both frozen now, neither tuned on the corpus)

| ID | Definition | Where the code already existed |
|---|---|---|
| **T1** | Team scoring model: `total = level + pace_home + pace_away`, ridge-regularised least squares, fitted on the **six prior seasons** only, pace shrunk by a fixed ridge of 4.0 games-equivalent, home-field prior 2.0 points, minimum 700 training games. | `origination/scripts/model.py` — `fit_total()`, unpublished change: none |
| **T2** | League-mean total plus one third of the form gap: `total = mean_train_total + (m − mean_train_total)/3`, where `m` is the mean of the four six-game rolling values (home points-for, away points-for, home points-allowed, away points-allowed) taken **only from games that kicked off strictly earlier**. If any rolling value is undefined (a club with no prior game), the estimator falls back to the league mean and the row says so. | `skill-lab/scripts/build.py` — `shrink_total()` and `engine/features.py` `rolling_team_form()` |

**Why these two and no others.** Both definitions already exist in the repository under a committed
pre-registration, so publishing them as a pair adds no new degrees of freedom to the project's
multiplicity count beyond the one comparison registered here. Neither is edited by this session.

**Deliberate asymmetry, stated before the result is seen.** T1 is fitted on prior seasons and therefore
carries no current-season information. T2 reads the current season's preceding weeks through the rolling
form window. That asymmetry is the hypothesis being tested, not an accident: *does adding recent form to a
prior-season pace model improve the point total out of sample?* It is also the estimator that must be
watched most closely, so §3 fixes the leakage rule it is checked against.

## 3. Leakage rule (checked by the build, not asserted in prose)

For a game in week `w` of season `s`:

- T1's fit window is seasons `s−6 … s−1`. No game from season `s` is in the fit.
- T2's rolling windows contain only games whose kickoff date is **strictly earlier** than the fixture's
  kickoff date. A week-`w` fixture never sees another week-`w` result, and a Thursday fixture never sees
  the Sunday games of the same week. `two-total/scripts/verify.py` recomputes the leakage test on the
  committed rows: for every row, the maximum kickoff date inside both estimators' inputs must be strictly
  less than the fixture's own kickoff date.
- Rolling form is built over each club's own history, so a club's first appearance in the corpus (or its
  first game after a bye) has fewer than six observations. The row publishes how many it had; it is never
  padded.

## 4. The corpus and the split

The corpus is the frozen, pre-registered backtest corpus: **136 games, 2026 Weeks 1–9**, file
`corpus/games_2026_w1_9.csv`, SHA-256 `4632744b44d59ff2c482c219ed65c6f6cf4924079013b82021933e91c2f6c9f7`,
registered in `corpus/PRE_REGISTRATION.md` before this session began. This session does not edit, extend or
re-freeze it.

One frozen row carries two blank score cells (Week 2, Washington at Dallas — the official page publishes a
hidden score). **Blank stays blank.** It is excluded from every scored number and counted in the
exclusions table. This session does not fill it.

The split is used exactly as frozen:

| Block | Weeks | Games | Use here |
|---|---|---|---|
| Train | 1–6 | 93 | not used to choose anything: T1 and T2 are frozen in §2 |
| Validation | 7–8 | 28 | the block on which the collapse decision in §6 is made |
| Holdout | 9 | 15 | reported once, after the rule in §6 was frozen; it cannot change the decision |

Because both estimators are frozen before the corpus is read, the train block does no work here. That is
stated rather than exploited: a frozen estimator cannot be tuned, so the train block cannot be overfitted
by this registration.

## 5. The scored quantity

For every corpus game with two published scores, two absolute errors are formed:

```
err_T1 = | T1_total − actual_total |
err_T2 = | T2_total − actual_total |
gap    =    T2_total − T1_total          (signed, published as its own column)
```

The primary statistic is the **difference in mean absolute error**, `MAE(T1) − MAE(T2)`, computed on the
identical set of games. It is reported with:

- a **game-cluster bootstrap** interval (10,000 resamples of games, seed `20261116`), because a game is
  the unit and both estimators see the same game;
- a **squared-error** companion (`RMSE(T1)`, `RMSE(T2)`) so a mean-absolute-error win cannot be reported
  alone;
- **n** on every row, and the exclusion count next to it.

Win rate of "which estimator was closer" is **not** a skill measure and is not published as one. It is
printed, with its n, only as a descriptive companion in a column explicitly titled *descriptive*.

No price, no ROI, no CLV and no staking number appears anywhere in this workspace. The price firewall in
`pricing/PRICE_DATA_POLICY.md` stays closed: **0 licensed sources**, so nothing here can be converted to a
bet. Totals are scored against official final totals only.

## 6. The collapse rule (frozen before the validation block is read)

The pair collapses to a single estimator **only if all five conditions hold on the validation block**:

| # | Condition |
|---|---|
| C1 | `MAE(T2) < MAE(T1)` — the challenger is better on the pre-registered primary statistic |
| C2 | the lower bound of the 95% game-cluster bootstrap interval on `MAE(T1) − MAE(T2)` is **greater than 0** — the improvement survives an interval, not just a point estimate |
| C3 | `MAE(T2) < RMSE-style` direction agrees: `RMSE(T2) < RMSE(T1)` — the win is not an artefact of one loss function |
| C4 | the sign of `MAE(T1) − MAE(T2)` is the same in **both halves** of the validation block (weeks 7 and 8) — no single week carries the result |
| C5 | n on the validation block is at least **20 scored games** — below that the interval is too wide to be worth computing, and the answer is "not yet", not "either" |

If all five hold, T2 replaces T1 as the published total, and this file gains a dated **Collapse record**
section naming the commit that performed the substitution. Until then **both estimators stay published**
with the gap column, which is what the requirement asks for.

If any condition fails, the pair stays a pair. A failed condition is published with the number that
failed it — a "not yet" is a result here, not a failure to be hidden.

**Holdout discipline.** The holdout (week 9, 15 games) is scored **once** and published on its own line,
labelled as the holdout, after the validation outcome is written. It cannot reverse the collapse decision.
If the holdout contradicts the validation block, that is published as a contradiction, and the collapse
record — if one was made — is re-opened under a new registration rather than silently kept.

## 7. What this registration forbids

- Adding a third estimator, changing either definition, or changing the scoring statistic after reading
  the validation or holdout block.
- Any number from this workspace appearing in a leaderboard result cell. Every page here says
  **"backtest corpus — not a leaderboard result"** on the same screen as the numbers.
- Filling a blank total, a blank score or a missing rolling value with an estimate.
- Reporting the collapse as a claim that either estimator is good. The comparison is between two models;
  it says nothing about beating a market, because no licensed price exists.

## 8. Relationship to the other registers

- Frozen corpus and its split: [`corpus/PRE_REGISTRATION.md`](../corpus/PRE_REGISTRATION.md).
- The nine-strategy family that counts this comparison among its trials: [`docs/PRE_REGISTRATION.md`](../docs/PRE_REGISTRATION.md).
- Proper-score evaluation of our line against a market price: `skill-lab/` (community price input, labelled).
- Price firewall: [`pricing/PRICE_DATA_POLICY.md`](../pricing/PRICE_DATA_POLICY.md).
- Decision-readiness row this registration moves: `P4` in [`readiness/data/readiness.csv`](../readiness/data/readiness.csv).
