# Verification evidence

This folder holds the evidence behind the **Verification report** page on the published site
(`/verification.html`).

## What each file is

| File | What it contains | How it was produced |
|---|---|---|
| `live_injuries_2026-11-12.csv` | 151 injury-report rows transcribed from the live official NFL Week 10 injury report (`https://www.nfl.com/injuries/`), read on 2026-11-12 at approximately 22:25–22:35 UTC. | Manual transcription of the live official page, row by row, for the 14 clubs whose tables were read in full. Each row keeps the player URL published on NFL.com. |
| `live_depth_commanders_2026-11-12.csv` | The complete Washington Commanders club depth chart (offense, defense, special teams) as published on `https://www.commanders.com/team/depth-chart`, read on 2026-11-12 at approximately 22:30 UTC. | Manual transcription of the live official club page, row by row, including the published order within each position group. |
| `verification.json` | Machine-readable result of comparing the two files above with the committed snapshot `decision-lab/data/official_snapshot.json`. | Produced by `scripts/verify_sources.py`. Regenerated on every build; never hand-edited. |

## Why a transcription file exists

The build agent that produced this evidence has no direct outbound network access to
`nfl.com` from its shell (HTTPS egress is blocked for the sandbox process). It can, however,
open official pages through a restricted read-only fetch path. The rows above were read from
that path and transcribed field by field, so the comparison against the committed snapshot is a
comparison against a *human-readable transcription of the live official page*, not a byte-level
re-fetch.

Two consequences, stated plainly:

1. The comparison is a **field-level** check (player, position, injury text, practice status,
   game status, published order). It is not a byte-integrity check. Byte integrity of the
   committed snapshot is recorded separately by `decision-lab/scripts/capture_official.py`,
   which stores the SHA-256 of each captured document.
2. Where the live page and the committed snapshot disagree, the disagreement is reported as
   **drift**, not as an error in either document. NFL.com publishes a mutable page; the
   committed snapshot is a point-in-time capture and is expected to lag the live page.

## Full-population verification

`scripts/verify_sources.py --recapture` re-fetches the official pages from a machine with
network access (the GitHub Actions runner), rebuilds the snapshot in memory and compares it
with the committed snapshot across the **whole** population of rows, not the sampled subset.
The Pages workflow runs that mode before publishing, so the published verification report
always carries the full-population result when it is available, and the sampled result when
it is not.

## Rules

* No value is inferred. A field that could not be read from the official page is left blank.
* The transcription files are evidence of what was read; they are never used to fill gaps in
  the committed snapshot. Gaps stay blank and are listed on the Flagged for Review page.
