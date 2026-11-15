# Price-data policy — pre-registered before any backtest was published

Registered: 2026-11-15 (UTC). Content hash is written into `data/prices/ledger.json`, so any later edit
shows up as a changed hash in the diff of this commit. This file is a decision, not a finding.

## The source boundary (why we hold what we hold)

* The NFL publishes no odds feed this project may use, and the NFL's own betting FAQ states that odds
  shown on NFL properties are a widget supplied by a partner. Those numbers are not a licensed archive.
  Legitimate historical price archives are licensed commercial products. This project holds none.
* The only price series in this repository is the community `schedules` release (nflverse-data). Its
  digest is verified against the published SHA-256 in `data/raw/manifest.json`. That proves byte
  integrity, **not** official authority, and it does not prove the number is an open or a close.
* Therefore every price on this site is labelled **COMMUNITY**. No price is ever labelled official.

## P01 — Opening and closing are different objects

Opening = the earliest pre-kickoff observation this repository holds for that event x market.
Closing = the latest pre-kickoff observation held before that event's kickoff.
Neither is ever inferred. If we hold no pre-kickoff observation, both stay blank.

## P02 — An after-the-fact number is not an opening, a close, or CLV evidence

An observation recorded after an event's kickoff is stored as `post_hoc`. It may be used as a reference
only. It may never enter an opening-line study, a closing-line-value study or any "we beat the close"
claim. The ledger counts those cells explicitly (`counts.post_hoc_only`).

## P03 — Day-one status, stated plainly

At the first observation (2026-11-15, Weeks 1-9 already played) this repository holds **one** price
observation. Consequences, published rather than hidden:

* the 136-game corpus (Weeks 1-10 including the played Week 10 game) keeps its numbers in `post_hoc`,
  so no backtest may claim an opening-line or CLV edge on it;
* the Week 10 games that had not kicked off at the observation time are the first genuine pre-kickoff
  numbers this repository owns; for them opening = closing until a second capture exists, and the
  ledger says so cell by cell.

## P04 — The capture schedule (the automation that must run)

A scheduled job captures the price source at least: daily during the week, and at T-60 minutes before
each kickoff. Each capture is a new immutable snapshot file. A missed capture is recorded as a gap, not
back-filled. No backtest may be published for a market whose capture coverage is below the pre-registered
gate (see `strategies.html`, gate G05).

## P05 — Vig removal

Two-way markets are de-vigged multiplicatively: `p_fair = p_raw / (p_raw + p_other)`. This is stated so
the residual and correlation work is reproducible. It is an assumption, not a measurement, and it is
applied identically to every price so it cannot favour a strategy.

## P06 — Push and void

Spread and total lines published on the half-point are push-free. Whole-number lines can push. Where a
result lands exactly on the number, the leg is graded as a push and excluded from win/loss scoring; it
still counts toward `n`. Moneyline has no push. This rule is applied mechanically by the grader and is
unit-tested.

## P07 — Settlement source

A bet settles against the official final score. In this workspace the official final score is the
reconciled result feed (`results.html`), which reproduces nfl.com's standing totals exactly for all 32
clubs. The community game log is a cross-check, never the settlement authority.

## P08 — One book, no line shopping, no best-of-multi-book

The price series carries no bookmaker identity, so a backtest may not assume a better number existed.
The grader uses exactly the stored number. If a licensed multi-book feed is later purchased, this policy
is superseded by a new dated policy file, not edited in place.

## P09 — Time zones

Kickoff times come from the schedule release in US Eastern and are converted at a fixed UTC-4 offset.
The boundary error (up to 60 minutes in EST weeks) is published, not corrected silently. It can only
mislabel an observation as pre-kickoff when that observation is within an hour of kickoff.

## P10 — What may never appear on the leaderboard

A backtest number produced under a superseded policy, or from a market without opening/closing
coverage, or from a source other than the settlement authority in P07. Those rows stay blank and are
published on Flagged for Review.
