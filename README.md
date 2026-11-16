# NFL3 — NFL research, decision and line-origination workspaces

This repository hosts several source-linked NFL research workspaces published with GitHub Pages.
Nothing here is betting advice, a sportsbook, or an approved wagering system.

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/

**Executive summary:** [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md)

## Start here

| Workspace | What it is | Entry point |
|---|---|---|
| **Origination workspace** | Model's fair line vs the market as separate columns for side, total and moneyline; a price-snapshot store with a pre-registered policy; a verified results feed that reproduces nfl.com's standings on 160/160 club × field checks; a proper-score leaderboard with intervals, controls and a demotion gate; official-only correlations with n; the removal-of-luck panel; and an availability graph built from playing time rather than jersey order. | [`origination/index.html`](origination/index.html) |
| **Decision desk (evidence chain)** | Verified game log for 2026 Weeks 1-9 cross-checked against official standings, opponent-adjusted ratings with a measured luck/skill split, measured correlations, a walk-forward skill test, an injury-to-depth-slot join, 24 blocking decisions and 17 reviewable suggestions. | [`decision-desk/index.html`](decision-desk/index.html) |
| **Ops centre** | Consolidated view: injury rows joined to club depth charts into replacement chains, the merged questions register, the suggestions review surface, the strategy leaderboard and gates, sources and flags. Every row carries an official link; blanks stay blank. | [`ops-center/index.html`](ops-center/index.html) |
| **Canonical decision lab** | Official-source decision dashboard: requirements, questions, suggestions, line-origination protocol, injury/depth snapshots, fail-closed validation gates, flagged review and independent audit. Unknown values stay blank. | [`decision-lab/index.html`](decision-lab/index.html) |
| **Verification log** | Independent hand-checked transcription with counted exceptions: every value either matches, or is explicitly counted as unverified. | [`decision-lab/verification.html`](decision-lab/verification.html) |
| **Verification & integrity (automated)** | Automated re-fetch that compares each published field with the live official source; drift and unreachable sources are reported, never counted as passes. | [`decision-lab/integrity.html`](decision-lab/integrity.html) |
| **Availability & replacements** | Which published starters are on the official report, who the club lists next, and where the data cannot answer the question (185 of 254 report rows joined; 69 unmatched, each with a reason). | [`decision-lab/availability.html`](decision-lab/availability.html) |
| **Decision paths** | Three routes (foundation, gated research, market-facing) compared on prerequisites, cost, benefit and risk, with the options register to record a choice. | [`decision-lab/decisions.html`](decision-lab/decisions.html) |
| **Verification lab** | Independent re-check queue and register: every published value re-fetched field by field, with drift and unreachable sources reported rather than hidden. | [`verification-lab/index.html`](verification-lab/index.html) |
| **Independent injury verification** | Line-by-line re-verification of the Week 10 injury extract against the live official report (279 live rows; 254/254 extraction agreement; every difference accounted for). | [`injury-verification/index.html`](injury-verification/index.html) |
| **Offline source-authority audit** | Independent offline audit of source-authority gates: host-registry checks, self-authorization and HTTP-host reproductions, with regression tests. | [`verification/index.html`](verification/index.html) |
| **Skill lab** | Pre-registered proper-score evaluation of our own line against the market's own de-vigged price: Brier and log-loss skill, a 10,000-resample game-cluster interval, Benjamini–Hochberg multiplicity control, four control baselines (random pick, favourites only, base rate, market), and a retrospective staking table that cannot promote a row. | [`skill-lab/index.html`](skill-lab/index.html) |
| **Availability ledger** | Official reserve-list and league-trade captures with source URL, retrieval time and SHA-256, joined to the committed club depth capture: stale depth rows flagged, same-day rows left unresolved, and reserve-listed players the weekly report never lists. | [`availability-ledger/index.html`](availability-ledger/index.html) |
| Overview | Root landing page and links to preserved concurrent workspaces | [`index.html`](index.html) |
| **Week 11 venue register** | The 13 Week 11 fixtures, each venue read from its official NFL game-centre "Game Info" block, kickoff and network matched to the official schedule page, the dated league announcement beside them, and flagged items on a Flagged for Review page. Built and fail-closed verified by `venues/scripts/`. | [`venues/index.html`](venues/index.html) · [`venues/flagged.html`](venues/flagged.html) |
| **Decision readiness** | Requirements register (one row per requirement): state, the gate that blocks it and the number that would clear it, built by `readiness/build_readiness.py` (PR #67). | [`readiness.html`](readiness.html) |
| **Pricing & price store** | Adopted price-data policy (fail-closed), price-snapshot schema and empty append-only store, residual table (our fair line / market line / difference), capture schedule and publication gates. | [`pricing.html`](pricing.html) |
| **Pre-registered backtest corpus** | The verified 136-game log (Weeks 1–9 2026) frozen with hashes, a pre-registered train/validation/holdout split, and the evaluation gates that keep backtest numbers off the leaderboard. | [`corpus.html`](corpus.html) |
| **Repo review** | Irregularities found line by line in this pass (live vs committed data, depth parsing, pre-registration history, venue sourcing, verification record, duplicate pages), with evidence and action. | [`repo-review.html`](repo-review.html) |
| **Verified results feed** | All 136 Week 1–9 finals verified against the official NFL.com score pages (136/136 scores and dates), frozen as the pre-registered backtest corpus; plus the injury-hub delta between dated observations (the change, never the level). | [`results-verification/index.html`](results-verification/index.html) · [`delta.html`](results-verification/delta.html) |
| Research desk | Exploratory community-data line/strategy engine using nflverse GitHub assets. Digest integrity is verified, but NFL official authority is **not** established; do not treat its results as official-only validation. | [`research-desk/index.html`](research-desk/index.html) |
| Line lab | Model-implied estimates and statistical research from official standings snapshots; not sportsbook lines or validated betting results | [`line-lab/index.html`](line-lab/index.html) |
| **Shadow board (pre-registered)** | Singles-only shadow baseline registered in `shadow-board/PREREGISTRATION.md` before any artifact: one frozen model on the official 2026 log, originated side/total/moneyline probabilities for the whole Week 11 slate, proper scores with control baselines, game-cluster bounds, BH correction and a removal-of-luck panel. Leaderboard shows only the prospective window; market and ROI columns are blank because `pricing/PRICE_DATA_POLICY.md` forbids any price-dependent number until a source carries a named licence and both timestamps, and its register grants nothing yet. Each forecast is pinned to the SHA-256 of the game log the file was issued against, matched against `corpus/manifest.json`. Gate: `python3 shadow-board/scripts/check.py`. | [`shadow-board/index.html`](shadow-board/index.html) |
| Dashboard | Weekly injury, game, starter and strategy tables with row-level citations | [`dashboard/index.html`](dashboard/index.html) |
| Decision hub | Requirements, origination, depth/injury, questions and suggestions | [`decision-hub/index.html`](decision-hub/index.html) |
| Research workspace | Supplemental sourced research pages | [`research-workspace/index.html`](research-workspace/index.html) |

## Source-authority boundary

- Official NFL/club pages establish published facts for review. A capture hash proves byte integrity, not reuse rights or future stability.
- nflverse/nflreadr GitHub assets are community-maintained. They may be useful for exploration, but this review does not establish them as official NFL data. The canonical decision lab excludes them from official-only gates and flags the mislabeling found in the research desk.
- No licensed historical odds/prop archive, confirmed replacement workload, empirical correlation, validated strategy edge or reward funding is verified. Those cells remain blank and are published on Flagged for Review.

## Canonical decision lab checks

```bash
python3 tests/test_decision_lab.py          # 37 offline unit tests (synthetic fixtures only)
python3 decision-lab/scripts/availability.py # injury -> club depth join; regenerated artifact is committed
python3 decision-lab/scripts/verify_live.py --offline   # structural families, no network
python3 decision-lab/scripts/verify_live.py             # live field-by-field re-fetch (needs egress)
python3 decision-lab/scripts/build.py
python3 decision-lab/scripts/audit.py
```

`availability.py` writes `decision-lab/data/availability.json`; `verify_live.py` writes
`decision-lab/data/verification.json`. Both are committed, and the build reproduces both pages from them,
so a reviewer can diff the numbers. CI re-runs the availability artifact and the offline verification on
every pull request, and runs the live verification (with an uploaded artifact) on every deployment.

The lab captures official NFL injury reports and club depth pages, preserves blank cells, and builds static tables with an official source link on every row. `validation.py` implements ten fail-closed gates; its unit tests use synthetic fixtures only and are not NFL performance evidence.

## Automation

- `.github/workflows/decision-lab.yml` runs lab tests/build/audit on pull requests and can capture fresh official sources on manual dispatch.
- `.github/workflows/pages.yml` validates the site, refreshes official decision-lab captures for deployment, builds the lab, audits it, and publishes GitHub Pages.
- `.github/workflows/data-and-site.yml` is the preserved community-data research-desk pipeline. Its outputs are exploratory and flagged, not official-only decision evidence.

## Ops centre

Joins the official NFL injury report to official club depth charts and publishes the result as
replacement chains: for every listed player, the string his club publishes behind him, whether that
next man is himself on the report, and — where the answer does not exist — an explicit blank.

It also merges the questions, suggestions, strategy, gate and flag registers that four separate
workspaces had each built into one register apiece, keeping the provenance of every merged entry.

```bash
python3 ops-center/scripts/build.py    # regenerate pages from the committed snapshot
python3 ops-center/scripts/verify.py   # strict gate
```

The gate fails the build if any table row lacks an official source link, if a local link is broken,
if a placeholder leaks into a cell, if a blank is rendered as though it were a value, or if two
consecutive builds differ. It reports rows with a source link and warns on community or secondary
sources so they are never mistaken for official ones.

## Repository checks

```bash
python3 scripts/validate_site.py
python3 tests/check_site.py
python3 ops-center/scripts/verify.py
python3 decision-lab/scripts/audit.py
```

See `COORDINATION.md` for parallel-session claims, conflict logs, verification records and publication results.
