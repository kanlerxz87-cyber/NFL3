# Pre-registration: backtest corpus, split policy and evaluation gates

**Status:** registered. **Registered:** 2026-11-15 UTC by session `arena/ba6c5155-nfl3`.
**Registration rule (as in `docs/PRE_REGISTRATION.md`):** the commit that created this file is the
registration. Its hash is recorded in [`manifest.json`](manifest.json) under `corpus_registration` by
the commit immediately following creation. Every evaluation window must open **after** that commit —
today there are **0 evaluations**, so the registration provably precedes any result.

This file is rule text. It contains no performance number, no price and no outcome estimate.

---

## 1. The corpus (frozen)

| Property | Value |
|---|---|
| File | [`games_2026_w1_9.csv`](games_2026_w1_9.csv) — frozen copy, never edited |
| Content | the verified 2026 game log, Weeks 1–9 (regular season), 136 rows |
| SHA-256 of the frozen copy | recorded in [`manifest.json`](manifest.json) (`frozen_sha256`) |
| Source of the copy | `decision-desk/data/games_2026.csv`, whose rows were cross-checked against the official NFL schedule pages (`https://www.nfl.com/schedules/2026/by-week/week-1` … `week-9`) and the official standings; the source hash at freeze time is in the manifest |
| Settlement rows | 135 of 136 games carry final scores read from the official schedule pages. One game (Week 2, Washington at Dallas) is published as "Hidden Score" on both the official schedule and game-centre pages; its score cells are **blank and never inferred**. Any evaluation that needs its result skips it and says so. |

If the upstream file changes, `corpus/verify.py` reports the drift. The frozen copy does not change;
any corpus amendment is a new dated section in this file plus a new manifest entry — never an edit.

## 2. Split (frozen before any fitting)

Within the only verified season, the split is chronological:

| Block | Weeks | Games | Use |
|---|---|---|---|
| Train | 1–6 | 93 | fitting, feature decisions |
| Validation | 7–8 | 28 | model/threshold selection only |
| Holdout | 9 | 15 | touched once, after the rule is frozen |

Season-level policy for future official data (also frozen now): the earliest complete seasons form
the training block, the next complete season the validation block, and the last complete season the
holdout. Blocks are disjoint and together cover the corpus; `corpus/verify.py` checks both.

**One hard rule:** a decision made after looking at holdout results invalidates the holdout. The
holdout may be evaluated once per frozen rule set.

## 3. What may and may not be computed from this corpus

| Allowed now (with citations to this file) | Forbidden until the price-data policy is satisfied |
|---|---|
| Descriptive counts of the log (games, weeks, score margins) | ROI, profit, edge, CLV of any kind |
| Baseline forecast arithmetic that is labelled **backtest corpus output** | Any number in a leaderboard result cell (`ops-center/leaderboard.html`) |
| Ablations that compare identical models with and without a feature set, on the split above, labelled with this registration | Ranking strategies by realised return (explicitly rejected in the brief) |

Backtest numbers stay in this workspace and in research pages, always labelled "backtest corpus —
not a leaderboard result". The leaderboard admits only pre-registered strategies whose forecasts were
recorded **before kickoff** and settled from official results (the shadow-baseline rule).

## 4. Evaluation gates (frozen with this registration)

Any claim of skill computed from this corpus must pass, at minimum:

| Gate | Test |
|---|---|
| Pre-registration | the rule text and threshold were committed before the evaluated window opened |
| Proper scoring | Brier score (or log score) with a game-cluster interval; win rate is not a skill measure |
| Multiplicity | one correction across every rule tried (this registration counts as one family) |
| Luck removal | the same evaluation run against the two required controls (random side; favourites-only where prices exist) |
| Label | the output says "backtest corpus" wherever it appears; it never appears on the leaderboard |

## 5. Relationship to other registers

- Price rows needed for ROI/CLV: [`pricing/PRICE_DATA_POLICY.md`](../pricing/PRICE_DATA_POLICY.md) —
  fail-closed; 0 licensed sources today.
- Strategy definitions and their two-sided falsification fields: `ops-center/leaderboard.html`
  (frozen in `ops-center/data/mindchange.json`, registered with this corpus).
- The nine-strategy family pre-registration: [`../docs/PRE_REGISTRATION.md`](../docs/PRE_REGISTRATION.md)
  (its own registration commit `c25ae53`, 2026-11-12).
