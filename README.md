# NFL Decision Lab

A static, evidence-first dashboard blueprint for NFL decision research: executive status, a suggestion review board, pre-decision questions, candidate line/prop/parlay signal designs, injury and replacement-role tracking, validation gates, a leaderboard/reward specification, and a flagged-review register.

## Current executive status

- The repository began with only the initial README; no football dataset, odds history, model, backtest, injury archive, leaderboard, or reward rules existed.
- Official NFL pages were checked as source routes on **2026-11-12**: [NFL injury reports](https://www.nfl.com/injuries/), [player statistics](https://www.nfl.com/stats/player-stats/), [team statistics](https://www.nfl.com/stats/team-stats/), [schedules](https://www.nfl.com/schedules/), [teams directory](https://www.nfl.com/teams/), [player directory](https://www.nfl.com/players/), and [NFL Football Operations rulebook](https://operations.nfl.com/rules-officiating/2026-nfl-rulebook).
- No player, team, injury, schedule, odds, correlation, model, or performance values were copied into the dashboard. A source route being available is not verification of an individual value.
- Lines/odds, settlement, historical market prices, depth order, replacement exposure, injury effect coefficients, correlation estimates, backtest metrics and contest/reward authorization remain unresolved. The site intentionally keeps these values blank and flags them.
- All strategies are hypotheses, not betting advice or proven edges. No system can literally eliminate luck; the proposed approach separates evaluation from training, preregisters comparisons, reports uncertainty, then uses prospective shadow records.

## Pages

- `index.html` — executive summary and evidence status.
- `suggestions.html` — dedicated review/selection board before implementation.
- `questions.html` — known/unknown facts and questions blocking decisions.
- `strategies.html` — single, prop, parlay and replacement-signal hypotheses; validation and correlation plan.
- `availability.html` — injury, offense/defense role and replacement data specification.
- `leaderboard.html` — separate competition boards and reward eligibility gates.
- `flagged.html` — material gaps and source irregularity register.
- `sources.html` — official-source route and access audit.

## Run and validate locally

The site uses plain HTML, CSS and JavaScript; no package installation is required.

```bash
python3 -m http.server 8000
python3 scripts/check_site.py
```

Open `http://localhost:8000` locally. GitHub Pages preview uses relative links, so the pages work under a repository subpath.

## Publishing

`.github/workflows/pages.yml` deploys the root static site to GitHub Pages when commits reach `main` or the workflow is manually run. The repository must have Pages configured to use GitHub Actions. Do not treat a successful code check as confirmation that GitHub Pages permissions or deployment have succeeded; confirm the Pages deployment in GitHub Actions after merge.

## Evidence policy

Every research-data table row links to a relevant official NFL source route. Source links are context, not proof of a candidate signal. Only record an observation after capturing a source URL, retrieval time/timezone, season/game/player identifiers, definition, version and reviewer/verification state. If an official source cannot confirm a value, leave it blank and add it to **Flagged for Review**. Obtain separate licensing/terms approval for third-party market odds and any redistributed content.

See [`COORDINATION.md`](COORDINATION.md) for the session claim, sources, verification record, irregularities, and publication results.
