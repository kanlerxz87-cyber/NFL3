# Coordination board

Read this board before starting work. Do not edit files claimed by another active session; log requests here. Claims with no commits for over 60 minutes may be handed off, with a note. All factual content requires an official source; unverified items belong on Flagged for Review.

| Task | Status | Owner / branch | File scope |
| --- | --- | --- | --- |
| Initial integration: research, dashboard, tests, and Pages deployment | in progress | 56e27bb4 / `arena/56e27bb4-nfl3` | `COORDINATION.md`, `README.md`, `index.html`, `pages/`, `assets/`, `scripts/`, `.github/workflows/` |

## Log

- 2026-11-12: Repository inspected; initial commit contains only `README.md`. No prior board or claims found. This session is acting as the integration session. Arena fixes the branch name, so the requested `session-<id>/<task>` naming convention cannot be used here.
- 2026-11-12: Built six static pages from `scripts/build.py`. Checked each of the four injury excerpt rows against the [NFL report](https://www.nfl.com/injuries/league/2026/REG9); the title says Week 10 while the body says WEEK 9, and that discrepancy is flagged. Reviewed [club depth-chart caveat](https://static.clubs.nfl.com/image/upload/buccaneers/ohiml2zpdqt07wdkhc7s), [NFL odds FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL), [NFL integrity announcement](https://www.nfl.com/news/nfl-draftkings-fanduel-fanatics-sports-betting-partners), [NIST validation discussion](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=933682), and [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Research proposals are labeled as proposals, not verified outcomes. Checked 46 table rows for official source links and all local links with `python3 scripts/check.py`. External source content was manually reviewed via the research tools; availability is not continuously monitored. Live feeds, model results, correlations, competition and legal/data rights are unverified and flagged on the site.
