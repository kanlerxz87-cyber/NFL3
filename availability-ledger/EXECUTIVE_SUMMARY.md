# Availability ledger — executive summary

**Written:** 2026-11-15 UTC
**Captures:** 3 official NFL transaction files, each with source URL, retrieval time and SHA-256
**Artifact:** `availability-ledger/data/ledger.json` · **Pages:** `availability-ledger/index.html`

---

## The one-paragraph version

The weekly injury report is not an availability register. It lists the players who are on it, and
a player who has been placed on the reserve list can be unavailable without appearing on the
report at all. "Not listed" read as "available" is a silent, repeated error, and it is the single
most expensive way to be wrong about a lineup. This ledger captures the league's own reserve list
and trade log, joins them to the published club depth charts, and publishes the three things that
usually get missed: depth rows that a later roster event has already invalidated, rows whose
ordering cannot be established, and reserve-listed players who never appear on the weekly report
at all.

## What was captured

| Capture | Source | Rows | Window |
|---|---|---|---|
| Reserve list, November 2026 | [nfl.com/transactions/league/reserve-list/2026/11](https://www.nfl.com/transactions/league/reserve-list/2026/11) | 25 | 11/07 – 11/14 |
| Reserve list, October 2026 | [nfl.com/transactions/league/reserve-list/2026/10](https://www.nfl.com/transactions/league/reserve-list/2026/10) | 25 | 10/24 – 10/31 |
| League trades, November 2026 | [nfl.com/transactions/](https://www.nfl.com/transactions/) | 12 | 11/06 – 11/10 |

Every capture file is stored in this repository with its source URL, the UTC time it was read, the
scope it covers, and the SHA-256 of the file. The digests are re-checked on every build, so a
capture that is edited cannot quietly change a published conclusion.

## What the join found

- **9 stale depth rows.** A club depth chart captured on 2026-11-12 still names a player the
  league had already placed on the reserve list — Terry McLaurin (Commanders, 10/28), Jordan
  Whittington (Rams, 11/10), Gracen Halton (49ers, 11/10), Demond Claiborne (Vikings, 11/09),
  Eyioma Uwazurike (Broncos, 11/07) and Dyami Brown (Commanders, 11/07). A depth chart that still
  shows an unavailable player makes the next man look like a starter.
- **1 unresolved row.** Puka Nacua was placed on the reserve list on 11/12, the same calendar day
  as the depth capture. The order of the two events is not published, so the row is published as
  unresolved — not as stale, and not as fresh.
- **12 control cases.** Every one of the twelve traded players is correctly absent from the depth
  chart of the club they left. This is the control that shows the test is not simply flagging
  every trade.
- **40 of 50 reserve-listed players do not appear on the weekly report.** Their unavailability is
  established by the reserve list. The report alone cannot clear them.

## The one case left unresolved, on purpose

The Baltimore quarter-back depth row is published as **unresolved**, not as confirmed stale. The
captured Ravens chart lists three quarterbacks; the official trade log records a replacement
quarterback acquired on 11/06; and the reserve-list captures in this workspace cover 26 September
to 14 November 2026 only, so the reserve date of either listed quarterback is not established
here. Asserting "stale" would go beyond the evidence. The row says what the evidence says and
names the capture that would settle it.

## Why the pages are shaped this way

- The **ledger** is the raw official record, one row per published transaction.
- The **availability** page joins the reserve list to the weekly report, so the gap between "on
  the reserve list" and "on the report" is visible rather than assumed.
- The **depth flags** page publishes the stale and unresolved rows with both published facts side
  by side: the club's own depth row, and the league's own transaction.
- The **weekly diff** page publishes the change between the dated depth capture and the dated
  roster events, because a static snapshot is not a diff. Where a second dated capture of the same
  page does not exist, the column stays empty with the reason; it never reads as "nothing
  changed".
- The **flagged** page names the gaps this ledger does not close.

## The gaps, stated plainly

1. The league's monthly reserve-list page shows only part of each month. A player absent from a
   capture is therefore **not** evidence of being available. Until the capture runs daily, the
   ledger is a floor and not a complete register.
2. Two clubs (Packers, Texans) have no captured depth chart at all, so their players cannot be
   flagged against the reserve list.
3. The depth capture is a point-in-time read of a mutable page; the ledger joins against that read,
   and the read itself is dated and hashed.

## Reproduce it

```
python3 availability-ledger/scripts/build.py      # rebuild the ledger and the pages
python3 availability-ledger/scripts/verify.py      # fail-closed checks on the captures and pages
python3 tests/test_availability_ledger.py          # regression tests (digests, joins, pages)
```
