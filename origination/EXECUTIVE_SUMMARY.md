# Executive summary — origination workspace (session 99122105, 2026-11-15 UTC)

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/origination/index.html
**Branch:** `arena/99122105-nfl3`

---

## 1. What was asked for, and what is now true

The brief asked for a system that originates its own NFL lines, tracks injuries and depth
deficiencies, ranks strategies on a leaderboard without being fooled by luck, publishes an
executive summary, and does all of it with every number traceable to a source.

| Asked for | State | The evidence that decides it |
|---|---|---|
| Price-snapshot store with opening **and** closing numbers | **Partial** — store built, series one observation deep | 78 of 816 event × market cells hold a pre-kickoff number; 411 are post-hoc only; 327 are empty. Opening equals closing wherever it exists, and the ledger says so cell by cell. |
| Verified results feed | **Done** | 137 played games, **160 of 160** club × field checks reproduce nfl.com's official standings; league points-for equals points-against at **6,291**. |
| Side → total → moneyline, in that order | **Done** | Three separate fits, each graded before the next is trusted; the moneyline is a transform of the side model's residual scale. |
| Fair line, market line, difference as separate columns | **Done** | All three columns on every played-game row, with an explicit blank where no price exists. |
| Separate signal from staking | **Done** | The leaderboard is a proper-score table. **No ROI column exists anywhere on the site.** |
| Depth of the replacement, not just the fact | **Partial** | 149 rank-1 slots name more than one player and are kept as groups; playing time measures who actually played. No official source names an assignment, so that cell is blank. |
| Correlations from official numbers only, with n | **Done** | 2 published with n and a Fisher-z interval; **4 withheld** with a written reason. |
| Demotion gate | **Done, and it fired** | Gate G10 demoted **S01 and S03** — two of this session's own rules — because their skill intervals sit entirely below zero. |
| Pre-register every strategy | **Done** | 10 rules, each with a content hash; blocked rules are excluded from scoring rather than shown as untested. |
| Availability graph as a first-class dataset | **Done** | 1,386 slots, 1,745 depth rows, 1,745 named players, 254 report rows, 400 reserve rows, 12,785 playing-time rows. |
| Depth from playing time, never jersey order | **Done** | Measured snap-share leader compared with published rank 1 in 46 groups; disagreement published, never resolved by inference. |
| Injury signal as a surprise, not a level | **Blocked** | A baseline needs a dated series. Exactly **one** official report capture exists. |
| 32-team roster/reserve sweep | **Partial** | Reserve status read for 32 clubs / 400 players; the official transaction log is not held. |
| Fixture-context features from published facts | **Done** | Rest, roof, surface, temperature, wind, division, kickoff on every fixture row. |
| Every model output as probability + inputs | **Done** | Ratings, home-field term, residual scale and probability stored for all three markets. |
| Removal-of-luck panel | **Done** | Sample-size arithmetic, Wilson intervals, paired bootstrap, exact binomial tails. |
| Two-sided "what would change our mind" | **Done** | Promote and kill condition on all 10 rules; the kill condition is executed by G10. |
| Decision-readiness table | **Done** | 62 requirements: 33 implemented, 21 partial, 8 blocked, **0 validated**. |
| Suggestions section | **Done** | 9 proposals ranked by what they unblock, each with cost, risk and the decision it needs. |
| Flagged for review | **Done** | 12 items, each with a source link. |

## 2. The three findings that matter

**Finding 1 — There is no price history, and pretending otherwise would invalidate everything.**
The repository holds one community price observation, taken after Weeks 1–9 had already kicked off.
Those numbers are post-hoc: they can be displayed and compared, but they cannot define an opening, a
close, or closing-line value. Weeks 10's unplayed games are the first genuine pre-kickoff numbers this
project owns, and for them opening equals closing because only one capture exists. This is why **no CLV
claim appears anywhere on the site** and why gate G05 is blocked.

*What closes it:* a scheduled capture (the script already exists) at T-60 minutes before kickoff, then a
second and third capture. Two captures turn one number into an interval.

