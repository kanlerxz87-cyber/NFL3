# Pre-registration — 2026 official-corpus walk-forward evaluation

This file freezes the evaluation **before any score from it is computed**. The commit that
adds this file is the registration. Nothing below may be edited after results exist; a change
requires a new registration file and a new commit, and the old number stays published.

- Registration date: 2026-11-15 UTC
- Registered by: session `arena/f0d1503b-nfl3`
- Corpus (frozen, by SHA-256):
  - `official-verify/data/games_2026_official.csv` — `44f9ea2b04ecaf1db7b8e98aadd2706672fc31fd7dee0c0367d4f838edba80b0`
  - `official-verify/data/standings_2026_official.csv` — `f11dfa827fa6c4316010ba31087216ece99ecada16fd48f2b10829f7f5bdf443`
- Sources: nine official 2026 weekly schedule pages (OV-S01…OV-S09) plus one official
  Game Center page (OV-S16) and the official standings page (OV-S10). Every row is linked to
  the page it was read from.

## 1. Question this evaluation answers

> Does a simple team-strength model built only from games already played beat two controls —
> a coin flip and the league's home base rate — on **out-of-sample** proper scores, on an
> official-only 2026 corpus, by enough to be distinguishable from noise?

It does **not** answer whether any bet is profitable. No price is used: this repository holds
no official or licensed price series (OV-B01). Return on investment, closing-line value and
market residual are therefore out of scope for this registration and are **not** published.

## 2. Model (frozen)

Home team expected points and away team expected points per game:

```
home = mu + hfa/2 + attack[home]  - defence[away]
away = mu - hfa/2 + attack[away]  - defence[home]
```

- `attack`, `defence` and `hfa` are fitted by ridge regression (`lambda = 2.0`) on the
  **sum-to-zero** constraint, using only games with `week < evaluation week`.
- `mu` is the mean points per team over the fitting games.
- Margin distribution: Normal with mean `home - away` and standard deviation
  `sigma = 13.5`, fixed in advance from the published NFL margin scale, and **not** re-fitted
  from results. Fixing sigma prevents the evaluation from tuning itself.
- Win probability: `P(home wins) = Phi(margin / sigma)`; ties are scored as a 0.5 outcome.
- Total distribution: Normal with mean `home + away` and standard deviation `sigma_total = 13.5`
  (same fixed constant, stated so it can be criticised).

This is one model with two outputs. It is the *only* model registered here. No feature
selection, no hyper-parameter search, no alternate sigma.

## 3. Evaluation window (frozen)

- Warm-up, not scored: Weeks 1–3 (insufficient history for a stable fit).
- Evaluation, scored: **Weeks 4–10**, every game with both scores present in the corpus.
- Re-fit at each step, using only `week < w`. No information from week `w` or later enters
  the fit for week `w`.

## 4. Controls (frozen)

Every leaderboard is required by the brief to carry controls. Three are registered:

| id | control | definition |
|---|---|---|
| C-FLIP | coin flip | `P(home wins) = 0.5` on every game |
| C-BASE | home base rate | the home-team win share among **fitting games only**, recomputed each step |
| C-FAV | favourites only | the side with the better win percentage among fitting games only; scored as a 0/1 probability |

## 5. Scoring rules (frozen)

- Primary spread/moneyline score: **Brier score** (mean squared error of the probability).
- Secondary: **log loss**.
- Skill is stated **relative to a benchmark**, never as a raw rate:
  `Brier skill score = 1 - Brier(model) / Brier(benchmark)`.
- Uncertainty: a **cluster bootstrap over games** (resampling whole games, 2,000 draws, fixed
  seed `20261115`) gives a 95 % interval on the skill score. A result is called positive only
  if the **lower** bound of that interval exceeds 0.
- Multiplicity: this registration contains **one** model and **one** primary benchmark
  (C-BASE). No correction is needed for it. If any further comparison is added later, it
  must be reported with a Bonferroni-adjusted threshold and the number of trials stated.
- Total-market check: the same walk-forward procedure on the **over/under** relative to
  the model's own total is reported as a secondary diagnostic only if a price exists. No price
  exists here, so the totals output is published as a *number*, not as a result.

## 6. Gates that must pass before anything enters a leaderboard

Both are evaluated **before** the leaderboard is written:

- **G-PREREG**: this file exists in a commit that is an ancestor of the results commit, and
  the corpus SHA-256 recorded above still matches the file on disk.
- **G-CLUSTER**: the 95 % cluster-bootstrap lower bound on benchmark-relative Brier skill is
  greater than 0.

If G-CLUSTER fails, the entry is published as **unvalidated** with its interval, and no
strategy claims reward eligibility.

## 7. What would change our mind (two-sided, required by the brief)

- **Evidence that would support the model**: a cluster-bootstrap lower bound above 0 against
  C-BASE on Weeks 4–10, reproduced by `python3 official-verify/scripts/evaluate.py`.
- **Evidence that would refute it**: a lower bound at or below 0, or a mean skill no better than
  C-FLIP; or a mismatch between the corpus and the official standings arithmetic when
  `verify_corpus.py` is re-run; or any official page later contradicting a transcribed score.
- **Both outcomes are published**. A failed gate is not deleted; it is reported with its interval.

## 8. Known limits, declared now

1. Weeks 4–10 is a small sample; the interval will be wide. A wide interval is the honest answer,
   not a reason to shorten the sample.
2. One season. No cross-season validation exists in this repository.
3. The corpus contains no prices, so no ROI, vig or closing-line claim is possible.
4. The corpus is a mid-season snapshot; games not yet played are absent, and their absence is
   not the same as a zero.
5. Availability, depth and injury features are **excluded** from this registration because no
   dated official series exists (OV-B02, OV-B04). Any future claim about injuries changing
   outcomes must be pre-registered separately.
