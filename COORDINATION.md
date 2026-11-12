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
- Final integration follow-up: added root Overview links to both `dashboard/` and `line-lab/`. `node dashboard/scripts/check.mjs` passed (254 injury rows, 14 games, 19 headlines; rows sourced or flagged); `python3 line-lab/scripts/verify.py` passed (13 checks, 17 pages); root validation scripts also passed. Both nested dashboards explicitly label unverified items and avoid claiming validated betting performance. External content is not continuously crawled.
- Final navigation PR [#15](https://github.com/kanlerxz87-cyber/NFL3/pull/15) merged as `d5ae1b09ff1a41d86a04cee5537f4babfb1b7ee6`. Its first Pages run was cancelled by a newer concurrent main push; the subsequent full validation/deploy [run 43157000573](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43157000573) succeeded on the combined main commit. GitHub Pages was independently fetched and showed both `dashboard/` and `line-lab/` links.

## Dashboard — arena/f445c027-nfl3 (session f445c027), 2026-11-12 UTC

| Task | Status | Owner | File scope |
|---|---|---|---|
| T1 Repo review & irregularities | done – needs review (6 flags) | f445c027 | `dashboard/data/repo_review.csv` |
| T2 Injury tracking, Week 10 2026 (official nfl.com) + starter-replacement headlines | done – second line-by-line pass recommended | f445c027 | `dashboard/data/injuries_2026_w10.csv`, `games_2026_w10.csv`, `news_signals_2026_w10.csv` |
| T3 Strategy lab: leaderboard, validation gates, correlation framework | done – 0 validated (no odds/results data) | f445c027 | `dashboard/data/strategies.csv`, `validation_gates.csv`, `correlation_framework.csv` |
| T4 Information gaps (Q&A) and suggestions (decision-only) | done – awaiting owner decisions | f445c027 | `dashboard/data/questions.csv`, `suggestions.csv` |
| T5 Source registry, executive summary, dashboard site | done – build and check pass | f445c027 | `dashboard/` (all of it) |
| T6 Integration: merge to main, Pages deploy | done – root link, checks, Pages deploy verified | f445c027 + integration | `index.html`, this log |

**Scope:** everything the dashboard touches is under `dashboard/`. Root files (`index.html`, other root pages, `assets/`, `scripts/validate_site.py`, `tests/`, `research-workspace/`, `.github/workflows/pages.yml`, `README.md`) were **not** edited by this session.

**Integration request (addressed in the final root-site integration):** the root Overview's "Research deep dives" table links to `dashboard/index.html` (https://kanlerxz87-cyber.github.io/NFL3/dashboard/), with an official NFL injury-report source link. The dashboard has a "Main NFL3 site" link back to `../index.html`.

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
- **Follow-up fixes (PR #10):** R-06 link corrected (was a malformed two-URL string); R-16 claim about Ksa-licensed operators marked UNVERIFIED (not from Ksa's own text); summary card now counts the Flagged for Review rows (it counted only repo flags).
- Root site, root validators, root README and other sessions' pages were not modified.
## Merge record — arena/2836662c-nfl3, 2026-11-12 UTC

- Integration PR [#7](https://github.com/kanlerxz87-cyber/NFL3/pull/7) merged as `994ceca09f9554ca14d2559bfd9bc23f7e6ebb0d`. Validation and GitHub Pages deployment [run 43156231866](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43156231866) succeeded. GitHub Pages status is `built`: https://kanlerxz87-cyber.github.io/NFL3/.
- Deployment logs carried non-blocking notices for `actions/checkout@v4` targeting Node.js 20 and an upcoming `ubuntu-latest` image migration. The build and deploy completed successfully.


## line-lab — arena/e5e2b753-nfl3 (session e5e2b753), 2026-11-12 UTC

| Task | Status | Owner | File scope |
|---|---|---|---|
| T01 Coordination claim + repo scaffolding | done | `arena/e5e2b753` | this log |
| T02 Verified source registry (13 official sources) | done | `arena/e5e2b753` | `line-lab/data/sources.json` |
| T03 Verified 2026 league data (32 clubs) | done | `arena/e5e2b753` | `line-lab/data/standings_2026.json` |
| T04 Verified rules layer (injury report, roster) | done | `arena/e5e2b753` | `line-lab/data/rules.json` |
| T05 Injury extract + availability/depth-stress model | done | `arena/e5e2b753` | `line-lab/data/injuries.json` |
| T06 Decision register (25 questions with closure routes) | done | `arena/e5e2b753` | `line-lab/data/questions.json` |
| T07 Suggestions register (18, scored, review protocol) | done | `arena/e5e2b753` | `line-lab/data/suggestions.json` |
| T08 Line-origination engine + luck decomposition | done | `arena/e5e2b753` | `line-lab/scripts/model_ratings.py`, `line-lab/data/model_outputs.json` |
| T09 Validation gates + leaderboard + gate mathematics | done | `arena/e5e2b753` | `line-lab/data/gates.json`, `line-lab/data/strategies.json`, `line-lab/data/strategy_math.json` |
| T10 Static sub-site (18 pages) | done | `arena/e5e2b753` | `line-lab/index.html`, `line-lab/pages/`, `line-lab/assets/` |
| T11 Build gate | done | `arena/e5e2b753` | `line-lab/scripts/verify.py` |
| T12 Executive summary | done | `arena/e5e2b753` | `line-lab/EXECUTIVE_SUMMARY.md` |
| T13 Integration + Pages verification | in progress | `arena/e5e2b753` | this log |

**Scope.** Everything this session produced is under `line-lab/`. Root files (`index.html`, the other root pages,
`assets/`, `scripts/`, `tests/`, `README.md`, `.github/workflows/`), plus `dashboard/` and `research-workspace/`,
were **not** edited. The site links back to the root site from its footer.

**Overlap, recorded rather than hidden.** This session began from the initial commit when `main` contained only
`README.md`, claimed T01–T13 and pushed that claim (commit `aeab37c`) before doing any work. `main` then advanced
through PRs #1, #4, #7 and #8, by which point three other sites existed. The first push attempt produced an
add/add conflict on this file during `git pull --rebase`; the rebase was **aborted** rather than forced, the
published board was left intact, and this session relocated its entire output into `line-lab/` before committing
again. Nothing from any other session was discarded or overwritten.

**What this build adds that the existing sites do not.** A reproducible quantitative layer: a fitted Pythagorean
exponent, a luck decomposition with its residual's limits stated, correlations with n and p, and the arithmetic of
the validation gates (required sample size, deflated Sharpe, Bonferroni thresholds, Gaussian-copula parlay
pricing, Kelly, Wilson intervals). Also a 25-item decision register where every open question names the cheapest
action that closes it, and a build gate that fails on a sourceless row, a broken anchor, a cell-count mismatch or
an internal arithmetic contradiction.

**Where the existing sites are ahead of this one.** `dashboard/data/injuries_2026_w10.csv` carries 254 injury rows
across 14 matchups; this session's extract covers 108 rows over 10 complete club reports (BUF partial, NYJ
missing, both flagged as F-03). For full-slate availability the dashboard extract should be preferred. Two findings
independently corroborate: the dashboard's R-11 ("no official depth-chart source") matches this session's F-08, and
the dashboard's note that `/teams/denver-broncos/depth-chart` returned 404 matches this session's conclusion that
the official roster feed carries no depth order (R14).

**Correction to a common claim, found while verifying.** The NFL does not publish its own lines, but odds *are*
visible on NFL surfaces: NFL Support (S13) states the widgets show odds "provided by official bookmaker partners of
the NFL (FanDuel, Caesars, and DraftKings)" with bets placed through a redirect. Earlier sessions correctly flagged
the rights/feed gap; this session narrows the claim to "no NFL-authored, historical, machine-readable line archive".

**Integration request (addressed by the final root-site integration):** the root Overview's "Research deep dives" table links to `line-lab/index.html` (https://kanlerxz87-cyber.github.io/NFL3/line-lab/), with an official NFL standings source link. The destination labels its figures as model-implied, not market lines.

**Sources (all fetched 2026-11-12):** `nfl.com/standings/`, `nfl.com/injuries/`, `nfl.com/schedules/2026/REG/`,
`nfl.com/teams/washington-commanders/roster`, `nfl.com/teams/washington-commanders/`,
`nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693`,
`nfl.com/news/players-now-eligible-to-return-from-injured-reserve-after-four-games`,
`operations.nfl.com/rules-officiating/2026-nfl-rulebook`, `support.nfl.com/.../If-I-place-a-bet-on-NFL-com...`,
and two probes recorded as broken (`nfl.com/odds/` 404, two guessed `operations.nfl.com` paths 404). One secondary
source (AP, practice-squad size 17 vs NFL.com's 16) is registered as non-official and unresolved — F-02.

**Verification performed.** `cd line-lab && python3 scripts/verify.py` → **PASS**, 13 checks, 0 warnings,
0 failures, 18 pages scanned. The gate checks: every data table exposes a source column and every table declares
its source class; every internal link and anchor resolves (including the link out to the root site); every table
row matches its header width; no duplicate ids; no placeholder/null leakage; standings arithmetic (W+L+T =
home+road, PF−PA = published NET, division ⊆ conference, conference + other = total) for all 32 clubs; every
injury row carries an official player link and a legal status value; every verified rule cites a source and every
unverified rule is blank; neutral-site games do not vary with home-field advantage; no strategy claims a passed
gate; all flag/question/suggestion/strategy/gate/source cross-references resolve. It does **not** crawl external
links — external content was read once, by hand, at fetch time.

**Flagged irregularities:** F-01 unequal games played; F-02 roster sizes and status deadline unconfirmed;
F-03 most game statuses unset on Thursday + BUF/NYJ coverage; F-04 no NFL-authored odds archive; F-05 half the
Week 10 slate uncaptured; F-06 no player-usage source; F-07 legal status of rewards unverified; F-08 no depth
order; F-09 no leg-level outcome data; F-10 'Questionable' calibration unmeasured. All published with sources on
`line-lab/pages/flagged.html`.

**Publication record.**

- Integration PR [#11](https://github.com/kanlerxz87-cyber/NFL3/pull/11) merged as `94b0518e1d2a98f5d44e7615fbd3d08f2b6cc63c` on 2026-11-12 04:43 UTC. The `validate` job passed; `deploy` is skipped on pull requests by design.
- Pages deployment for `main` completed successfully (`Validate and deploy GitHub Pages`, conclusion `success`), and the published page was independently fetched at
  https://kanlerxz87-cyber.github.io/NFL3/line-lab/ — the dashboard rendered with its data intact.
- Follow-up fixes after reading the live page (second PR): the source counter said "9 resolving · 3 broken" for 13 sources and silently dropped one; an already-answered P0 question was listed under "Hard blockers"; and the highest-priority action (SG-01, buy an odds archive) ranked **last** on the suggestion table because the ratio score does not encode sequencing. All three are corrected — the counter now reads 9 / 3 / 1, blockers are filtered to open items, and SG-01 and SG-02 are flagged and surfaced as a critical path panel.
- Follow-up PR [#14](https://github.com/kanlerxz87-cyber/NFL3/pull/14) merged as `ef7ae0e3101bac20ead7ccfe440b8de7f503d1a1`; Pages deploy succeeded for that commit and the live page was re-fetched with a cache-busting query, confirming the corrected counter (9 resolving / 3 broken / 1 not fetched), seven open blockers, and the critical-path panel. The first fetch after deploy returned the **cached** pre-fix page — worth remembering when verifying Pages output.
- Third pass, also from reading the live site: three arithmetic inconsistencies in this session's own prose. G2's note claimed a required t of 3.31 at 100 trials where the computed table says 3.48; G5's note claimed an observed Sharpe of 0.08 could pass with fewer than 200 trials when at n=500 it cannot (DSR 0.897 at one trial); and the deflated-Sharpe grid was set so thinly that every cell read "fail", making the gate look unpassable rather than demanding. The grid now spans Sharpe 0.05/0.10/0.20 so the bar is visible (≈0.10 at one trial, ≈0.18 at fifty), and both notes are corrected to match the computation.
- Live verification after the follow-up merge is recorded in the section below.

### Final result — f445c027 (recorded 2026-11-12 UTC)
- **PR #10** (follow-up fixes) — **merged** as `1b713ce76866ca5e4eaffeb43d3d764c6fdfa75d` (merge commit). Its first Pages run was cancelled by a newer `main` push (PR #11, another session); the run on the following commit `94b0518` completed **success** (`pages build and deployment` 43156630277; `Validate and deploy GitHub Pages` 43156630287).
- **Live verification (fetched 2026-11-12):** https://kanlerxz87-cyber.github.io/NFL3/dashboard/ shows R-06 corrected, R-16 marked UNVERIFIED, and the Flagged count (27).
- **Dashboard status:** 10 pages, 254 injury rows, 14 games, 19 headlines, 0 of 12 strategies validated, 13 proposals awaiting decision, 27 flagged items. Checks: `dashboard/scripts/check.mjs` OK; root `tests/check_site.py` and `scripts/validate_site.py` OK.
- **Still open (for owner review):** second line-by-line pass on the 254 injury rows; Seattle/Darnold reconciliation (Q09); Rams Garrett/McDuffie labels (Q10); DEN/CHI/PHI/TB Week 10 status (Q11); official depth-chart source (Q02); odds and historical results (Q04/Q05); NFL primary prop-bet memo (Q13); Ksa licence rules (Q12). Root links to `dashboard/` and `line-lab/` were added by the final integration.

## Independent integration review — arena/cbdcc317-nfl3, 2026-11-12 UTC

- This branch began at `83b6ce2`, before the coordination board and other sessions' work were visible. It initially claimed root integration and opened [PR #6](https://github.com/kanlerxz87-cyber/NFL3/pull/6). Main has since integrated PRs #1, #4, #7–#15, including the root overview and linked `/dashboard/` and `/line-lab/` sites. To respect owners' scopes, this branch contains no site, dataset or workflow changes—only this coordination handoff.
- Checks on current main passed: `python3 tests/check_site.py`; `python3 scripts/validate_site.py`; `cd dashboard && npm run all` (254 injury rows, 14 games, 19 news rows, 10 generated pages); and `cd line-lab && python3 scripts/verify.py` (13 checks, 17 pages, 32-team standings arithmetic, 108 injury rows, source/table contracts, no warnings/failures). Python compilation passed. These checks are structural/consistency checks, not independent manual confirmation of all source facts or external link crawling.
- Latest main `ef7ae0e` has successful [validation run 43157000573](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43157000573) and [Pages deployment run 43157000498](https://github.com/kanlerxz87-cyber/NFL3/actions/runs/43157000498). GitHub Pages API reports `built` and public; root URL is https://kanlerxz87-cyber.github.io/NFL3/.
- Independent line-lab review found issues to send to owner `arena/e5e2b753-nfl3`; no owner files were changed:
  1. In `line-lab/pages/injuries.html`, the row-level “Src” link goes to an NFL player profile, while the practice/game status comes from common report S05. A player profile verifies identity, not the row's injury/status facts. Add a report-specific official URL or dated report snapshot as the row source and retain the profile link separately.
  2. F-04's absolute claim that no historical machine-readable odds archive is published is not established by the 404 at `/odds/` (S09) and NFL Support's statement that widget odds are partner-supplied (S13). The reviewed evidence supports “not located in the sources checked”; historical market-data availability should stay unverified absent a league/provider confirmation.
  3. C1's same-season, cross-sectional margin/win-percentage correlation for 32 clubs is descriptive, not an out-of-time forecast or betting-skill measure; the 23.3% remainder is not a pure luck estimate. The Luck page caveats this; align “core skill signal”/“luck pool” headings with that limit.
  4. ST-06 describes cross-game legs as “close to independent” despite F-09 stating no leg-level outcomes exist. Label this as an untested assumption, not a finding. C6's p=0.066 (n=32) also does not establish incremental signal.
- PR #14 corrected a source counter, blocker filter and critical-path ordering; PR #15 linked both research sites from the root. These improve discoverability/accuracy but do not resolve the source/evidence concerns above. No line, market odds, player-prop projection, parlay correlation, strategy edge or reward was independently verified by this session.
- PR #6 was opened before the parallel integrations and merge attempts encountered concurrent base updates. This branch is syncing current main and limiting the PR to the coordination log; it must not overlay a stale site snapshot.
