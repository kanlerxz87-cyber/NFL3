# SL-PRE-01b — Two-sided "what would change our mind" field, and the next evaluation window

**Amendment to:** `docs/SKILL_LAB_PRE_REGISTRATION.md` (SL-PRE-01, commit `d80b8453`)
**Status:** committed after the first run's results exist, and therefore **not** applied to them.
**Written:** 2026-11-15 UTC
**Applies to:** the next evaluation window (2026 weeks 10–18, the games not in the SL-PRE-01 corpus)
**Does not change:** any number published from the SL-PRE-01 run.

---

## 1. Why this amendment exists

The brief requires every strategy entry to carry a **two-sided** "what would change our mind"
field: one side that would move the entry towards being believed, and one side that would move it
towards being rejected. The first run (SL-PRE-01, 2026 weeks 1–9) was registered without that
field, because the field is a governance statement and not a statistic.

Writing the field *after* the results exist would be a way of making the results look better
described, so this amendment does not do that. Instead:

1. The two-sided field is stated here, **forward-looking**, for the next evaluation window.
2. It is stated in a form that is **falsifiable by a rule**, not by a narrative.
3. The SL-PRE-01 run's own numbers are **not** re-interpreted through it. What happened is
   published as what happened.

## 2. The two-sided field, as written for every registered row

> **Would move this towards belief:** a pre-registered evaluation on a corpus the model has never
> seen, of at least the registered sample size, in which the row's 95% game-cluster lower bound on
> Brier skill is above zero **and** the row clears the random-pick control's 95th percentile
> **and** the row survives Benjamini–Hochberg correction inside its family **and** the row's
> calibration error is at or below 0.05. All four conditions, on the same corpus, in one run.
>
> **Would move this towards rejection:** a pre-registered evaluation on an equally sized unseen
> corpus in which the row's Brier skill is at or below zero, **or** its 95% lower bound is below
> zero, **or** it fails to beat the random-pick control's 95th percentile, **or** it fails the
> multiplicity control, **or** its calibration error exceeds 0.05. Any one of these is sufficient.
> A second consecutive such result demotes the row to paper status.

The two sides are deliberately asymmetric in one way: belief requires **four** simultaneous
conditions, rejection requires **one**. That is the right asymmetry for a strategy family that
is being tested, because the cost of a false positive (a promoted strategy that loses money) is
paid repeatedly, while the cost of a false negative (a real edge discarded) is paid once.

## 3. The next evaluation window, frozen

- **Corpus:** 2026 regular-season games from week 10 onward, with both scores published. The
  games are *not* selected by the model, by their result, or by whether they are easy to grade.
- **Sample size:** the registered minimum of 100 graded games per row (gate G1). If fewer than 100
  games can be graded for a row, the row is reported as **under-powered** and is not evaluated —
  it is not reported as a negative result, because a small sample cannot support one.
- **Model:** unchanged from SL-PRE-01 §3. The coefficients are fitted on earlier seasons only and
  applied to the target season. No feature, coefficient or constant is changed after this
  amendment.
- **Metrics:** unchanged from SL-PRE-01 §6 — Brier score and log loss against the de-vigged
  market probability, with proportional de-vigging primary and Shin secondary.
- **Uncertainty:** unchanged — a game-cluster bootstrap with 10,000 resamples.
- **Multiplicity:** unchanged — Benjamini–Hochberg at q = 0.05 across the family, with the trial
  count published.
- **Controls:** unchanged — market benchmark, random hard pick over 1,000 seeds, favourites-only,
  base rate, and the neutral p = 0.5 control.

## 4. What is explicitly **not** changed by this amendment

- No gate threshold.
- No corpus definition for the completed run.
- No metric, no bootstrap seed, no control.
- No promotion rule and no demotion rule.

## 5. Standing rules that apply to every published row from now on

1. A row's two-sided field is written **before** that row's evaluation window opens, in a numbered
   amendment, and is committed.
2. A completed row publishes, beside its field: the corpus, the sample size, the point estimate,
   the interval, the control comparison, the multiplicity result, and the gate outcomes.
3. The field is never edited after the window closes. A changed field is a new numbered amendment
   and the old text stays published beside it.
4. A row that fails the gates is published as a negative result. It is not hidden, not ranked and
   not quietly dropped.

## 6. Effect on the published site

- `skill-lab/leaderboard.html` gains a "What would change our mind" panel showing the field above
  for every registered row, with the note that the field is written for the next window and does
  not reinterpret the completed run.
- `skill-lab/flagged.html` records that the first run predates this field.
- `readiness/data/readiness.csv` row P10 moves from **Not started** to **Partial**, with the gate
  still unmet for the eight strategies that live outside this lab.
