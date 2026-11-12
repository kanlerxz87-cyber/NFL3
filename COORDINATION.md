# COORDINATION.md — shared task board

Session ID: **f445c027** · Branch: `arena/f445c027-nfl3` (base `83b6ce2`, main)

> Branch note: the session's branch name is fixed by Arena (`arena/f445c027-nfl3`). The
> `session-<id>/<task>` naming in the brief could not be used for this session; all work stays on
> this branch and is logged in the Repo Review (R-05). Other `arena/*` branches on origin belong to
> other sessions and were not modified.

## Task board

| ID | Task | Status | Owner (session) | Files in scope |
|----|------|--------|-----------------|----------------|
| T1 | Repo review & irregularities | done (needs review items published: 6 flags) | f445c027 | `data/repo_review.csv` |
| T2 | Injury tracking, Week 10 2026 (official nfl.com) + starter-replacement signals | done (second line-by-line pass recommended – see Flagged) | f445c027 | `data/injuries_2026_w10.csv`, `data/games_2026_w10.csv`, `data/news_signals_2026_w10.csv` |
| T3 | Strategy lab: leaderboard, validation gates, correlation framework | done (no results – data missing, blocked gates logged) | f445c027 | `data/strategies.csv`, `data/correlation_framework.csv` |
| T4 | Information gaps (Q&A) and improvement suggestions (decision-only) | done (awaiting owner decisions) | f445c027 | `data/questions.csv`, `data/suggestions.csv` |
| T5 | Source registry, executive summary, GitHub Pages site build | done (site builds, check passes) | f445c027 | `data/sources.csv`, `scripts/*`, `docs/*`, `package.json` |
| T6 | Integration: build, link/verification check, PR to main, merge, Pages deploy | pending | f445c027 | `COORDINATION.md` (log) |

Status values: unclaimed · in progress · done · needs review (published on *Flagged for Review*, does not block).

## Log

- **2026-11-12 · f445c027 · claim** — claimed T1–T6 (single session on this branch). Repo at
  start: README only (`# NFL3`), one commit, no COORDINATION.md (created here).
- Sources used so far (all fetched 2026-11-12): nfl.com Week 10 injury report
  (https://www.nfl.com/injuries/); nfl.com Competition Committee injury-policy article
  (https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693).

- **2026-11-12 · f445c027 · T2 done** — 254 injury rows transcribed from the nfl.com Week 10 page (fetched in 7 parts), reconciled by team (24 teams with rows; SEA, CIN, LAC, BAL "No Injuries Reported"; 14 matchups / 28 teams). Status counts: 93 DNP, 89 Limited, 72 Full; 5 Out, 1 Questionable. Second line-by-line check not yet done – recommended (see Flagged).
- **T1 done** — 16 repo-review items (R-01…R-16). Flags: R-03 (other session branches), R-04/R-05 (branch naming), R-06 (Seattle "No Injuries Reported" vs headline), R-07 (Garrett/McDuffie labels), R-10 (4 teams not on page), R-12 (prop-memo source secondary), R-16 (NL regulator). R-11 blocker: no official depth-chart source.
- **T3 done** — 12 strategies tracked, 0 validated; gates G0–G8 proposed; correlation framework has blank values. Nothing computed (no odds or results data).
- **T4 done** — 18 questions (Q01–Q18), 14 suggestions (SG-01–SG-14). Only SG-12 (verification tooling) implemented; the rest await owner decision.
- **T5 done** — 11 sources registered (S01–S11). Official: S01 nfl.com injury report, S02 nfl.com injury-policy article, S03 media.nfl.com 2026 schedule, S05 Ksa home page. Excluded as non-official: S08–S11. Site: `docs/` (10 pages) built by `scripts/build.mjs`; gate `scripts/check.mjs` passes (0 broken links; every row sourced or flagged).

### Sources used this session (all fetched 2026-11-12)
- https://www.nfl.com/injuries/ (Week 10 report + linked headlines)
- https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693
- https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced
- https://kansspelautoriteit.nl/
- Secondary, flagged UNVERIFIED: https://sports.yahoo.com/article/nfl-says-worked-ban-more-152200232.html ; https://lamag.com/sports/nfl-gambling-november-13-memo-prop-bets-limit/

### Handoff / merge status
- Integration (T6): build + check run; PR to `main` and merge pending in this session.
