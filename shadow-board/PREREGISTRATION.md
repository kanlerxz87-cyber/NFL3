# Pre-registration — Shadow Board (singles-only baseline)

Registration date: 2026-11-15 (UTC). This file is committed **before** any forecast file, ledger or page in
`shadow-board/` is generated, and before any out-of-sample game in the evaluation window is played. The commit
that contains this file, and nothing else from this workspace, is the registration record; its hash is published
on `shadow-board/index.html` and read back by `shadow-board/scripts/check.py` (which fails if a result artifact is
older than the registration).

Rule of operation: after this commit, the model form, the constants, the gates, the scoring rules and the
evaluation window are frozen. Any edit to them is an **amendment**, recorded in §9 with a date and a reason, and
it restarts the prospective clock (the strategies affected lose any accumulated prospective credit for ranking
purposes). Nothing in §1–§8 may be justified by pointing at a result.

---

## 1. Data the model may read

| Item | Decision |
|---|---|
| Source authority | Only game results published by the league on `nfl.com` (official). Community files (`data/raw/*.csv`, nflverse) are **not** inputs to this model. |
| Corpus | `decision-desk/data/games_2026.csv` — the 2026 regular-season log, Weeks 1–9, 136 games, each row carrying an official `nfl.com` source URL. |
| Blank scores | A row with a blank score is excluded from fitting and from grading. It is never imputed and it is always counted in the published "excluded rows" figure. |
| As-of discipline | Fitting for a forecast issued for week *w* uses only games whose `kickoff_date_et` is strictly earlier than the first kickoff of week *w* and whose week number is < *w*. |
| Market prices | Not read. No spread, total, moneyline, vig or settlement input of any kind is used, because the price-data policy (requirement P7) is undecided and no permissioned price source exists in this repository. |
| Injuries / depth / snap counts | Not read in this registration. Availability features enter only through a *separate* pre-registered amendment (§9) once the availability evidence passes the provenance gate; a fixed point penalty for a missing player is forbidden by §6 of this document. |

## 2. Feature construction (frozen)

For every team *t* in the fitted window, using only games with two published scores:

- `G_t` = games played, `PF_t` = points for, `PA_t` = points against.
- `net_t = PF_t / G_t − PA_t / G_t` (net points per game).
- `att_t = PF_t / G_t`, `def_t = PA_t / G_t` (scoring rate and allowance rate).
- League means `μ_net`, `μ_att`, `μ_def` are the plain means of those quantities over the 32 clubs.
- Shrinkage toward the league mean is applied to every team quantity `x_t`:
  `x̂_t = μ + λ_t (x_t − μ)` with `λ_t = G_t / (G_t + k)` and **k = 2.0 games** (fixed).
- Home environment `h_margin` = mean of (home score − away score) over the fitted games;
  `h_home_pts` = mean home points; `h_away_pts` = mean away points; `home_rate` = share of fitted games
  won by the home team, with ties counted as 0.5 to each side.

No other feature enters. Jersey order, roster order, depth-chart rank, salary, experience and win-loss records
are explicitly excluded as model inputs (the last because it is a monotone function of the point totals already used).

## 3. Forecast (frozen)

For a fixture with away team *a* at home team *h*:

- Expected home margin `m = h_margin + (net̂_h − net̂_a)`.
- Expected home points `E_h = μ_att + (def̂_a − μ_def) + (h_home_pts − (h_home_pts + h_away_pts)/2)`.
  Expected away points `E_a = μ_att + (def̂_h − μ_def) − (h_home_pts − (h_home_pts + h_away_pts)/2)`.
- Originated total `T = E_h + E_a`; originated side = `E_h − E_a` (home team listed first, positive = home gives).
- Home win probability `p = Φ(m / σ)` where `Φ` is the standard normal CDF and
  `σ = clip(stdev(actual home margin − h_margin over the fitted games), 10.0, 17.0)` (fixed bounds).
- Moneyline is reported only as a probability and as the vig-free fair decimal price `1/p` and `1/(1-p)`.
  No offer, no payout and no settlement is computed, because there is no price input (§1).
- Ties: `p` is a probability of a home win; the tie probability is **not** modelled (normal-approximation model).
  Every graded row records whether the actual result was a tie; ties are excluded from side/win grading and
  reported as a count, never absorbed into a win.
- Rounding: published lines are rounded to 0.5; the probability is published to 4 decimals; the unrounded
  values are what get graded. Every published forecast stores the inputs that produced it (§4) plus a config
  hash, so a row can be re-derived from the repository alone.

## 4. Output record (frozen schema)

`shadow-board/data/forecast_records.jsonl` — one JSON object per fixture per strategy version, fields:
`forecast_id`, `issued_at_utc`, `as_of_data` (last included week), `season`, `week`, `slot`,
`away`, `home`, `p_home`, `fair_spread_home`, `fair_total`, `inputs` (the exact team quantities of §2 for both
clubs plus the league constants), `model_version`, `config_hash`, `market_line` (blank until P7), `residual`
(blank until P7), `source_urls` (one per fixture: the official schedule page and, where transcribed, the game
centre). A record is immutable once issued; a correction is a **new** record with `supersedes`, and the
superseded record is retained.

