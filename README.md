# NFL3 — NFL research, decision and line-origination workspaces

This repository hosts several source-linked NFL research workspaces published with GitHub Pages.
Nothing here is betting advice, a sportsbook, or an approved wagering system.

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/

## Start here

| Workspace | What it is | Entry point |
|---|---|---|
| **Canonical decision lab** | Official-source decision dashboard: requirements, questions, suggestions, line-origination protocol, injury/depth snapshots, fail-closed validation gates, flagged review and independent audit. Unknown values stay blank. | [`decision-lab/index.html`](decision-lab/index.html) |
| Overview | Root landing page and links to preserved concurrent workspaces | [`index.html`](index.html) |
| Research desk | Exploratory community-data line/strategy engine using nflverse GitHub assets. Digest integrity is verified, but NFL official authority is **not** established; do not treat its results as official-only validation. | [`research-desk/index.html`](research-desk/index.html) |
| Line lab | Model-implied estimates and statistical research from official standings snapshots; not sportsbook lines or validated betting results | [`line-lab/index.html`](line-lab/index.html) |
| Dashboard | Weekly injury, game, starter and strategy tables with row-level citations | [`dashboard/index.html`](dashboard/index.html) |
| Decision hub | Requirements, origination, depth/injury, questions and suggestions | [`decision-hub/index.html`](decision-hub/index.html) |
| Research workspace | Supplemental sourced research pages | [`research-workspace/index.html`](research-workspace/index.html) |

## Source-authority boundary

- Official NFL/club pages establish published facts for review. A capture hash proves byte integrity, not reuse rights or future stability.
- nflverse/nflreadr GitHub assets are community-maintained. They may be useful for exploration, but this review does not establish them as official NFL data. The canonical decision lab excludes them from official-only gates and flags the mislabeling found in the research desk.
- No licensed historical odds/prop archive, confirmed replacement workload, empirical correlation, validated strategy edge or reward funding is verified. Those cells remain blank and are published on Flagged for Review.

## Canonical decision lab checks

```bash
python3 tests/test_decision_lab.py
python3 decision-lab/scripts/verify_sources.py
python3 decision-lab/scripts/add_depth_integrity.py
python3 decision-lab/scripts/build.py
python3 decision-lab/scripts/audit.py
```

`verify_sources.py` is the line-by-line check: it compares every published official
value with a separate hand transcription (`decision-lab/data/verification_baseline.json`)
and with the official page's own arithmetic, then writes
`decision-lab/data/verification_report.json` and publishes `decision-lab/verification.html`.
It runs offline on purpose, so an unreachable network cannot look like a pass. Its
negative-control test mutates a published number and asserts the checker reports it.

The lab captures official NFL injury reports and club depth pages, preserves blank cells, and builds static tables with an official source link on every row. `validation.py` implements ten fail-closed gates; its unit tests use synthetic fixtures only and are not NFL performance evidence.

## Automation

- `.github/workflows/decision-lab.yml` runs lab tests/build/audit on pull requests and can capture fresh official sources on manual dispatch.
- `.github/workflows/pages.yml` validates the site, refreshes official decision-lab captures for deployment, builds the lab, audits it, and publishes GitHub Pages.
- `.github/workflows/data-and-site.yml` is the preserved community-data research-desk pipeline. Its outputs are exploratory and flagged, not official-only decision evidence.

## Repository checks

```bash
python3 scripts/validate_site.py
python3 tests/check_site.py
python3 decision-lab/scripts/audit.py
```

See `COORDINATION.md` for parallel-session claims, conflict logs, verification records and publication results.
