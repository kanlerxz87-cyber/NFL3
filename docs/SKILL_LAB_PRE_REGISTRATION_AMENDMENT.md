# Amendment SL-PRE-01a to the skill-lab pre-registration (SL-PRE-01)

**Registered:** 2026-11-15 UTC, **before any result in the protocol was computed.** No score,
no bootstrap, no gate outcome existed when this amendment was written. The base protocol
(`docs/SKILL_LAB_PRE_REGISTRATION.md`) was registered earlier the same day; this amendment only
removes an internal inconsistency in the wording of control C2 and adds one further control.

## Why an amendment at all

Section 6 of SL-PRE-01 defined control C2 as *"`p = 0.5` on both sides, 1,000 fixed seeds, the
distribution of the statistic reported"*. A forecast of `p = 0.5` on both sides is deterministic:
re-seeding it produces the same numbers, so a "1,000-seed distribution" is meaningless for that
definition. The control itself is sound; only the wording was wrong. Rather than change the rule
after results existed, the wording is corrected here, before any result was computed, and the
correction is published next to the results.

## C2 — random control (corrected wording)

> **C2 Random hard pick.** For each of 1,000 fixed seeds, pick one side of every graded game
> uniformly at random and treat that pick as a probability forecast of `p = 1` on the picked side
> and `p = 0` on the other. Report the distribution over the 1,000 seeds of the mean Brier score,
> the mean log loss, the Brier skill against the market benchmark, and the flat-stake return at the
> closing price. The 95th percentile of the skill distribution is the luck floor used by gate G5.

## C2b — neutral control (added)

> **C2b Neutral.** A forecast of `p = 0.5` on every graded event. It is deterministic: its mean
> Brier score is 0.25 and its log loss is `ln 2`. It is published as the information-free floor for
> a probability forecast and is not used to pass or fail a gate.

## What this amendment does not change

- The corpus, the model, the feature list, the fitting rule, the residual-scale rule, the
  probability mapping, both total estimators, the de-vig methods, the proper scores, the cluster
  bootstrap (10,000 resamples, seed 20260101, percentile interval), the one-sided bootstrap
  p-value, the Benjamini–Hochberg control at q = 0.05, the trial count rule, gates G1–G7, the
  demotion rule, the signal/staking separation, the four divisions and the publication rules.
- The number of trials in the family: a "run" remains one evaluation of the registered strategies
  on one corpus, and the trial count is published with the adjusted values.

Any later change to the protocol requires a new numbered amendment (SL-PRE-01b, …), must be
committed before the affected numbers are computed, and must be published on the methodology
page.
