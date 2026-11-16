# Pre-registration — FL1, the forward-ledger singles baseline

**Registered before any model artifact in this workspace exists.** The commit that introduces this file is the
registration; its hash is published on `forward-ledger/index.html` by `scripts/build_site.py`, which fails the build
if any of the five model artifacts (`data/ratings_2026_w10.csv`, `data/fit_diagnostics.json`,
`data/prospects_2026_w11.csv`, `data/prospect_records.jsonl`, `data/leaderboard.json`) was committed before this
file. No threshold, window, constant or gate below is chosen after seeing a result, because none of them was
written after one. Any later change is an amendment in a new section; §1–§8 stay byte-identical, per the standing
convention in `docs/PRE_REGISTRATION.md`.

## §1 Scope and standing

- One model (`FL1`), three singles markets (side, total, moneyline), one 2026 season, official score pages only.
- This workspace grades **prospective** fixtures. The 2026 Weeks 1–10 results are its fitting data and its
  backtest surface; no number computed from them may appear on a leaderboard page (`forward-ledger/leaderboard.html`
  is built from `data/leaderboard.json`, which contains no performance field, and `scripts/verify.py` proves that no
  value listed in `fit_diagnostics.json → backtest_only_values_for_the_firewall_check` is echoed there).
- Nothing here is betting advice. No reward is funded. `pricing/PRICE_DATA_POLICY.md` grants no price source, so
  **the market-line and difference columns exist and are empty by rule**, and no ROI, CLV or staking result is
  computed anywhere in this workspace.

## §2 The model, exactly

For a game with home club `h` and away club `a`, fitted by alternating least squares on games with
`week` in the fitting window:

```
points_home = mu + att[h] - def[a] + hfa
points_away = mu + att[a] - def[h]
```

- `mu` — league mean points per club per game in the window (estimated).
- `att[c]`, `def[c]` — club attack and defence terms (estimated); both vectors are re-centred to mean zero after
  every sweep, which is an identifiability device, not a prior. No shrinkage, no ridge, no rounding.
- `hfa` — home-field term (estimated), bounded to [-14, +14] and initialised at **2.0**.
- Sweeps: **400**, fixed, so the fit is reproducible without a convergence flag.
- Margin and total are treated as Normal around the fitted expectation with `sigma_margin` and `sigma_total` equal
  to the population standard deviation of the in-sample residuals. If either falls below the floor **6.0** the fit
  is declared a failure and the build stops; a suspiciously tight model is a bug, not an edge.
- The fit is a function of `data/results_ledger.csv` only. That file is a hash-pinned transcription of the official
  NFL.com score pages (see `data/ledger_manifest.json`); no community file enters it.

## §3 Lines we originate, and the second total

- `fair_spread_home = -round(margin / 0.5) * 0.5` — a negative number means the home club is the favourite.
- `fair_total = round(total_expectation / 1.0) * 1.0`.
- Probabilities: side uses `P(margin + fair_spread_home > 0)`, total uses `P(total > fair_total)` and publishes the
  push probability `P(|total - fair_total| < 0.5)` beside it, moneyline uses `P(margin > 0)`.
- Moneyline carries a declared defect: a Normal model gives a tie probability zero, while the league recorded ties in
  2026. The count is published on the backtest page with n, and the moneyline row is labelled `tie-blind`.
- **Both** total estimators are published until a walk-forward comparison retires one, as the brief requires:
  `primary = fl1-additive` (§2 equations summed) and `secondary = fl1-sum-of-rates`, the two clubs' own scoring
  averages summed, with the signed gap in its own column. The retirement rule: after at least 40 graded fixtures with
  both alive, the estimator with the lower mean absolute total error keeps the row; a tie keeps the primary. Until
  that gate can be evaluated, both stay visible.

## §4 Evaluation protocol

- Fitting window: all graded games through the last completed week before issuance. First issuance: 2026 Week 11,
  fitted on Weeks 1–10 (149 graded games), issued before the 2026-11-19 20:15 ET kickoff.
