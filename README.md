# NFL3 — NFL research, decision and line-origination workspace

This repository hosts a source-linked NFL research site published with GitHub Pages.
Nothing here is betting advice, a sportsbook, or an approved wagering system.

**Live site:** https://kanlerxz87-cyber.github.io/NFL3/

## Start here

| Page | What it is |
|---|---|
| [Overview](index.html) | Landing page: what is established, what is missing, the recommended path and the page directory. |
| [Executive summary](executive-summary.html) | Findings, the full requirements register, the fact boundaries and the blockers. |
| [Questions & answers](questions.html) | Every question that must be answered before a decision, what is confirmed, the blank answer cells and the action that closes each one. |
| [Decision journal](decisions.html) | How a question becomes a decision: the flow, the blocking questions and the proposals waiting for a choice. |
| [Suggestions & decision paths](suggestions.html) | The review board: proposed paths, 13 site-improvement proposals and the registered suggestions, ready to accept, defer or reject before anything is implemented. |
| [Flagged for review](flagged.html) | Every gap, irregularity and unverified value, with the official source a reviewer needs, plus the repository-wide citation coverage. |
| [Verification report](verification.html) | The published capture checked line by line against the live official pages, with every difference listed. |
| [Review protocol](review.html) | How to close a published gap and what a change request has to contain. |
| [Source register](sources.html) | Every official source, with publisher, date checked, what it establishes and what it cannot establish. |

Research pages: [signals & models](signals.html) · [strategy lab](strategies.html) ·
[validation gates](validation.html) · [injuries & lineups](lineups.html) · [depth & schema](lineup.html).

## Preserved workspaces

Concurrent sessions' workspaces are preserved and clearly labelled, with their evidence boundary stated.

| Workspace | Entry point | Evidence boundary |
|---|---|---|
| [Canonical decision lab](decision-lab/index.html) | Official-source decision dashboard: requirements, questions, suggestions, injury and depth snapshot, fail-closed validation gates, flagged review and independent audit. | Official NFL and club sources only. Unknown values stay blank. |
| [Dashboard](dashboard/index.html) | Weekly injury, game, starter and strategy tables with row-level citations. | Some rows cite community or secondary sources and are marked unverified there. |
| [Line lab](line-lab/index.html) | Model-implied estimates and statistical research. | Model-implied, not sportsbook lines; not validated betting results. |
| [Decision hub](decision-hub/index.html) | Requirements, origination protocol, depth/injury evidence, questions and suggestions. | Empirical cells remain blank where unverified. |
| [Research desk](research-desk/index.html) | Exploratory community-data engine. | Community nflverse assets. A matching digest proves byte integrity, not NFL authorship, so it is excluded from official-only gates. |
| [Research workspace](research-workspace/index.html) | Supplemental sourced research pages. | Supplemental; the canonical flagged-review and audit pages define the integration boundary. |

## Source-authority boundary

- Official NFL and club pages establish published facts for review. A capture hash proves byte integrity, not reuse rights or future stability.
- nflverse/nflreadr GitHub assets are community-maintained. They are useful for exploration, but this review does not establish them as official NFL data, and they are excluded from the official-only gates.
- No licensed historical odds or prop archive, confirmed replacement workload, empirical correlation, validated strategy edge or reward funding is verified. Those cells stay blank and are published on [Flagged for review](flagged.html).

## How the site is built

The root pages are generated; no table row is hand-typed.

```bash
python3 scripts/build_root.py       # render the 14 root pages from the canonical register
python3 scripts/verify_sources.py   # line-by-line check of the capture against the live readings
python3 scripts/validate_site.py    # local links, assets and per-row citation checks
python3 tests/check_site.py         # root page source-link check
python3 tests/test_decision_lab.py  # canonical lab unit tests (synthetic fixtures only)
python3 decision-lab/scripts/build.py
python3 decision-lab/scripts/audit.py
```

Inputs: `decision-lab/data/catalog.json` (sources, requirements, questions, suggestions, strategies, gates, flags),
`decision-lab/data/official_snapshot.json` (the official capture), `data/root_decisions.json` (root content and
the site-improvement proposals) and `data/verification/verification.json` (the verification result).

The workflow `.github/workflows/pages.yml` captures the official sources, rebuilds and audits the canonical lab,
runs the verification, builds the root site, validates the whole site and publishes GitHub Pages.

## Verification

`scripts/verify_sources.py` compares the committed capture with the official pages:

- default mode compares it with the transcribed live readings in `data/verification/` (see that folder's README for exactly how they were produced);
- `--recapture` re-fetches the official pages on a networked runner and checks the full population.

Drift between the live page and the committed capture is reported as a finding, never repaired silently: NFL.com
publishes a mutable page and the capture is a point in time.

## Automation

- `.github/workflows/pages.yml` validates, refreshes official captures, rebuilds, audits and publishes the site.
- `.github/workflows/decision-lab.yml` runs the canonical lab checks on pull requests and can capture fresh official sources on manual dispatch.
- `.github/workflows/data-and-site.yml` is the preserved community-data research-desk pipeline. Its outputs are exploratory and flagged, not official-only decision evidence.

See `COORDINATION.md` for parallel-session claims, conflict logs, verification records and publication results.
