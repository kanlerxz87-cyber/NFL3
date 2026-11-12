# NFL3 — executive summary

**Status: research workspace. No strategy has been validated, no line has been published, and no
reward is funded.** Everything below is traced to an official page or is an explicit blank.

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