**Finding 2 — The model is measurably worse than the market, and that is published as the baseline.**
On 137 games the ridge side model's mean absolute error is **10.48 points** against the market's
**9.45**; the total model is **11.36** against **10.55**. A second estimator (leak-free Elo) gives
**9.87** and correlates with the first at about **0.95**. Both trail the market. That is the honest
starting point: a benchmark that loses to the number it is trying to beat, published with its errors so
any future model has something real to beat.

**Finding 3 — The injury effect is not measurable at this sample size, and the system says so.**
The personnel ablation was built as the brief demanded: the same model with and without availability
features, on a chronological holdout (weeks 7–10), with **λ not fitted** and the full grid published.
The holdout MAE improvement at λ=1.0 is **−0.003 points [−0.166, +0.179]**. The interval spans zero for
every λ tested. This is a statement about 137 games and one injury snapshot, not a claim that injuries
do not matter — and the row says exactly that.

## 3. Leaderboard state — nothing is validated

| Rule | n | Brier skill | 95% interval | Status |
|---|---|---|---|---|
| S01 Model spread, no threshold | 131 | −0.106 | interval below 0 | **demoted** |
| S02 Model spread, Δ ≥ 1.5 | 105 | −0.128 | includes 0 | scored |
| S03 Model total | 113 | −0.119 | interval below 0 | **demoted** |
| S04 Win probability vs de-vigged moneyline | 113 | −0.129 | includes 0 | scored |
| S05–S08 Control arms | 131–137 | 0.000 | by construction | controls |
| S09 Two-leg parlay | — | — | — | **blocked** |
| S10 Prop combination | — | — | — | **blocked** |

Every score carries a multiplicity adjustment over 10 trials (α per test = 0.005). Promotion needs
n ≥ 200 and an interval above zero. The largest arm holds 131 graded legs.

## 4. The decisions the site is waiting on

These are the questions, in priority order, that a reader needs answered before any decision is
reasonable. All 20 are on `origination/decisions.html` with their discovery actions.

1. **Price data (Q01–Q02).** Either license an archive with open/close timestamps, or accept a
   community source and label every price as community forever. Nothing else unlocks as much.
2. **Availability evidence (Q03–Q04).** Are listed players actually inactive? Without official inactive
   lists, a replacement is suspected and never established.
3. **Depth semantics (Q05–Q07).** What does a rank mean when one slot names three players? And what is
   the authorised structured source for the two clubs that publish no parseable chart?
4. **Sample and rewards (Q11–Q12).** Is 200 the right promotion floor given same-week dependence, and
   where would any reward money come from?
5. **Reuse terms (Q15).** What may be republished, and does a derived fair line count as republished
   source data?
6. **Automation (Q16–Q17).** What runs the capture schedule, and how is a missed capture recorded?

## 5. Verification performed

- **Settlement reconciliation:** 137 games aggregated to 32 clubs; wins, losses, ties, points for and
  points against match nfl.com's 2026 standings exactly. League PF = PA = 6,291.
- **Independent score spot-check:** 18 games across weeks 1 and 5 read from nfl.com's own scoreboards
  (18/18 match the feed), on top of the standings reconciliation.
- **Depth claims cross-checked against the repository's existing independent audit:** 149 shared rank-1
  slots and 30/32 parsed clubs reproduce the counts already published by the canonical decision lab.
- **Site gate:** 13 pages, 448 table body rows, 0 without a source link, 326 carrying an official
  nfl.com link; 0 broken local links; 0 conflict markers; a rebuild produces byte-identical output.
- **Unit tests:** 35 tests, including the sign-convention regression that was caught during development
  (a losing rule had been labelled a "skill signal") and the push rule.

## 6. Irregularities (published on `origination/flagged.html`)

F01 one price observation · F02 two clubs without a parseable depth chart · F03 no inactive lists ·
F04 the ablation cannot resolve an effect · F05 team-code alias (AZ vs ARI) · F06 kickoff times carry no
time zone · F07 two strategies already failed their kill rule · F08 no reward funding exists · F09 a
club with no report section is not injury-free · F10 one correlation mixes a community price with an
official score · F11 unjoined report rows · F12 the site's own model trails the market.

## 7. What this is not

Not a sportsbook, not betting advice, not a validated system, and not a claim of profitability. No
reward is available, no strategy has earned one, and every number above can be reproduced from
committed artifacts by running `python3 origination/scripts/build.py` and
`python3 origination/scripts/verify.py`.