- Backtest surface (never on the leaderboard): in-sample diagnostics over the fitting window, and one chronological
  holdout — fit on Weeks 1–8, evaluate on **Weeks 9–10** — with no refit between them.
- Headline score: Brier for binary events, benchmarked against the window's home-win base rate and against 0.5.
  Skill = `1 - Brier_model / Brier_benchmark`. Uncertainty: game-cluster bootstrap, **2000** draws, seed **20261116**,
  resampling whole games (one game is one cluster), reported as a 95% percentile interval; the lower bound is the
  number that matters.
- Multiplicity: at most 3 registered singles rows and 4 controls per window, so Benjamini–Hochberg at q = 0.10 is
  applied to the family of registered rows whenever more than one is graded; with one graded row the correction is
  recorded as "not applicable, n tests = 1" rather than silently skipped.
- Promotion to a ranked row requires all of: ≥ 40 graded fixtures in the prospective window, benchmark-relative skill
  with a bootstrap **lower bound above zero**, BH-adjusted p < 0.10, and a price register that permits a residual.
- Demotion gate (a live row returns to paper automatically, no discussion): 20 consecutive graded fixtures with
  skill below zero, or two consecutive windows whose lower bound crosses zero downward, or one failed freshness check
  on the input ledger older than 48 hours at kickoff, or any source-label anomaly that changes a graded score.

## §5 Gates that block publication in this workspace

| Gate | Rule | Failure action |
|---|---|---|
| G1 pre-registration order | this file's commit precedes every artifact commit | build fails |
| G2 official-only inputs | every ledger row carries an `nfl.com` score/schedule/game URL | build fails |
| G3 point-in-time | issuance timestamp precedes the fixture's kickoff and is recorded | row excluded, flagged |
| G4 price firewall | market line, difference, ROI, CLV stay empty | build fails on any non-empty value |
| G5 backtest firewall | backtest values never appear on the leaderboard page | build fails |
| G6 blank honesty | an unread cell renders blank with a reason, never as 0 or "—" | build fails |
| G7 joint-evidence gate | no parlay or prop-combo row without a validated joint probability **and** the operator's void/push rules | division stays empty |
| G8 staleness | the ledger's newest graded game must be within 7 days of a scheduled read | alarm row on the page |

## §6 What would change our mind, per entry

- **FL1-SIDE** — confirmed: a positive bootstrap lower bound against the base rate over ≥ 40 graded fixtures.
  Killed: two consecutive windows with a lower bound at or below zero on a fixed model, or an in-sample R² above 0.10
  that fails to reproduce out of sample at half its size. Then the row is retired, not re-tuned.
- **FL1-TOTAL** — confirmed: the primary beats the secondary on mean absolute error in the same graded window and
  the pair beats a constant-league-total benchmark. Killed: if either estimator's error grows after the retirement
  rule is applied, both return to paper.
- **FL1-ML** — confirmed: skill over the base rate with the tie rate handled explicitly. Killed: if the observed tie
  rate in graded fixtures exceeds 1%, the moneyline row is suspended until ties are modelled, because a tie-blind
  model on a league that records ties is wrong in a way that flatters the underdog.
- **Controls** — the coin row must not out-score the registered row; if it does, the registered row is demoted
  regardless of its own numbers.

## §7 What is deliberately not registered here

Parlays, same-game parlays and prop combos (G7), any reward amount, any stake size, any price, and every
correlation whose inputs are not official. The correlation register in `fit_diagnostics.json` is a *structural*
measurement on game results — it says how much dependence a naive independence assumption discards; it is not a
claim of edge.

## §8 Amendments

An amendment is a new numbered section with its own commit hash, stating what moved and which published number
changed. Amendments may not alter §1–§7, may not loosen a gate retroactively, and may not be written after a window
has graded fixtures whose result is already visible to the author of the amendment.
