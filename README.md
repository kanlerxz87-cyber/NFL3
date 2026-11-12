# Fourth Down Lab

An evidence-first NFL lines and strategy research dashboard, published as a static GitHub Pages site from `index.html`.

## Purpose

The dashboard organizes decision questions, source requirements, injury/depth-chart tracking needs, candidate signal families, validation gates, suggestions, and unverified items. It does not contain a live data feed, model, betting picks, verified edge, or player-specific facts. Empty fields are deliberately left blank rather than inferred.

## Publish

The workflow in `.github/workflows/pages.yml` deploys the repository root to GitHub Pages on pushes to `main` and manual dispatch. Enable GitHub Pages with GitHub Actions as the repository's build/deployment source. A successful workflow and Pages URL must be confirmed in Actions; this repository change alone does not prove it is live.

## Evidence standards

- Prefer official NFL/team sources for NFL facts; capture the date, URL, and retrieval timestamp.
- Preserve source history; do not overwrite changes to injury designations or lineup depth.
- Report model probabilities as estimates, not facts. No result is verified without reproducible data and a held-out test.
- Review `COORDINATION.md` for source checks, open risks, and task status.

## Limitations

No historical odds/results, official data feed, sportsbook settlement definitions, jurisdiction, bankroll requirements, or approved model specification were present at initial review. No profitability or correlation claims are made.
