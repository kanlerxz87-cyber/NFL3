# Coordination board

| Task | Status | Owner | File scope |
|---|---|---|---|
| Repository review, source research, dashboard and integration | needs review | arena-4fd6bbbb | COORDINATION.md, README.md, site files, tests and Pages workflow |

The Arena-provided branch is fixed as `arena/4fd6bbbb-nfl3`; this session cannot create or switch to a session-named branch. Other sessions should avoid the claimed files and log integration requests here.

## Research and integration log — arena-4fd6bbbb, 2026-11-12 UTC

- Repository review: baseline contained only `README.md`; no existing data or application to verify. No other claims were present when this task was claimed.
- Inspected official [NFL injury report](https://www.nfl.com/injuries/), [NFL statistics](https://www.nfl.com/stats/), [NFL Broncos roster](https://www.nfl.com/teams/denver-broncos/roster), [NWS API documentation](https://www.weather.gov/documentation/services-web-api), [scikit-learn cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html), and [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). Selected injury rows were checked against the report; proposals are explicitly labeled, and unknowns are blank.
- The NFL depth-chart URL `/teams/denver-broncos/depth-chart` returned a 404 page. Roster status is not evidence of replacement order. Current injury report is not a historical point-in-time archive. Data rights, market quotes, lineup histories, automated refresh, correlations, validation results, leaderboard rewards and live models are unverified / not implemented; published on Flagged for Review.
- Static integration: `python3 tests/check_site.py` checks local references and external source links in each data row; it passed. This is not an external link crawler or proof that future source content remains unchanged.
- Status: needs review for the above open research and system gaps; the research dashboard itself is ready for static publication. No claims of complete automated tracking or verified profitable strategies are made.

- Integration PR [#1](https://github.com/kanlerxz87-cyber/NFL3/pull/1) merged as `03e8669d6c9caaa1bb0b5c6e7b785a73a6a07bd7` on 2026-11-12 UTC. [Pages deployment run](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43155632864) succeeded; the published landing page was independently fetched with a cache-busting query. GitHub reported a Node 20 deprecation annotation for its managed Pages build action; deployment succeeded.

## Supplemental research — arena-56e27bb4, 2026-11-12 UTC

| Task | Status | Owner | File scope |
|---|---|---|---|
| Supplemental sourced dashboard | needs review | arena-56e27bb4 | `research-workspace/`, coordination log |

- Both sessions started from the initial commit with no board and independently claimed overlapping integration work. Main advanced while this session worked, producing an add/add conflict on this board. The conflict was resolved by preserving the previously published integration and both logs; this session moved its separate work under `research-workspace/` and left the published root site untouched.
- Integration request to the root-site owner: review and, if appropriate, link the supplemental workspace from root navigation. This session did not change the owner's files.
- Four injury excerpt rows checked against the [NFL report](https://www.nfl.com/injuries/league/2026/REG9); its title says Week 10 while its body says WEEK 9, so that discrepancy is flagged. Also reviewed [club depth-chart caveat](https://static.clubs.nfl.com/image/upload/buccaneers/ohiml2zpdqt07wdkhc7s), [NFL odds FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL), [NFL integrity announcement](https://www.nfl.com/news/nfl-draftkings-fanduel-fanatics-sports-betting-partners), [NIST validation discussion](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=933682), and [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Proposals are not verified outcomes. `python3 research-workspace/scripts/check.py` checks 46 table rows for official source links and local links. External source content was manually reviewed; availability is not continuously monitored. Live feeds, models, correlations, competition and legal/data rights are unverified and flagged.
- Supplemental PR: [#4](https://github.com/kanlerxz87-cyber/NFL3/pull/4). The baseline dashboard was already merged via PR #1; the supplemental PR is separate.
- Supplemental PR [#4](https://github.com/kanlerxz87-cyber/NFL3/pull/4) merged as `8d1926e0723e1440405b908129623b3a814dae29`. [Pages deployment run](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43155889164) succeeded, and the published root and supplemental review page were fetched independently. GitHub's managed Pages action reported a Node 20 deprecation annotation; deployment succeeded.

## Integration follow-up — arena/2836662c-nfl3, 2026-11-12 UTC

| Task | Status | Owner | File scope |
|---|---|---|---|
| Additional evidence-first decision-site pages and validation workflow | needs review | `arena/2836662c-nfl3` | root static site pages/assets, `scripts/validate_site.py`, Pages workflow |

- This session began from the initial commit before other sessions' changes were available locally and initially claimed a broad root-site integration. A subsequent rebase encountered an add/add conflict in the shared coordination file as `main` advanced through other merged sessions. The previous board and logs are preserved; this entry records the overlap, not a request to discard prior work.
- Added supplementary requirements/questions, signal hypotheses, lineup/injury evidence schema, validation gates, prioritized suggestions and extended flagged items. The previously published landing and source register were preserved; a research-deep-dives table links the additions from the overview. Official NFL injury, player-stat, team-stat, team-directory and 2026 rulebook pages were opened on 2026-11-12 UTC. No live values were copied; unknowns remain flagged.
- Verification: `python3 scripts/validate_site.py` passed across 12 HTML pages (local links/assets and citation links); `python3 tests/check_site.py` passed for the existing dashboard; `git diff --check` passed. These checks do not crawl external links or guarantee future source content.
- Unresolved market-feed/rights, historical price, depth-chart, model, correlation, automated ingestion and leaderboard policy gaps remain visible on Flagged for Review. No verified strategy or automated injury pipeline was produced by this session.

## Dashboard — arena/f445c027-nfl3 (session f445c027), 2026-11-12 UTC

| Task | Status | Owner | File scope |
|---|---|---|---|
| T1 Repo review & irregularities | done – needs review (6 flags) | f445c027 | `dashboard/data/repo_review.csv` |
| T2 Injury tracking, Week 10 2026 (official nfl.com) + starter-replacement headlines | done – second line-by-line pass recommended | f445c027 | `dashboard/data/injuries_2026_w10.csv`, `games_2026_w10.csv`, `news_signals_2026_w10.csv` |
| T3 Strategy lab: leaderboard, validation gates, correlation framework | done – 0 validated (no odds/results data) | f445c027 | `dashboard/data/strategies.csv`, `validation_gates.csv`, `correlation_framework.csv` |
| T4 Information gaps (Q&A) and suggestions (decision-only) | done – awaiting owner decisions | f445c027 | `dashboard/data/questions.csv`, `suggestions.csv` |
| T5 Source registry, executive summary, dashboard site | done – build and check pass | f445c027 | `dashboard/` (all of it) |
| T6 Integration: merge to main, Pages deploy | in progress | f445c027 | this log |

**Scope:** everything the dashboard touches is under `dashboard/`. Root files (`index.html`, other root pages, `assets/`, `scripts/validate_site.py`, `tests/`, `research-workspace/`, `.github/workflows/pages.yml`, `README.md`) were **not** edited by this session.

**Integration request to the root-site owner (not actioned here):** add a link to `dashboard/index.html` (live: https://kanlerxz87-cyber.github.io/NFL3/dashboard/) from the root navigation. The dashboard has a "Main NFL3 site" link back to `../index.html`.

**Overlap noted:** this session first merged into `main` after PR #5 and #7 were merged; main's `COORDINATION.md` and `README.md` were kept as published and this section appended. Other sessions' branches (`arena/2836662c-nfl3`, `arena/4fd6bbbb-nfl3`, `arena/56e27bb4-nfl3`, `arena/cbdcc317-nfl3`) were not modified.

**Sources (all fetched 2026-11-12):**
- NFL.com 2026 Week 10 injury report — https://www.nfl.com/injuries/ (254 rows, 14 matchups, 19 headlines)
- NFL.com injury-policy article — https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693
- NFL 2026 schedule announcement — https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced
- Kansspelautoriteit (NL) — https://kansspelautoriteit.nl/
- Secondary, UNVERIFIED: Yahoo Sports (https://sports.yahoo.com/article/nfl-says-worked-ban-more-152200232.html) and LA Mag (https://lamag.com/sports/nfl-gambling-november-13-memo-prop-bets-limit/) reports on an NFL prop-bet memo.
- Excluded (not official): statrankings.com, fsroundup.com, sticktothemodel.com (depth charts).

**Flagged irregularities** (published on the dashboard's Flagged for Review page): R-06 Seattle "No Injuries Reported" vs. headline that Sam Darnold is ruled out; R-07 Garrett/McDuffie listed under Rams; R-10 DEN/CHI/PHI/TB not on the page; R-11 no official depth-chart source; R-12 prop-memo source secondary; R-03/R-04/R-05 branch and board overlap.

### Integration result — f445c027 (2026-11-12 UTC)
- **PR #8** (`arena/f445c027-nfl3` → `main`, dashboard in `dashboard/`) — **merged** as `ca49fad5de3e4b8499854b5ca55fc3a93215f760` (merge commit, not squash). Checks: `validate` (Validate and deploy GitHub Pages) SUCCESS on the PR; after merge, `Validate and deploy GitHub Pages` runs 43156231866 and 43156363844 SUCCESS, and `pages build and deployment` runs 43156231704 and 43156362784 SUCCESS.
- Independent live fetch (2026-11-12): https://kanlerxz87-cyber.github.io/NFL3/dashboard/index.html and /flagged.html returned the generated content.
- **Follow-up fixes (this PR, #9):** R-06 link corrected (was a malformed two-URL string); R-16 claim about Ksa-licensed operators marked UNVERIFIED (not from Ksa's own text); summary card now counts the Flagged for Review rows (it counted only repo flags).
- Root site, root validators, root README and other sessions' pages were not modified.
