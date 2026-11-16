# NFL3 — executive summary

**Status: research workspace. No strategy has been validated, no line has been published, and no
reward is funded.** Everything below is traced to an official page or is an explicit blank.

**Update, 2026-11-15:** a [decision-readiness register](readiness.html) now lists one row per requirement in the brief, the gate that blocks it, and the number that would clear it. As built, the counts are 14 blocked, 29 not started, 18 partial, 1 decision recorded and 2 done (64 rows, computed from committed files). The landing page also holds a separate 18-row summary from another session; the two are not reconciled (flag F9). Ten irregularities are on its Flagged for Review section, including two injury-row counts (254 and 279) and three chain counts (117, 195 and 280) that are still published side by side. Official pages could not be re-fetched from the build sandbox, so no value was re-verified today.

**Update, 2026-11-15 (session ba6c5155):** the [price-data policy](pricing/PRICE_DATA_POLICY.md) is now decided and pre-registered (P7 done): nothing price-dependent publishes until a licensed, timestamped two-sided source exists. The [price-snapshot store](pricing.html) is built fail-closed with an append-only schema and **0 rows** (0 licensed sources). The 136-game log is frozen as a [pre-registered backtest corpus](corpus.html) with a train/validation/holdout split (93/28/15) and evaluation gates that keep backtest numbers off the leaderboard. Every one of the 34 merged strategy entries now carries a two-sided "what would confirm it / what would change our mind" field ([mindchange register](ops-center/leaderboard.html)), the leaderboard separates signal from staking columns, and both required control baselines (random side, favourites-only) are shown beside every strategy. Readiness register counts after this pass: 7 done, 1 decision recorded, 19 partial, 24 not started, 13 blocked (64 rows). Still blocked and unchanged: licensed price data, official game books and inactive lists, verified snap counts, and the Texans depth source.

**Update, 2026-11-16 (final integration session `arena/dd2f5cf1-nfl3`):** the combined data was re-verified line by line against **live official pages** and the results are published as a new "Final integration verification — 2026-11-16" section on the [repo review](repo-review.html). What was re-read and confirmed today: (1) the transcribed standings snapshot plus the 13 played official Week 10 results reproduce the live official standings for all 32 clubs — **160/160** club × field values; (2) the live transactions log confirms the Colts' two 11/10 receiver trades (Keenan Allen to the 49ers, Josh Downs to the Chiefs) and the Brissett trade; (3) the live injury report shows the three Lions designations (Kerby Joseph, Cade Mays, D.J. Reed) as Out, matching the corrected archive; (4) the official competition-committee article confirms the Questionable/Doubtful/Out definitions with **no percentages**; (5) the official Week 11 schedule matches the pre-registered 13-fixture slate and six byes exactly; (6) both venue flags were confirmed on the official game centres (Houston "RELIANT STADIUM" vs "NRG Stadium" stands; Mexico City / Estadio Banorte verified); (7) the latest hashed injury capture (2026-11-16T06:31Z, 347 rows) agrees with the live page; (8) the corpus SHA-256 pin, the 0-row price store firewall and the 34/34 two-sided strategy fields all re-check. Every local gate and build passes, the live GitHub Pages site was fetched and renders with no broken links. One item remains open and is **not** merged: pull request #96 (session `arena/37020320-nfl3`) had a failing validation check at the time of this pass; per the standing rule, a broken build is not merged, and the PR is left with its owning session to fix. No value was inferred or filled anywhere in this pass.

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
