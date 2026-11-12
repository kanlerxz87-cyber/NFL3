# Coordination board

| Task | Status | Owner | Files | Notes |
|---|---|---|---|---|
| Repository review, source research, dashboard and integration | needs review | arena-4fd6bbbb | site files, tests, Pages workflow | Prior completed session's work was merged into `main` during this session; preserve all its pages, sources, and tests. |
| Evidence-first strategy framework and decision review | needs review | c56ed83b-nfl3 | COORDINATION.md, README.md, index.html, `.github/workflows/pages.yml` | This session's proposed one-page work was superseded by the more complete multi-page site already merged to `main`; its distinct proposed methodology has not been fully integrated. |

The Arena-provided branch is fixed; the session cannot switch to the requested `session-<id>` branch. Current branch `arena/c56ed83b-nfl3` is retained. Changes belonging to the other session were preserved during conflict resolution.

## Research / verification recorded by prior integration session

- Baseline before project work contained only `README.md`; no prior dataset or application existed.
- Official sources checked by the prior session: [NFL injury report](https://www.nfl.com/injuries/), [NFL stats](https://www.nfl.com/stats/), [NFL Broncos roster](https://www.nfl.com/teams/denver-broncos/roster), [NWS API documentation](https://www.weather.gov/documentation/services-web-api), [scikit-learn cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html), [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). NFL depth-chart URL tested by that session returned 404; roster membership is not proof of replacement order.
- `tests/check_site.py` in merged main validates local references and that each data row has a source link; prior session reported it passed. This is not proof that dynamic source content remains correct.
- Unverified / not implemented: historical point-in-time injury archive, odds and settlement history, data rights, automated refresh, lineup history, model/correlations, validation results, leaderboard rewards, and live betting lines.

## Current session evidence and irregularities

- Inspected live [NFL injury reports](https://www.nfl.com/injuries/). The returned snapshot identified a 2026 Week 10 slate and contained apparent roster/schedule inconsistencies. No injury values were ingested; retain as a review flag until checked against dated primary reports.
- No historical odds/results or model data was present in this branch at session start; no numeric edge, correlation, player-specific status, or profitability is claimed.
- The GitHub Pages workflow added in this session remains in this branch, but the older site's existing tests/workflow require integration review. GitHub PR #2 encountered merge conflicts because PR #1 had already added a multi-page site on `main`; merging `origin/main` into this branch exposed conflicts in `index.html`, `README.md`, and this file. Resolved while preserving the merged main site pages and assets. The PR has not yet been merged; no deployment is asserted.

## Source policy

Prefer primary official sources, timestamp every factual record, and preserve source history. Leave unsupported values blank and flag them for review. Statistical model estimates are not facts; require reproducible data and held-out testing.
