# NFL3 Decision Desk

A source-linked decision dashboard: what the evidence supports, what it does not, and what must be
decided before anything is built.

**Live:** https://kanlerxz87-cyber.github.io/NFL3/decision-desk/

## Pages

| Page | What it answers |
|---|---|
| `index.html` | Overview: what was done this session, with the evidence to re-check each line |
| `summary.html` | Executive summary: six findings that change decisions, and the recommended order |
| `requirements.html` | Every requirement, its delivery state and where to inspect it |
| `decisions.html` | 24 questions that must be settled first: known, missing, how to discover, blocking or not |
| `questions.html` | The same gaps reorganised by discovery action, plus what we have and do not have |
| `suggestions.html` | 17 reviewable suggestions in two paths, with a browser-local approve/defer/reject console |
| `lines.html` | Independent spread and total numbers from official finals, with bands and blanks for market columns |
| `strategies.html` | Ten hypotheses, gate progress, five leaderboards and the reason each is empty |
| `validation.html` | Ten fail-closed gates and how many strategies fail each one |
| `injuries.html` | Week 10 injuries joined to published depth slots, with next man up and blanks for confirmation |
| `luck.html` | Reliability, luck residuals, measured correlations, walk-forward skill week by week |
| `audit.html` | What was verified, what came back negative, and source rot found |
| `flagged.html` | Irregularities and unverified items, each with its source |
| `sources.html` | Source register with what each page can and cannot establish |

## Verification rules this desk enforces

1. Every table row contains a link to an official NFL/club page or a methods reference.
2. A value that no official source settles is printed as a blank marked `unverified`. Nothing is inferred.
3. The 136-row game log must reproduce the official standings before the site may publish; the check runs in CI.
4. No page may claim an approved line, a market price, an edge or a reward. A banned-phrase list enforces it.

## Reproduce

```bash
python3 decision-desk/scripts/crosscheck_games.py   # game log vs official standings
python3 decision-desk/scripts/game_model.py         # ratings, reliability, correlation, walk-forward
python3 decision-desk/scripts/availability.py       # injury to depth join, second-source check
python3 decision-desk/scripts/build.py              # regenerate every page
python3 decision-desk/scripts/check.py              # verify links, row citations, blanks, data counts
```

## Data

| File | Contents |
|---|---|
| `data/games_2026.csv` | 136 official finals, Weeks 1-9, one NFL.com URL per row |
| `data/week10_slate.csv` | 14 Week 10 games with venue and kickoff |
| `data/analysis.json` | Generated analysis output |
| `data/availability.json` | Generated injury-to-depth join and second-source comparison |
| `data/availability_week10.csv` | Flat export of the join |

## Boundary

Research and decision support only. Not betting advice, not a sportsbook, and not an approved strategy.
No licensed price data, player-level outcome data or settlement archive exists in this repository, so no
edge, hold or closing-line value is measurable here.
