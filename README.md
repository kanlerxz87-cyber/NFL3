# NFL3 research desk

A static, source-linked NFL decision dashboard for GitHub Pages. Open `index.html` locally or serve the repository root with `python3 -m http.server`. Navigation uses relative paths for project-site hosting.

This is a research foundation, **not** an automated data pipeline, live injury tracker, betting model, leaderboard, or source of betting advice. The injury table is a small, dated snapshot, not a complete report. See the site's Flagged for Review page for unverified gaps and the decision journal for proposed next steps. Source links provide context for proposals and are not endorsements.

Run `python3 tests/check_site.py` to validate internal links, HTML parsing, and a source link on each table row. External links were manually inspected at research time; content may change.

## Additional research pages

The Overview includes a **Research deep dives** table linking to expanded questions and requirements, signal hypotheses, lineup evidence schema, validation gates, implementation suggestions, and extended flagged items. These pages supplement (and do not replace) the primary dashboard pages.

`python3 scripts/validate_site.py` additionally checks local links/assets and citation rows across the extended pages. `.github/workflows/pages.yml` runs validation on pull requests and deploys the static repository to GitHub Pages after a push to `main` (repository Pages must be configured to use GitHub Actions). This remains documentation and research design: it does not automatically ingest current data or provide picks.
