# NFL3 — NFL research, decision and line-origination workspaces

This repository hosts several independent, source-linked NFL research workspaces, published as a GitHub
Pages site. Each one was built by a separate session and each keeps its own scope, checks and data
origins. Nothing here is betting advice.

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/

## Start here

| Workspace | What it is | Entry point |
|---|---|---|
| **Research desk** | The evidence-first line-origination and validation desk: an original-line engine graded out of sample against the closing market, seven pre-registered validation gates, a measured correlation matrix, and a pooled 2021-2024 injury/backup study. Every value comes from a digest-verified official snapshot. | [`research-desk/index.html`](research-desk/index.html) |
| Overview | The root landing page and the decision-first brief | [`index.html`](index.html) |
| Line lab | Model-implied estimates and statistical research | [`line-lab/index.html`](line-lab/index.html) |
| Dashboard | Weekly injury, game, starter and strategy tables with row-level citations | [`dashboard/index.html`](dashboard/index.html) |
| Decision hub | Requirements, origination, depth/injury, questions and suggestions | [`decision-hub/index.html`](decision-hub/index.html) |
| Research workspace | Supplemental sourced research pages | [`research-workspace/index.html`](research-workspace/index.html) |

## The research desk, in one paragraph

The desk originates its own NFL numbers rather than quoting anyone else's. A walk-forward model — Elo,
prior-six-game form and rest, fitted only on seasons *before* the one it predicts — produces an
independent spread and total for every game. Those numbers are then graded against the market's closing
line across **3,287 out-of-sample games**. The answer is published even though it is unflattering: the
closing line is **still better** than the model (spread MAE 9.80 vs 10.17 points). Nine pre-registered
strategies were tested; **none passes all seven validation gates**. That result is the product, because a
leaderboard that cannot reject its own strategies cannot be trusted when it endorses one.

## What makes the research desk different

| Principle | How it is enforced |
|---|---|
| No invented numbers | Anything not confirmable from an official source is rendered `— unverified` |
| No cherry-picked backtests | Each season is predicted before its result enters training |
| No luck dressed as skill | Seven gates including Benjamini-Hochberg control, a deflated-Sharpe selection threshold and closing-line value |
| No silent data drift | Every file is checked against the SHA-256 digest GitHub publishes for that release asset; a mismatch stops the build |
| No unverifiable rows | The build fails if any data-table row lacks an official source link |

## Running the research desk

```bash
python3 engine/test_engine.py          # 40 self-tests pinning sign conventions and statistics
python3 pipeline/fetch_official.py     # download + digest-verify the official snapshot (needs network)
python3 engine/build.py                # rebuild research-desk/ from data/raw/
python3 tests/check_site.py research-desk
```

`.github/workflows/data-and-site.yml` runs the whole chain on a schedule, commits the refreshed
snapshot and deploys. No manual input is needed.

## Repository checks

```bash
python3 scripts/validate_site.py       # every HTML page: local links, assets, table citations
python3 tests/check_site.py research-desk
```

## Data sources

Official [nflverse-data releases](https://github.com/nflverse/nflverse-data/releases) (schedules,
injuries, depth charts, snap counts, team stats, rosters, players), with field semantics from the
[nflreadr dictionaries](https://nflreadr.nflverse.com/) and spot checks against the NFL's own
[injury report](https://www.nfl.com/injuries/), [scores](https://www.nfl.com/scores/) and
[standings](https://www.nfl.com/standings/). The full register, with a digest and timestamp per file, is
on the research desk's **Official sources** page; everything unconfirmed is on **Flagged for review**.

## Scope and honesty statement

Research instrument, not betting advice. No workspace claims a profitable strategy, prices player props
(no verified prop history is in any snapshot) or makes a legal claim about staking or rewards. Open gaps
are listed as questions with the exact data each one needs. See `docs/PRE_REGISTRATION.md` for the fixed
strategy family and gate definitions, and `COORDINATION.md` for the parallel-session log.
