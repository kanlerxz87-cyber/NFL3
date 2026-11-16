# NFL3 — executive summary

**Current position: a research and decision-support site, not a validated betting system.** The repository now contains a public GitHub Pages analysis site, a pre-registered single-model forecast ledger, a verified NFL results ledger, injury/depth workspaces, a 64-row decision-readiness register, and dedicated questions, suggestions, and flagged-review pages. The key guardrail is working: no licensed price data means no market residuals, ROI, stakes, or rankable strategy leaderboard. No funded reward or strategy qualified for live use is established.

**Evidence boundary.** This summary describes the checked-in repository state and recorded reads dated 2026-11-16. The attempted NFL source re-check did **not** complete a full refresh: a fetch timed out, the verifier reported structural drift (an injury table missing the Game Status column), and two captured Lions practice-status values were flagged as source-updated. No capture was silently rewritten; treat those values as requiring a fresh authorized capture. After PR #120 merged, GitHub Actions completed a successful Pages deployment and the GitHub Pages API reported `built`; the live landing page and this summary were fetched for verification. A stored digest supports integrity of the bytes it covers, not that a capture is byte-exact, licensed, or still current. See the [source register](forward-ledger/sources.html), [repository review](repo-review.html), and the append-only [coordination and deployment log](COORDINATION.md) for read times, verification detail, historical handoffs, and limitations.

## Decision snapshot

**Source convention:** repository links prove what this repository currently publishes; each official URL below is the upstream NFL/GitHub source context for the associated data or site requirement, not an endorsement of the model, a licence grant, or proof that the repository count appears on that external page. If a value cannot be verified from the official page, the relevant data table keeps it blank and flags it.

