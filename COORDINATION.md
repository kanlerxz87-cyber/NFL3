# Coordination board

Shared task board for parallel agent sessions. Claim a task by adding a row with your session ID
and file scope, commit and push immediately, and never start a task another session has claimed.

| Task | Status | Owner | File scope |
|---|---|---|---|
| Repository review, source research, dashboard and integration (baseline root site) | needs review | arena-4fd6bbbb | root `index.html`, `strategies.html`, `lineups.html`, `decisions.html`, `sources.html`, `flagged.html`, `assets/`, `tests/` |
| Supplemental sourced dashboard | needs review | arena-56e27bb4 | `research-workspace/` |
| Evidence-first NFL research dashboard | needs review | arena-cbdcc317 | PR #6 files (root pages, `scripts/`, `assets/site.*`) |
| **Original line engine, empirical study, validation gates, suggestion + question registers, integration** | **in progress** | **arena-f9dd481e** | `pipeline/`, `data/`, `engine/`, `lab/`, `docs/`, `.github/workflows/data-refresh.yml`, `.gitignore`, `README.md`, `COORDINATION.md` |

A status of `needs review` means the item is published on the Flagged for Review page and does not
block anything.

## Claim: arena-f9dd481e — 2026-11-12 UTC

Branch: `arena/f9dd481e-nfl3` (fixed by the session; a session-named branch cannot be created because
the working branch is enforced).

Task: replace the proposal-only baseline with an evidence-first workspace built on **real, verifiable
data**. Scope is deliberately non-overlapping with the sessions above: all new work is written to
`pipeline/`, `data/`, `engine/`, `lab/` and `docs/`. No file owned by another session is edited during
the build phase.

Integration rule for this session: the root landing page and navigation are shared outputs. They are
edited only at the end, after the other sessions' work is re-read, and only to add navigation to the
new section while preserving the existing pages and their content. If another session is writing a
root page at that moment, the change is deferred to a rebase and re-applied on top, never by
discarding the other session's file.

## Log

### arena-4fd6bbbb
- Baseline contained only `README.md`; no data or application to verify.
- Built a static, source-linked proposal dashboard (PR #1, merged `03e8669`), verified with
  `python3 tests/check_site.py`.
- Flagged: no data feed, no point-in-time injury history, no odds history, no validated strategies.

### arena-56e27bb4
- Built a supplemental workspace under `research-workspace/` (PR #4, merged `8d1926e`) to avoid
  an add/add conflict on this board.
- Flagged: injury page title/body week mismatch on nfl.com; proposals are not verified outcomes.

### arena-f9dd481e (this session)
- Repository review and claim recorded above.
- Approach: collect official data with a reproducible, digest-verified pipeline; publish findings with
  per-row source links and explicit unverified flags; never fill a value that is not confirmed.

### arena-cbdcc317
- Opened PR #6 with an alternative root dashboard (`availability.html`, `leaderboard.html`,
  `questions.html`, `suggestions.html`, `strategies.html`, `sources.html`, `flagged.html`).
- Treated as an unclaimed-but-open contribution: the last state of this board did not record it as
  claimed, and its PR is still open. Its page inventory is used as an input to the final navigation so
  that both works remain reachable; files are not overwritten.


## Result log — arena-f9dd481e

### Data layer
- `pipeline/fetch_official.py` fetched **16 official nflverse release assets** (schedules, 2026 injuries,
  2021-2025 injuries, 2021-2024 + 2026 depth charts, snap counts, team stats, rosters, players) and each
  one matched the **SHA-256 digest GitHub publishes for that asset**. 0 failures.
- Snapshot committed under `data/raw/` (gzip; ~19 MB). Manifest with every digest in
  `data/raw/manifest.json`. Verified at 2026-11-12T05:01:25Z.

### Bugs found and fixed during verification (recorded because they changed published numbers)
1. **Spread sign convention.** `home_cover_margin` was `result + spread_line`; the official schema needs
   `result - spread_line`. Caught by a per-bucket home-cover check showing a 30% rate. Fixed and pinned by
   `engine/test_engine.py` against three real games (DAL@PHI, KC@LAC, ARI@NO).
2. **Market MAE sign.** The model target was `-result`, producing a *negative* correlation between the
   closing line and the result (r = −0.44). Corrected to `+result`; market r is now +0.443.
3. **CLV definition.** Originally reported `|edge|`, which is always positive. Now reports the signed
   distance on the taken side and is labelled as such.
4. **Same-game correlation.** Originally compared two bets on the same side (phi = 1.000 by construction).
   Rebuilt as four distinct leg pairs.
5. **Depth-chart schema change.** 2025+ files have no `week` column and no `depth_team`. Added
   `loader.depth_rows_for_season()` to normalise both schemas, and `features.snapshot_week_map()` to attach
   daily snapshots to the game week they precede.
6. **Historical injuries read from the 2026 file.** `loader.injuries()` is 2026-only, so the 2021-2024
   join matched 0 starters. Added `loader.injuries_for_season()`; the pooled study now matches **13,850**
   starter rows.
7. **Backup watchlist matched any snapshot.** It now uses only the newest snapshot, so a player is never
   listed as his own backup.

### Published results (all reproducible from `data/raw/`)
- Our spread MAE **10.17** vs market **9.80**; totals **10.78** vs **10.43**; r **0.385** vs **0.443**.
- **0 of 9** strategies pass all seven gates. Best: Elo-gap fade, +0.005/unit, z = 0.22.
- Same-game home win vs home cover phi **+0.67**; three-leg same-game parlay observed **14.6%** vs
  independent **12.8%** (1.14x lift).
- Pooled injury study, 2021-2024, 1,139 games: market already prices injuries
  (r = −0.178, p = 1.0e-9) but totals **under-react** (r = −0.243, p < 1e-15).

### Verification
- `engine/test_engine.py` — 40 assertions on conventions, statistics and gate logic. All pass.
- `tests/check_site.py` — 11 pages, **179 data-table rows, 100% carry an official source link**. Passes.
- CI job `build` passes end to end (fetch → verify → test → build → check → commit).


## Integration plan — arena-f9dd481e

Main had advanced to `bede878` with four parallel workspaces (`research-workspace/`, `dashboard/`,
`line-lab/`, `decision-hub/`) plus a root site published from the repository root. To avoid destroying
published work:

1. Merge `origin/main` into this branch, preserving every existing file.
2. Move this session's site from `site/` to `research-desk/` so it is a self-contained sub-site and
   nothing at the root is disturbed.
3. Extend the root `index.html` with a **new section only** (existing sections and links untouched) that
   routes readers to the research desk.
4. Extend `scripts/validate_site.py` (root deploy validator) to recurse into sub-directory sites, because
   the current root-only glob would stop validating everything that has already been published.
5. Keep this branch's Pages workflow limited to `main` + the working branch so the root deploy stays the
   single publisher on main.
