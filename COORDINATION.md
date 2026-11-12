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
