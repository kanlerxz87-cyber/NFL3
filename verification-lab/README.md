# Verification lab

An independent, dated re-check of what the published NFL3 site claims.

The rest of this repository builds tables. This workspace asks a narrower and
less comfortable question: **does each published claim still reproduce from the
official page it cites?**

- **Live page:** https://kanlerxz87-cyber.github.io/NFL3/verification-lab/
- **Checked:** 2026-11-12 (UTC), session `arena/0619a74f-nfl3`
- **Scope:** 31 claim-level records, 16 questions (13 blocking), 13 queued proposals

## What it found

| Finding | Detail |
|---|---|
| Stale injury capture | Published: 254 rows, Seattle and Cincinnati "No Injuries Reported". Live report: 279 rows, only the Chargers and Ravens listed with no injuries. No published row names a player absent from the official page, so rows were dropped, not invented. |
| Missing game statuses | Kerby Joseph, Cade Mays and D.J. Reed are published with a blank game-status cell while the official Week 10 article lists all three as **Out**. |
| Colts depth defects | One row merges two players ("Will Mallory Pharaoh Brown"); another duplicates Charvarius Ward under a second spelling. The row total matches only because the two faults cancel. |
| Packers coverage error | Green Bay is published as "no depth table parsed" but does publish a full text table dated Nov 10. |
| Stale depth rows | Baltimore's chart is published with Lamar Jackson first and Tyler Huntley second; both went on injured reserve on Nov 5 and the live chart lists Brissett, Fagnano and Slovis. |
| Confirmed, not changed | Market prices, walk-forward validation, interval reporting and the injury-status definitions all still hold. No market archive exists, so line and correlation cells stay blank. |

## Files

| Path | Purpose |
|---|---|
| `data/recheck.json` | Claim-level register: claim, observed value, status, action, source |
| `data/questions.json` | Questions that must be answered before a decision; the answer column is intentionally blank |
| `data/queue.json` | Ordered proposals with acceptance tests and risks |
| `scripts/build.py` | Renders the five pages; refuses to emit an uncited row |
| `../tests/test_verification_lab.py` | Fail-closed checks |

## Checks

```bash
python3 verification-lab/scripts/build.py
python3 tests/test_verification_lab.py
```

The test file enforces: every table row carries a source link; every claimed
host is registered as trusted; blanks are marked `unverified` instead of being
left as empty cells; `unknown` fields stay empty; every cited verification ID
exists; and no page claims that luck was removed or that a strategy is proven.

These checks are structural. They cannot prove that a source will still show
the same value tomorrow, which is why every record carries the date it was
opened.

## Boundary

This workspace does not edit other sessions' files. Contradictions are reported
with a proposed action so the owner can accept or reject them. A working source
link is evidence for review; it is not reuse permission or betting advice.
