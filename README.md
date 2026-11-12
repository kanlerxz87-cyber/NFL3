# NFL3 — an evidence-first NFL research desk

A GitHub Pages research workspace that **originates its own NFL lines**, grades them against the
market's closing line, and only calls a strategy good when it survives seven pre-registered validation
gates. Every number on the site is generated from an official, digest-verified data snapshot and every
table row links to its source.

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/

## What makes this different from a picks site

| Principle | How it is enforced |
|---|---|
| No invented numbers | Values that cannot be confirmed from an official source are rendered as `— unverified`, never filled in |
| No cherry-picked backtests | The model is refitted each season on earlier seasons only; every graded game was predicted before its result entered training |
| No luck dressed as skill | Seven gates, including multiple-testing control, a deflated-Sharpe selection threshold, and closing-line value |
| No silent data drift | Each downloaded file is checked against the SHA-256 digest GitHub publishes for that release asset; a mismatch stops the build |
| No unverifiable rows | `tests/check_site.py` fails the build if any data-table row lacks an official source link |

## Headline findings (out of sample)

Computed from 7,103 official regular-season games with lines, 3,287 of them genuinely out of sample.

| Finding | Result |
|---|---|
| Our spread vs final margin (MAE) | **10.17 pts**, versus **9.80 pts** for the closing line |
| Our total vs final total (MAE) | **10.78 pts**, versus **10.43 pts** for the closing line |
| Correlation with the result | our number **0.385**, closing line **0.443** |
| Strategies passing all seven gates | **0 of 9** |
| Best of the family | Elo-gap fade, **+0.005** per unit, z = 0.22 — statistically indistinguishable from zero |
| Home win vs home cover, same game | phi **+0.67** — same-game legs must be priced jointly, not multiplied |
| Offensive starters out vs closing total | r **−0.243** (95% CI −0.297 to −0.188), 1,139 games, 2021–2024 |

**The honest conclusion:** the market's closing number is still better than our model. That is the
correct result to publish, and it is the baseline every future strategy has to beat.

## How the pipeline works

```
pipeline/fetch_official.py   download the official nflverse release assets, verify each SHA-256
engine/stats.py              dependency-free statistics (bootstrap, Wilson, BH, deflated Sharpe)
engine/conventions.py        the ONLY place sign conventions live, with worked examples
engine/features.py           leak-free Elo, rolling form, injury + depth-chart availability
engine/lines.py              walk-forward line origination
engine/studies.py            line study, correlation, pooled injury study, strategy family
engine/gates.py              the seven validation gates
engine/build.py              renders 11 static pages into site/
engine/test_engine.py        self-tests pinning conventions and statistics to known values
tests/check_site.py          every data row must carry an official source link
```

`.github/workflows/data-and-site.yml` runs the whole thing on a schedule and on every push, commits the
refreshed snapshot, and deploys `site/` to GitHub Pages. No manual input is required at any step.

## Data sources

All values come from the official [nflverse-data releases](https://github.com/nflverse/nflverse-data/releases)
(schedules, injuries, depth charts, snap counts, team stats, rosters, players). Field semantics are
taken from the [nflreadr dictionaries](https://nflreadr.nflverse.com/) and spot-checked against the
NFL's own pages: [injury report](https://www.nfl.com/injuries/), [scores](https://www.nfl.com/scores/),
[standings](https://www.nfl.com/standings/).

The full register, including each file's SHA-256 digest and timestamp, is on the site's **Official
sources** page. Everything the desk could not confirm is on **Flagged for review**.

## Local use

```bash
python3 engine/test_engine.py          # engine self-tests
python3 engine/build.py                # rebuild site/ from data/raw/
python3 tests/check_site.py site       # structural + sourcing checks
python3 -m http.server -d site 8000    # view it
```

## Scope and honesty statement

This is a research instrument, not betting advice. It does not claim a profitable strategy, does not
price player props (no verified prop history is in the snapshot), and makes no legal claim about
staking or rewards. Those gaps are listed as open questions with the exact data each one needs.

See `docs/PRE_REGISTRATION.md` for the fixed strategy family and gate definitions, and
`COORDINATION.md` for the parallel-session log.
