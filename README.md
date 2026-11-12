# NFL3 · Decision research workspace

A dependency-free static GitHub Pages dashboard for reviewing evidence, open questions, proposed NFL modeling strategies and limitations before implementation. Start at `index.html` or the [Pages site](https://kanlerxz87-cyber.github.io/NFL3/).

## Current scope and limitations

This is **not** a live injury tracker, line generator, betting system or functioning competition. It contains a small, dated injury-report excerpt and a research plan. No automated data ingestion, historical data, verified line, correlation, performance score, reward or ranking is available. Source links support the cited factual statements or provide context for proposals; they do not endorse those proposals. Luck cannot be removed from betting outcomes. Check the Flagged for Review page for source discrepancies and missing evidence.

## Build and verify

Python 3.9+ is required. No packages or credentials are needed:

```sh
python3 scripts/build.py
python3 scripts/check.py
python3 -m http.server 8000
```

Open `http://localhost:8000/`. `scripts/build.py` is the source of the generated HTML; commit both the generator and its outputs. `check.py` checks internal links, fragments, source domains and that each data row links to an official source. It does **not** independently verify external availability, changing source content, or the accuracy of claims: review those manually.

## Publishing

The repository's GitHub Pages configuration is branch-based (`main`, root). After merge to main, GitHub publishes the static files. No Actions workflow is required. Check the Pages deployment status and the published URL after merging. The sources and claim log are in `COORDINATION.md`.
