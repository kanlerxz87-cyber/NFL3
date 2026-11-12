# NFL3

Collects, organizes and analyzes NFL data, and publishes it as a static dashboard on GitHub Pages.

- **Live site:** https://kanlerxz87-cyber.github.io/NFL3/ (after the merge to `main` and Pages deploy; see COORDINATION.md)
- **Data (source of truth):** `data/*.csv` — every row has a source link or an `UNVERIFIED` flag.
- **Site (generated):** `docs/` — built from the CSVs by `scripts/build.mjs`. Do not hand-edit `docs/`.
- **Verification gate:** `scripts/check.mjs` — fails if a row has no source, an internal link is broken, or an external link is not https.
- **Coordination:** `COORDINATION.md` (shared task board and log).

## Rebuild

```bash
npm run all    # node scripts/build.mjs && node scripts/check.mjs (no dependencies)
```

## Scope and limits

- Verified values come from official NFL sources (nfl.com) and the Dutch regulator (kansspelautoriteit.nl).
- Depth charts, betting lines, historical results and correlations are **not** in the repo yet; those fields are blank and flagged.
- No strategy is validated and no reward is assigned yet. Analysis only; not betting advice.