| Area | What is supported now | What is not established | Repository evidence | Official source context |
|---|---|---|---|
| Requirements and decisions | The readiness register has **64 rows**: 35 partial, 13 not started, 8 blocked, 7 done, and 1 decision recorded. The question and suggestion registers contain **100 questions** and **75 proposals**. | A status label is not proof that an external source or live feed remains current. | [Readiness](readiness.html) · [questions](ops-center/questions.html) · [suggestions and review controls](ops-center/suggestions.html) | [NFL injury report](https://www.nfl.com/injuries/) (source context for availability requirements) |
| Results | The forward ledger holds **150 fixtures: 149 graded and 1 still unplayed at its recorded read**. The independent standings check is **160/160 fields**, and the frozen 136-game Weeks 1–9 corpus has 135 identical rows, one unresolved blank, and no mismatches. | The unresolved corpus blank is not silently repaired; weekly extension and recapture are operational tasks. | [Results ledger](forward-ledger/results.html) · [corpus](corpus.html) | [NFL 2026 scores](https://www.nfl.com/scores/2026/week-10) · [NFL standings](https://www.nfl.com/standings/) |
| Model and originated lines | A model version was pre-registered before its forecast artifacts. The Week 11 slate has **39 forecasts** (side, total, moneyline over 13 fixtures), with inputs and probabilities retained. Each total is published from two estimators. The reported 28-game chronological holdout has Brier skill **+0.3223 versus the in-window base rate**; the removal-of-luck panel reports 0.2059 of game-margin variance inside the model expectation. | These are research diagnostics from one season and one 28-game holdout, with no interval reported for that Brier skill. Neither that score nor a model/variance decomposition establishes stable prospective skill or a live edge. | [Originated forecasts](forward-ledger/prospects.html) · [pre-registration](forward-ledger/PREREGISTRATION.md) · [backtest, explicitly excluded from ranking](forward-ledger/backtest.html) | [Official schedule](https://www.nfl.com/schedules/2026/by-week/week-11) |
| Prices and staking | The price policy is adopted and fail-closed; the append-only store schema exists. | **Zero licensed price rows**: the market-line and difference fields are blank on all 39 forecasts. There is no verified opening/closing quote history, CLV, ROI, vig-free market consensus, or stake result. | [Price policy](pricing/PRICE_DATA_POLICY.md) · [price ledger](pricing.html) | [NFL betting FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) (source-rights boundary) |
| Leaderboard and rewards | Singles divisions, controls, proper-score qualification, uncertainty and a demotion gate are registered. Backtest diagnostics are withheld from the leaderboard. | **Zero eligible/rankable strategies** and zero graded games in the prospective window at the checked-in snapshot. Parlays and prop combos are gated until directly validated joint probabilities and operator settlement/void rules exist. Rewards are unfunded. | [Prospective leaderboard](forward-ledger/leaderboard.html) · [forward-ledger gates](forward-ledger/PREREGISTRATION.md) | [NFL schedules](https://www.nfl.com/schedules/2026/by-week/week-11) (fixture/results source; does not validate strategy outcomes) |
| Correlation | One official-input descriptive score correlation is reported with sample size and uncertainty: home margin × total points, **n=149, r=-0.141, 95% CI [-0.295, 0.020]**. | This is not a player-prop or bet-leg correlation, and it does not validate a parlay. The separate community-input row is excluded from official-only gates. | [Correlation register](origination/correlations.html) | [NFL standings](https://www.nfl.com/standings/) (official score inputs) |
| Injuries and availability | A dated Week 10 read records **347 injury rows across 28 clubs**, and the corresponding inactive article records **147 entries**. The matchup workspace models published depth slots as groups, preserves blanks, and flags roster/depth conflicts. | This is not a multi-day, multi-season point-in-time series. The archived hashes cover reconstructed rendered text, not byte-exact NFL responses. The coverage is not complete for 32 clubs; actual starters, snaps, workload and confirmed replacements remain unverified. | [Availability ledger](forward-ledger/availability.html) · [injury archive and limits](injury-archive/limits.html) · [matchup desk](matchup/index.html) | [NFL injury report](https://www.nfl.com/injuries/league/2026/REG10) · [official inactives article](https://www.nfl.com/news/nfl-week-10-inactives-players-ruled-out-sunday-2026-season) |
| Designation calibration (measured, provisional) | Joined to the official Week 10 inactive article: **Out 48/64 = 75.0%** (95% CI 63.2–84.0), **Doubtful 4/10 = 40.0%** (16.8–68.7), **Questionable 15/82 = 18.3%** (11.4–28.0); 171 designated rows = 67 inactive + 89 active + 15 uncovered. Pre-registered protocol, per-row evidence with both source links. | One week is 1/18 of a season (confirmation gate: n ≥ 100 per label, per-season separation), and the join is not point-in-time consistent: of the 89 rows counted active, only 32 practised fully (the timing signature); 57 did not, including 15 of 16 ruled Out. (Wording corrected 2026-11-16 after recount; per-row evidence unchanged.) | [Calibration table](injury-archive/designations.html) · [flags](injury-archive/flags.html) · [limits](injury-archive/limits.html) | [Official Week 10 report](https://www.nfl.com/injuries/league/2026/REG10) · [official Week 10 inactives](https://www.nfl.com/news/nfl-week-10-inactives-players-ruled-out-sunday-2026-season) |
| Website | The repository has a grouped landing page, category workspaces, source registers, decision pages and a clearly labeled flagged-review page, with Pages workflows and offline link/data checks. Post-merge, the main validation/deploy workflow and a subsequent Pages build/deploy both succeeded; the Pages API reports `built`, and the live landing page and summary were fetched. | Eight disclosed source-class warnings remain in the ops-centre checker; non-official evidence must not be presented as official. This confirms the deployment, not the freshness of every NFL source row. | [Live landing page](https://kanlerxz87-cyber.github.io/NFL3/) · [live executive summary](https://kanlerxz87-cyber.github.io/NFL3/EXECUTIVE_SUMMARY.md) · [Flagged for Review](flagged.html) · [source register](sources.html) · [deployment history](COORDINATION.md) | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## What must be answered before decisions are reasonable

| Question | Known answer | Missing information / why it matters | Recommended discovery action | Evidence |
|---|---|---|---|---|
| What price source may be used, and under what terms? | The adopted policy requires a named source, written permitted-use licence, market as-of time and capture time for every price. None is registered. | Without historical two-sided quotes, own-line residuals, closing-line value and ROI cannot be computed without violating the project policy. | Compare providers' written NFL odds/props coverage, historical depth, timestamp precision, correction policy and derivative rights; approve and register a licence before ingest. Until then keep price-derived fields blank. | [Policy and gate](pricing/PRICE_DATA_POLICY.md) · [NFL betting FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) |
| Which availability evidence confirms who actually started or played? | Dated injury and inactive evidence exists for one Week 10 pair; club charts publish named depth slots for most, not all, captured clubs. | An injury designation is not proof of a start, snap share, or replacement workload. Reconstructed captures cannot reproduce exact original bytes. | Where terms permit, retain immutable raw responses with fetch clocks and hashes from Wednesday through kickoff; join official inactives and dated NFL Game Books; report disagreements and unresolved clubs instead of inferring. | [Archive limits](injury-archive/limits.html) · [NFL injury report](https://www.nfl.com/injuries/) · [NFL scores/Game Centres](https://www.nfl.com/scores/) |
| Is depth coverage reliable across all 32 teams and position groups? | Shared rank-1 slots are preserved as groups; stale and conflicting entries are flagged. | A complete official depth route is not established for every club. Texans image parsing needs an authorized structured source; jersey number, experience, salary and roster order are invalid substitutes. | Audit each club's dated official chart and source format; record unavailable/empty/shared slots explicitly. In parallel, verify whether an official snap-count feed with reuse rights can supply a measured alternative. Do not publish a complete replacement feature until one route covers all clubs. | [Coverage and flags](matchup/coverage.html) · [official club depth pages register](matchup/sources.html) | [49ers depth chart](https://www.49ers.com/team/depth-chart) · [Packers depth chart](https://www.packers.com/team/depth-chart) (examples, not full-league coverage) |
| Do availability features improve forecasts? | A one-week availability snapshot and team-strength results exist. Fixed injury penalties are not used as evidence of value. | There is no multi-week, point-in-time alignment of reports, inactives, starters, snap counts and outcomes sufficient for a robust personnel ablation. | Capture successive weekly vintages; preregister identical models with/without verified availability features; use chronological season holdouts, group uncertainty by game, and publish sample counts and intervals before interpreting differences. | [Availability delta](forward-ledger/availability.html) · [pre-registration](forward-ledger/PREREGISTRATION.md) · [NFL injury report](https://www.nfl.com/injuries/) |
| Are singles, parlays or prop combos skill-based? | The leaderboard separates signal and staking, has control baselines, and bars retrospective backtests from rank placement. | There is no prospective graded sample yet; official leg-level odds/settlements and validated joint probabilities are absent. Raw win rate or season ROI is not sufficient evidence. | Keep singles first. Require the registered prospective window, benchmark-relative proper score with game-cluster uncertainty and multiple-testing control; require direct joint-probability evidence plus exact void/push rules before any combo can enter. | [Leaderboard divisions and gates](forward-ledger/leaderboard.html) · [official score results](forward-ledger/results.html) · [NFL game-centre scores](https://www.nfl.com/scores/) |
| Who funds rewards, and what operating/legal constraints apply? | The repository records no funded reward. It does not assume a wagering operator or regulatory status. | Funding, eligible jurisdictions, data rights, and whether this remains analysis-only cannot be inferred from NFL pages or automated responsibly. | Treat these as explicit governance/legal decisions; obtain written operator, licence and jurisdiction review before enabling wagering, reward payment or price-dependent publication. Keep the current public layer analytical. | [Flagged for Review](flagged.html) · [questions register](ops-center/questions.html); official NFL source: **not applicable / unverified** for this governance choice. |

## Recommended order of work

1. **Keep the evidence firewall.** Do not fill licensed-price, snap, starter, replacement, or joint-prop fields with estimates. Do not rank by season ROI or expose backtest figures as leaderboard performance.
2. **Complete the source-rights and source-coverage inventory.** Resolve licensed prices first; verify official availability/depth/snap coverage club by club; preserve raw bytes only where terms allow.
3. **Automate point-in-time collection and drift alarms.** Schedule source captures, retain timestamps/hashes, compare schema and expected row counts, and publish changes/conflicts rather than overwriting history.
4. **Build prospective evidence before expanding bet types.** Run the registered singles baseline and control strategies through chronological windows; use proper scores, uncertainty, multiplicity adjustment, and explicit demotion-to-paper rules.
5. **Only then evaluate personnel ablations and combo markets.** Use verified inactive/starter/snap evidence and directly validated joint probabilities. Publish uncertainty and sample size, including null findings.
6. **Keep recommendations reviewable.** The [suggestion board](ops-center/suggestions.html) contains path choices and approve/defer/reject controls that save only in the viewer's browser and can be exported; choosing an option does not change repository data. The [question register](ops-center/questions.html) identifies blockers and discovery steps. No source can choose a vendor licence, spending limit or reward budget on the owner's behalf.

## Verification performed for this update

Offline checks passed in this checkout:

- `python3 scripts/validate_site.py` and `python3 tests/check_site.py` — root links/assets, citations, readiness/ops metrics and decision-review routes.
- `python3 forward-ledger/scripts/verify.py` — 30 gates, including preregistration ordering, 39 forecasts, 0 market-price fields, 0 leaderboard statistics copied from backtests, results reconciliation and row citations.
- `python3 matchup/scripts/check.py` — 14 checks; `python3 injury-archive/scripts/verify.py` — 2,174 checks.
- `python3 shadow-board/scripts/check.py`, `python3 pricing/test_pricing.py`, `python3 corpus/test_corpus.py`, `python3 origination/scripts/verify.py`, `python3 tests/test_decision_lab.py`, `python3 tests/test_readiness.py`, and `python3 tests/test_skill_lab.py` — passed.

The ops-centre verifier reports **0 failures and 8 source-class warnings** (community/secondary sources explicitly identified); it does not mean every row is official-only. `decision-lab`/strategy tests use synthetic fixtures and are not NFL performance validation. The full-clone CI check is authoritative for gates that inspect git history; a shallow local clone cannot prove all preregistration ordering checks. The coordination log contains the previous dated report, PR/deploy records, and unresolved integration flags; those historical notes are not all current-state claims.

### Primary public pages

- [NFL3 landing page](index.html)
- [Decision readiness](readiness.html)
- [Verified results and prospective model ledger](forward-ledger/index.html)
- [Price store and policy](pricing.html) · [pre-registered corpus](corpus.html)
- [Availability and matchup analysis](injury-archive/index.html) · [Matchup desk](matchup/index.html)
- [Questions](ops-center/questions.html) · [Suggestions](ops-center/suggestions.html) · [Flagged for Review](flagged.html)

---

## Archived dated reports (preserved for the record)

The current-state summary above replaced an earlier long-form executive summary on 2026-11-16. The rewrite said the previous dated report lived in `COORDINATION.md`; a verification during the same-day integration pass (session `arena/cea77066-nfl3`) found that sections 2–6 of the old report existed nowhere else, and section 9 (injury-designation calibration) came from PR #105, which was closed without merging. To discard nothing, all of it is preserved verbatim below. These are historical notes, not current-state claims; the table above is current state.

---

## 2. The three findings that should change the plan

**1. The official injury page is not an archive.** Captured at 06:32Z on 2026-11-12 it held 254 rows
across 24 clubs, with four clubs reporting no injuries. Re-read at 22:25Z the same day it held 279.
Seattle and Cincinnati had published 19 rows that did not exist in the morning; six more rows were
added to four clubs; four Colts practice statuses moved in both directions. Nothing was removed.
Any figure computed from a single capture silently carries hindsight.
→ [Source drift](ops-center/drift.html)

**2. Published depth is shallower than the requirement assumes.** Across 30 captured club charts,
500 of 676 position groups (74%) publish no third string. A handful publish a fourth. The request to
track third- and fourth-string replacements cannot be met from official club charts as they stand.
Where it is needed, the cell is blank.
→ [Published depth](ops-center/coverage.html)

**3. Nothing can be scored.** There is no licensed odds, prop or settlement history in this
repository. Every strategy therefore sits at "not run" — not by choice, but because there is no
price to compare against and no result to grade. Any leaderboard published before that is fixed
would be decoration.
→ [Line origination](ops-center/leaderboard.html)

---

## 3. What the data *does* support right now

- **279 official injury rows** and **1,745 official club depth rows** across 30 clubs.
- **195 replacement chains**: for each listed player, the string his club publishes behind him — and
  whether that next man is himself on the injury report.
- Worked example: the Patriots rule out three players. Their running-back chain is published four
  deep — Stevenson (1st), Henderson (2nd), Kiner (3rd), Larison (4th). Henderson is **Out** and
  Stevenson is **Did Not Participate** on the same report, so the published next men are the 3rd and
  4th strings. This is exactly the case the brief describes, and it is the only *kind* of case the
  data can answer: who actually plays, and what it costs, is published by nobody.
- **24 clubs** have at least one published string on the official report; a handful have two
  compromised strings at the same position group.

---

## 4. What is deliberately blank

Confirmed replacement. Expected snaps. Performance or points impact. Edge. Closing line value.
Leaderboard rank. Reward amounts. Correlation measured on official data. Each of these is either
unpublished by any official source or unmeasurable without a licensed result history. They are
rendered as blank, marked `unverified`, and listed on
[Flagged for review](ops-center/flagged.html).

---

## 5. Irregularities found while verifying (10, each with its source)

| # | Severity | Finding |
|---|---|---|
| OF-01 | Critical | The official injury page changed 25 rows in sixteen hours |
| OF-02 | Critical | Patriots depth rows are labelled "club depth chart", but the page states it is unofficial |
| OF-03 | High | 43 injured players do not appear at their position on their own club chart |
| OF-04 | High | 500 of 676 position groups publish no third string |
| OF-05 | High | Two Week 10 clubs have no depth capture at all |
| OF-06 | Medium | Published strings are not always one player (Seahawks WR cell holds two) |
| OF-07 | Medium | Status is a category, not a probability — the official policy says so |
| OF-08 | Medium | No licensed odds, prop or settlement archive is held |
| OF-09 | Medium | Inherited strategy text carries figures computed on community data |
| OF-10 | Medium | One question row cites a secondary news source as its evidence |

---

## 6. The decision I need from you

Everything above converges on one sequencing: **approve a dated, hashed capture schedule first,
then secure written odds terms, then run a single pre-registered singles baseline.** Doing the third
before the first two produces numbers that look like evidence and are not. The
[suggestions page](ops-center/suggestions.html) is set up for exactly this review — pick a path,
record the decision, export it.

---

## 7. Update, 2026-11-15 (session `arena/745d100d-nfl3`): the pre-registered singles baseline is now built

The third step of the sequencing in §6 — "run a single pre-registered singles baseline" — has been carried out in a
new workspace, [`shadow-board/`](shadow-board/index.html), with the first two steps still unapproved. That is the
honest reading of what follows: a baseline that can be scored, not a baseline that can be priced.

**What is now in place.** `shadow-board/PREREGISTRATION.md` was committed at 13:00:32Z **before** any model file,
data artifact or page in that workspace, and the git hash of that commit is the registration record (the sequence
is re-checked by `python3 shadow-board/scripts/check.py`, which fails if a result artifact predates the rule text).
It freezes one model, five declared entries (two real strategies, one totals strategy, two controls — a
no-team-information home-rate benchmark and a coin flip), eight fail-closed gates and the evaluation window, with
both a falsification and a confirmation condition for every entry. The leaderboard page shows only the prospective
window; nothing computed from finished games can appear beside a ranking, and the build refuses if a backtest value
is echoed there. The 2026 schedule page was captured for Week 11 (13 fixtures, kickoff slots, published records, six
byes), and originated side, total and moneyline probability were issued for all 13 fixtures on 2026-11-15, before
the Thursday 8:15 PM ET kickoff, with the inputs of every forecast stored alongside it.

**What the pass measured, on 118 finished games from the official log.** The model's Brier skill against that
no-team-information benchmark is **+0.068 with a game-cluster lower bound of −0.052** (bootstrap p = 0.13), so it is
not distinguishable from zero at this sample size. The selective variant is **−0.004**: filtering for big projected
margins did not help. Totals are worse than naming the league average (**skill −0.100**). The coin-flip control
reaches p = 0.045 on the same window and still has an interval covering zero, which is the clearest argument on the
site for why win-rate and single-number leaderboards mislead. Roughly a quarter of the variance in margins sits
inside what an expectation can address, and the calibration table shows over-confidence in the 0.6–0.8 band. The
sample size for a positive lower bound at the current effect is on the order of hundreds of games, so the register's
default state — "not ranked — record only" — is the correct state today.

**Overlap found while integrating, and how it is handled.** A second session registered a comparable evaluation of a
team-strength model on the same official 2026 corpus in [`official-verify/`](official-verify/index.html)
(`PREREG-2026-OV1.md`, ridge attack/defence, fixed sigma 13.5, Weeks 4–10 with Weeks 1–3 warm-up, three controls). The
two workspaces are separate registrations of the same question and their numbers are not pooled or averaged anywhere;
[`shadow-board/method.html`](shadow-board/method.html) states which claim comes from which registration in a
side-by-side table. The agreement worth recording for the owner is the negative one: on this corpus neither model's
benchmark-relative skill clears a game-cluster lower bound above zero (this workspace +0.068 with a lower bound of
−0.052; their published interval on the paired improvement is −0.0099 to +0.0691, and their own lower-bound gate is
False). Two independent formulas, the same conclusion, so a selective-skill claim is premature whichever is used.

**What was verified against official pages, line by line.** 21 values were read off official pages and compared with
the committed log field by field: 17 match, 0 disagree, and 2 fill cells the log leaves blank. The repo-review
register now carries 19 findings (from 14) and 9 verified checks: Week 2 Washington at Dallas is now published
20-37, so the corpus is 135 graded of 136 and the blank is closable by the log's owner, not by this workspace; two
official pages disagree about the Houston venue (game centre "RELIANT STADIUM" against the schedule page's travel
link "NRG Stadium"), so 11 of 13 Week 11 venue cells are blank rather than guessed; the past-season injury archive
`nfl.com/injuries/league/{season}/REG{week}` does render, which **narrows** the archive gap in `flagged.html`, but the
win-loss records printed beside it are end-of-season values, so it is not point-in-time safe and must not be used to
calibrate "Questionable" against inactives; and those pages' titles state a different week from their own body
headers, which would mislabel every capture by a week for a parser keyed on the title.

**Decisions this workspace still needs (nothing here acts on them).** Two of the six moved while this pass was in
flight, and the pages were corrected rather than left asserting the older state. The **price-data policy** is now
written and adopted in [`pricing/PRICE_DATA_POLICY.md`](pricing/PRICE_DATA_POLICY.md) as a fail-closed rule — a named
source, a named licence with permitted use, and both the price's as-of time and the capture clock time, or the row is
not stored and no price-dependent number is published — and its own register currently grants nothing (no permitted
source, no stored price rows, no residual rows), so the market and residual columns here are blank **by rule** rather
than by omission. The verified game log is now **frozen by SHA-256** in [`corpus/manifest.json`](corpus/manifest.json)
with a registered chronological train/validation/holdout split, and `shadow-board/scripts/build.py` pins each
forecast to the log's hash, with the gate failing if the live file and the frozen copy diverge. What is still open:
whether the log is extended and hashed weekly, which is what makes rest-day, form and availability features possible
at all; which official field is authoritative for venue; and what a tier pays. Each remaining item is a row with its
unblocking effect on [`shadow-board/registers.html`](shadow-board/registers.html), beside six suggestions with cost
and blocker stated. The §1 sentence of the pre-registration that said the price policy was "undecided" is kept as
written and annotated as amendment A1 in §9, because a frozen registration must be annotated, not re-worded.

## 8. Update, 2026-11-16 (session `arena/5600e7eb-nfl3`): the forward ledger is published, and the root has a questions page

**What moved.** [`forward-ledger/`](forward-ledger/index.html) is now a published sub-site with eight pages and its own
fail-closed verifier, and the root of the site has a [questions page](questions.html) for the first time. Three
numbers in this file, and in [the readiness register](readiness.html), were stale in the same way: the counts in the
two update paragraphs at the top of this document (14 blocked / 29 not started / 18 partial, and 7 done / 19 partial /
24 not started / 13 blocked) are what those two passes recorded on 2026-11-15. The register read today is **64 rows:
35 partial, 13 not started, 8 blocked, 7 done, 1 with a decision recorded** ([`readiness/data/readiness.csv`](readiness/data/readiness.csv)).
The earlier sentences are left as written because they record what was true when they were committed; the register is
the current source, and this paragraph is the reconciliation (finding FL-08).

**Verified, line by line, against official pages.** The results feed now runs to Week 10: **150 fixtures, 149
graded, 1 left scheduled** because Los Angeles at Baltimore had not been played when the page was read
([`forward-ledger/results.html`](forward-ledger/results.html)). Three independent cross-checks were run rather than
asserted: club records against the record chips printed on the official pages (31 of 32 clubs read, 0 mismatches,
Cincinnati deliberately not compared with a self-computed number), the same records plus points for and against
against a same-day independent standings read (**160 of 160 field checks**, [`data/standings_crosscheck_origination.json`](forward-ledger/data/standings_crosscheck_origination.json)),
and Weeks 1-9 against the frozen pre-registered corpus (**135 of 136 identical, 0 mismatches**; the 136th is the
Washington at Dallas row the corpus still leaves blank while the official game centre publishes 20-37 - closable only
by the corpus owner, FL-02). One official irregularity survived checking: `2026_01_NE_SEA` is labelled "Sunday Night
Football, September 9th" on a page whose own printed date, 2026-09-09, is a Wednesday.

**What the model is, and what it is not.** The registration is [`forward-ledger/PREREGISTRATION.md`](forward-ledger/PREREGISTRATION.md)
at commit `e2f97c5`, before any Week 11 result existed; `verify.py` recomputes that ordering from git history on every
run instead of trusting a sentence. `fl1.0.0` (config `0f30928f51ca8cde`) fits `mu` 23.087 and a home-field term of
**-0.255**: on 2026 data as published there is no home advantage to assume, which is why the term is fitted and not
hardcoded (FL-10). In sample over 149 games the margin R² is 0.4102 and the total R² 0.2605; on the pre-declared
chronological holdout (Weeks 1-8 fitted, 9-10 evaluated, 28 games) margin R² is 0.4266 with Brier skill **+0.3223**
against the in-window base rate and **+0.4087** against a coin - one window, one season, no interval claimed. The
removal-of-luck panel puts **0.2059 of game-margin variance inside the expectation**; the rest is luck by
construction, and the [backtest page](forward-ledger/backtest.html) is barred from the leaderboard by a gate that
checks the two pages do not share a number.

**Lines originated, prices still absent.** [`forward-ledger/prospects.html`](forward-ledger/prospects.html) prints **39
forecast rows over 13 Week 11 fixtures** (side, total, moneyline), issued `2026-11-16T14:55:05Z`, before the Thursday
kickoff. Fair line, market line and difference are separate columns; the market-line and difference columns are blank
on **39 of 39** rows because [`pricing/PRICE_DATA_POLICY.md`](pricing/PRICE_DATA_POLICY.md) grants no source, and
every total is published twice - the additive model and the sum-of-scoring-rates estimator, disagreeing by
0.46 to 5.50 points - with neither retired until the walk-forward comparison in §3 can be evaluated. The
[leaderboard](forward-ledger/leaderboard.html) is an eligibility table with **0 rows rankable**, signal and staking in
separate columns, both control baselines registered, parlays and prop combos behind a joint-evidence gate, and the
reward field unfunded.

**Availability, stated as a property of the read.** [`forward-ledger/availability.html`](forward-ledger/availability.html)
aggregates the newest hash-pinned capture (`991825b7`, 2026-11-16T06:31:00Z, **347 rows over 28 clubs**) against the
2026-11-12 read other pages still publish: **+93 rows, 120 game-designation changes, 106 practice-status changes,
0 removals**. Designated rows went from 9 of 254 to 171 of 347, so any "Questionable plays X% of the time" number
computed from one read time measures the page's publication schedule, not the label (FL-04). The numbers on this
line moved twice inside this session: they were 123 and 107 before the rebase onto `main`, and changed to 120 and
106 because commit `91d5d86` filled the three blank Lions game-status cells that the baseline snapshot reads, which
is the delta doing its job rather than a page being corrected by hand (FL-16). The re-parse also surfaced one row
that contradicts itself on the official page - a Jaguars player listed Out for the game with Full Participation in
practice - carried as a conflict flag rather than resolved by picking a half (FL-17). No player names are
republished at root level, because the public/private layer split is still an open decision (FL-03).

**Defects found in the site itself and fixed while publishing.** The landing page shipped **two concatenated HTML
documents** - a stale truncated copy ahead of the current page, which no gate checked for (FL-14); the shared footer
asserted a single "Source reviewed" date that had gone stale for every workspace it serves (FL-06); and
`assets/site.js` had an unclosed array literal, so the nav threw before rendering on every root page - `node --check`
is the only gate that catches it, and none existed. Root [`suggestions.html`](suggestions.html) was hand-written prose
with no register rows and no questions page beside it; both pages are now generated from
`ops-center/data/derived.json` by [`questions/build.py`](questions/build.py), which preserves the curated Path A-D
narrative verbatim and prints **100 questions (67 blocking, 14 with an answer recorded, 65 blocking and unanswered)**
and **75 proposals (40 with no priority, 54 with no path, 13 holding a sentence where a status belongs)** - the
gaps are displayed, not filled (FL-07, FL-15).

**The gate that is not enforcing what it says, and was not repaired.** `scripts/validate_site.py` prints "Sub-sites
with their own checker are validated by that checker" while setting a flag and `continue`-ing without running any of
them. Locating the checkers is the last thing it does. Probed by hand on this branch, `origination/scripts/verify.py`
and `node dashboard/scripts/check.mjs` pass and `skill-lab/scripts/verify.py` fails here - "pre-registration commit
`a60261fa0f9a` is not in the repository history" - while passing in CI, which checks out with `fetch-depth: 0`: a
gate that reads git history is only reproducible in a full clone, which is a caveat for
`forward-ledger/scripts/verify.py`'s ordering check too, and is why CI rather than a sandbox is the arbiter here. The
candidate list also offers `.mjs` files to an interpreter that is `python3` everywhere else. Changing the shared
validator is the root owner's call, so it is logged as **FL-13** with the cause, and the forward-ledger gate is wired
into [`.github/workflows/pages.yml`](.github/workflows/pages.yml) directly: rebuild the ledger, the availability
aggregates and the pages, run the 30 gates, and `git diff --exit-code -- forward-ledger` so a published page can never
drift from committed data.

**What the first CI run of this pull request caught, on somebody else's step.** It went red at "Price-store policy,
ingestion tests, deterministic page build and integrity check" - a step this pull request does not touch. On `main`
at `4f35ac9`, `python3 pricing/build.py` rewrote the committed `pricing.html`, and `corpus.html` was stale against its
own builder in the same way, so the `git diff --exit-code` that ends those steps fails for whoever merges next. The
only difference in either file is the shared sidebar those builders stamp in, which was updated without rebuilding the
dependent pages - and in the process dropped `shadow-board/index.html`, which is also why the live landing page linked
shadow-board nowhere (the stale duplicate document removed under FL-14 was the last place that carried it). Both
generated pages were regenerated here so the shared gate is green for the next session, no value or claim in either
file moved, and the nav itself is left to its owner (**FL-18**).
## 9. Injury-designation calibration: what "Questionable" is actually worth (session d37d5907, 2026-11-16)

**Status: measured, published, and explicitly provisional.** This section reports the first time this project
has been able to put a number on an injury designation instead of importing one from memory or a third party.

**The blocker, and how it was cleared.** Two readiness requirements had been blocked for the same reason: the
repository held one day's capture of the official injury report (R6) and **no** official inactive list at all
(A6), so there was nothing to join a designation to. Both now have a scheduled, content-addressed mechanism in
[`injury-archive/`](injury-archive/index.html), and a pre-registered protocol
([`injury-archive/PREREGISTRATION.md`](injury-archive/PREREGISTRATION.md), IA-PRE-01) that fixed the population,
the join, the estimator, the exclusions and the gates **before the first result existed**.

**The two official documents.** The NFL publishes inactive lists not at `nfl.com/inactives/` — which on
2026-11-16 read *"Please check back soon for NFL Inactive Reports for this Season"* and listed no player — but in
a weekly article, `nfl.com/news/nfl-week-{week}-inactives-players-ruled-out-sunday-{season}-season`. That finding
is the reason A6 was cleared; it is recorded on the site rather than assumed.

**The first measurement (2026 Week 10, both documents joined by club and player name):**

| Designation | n joined | Inactive | Rate | 95% Wilson interval |
|---|---|---|---|---|
| Out | 64 | 48 | **75.0%** | 63.2–84.0% |
| Doubtful | 10 | 4 | **40.0%** | 16.8–68.7% |
| Questionable | 82 | 15 | **18.3%** | 11.4–28.0% |

171 designated rows are fully accounted for: 67 inactive + 89 active + 15 uncovered + 0 ambiguous. The 15
uncovered rows are four clubs whose game had not been played when the article was written; they are **excluded**
from every rate and never counted as active.

**Why this is not yet a finding.** The pre-registered confirmation gate is `n ≥ 100` per label with per-season
separation, and one week is 1/18 of a season. More importantly, the Week 10 report was read on 2026-11-16, after
several clubs had already played, so pairing it with the pre-game inactive list is **not point-in-time
consistent**. Of the 89 designated rows counted active (absent from the inactive list), the 32 that had
practised fully are the signature of that timing problem; the other 57 did not (38 limited, 19 did not
participate), including 15 of the 16 ruled **Out** — Kerby Joseph among them (the sixteenth, BJ Green II,
had practised fully and sits inside the 32 above) — so the timing story does not explain
those rows and no reason for them is established. *(Corrected 2026-11-16 by the integration verification
pass: this paragraph earlier said "All 32 'designated but active' rows practised fully", which misnamed the
32-row full-practice anomaly bucket as the whole set of designated-but-active rows. The per-row evidence
never changed; only this sentence did.)* Protocol amendment **A1** records this, publishes the anomaly
counts, and changes no threshold. Every rate on the page is therefore labelled provisional until the
scheduled capture stores each report **before** kickoff.

**Evidence strength, stated in the archive itself.** This session's shell has no nfl.com egress, so the Week 10
rows were transcribed from the session fetch tool's rendered text; those index lines carry
`raw_bytes_retained: false` and say so. The transcription is machine-checked against the verified parser with
`--expect 347 --expect-clubs 28`, and it returns **the same 347 rows the repository's independent byte-exact
capture of that page records**. The scheduled workflow replaces every such capture with a real byte capture.

**What a reader should do with the numbers today.** Use them as a measured prior for direction and rough
magnitude, with the intervals attached, and do not use the labels as model features until the gate clears. The
practice-status cut is the more actionable result even at this sample size: a designated player who practised
fully is inactive far less often than one who did not.

**What is still blocked.** The snap-count half of A6 (no official snap or participation source is verified), the
official Game Books behind A1/A2, and past-season coverage (every 2021–2025 inactives address probed so far is a
404). Each is listed with its evidence on [`injury-archive/flags.html`](injury-archive/flags.html) and on the
Flagged for Review page.

**One main-branch defect found and fixed in passing.** A scheduled `data-refresh` commit had pulled in a community
schedule release containing the Week 10 finals while the official standings snapshot still described the
pre-Week-10 league, so `origination/scripts/build.py` correctly refused to reconcile and **failed** — which meant
no change could pass CI. It was fixed by re-transcribing all 32 official standings rows on 2026-11-16 (24 rows
had moved; every before/after pair is recorded in the artifact), not by reverting the refresh or relaxing the
check. Reconciliation is now 160/160.
