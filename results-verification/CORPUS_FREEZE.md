# Pre-registered backtest corpus freeze — 2026 Week 1–9 finals

Frozen before any evaluation. No backtest, walk-forward, ROI, CLV or skill statistic has been
computed against this corpus in this repository (the decision-readiness register records 0
validated strategies). The commit that introduces this file **is** the registration; its hash is
recorded on the results-verification page and in `readiness/build_readiness.py` after the freeze.

## What is frozen

| File | Rows | sha256 |
|---|---|---|
| `results-verification/data/backtest_corpus_w1_w9.csv` | 136 | `a1633c2011bc8fb4c6508ada2ed1cd32ddede8993300b5e03ef157f762ee73b1` |
| `results-verification/data/official_scores_2026/week_01..09.json` (bundle, ordered sha256) | 136 | `59ae6520a71e9021dd97945ab7f5ab4182de4824186222833b4c002ddc05fc18` |
| `results-verification/data/verification_report.json` | 136 | `95f2397ea2c6f2ce417e8946a68d904827c74e91cea604719a22fa9edc2b2ec2` |

## Provenance

- Values: `data/raw/games.csv` (community nflverse file; digest-verified in `data/raw/manifest.json`; **not** official).
- Verification: every one of the 136 final scores and game dates was read from the official
  NFL.com score pages `https://www.nfl.com/scores/2026/week-1` … `week-9` on 2026-11-15 UTC
  (observed window 12:59:59Z–13:46:00Z) and agrees with the community file: 136/136 scores,
  136/136 dates, 0 mismatches, 0 unmatched rows. Per-game rows with the official link are in
  `results-verification/data/verification_report.json`.
- One documented normalization: the official pages render Arizona's club code as `AZ` and the
  community file uses `ARI`; the join maps `AZ→ARI` and no other club needed a mapping.

## Rules of the freeze (fixed now)

1. The corpus is the 136 games above, exactly as committed. Any change — a score correction, an
   added column, a re-verification that alters a value — must be a **new** commit with a **new**
   hash, noted here, and invalidates any evaluation keyed to the earlier hash.
2. Any strategy or model evaluated on this corpus must have its rule text committed before the
   evaluation window is opened (see `docs/PRE_REGISTRATION.md` for the standing convention).
3. Price data is still missing (readiness register P1/P7): no ROI, CLV or staking result can be
   computed on this corpus, and none may be published until the price-data policy exists.
4. Backtest numbers from this corpus never appear on any leaderboard; leaderboards rank only
   prospectively graded, registered strategies.
