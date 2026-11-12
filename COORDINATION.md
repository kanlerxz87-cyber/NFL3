# Coordination board

Last checked: 2026-11-12 (UTC). At session start this checkout contained only the initial README; no other claims or shared data were present.

## Tasks

| Task | Status | Owner / session | File scope |
|---|---|---|---|
| Final integration: inspect baseline, establish evidence-first NFL research dashboard, document requirements/questions/strategy gates, validate build and links, and publish if repository permissions allow | in progress | `arena/cbdcc317-nfl3` (current Arena session/branch; no separate session ID was supplied) | `COORDINATION.md`, `README.md`, root site pages, `assets/`, `scripts/`, `.github/workflows/`, `.gitignore` |

## Activity and verification log

- 2026-11-12: Initial inspection found only `README.md` (6 bytes) and the initial commit; no NFL datasets, research notes, site files, or prior coordination board. No other active claims were visible.
- Claim recorded before implementation and pushed on the Arena-assigned branch `arena/cbdcc317-nfl3` as commit `1f711a4` (claim only). This session is acting as integration owner because no other tasks/sessions were represented. Work stays on this assigned branch; it cannot switch to a separately named integration branch.
- Implemented a static, responsive dashboard with an executive summary, suggestions/review board, pre-decision question ledger, proposed singles/props/parlay signal designs, injury/depth replacement specification, leaderboard/reward gates, official-source audit, and flagged-review page. No sports-value dataset or model results were added.
- Automated verification: `python3 scripts/check_site.py` passed: 8 HTML pages, local links/assets resolve, and all 85 research-table body rows contain an HTTPS source link on an NFL official domain. External crawling is not part of this offline checker.
- Build verification: `python3 scripts/build_site.py` generated the 8-page publication artifact in ignored `_site/`; `git diff --check` passed. Local HTTP preview started on port 8000.
- Manual official-source route checks via page retrieval on 2026-11-12: [NFL injury reports](https://www.nfl.com/injuries/), [player stats](https://www.nfl.com/stats/player-stats/), [team stats](https://www.nfl.com/stats/team-stats/), [schedules](https://www.nfl.com/schedules/), [standings](https://www.nfl.com/standings/), [team directory](https://www.nfl.com/teams/), [player directory](https://www.nfl.com/players/), [NFL Football Operations](https://operations.nfl.com/), and the [2026 NFL Rulebook](https://operations.nfl.com/rules-officiating/2026-nfl-rulebook). These confirm source routes/page types only; no individual value was treated as verified by the route check.
- Source irregularity: NFL live schedule, injury and stats routes returned 2026-season content on the current date, but no frozen snapshot or second-official-source record was used to independently confirm any row-level values. No such values were copied. A few guessed/legacy NFL pages returned 404 (including legacy analytics/stats paths); they were not used, and working source routes are listed above and in `sources.html`.
- Unresolved and flagged: no authorized odds/history feed; no line, settlement or payout records; no historical depth order / snap-role archive verified; no estimated injury effect or correlation; no model, backtest, skill result or reward/legal review. All remain blank and explicitly flagged.

## Sources, irregularities, publication

- Primary official source routes and their verification boundary: see the source links above and [`sources.html`](sources.html). Every research table row in the site links to a relevant official NFL route; source citation does not validate a proposed signal or unobserved value.
- The site intentionally does not load live values; source snapshots, terms/licensing, data provenance and field-by-field review remain required before any data pipeline or model output is represented as verified.
- Pull request, merge result, GitHub Pages deployment URL and deployment status: pending publication workflow; record here after completion.
