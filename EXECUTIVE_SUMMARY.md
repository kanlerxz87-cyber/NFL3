# NFL3 — executive summary

**Status: research workspace. No strategy has been validated, no line has been published, and no
reward is funded.** Everything below is traced to an official page or is an explicit blank.

**Update, 2026-11-15:** a [decision-readiness register](readiness.html) now lists one row per requirement in the brief, the gate that blocks it, and the number that would clear it. As built, the counts are 14 blocked, 29 not started, 18 partial, 1 decision recorded and 2 done (64 rows, computed from committed files). The landing page also holds a separate 18-row summary from another session; the two are not reconciled (flag F9). Ten irregularities are on its Flagged for Review section, including two injury-row counts (254 and 279) and three chain counts (117, 195 and 280) that are still published side by side. Official pages could not be re-fetched from the build sandbox, so no value was re-verified today.

**Update, 2026-11-15 (session ba6c5155):** the [price-data policy](pricing/PRICE_DATA_POLICY.md) is now decided and pre-registered (P7 done): nothing price-dependent publishes until a licensed, timestamped two-sided source exists. The [price-snapshot store](pricing.html) is built fail-closed with an append-only schema and **0 rows** (0 licensed sources). The 136-game log is frozen as a [pre-registered backtest corpus](corpus.html) with a train/validation/holdout split (93/28/15) and evaluation gates that keep backtest numbers off the leaderboard. Every one of the 34 merged strategy entries now carries a two-sided "what would confirm it / what would change our mind" field ([mindchange register](ops-center/leaderboard.html)), the leaderboard separates signal from staking columns, and both required control baselines (random side, favourites-only) are shown beside every strategy. Readiness register counts after this pass: 7 done, 1 decision recorded, 19 partial, 24 not started, 13 blocked (64 rows). Still blocked and unchanged: licensed price data, official game books and inactive lists, verified snap counts, and the Texans depth source.

---

## 0. Status at 2026-11-15 (this pass)

**Where to look first:** the decision-readiness register, one row per requirement, with the gate that blocks it and the number that would clear it ([readiness.html](readiness.html); the same register is summarised on the [landing page](index.html)). It holds 64 rows: 29 not started, 18 partial, 14 blocked, 2 done and 1 with a decision recorded. The [repo review](repo-review.html) lists 14 irregularities, 8 of them high. Every row links to a repository file and an official NFL page; blanks are unverified.

**What is verified today (opened 2026-11-15):**
- The official injury page shows the three Lions designations (Kerby Joseph, Cade Mays, D.J. Reed) as "Out". The committed snapshot does not (RR-02).
- The official transactions log shows two Colts receivers traded on 11/10: Keenan Allen and Josh Downs (V-02).
- The official injury-policy article defines Questionable, Doubtful and Out, and gives no percentage for Questionable (V-03).
- 149 of 676 club/unit/position slots in the committed depth data list more than one rank-1 player, as the brief says (V-04).

**What is wrong and needs an owner (highest impact first):**
- The published injury page is newer than anything in git. The committed snapshot is 254 rows from 2026-11-12; the published page is 347 rows from 2026-11-15, and it comes from a CI capture that is never committed (RR-01, RR-07).
- The pre-registration cannot be shown to precede the results: the registration, engine changes and computed results were committed together in c25ae53 (RR-04).
- The committed verification record was switched from a live run to an offline run whose status is "drift" (RR-06).
- Depth still fails for the Texans and the Packers in the committed snapshot (RR-03).
- No workflow raises an alert, and no workflow computes a residual. Capture and verification steps are allowed to fail without stopping the deploy (RR-08).

**What is still blocked, and by what:** price data and a price-data policy (R01, R08); official game books and inactive lists (R35, R45); a verified snap-count source (R48); the Texans depth source (R57). No strategy is validated. No correlation, edge, ROI or leaderboard position is published.

---

## 1. What the brief asked for, and where it stands

| Requirement | State | Where it lives |
|---|---|---|
| Collect, organise and analyse NFL information against a full requirements register | Partial — 17 requirements traced; completeness limited to verified sources | [Requirements](decision-lab/requirements.html) |
| A clean GitHub Pages site with subpages organised by category | Done — landing page grouped by Decide / Availability / Origination / Verify / Archive | [Overview](index.html) |
| Improve decision making; a suggestions section someone can review before implementing | Done — 75 merged proposals, path A/B, approve/defer/reject, export. Nothing is implemented | [Suggestions](ops-center/suggestions.html) |
| A clear list of questions, known information, answers and discovery actions | Done — 100 merged questions across the workspaces, themed, blocking first, blank answers marked unverified | [Decision register](ops-center/questions.html) |
| Originate our own NFL lines | Blocked — no licensed price history, so nothing can be scored | [Line origination](ops-center/leaderboard.html) |
| Research and develop signal strategies; leaderboard with rewards | Partial — 34 strategies and 31 gates registered, 0 validated; reward rules drafted, none funded | [Line origination](ops-center/leaderboard.html) |
| Single bets, parlays, player-prop combos | Registered, not evaluated — no leg-level outcome data exists | [Line origination](ops-center/leaderboard.html) |
| Each strategy must pass validation gates | Done as a gate set; every strategy fails at the data gate by construction | [Gates](ops-center/leaderboard.html) |
| Determine correlation values | **Not done on official data.** No leg-level settlement history exists, so the value is blank. Community-data figures are shown, labelled, and excluded from official-only gates | [Correlation](ops-center/leaderboard.html) |
| Remove luck; build selectively skill-based strategies | Done as arithmetic and gates, not as results — required sample sizes, deflated Sharpe, multiplicity | [Line origination](ops-center/leaderboard.html) |
| Track injuries and 2nd/3rd/4th-string defensive and offensive deficiencies | Partially delivered — 195 replacement chains published; **43 injured players do not appear on their own club chart**, and **500 of 676 position groups publish no third string** | [Availability](ops-center/availability.html), [Published depth](ops-center/coverage.html) |

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
consistent**. All 32 "designated but active" rows practised fully, which is the signature of that timing problem
rather than of a bad label. Protocol amendment **A1** records this, publishes the anomaly counts, and changes no
threshold. Every rate on the page is therefore labelled provisional until the scheduled capture stores each
report **before** kickoff.

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
