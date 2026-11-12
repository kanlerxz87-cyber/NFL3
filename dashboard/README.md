# NFL3 Dashboard (dashboard/)

Static dashboard built from CSV data. Served by GitHub Pages at
https://kanlerxz87-cyber.github.io/NFL3/dashboard/ (the main research site is at the repository root).

- `data/*.csv` — source of truth. Every row has an official source link or an `UNVERIFIED` flag.
- `scripts/build.mjs` — generates the HTML pages in this folder from `data/`. No dependencies.
- `scripts/check.mjs` — verification gate: fails if a row has no source, an internal link is broken,
  or an external link is not https.

```bash
cd dashboard
npm run all    # build + check
```

Do not hand-edit the generated `*.html` or `assets/`; change the CSVs or the build script instead.
