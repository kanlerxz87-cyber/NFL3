#!/usr/bin/env python3
"""Research protocol for the injury-designation calibration, written before any result exists.

What this file freezes
----------------------
The question, the population, the join, the estimator, the exclusion rules, the gates and the
two-sided falsification statement. It is committed *before* `build.py` is first run against the
archive, so the numbers that page `designations.html` publishes cannot have been chosen after the
fact. Any later change is an amendment appended below, never an edit to the frozen text.

The registration commit is the commit that adds this file. `injury-archive/scripts/verify.py`
asserts that the commit exists and precedes the commit that added `injury-archive/data/designations.json`.
"""
# Injury-designation calibration — pre-registration (ID: IA-PRE-01)

**Registered by:** session `arena/d37d5907-nfl3`
**Registration date:** 2026-11-16 UTC
**Registration commit:** the commit that adds this file (asserted by `injury-archive/scripts/verify.py`)

## 1. Question

Does an official weekly game-status designation predict whether the player is on that week's
official inactive list? The NFL rulebook and the Competition Committee's published revision define
the labels but publish no percentage. This protocol measures the observed rate and its uncertainty
rather than importing a remembered or third-party percentage.

## 2. Sources (both official, both required per observation)

| Field | Source |
|---|---|
| designation, practice status, injury, club, player | `https://www.nfl.com/injuries/league/{season}/REG{week}` |
| inactive list membership, club, player | `https://www.nfl.com/news/nfl-week-{week}-inactives-players-ruled-out-sunday-{season}-season` |

Each captured page is stored content-addressed under `injury-archive/data/raw/{sha256}.html.gz`
and its retrieval clock time and digest are recorded in `injury-archive/data/index.jsonl`.

## 3. Population

Every row of a captured weekly injury report whose *Game Status* cell is one of `Out`, `Doubtful`,
`Questionable` — the three labels the official page publishes. Rows with a blank game-status cell
are out of scope for this measurement (they are still published on the injury pages) because there
is no designation to calibrate. Every reported exclusion is counted and published beside the rates.

## 4. Join

Within one club and one week:

* normalise the name by lower-casing, removing parenthetical text, removing every non-alphanumeric
  character except spaces, and collapsing whitespace;
* an **exact** normalised match to an inactive list entry is a match;
* if there is no exact match, a match that ignores a trailing generational suffix (`jr`, `sr`,
  `ii`, `iii`, `iv`, `v`) is accepted and labelled `suffix-insensitive`;
* two or more candidate matches are `ambiguous` and are excluded, not resolved by choosing one;
* a designation whose club does not appear in the inactives article is `uncovered` and excluded;
* a designation with no match is `active` — the only reading the two documents support.

The join key is a name and a club. It is not a player ID, and the protocol does not pretend
otherwise: a same-club, same-week duplicate name would be ambiguous and is excluded by the rule
above, and any residual mismatch is a bias towards *active* that the published counts expose.

## 5. Estimator and uncertainty

For each designation `d` over the pooled population:

* `n_inactives` = number of captured inactives articles in the population
* `n` = joined designations for `d`
* `k` = joined designations where the player is on the inactive list
* point estimate `p = k / n`
* 95% interval: Wilson score interval, `z = 1.959964` (two-sided)
* `n` is published beside every value. A cell with `n = 0` is published blank, never as zero.

Secondary cuts, published with the same rule and the same `n`:

* by season;
* by practice status (`Did Not Participate In Practice`, `Limited Participation in Practice`,
  `Full Participation in Practice`);
* by designation rank (`Out` < `Doubtful` < `Questionable`);
* emergency third quarterback entries counted separately, because the article labels them and they
  are inactive by rule rather than by injury.

## 6. Exclusion accounting (fail-closed)

The page publishes, next to every rate: the number of designations with no captured inactives
article, the number that were ambiguous, the number whose club was uncovered, and the number of
captured inactives articles whose own parse recorded a structural failure. A rate is **not
published** for any season × week pair whose two documents did not both parse cleanly.

## 7. Gates (all must pass before any rate is called a finding)

1. `G1` coverage: at least one season × week pair has both documents captured and clean.
2. `G2` accounting: `uncovered + ambiguous + active + inactive == total designations` for every cut.
3. `G3` interval: every published rate carries its Wilson interval and its `n`.
4. `G4` no back-fill: no row enters the population without both official URLs and digests.
5. `G5` stability: the rate is reported per season as well as pooled, and the page says so if the
   per-season intervals do not overlap.
6. `G6` no causal language: the statistic is a conditional rate on published documents, not an
   estimate of a player's probability of playing, which additionally depends on the game-day
   roster and on information the report does not contain.

## 8. What would change our mind (two-sided, frozen)

* **Would confirm** the designation is a usable feature: for each of the three labels the lower
  bound of the pooled Wilson interval separates it from the next label's upper bound, with
  `n >= 100` per label, holding in the per-season cuts.
* **Would falsify** it: overlapping intervals between adjacent labels, or a pooled ordering that
  inverts a per-season ordering, in which case the label is a weak ordinal and may not be used as
  a model feature; it would be replaced by the measured rate itself with its interval.

## 9. What this protocol does not claim

It does not measure snaps, starter status, workload or replacement quality. Being inactive is not
the same as being unavailable for the whole game, and a player who is active may take no snaps.
Those questions need an official snap-count or participation source, which this repository has not
verified (see `readiness.html` row A7).