## 5. Evaluation window

| Window | Contents | Use |
|---|---|---|
| Backtest (in-sample growth, walk-forward) | 2026 Weeks 2–9: each week is forecast from the model fitted on all earlier weeks only. Week 1 has no prior and is never forecast. | Published on `backtest.html` only. Labeled *backtest*. Never appears on the leaderboard. |
| Prospective (leaderboard) | Every fixture whose first kickoff is later than the registration commit: Week 10 remainder and Week 11 onward (Week 11 begins Thursday 2026-11-19, 8:15 PM ET per the official schedule page). | The only window the leaderboard may display. |
| Final holdout | 2026 Weeks 15–18 plus all of 2027, reserved, not used for any development decision. | Recorded here so the reservation is auditable. |

## 6. Gates (frozen, fail-closed)

A strategy is `ranked` only when every gate passes. Default state is `not ranked — record only`.

| Gate | Test | Threshold |
|---|---|---|
| A Provenance | Every fixture row in the graded set carries an official `nfl.com` source URL and an as-of date earlier than kickoff; the forecast commit precedes the first kickoff (git hash proof). | any failure → strategy suspended |
| B Sample | Graded games in the prospective window, per division. | ≥ 30 graded games to be ranked; 10–29 → "forming"; < 10 → "not rankable" |
| C Skill | Benchmark-relative Brier skill `1 − BS_model / BS_bench` with a game-cluster bootstrap (resample whole games, 5,000 draws, seed 20261115, percentile 2.5 %). | lower bound > 0 |
| D Multiplicity | Benjamini–Hochberg across every strategy evaluated in the same window, `q = 0.10`. | survives |
| E Stability | Skill > 0 in both halves of the graded window (halves split by game order, not by date). | both halves |
| F Independence | No outcome from the graded window entered §2 fitting for that window (re-derived at check time). | exact |
| G Price firewall | Staking, ROI, CLV and payout columns are blank while P7 is undecided. No strategy may be called "profitable". | structural |
| H Joint evidence | Parlays, same-game parlays and prop combos are not ranked; multiplying marginal probabilities is not published. A joint probability may only be published if it is estimated directly from matched outcomes, with its n. | structural |

**Reward ladder (tied to gates, never to profit).** Tier 0 registered (this file) · Tier 1 A+F · Tier 2 B ·
Tier 3 C+D · Tier 4 E · Tier 5 G-released and H-satisfied. A tier is an eligibility state for a *future*
reward decision, not a payout; funding, eligibility and tax treatment remain owner decisions.

**Demotion gate (live → paper).** A ranked strategy returns to `paper` when either (i) the trailing 20 graded
games' cluster-bootstrap skill lower bound is < 0 in two consecutive weekly evaluations, or (ii) any Gate A
provenance check fails (immediate). Demotion is recorded in §9 with the evaluation date and the numbers.

## 7. Statistics used, and why

Brier score and logarithmic score (proper scoring rules — a score that can be gamed cannot be used here);
benchmark-relative skill against a no-team-information baseline (raw Brier rewards nothing for knowing who plays);
game-cluster bootstrap (two bets on the same game are not independent, so resampling bets would understate the
interval); Wilson intervals for hit rates; Benjamini–Hochberg across the declared family (a leaderboard with *k*
entries produces a large best z by luck); Fisher-z intervals for correlations, with `n` printed beside every
correlation or `null` with the reason.

## 8. Declared family (5 entries; no entry may be added after results are seen without an amendment)

| ID | Division | Rule | What would change our mind (falsify) | What would confirm (falsify the null) |
|---|---|---|---|---|
| SB1-ML | Singles · moneyline | Bet every fixture at the model's probability; report the probability, not a pick. | Cluster-bootstrap skill lower bound < 0 over ≥ 30 graded games; or calibration slope < 1 with a CI excluding 1. | Skill lower bound > 0 over ≥ 60 graded games with BH survival. |
| SB1-ML-S | Singles · moneyline, selective | Same forecasts, only fixtures with \|m\| ≥ 4.5. | Hit rate no better than SB1-ML while sample ≥ 30; or selection rule shows no calibration gain. | Skill lower bound > SB1-ML's over ≥ 30 graded selections. |
| SB1-TOT | Singles · total | Forecast the total; graded on squared error against the official final total, benchmark = fitted league mean total. | RMSE ≥ benchmark RMSE with a CI that excludes an improvement. | Quadratic skill lower bound > 0 over ≥ 60 graded games. |
| CT-HOME | Control | Predict `home_rate` for every fixture, no team information. | It should not beat SB1; if it does, SB1 is refuted and the workspace must say so. | n/a — a control is never promoted. |
| CT-RAND | Control | 0.5 for every fixture, seeded uniform pick for the hit-rate column. | n/a — noise floor. | n/a. |

Controls run in the same window with the same data. A strategy that cannot beat CT-HOME and CT-RAND is reported
as such on the leaderboard; that is the point of running them.

## 9. Amendments

None.
