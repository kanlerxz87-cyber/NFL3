# Executive summary — official-source verification and line origination (2026-11-15)

Session `arena/f0d1503b-nfl3`. This summary covers the workspace at
[`official-verify/`](official-verify/index.html). It is deliberately short and every claim in it
can be traced to a page that links its own official source.

**What changed in one sentence:** for the first time in this repository, the 2026 game log was
re-read from official NFL pages and reconciled to official standings arithmetic, a model was
pre-registered *before* it saw results, and the result of that pre-registered test was published
as a failure rather than as a favourable point estimate.

---

## 1. The honest headline

The pre-registered model scores a Brier skill of **+0.1187** against the home base rate on
**89 out-of-sample games**. The 95 % cluster-bootstrap interval on the paired per-game improvement
is **−0.0099 to +0.0691**. The lower bound is below zero, so under the rule frozen before the run
the model **does not clear its own promotion gate**.

It is published on the leaderboard with its interval, marked **unvalidated**, and it earns
nothing. Nothing in this workspace is claimed to be profitable, and no spend or reward is
justified by it.

## 2. What was verified, and how

| What | How it was checked | Result |
|---|---|---|
| 2026 game log | Transcribed line by line from nine official weekly schedule pages plus one Game Center page, then recomputed into a league table and compared field by field with the official standings | **137 games; 192/192 club-field comparisons match; 0 mismatches** |
| Official standings | All 32 club rows transcribed (W, L, T, PF, PA, net) | 32/32 clubs present, totals reconcile |
| Fixture context | Week 11: 13 fixtures with weekday, date, kickoff, venue and neutral-site flag, each cited | 13/13 sourced |
| Injury report | Current-state page read directly; sample rows transcribed verbatim with blank cells preserved | 6 rows published, blanks kept blank |
| Depth ordering | Two official routes tested | **Both return the league's 404 page** — nothing invented |
| Snap counts | Official route tested | **404** — no snap value appears anywhere |
| Market prices | Not obtainable from any official page fetched | **Every market column blank and flagged** |

The standings cross-check is not a formality: it caught **two real defects**, described next.

## 3. Defects found in the existing repository

1. **The committed game log stopped at Week 9.** It contained 136 games and omitted the Week 10
   Thursday fixture. Recomputing its own standings left both the Giants and the Commanders one
   game short of the official record. The missing game is officially **Commanders 24, Giants 21**
   (Week 10, 12 November). Appended with its Game Center source; all 192 comparisons now pass.
2. **One score was published as a blank.** Commanders at Cowboys, Week 2, was stored with both
   scores empty and described as a page rendering a hidden score. The official weekly schedule
   page reads **"Commanders 20, Cowboys 37, FINAL"** and the Game Center prints 20 and 37 with a
   full quarter breakdown. The value is published in this workspace; whether the earlier blank
   was correct at capture time or a parse failure is recorded as an open question (Q05), because
   it cannot be resolved from the committed files.

Both are on the [Flagged for Review](official-verify/flagged.html) page with their evidence.

## 4. What was built

- **A verified corpus** — 137 games, hashed in the registration, each row carrying its source URL.
- **A pre-registration that gates itself** — `PREREG-2026-OV1` fixes the model form, the fixed
  sigma, the window (warm-up Weeks 1–3, scored Weeks 4–10), three controls, the scoring rules and
  two gates. A gate fails the build if the registration does not precede `HEAD`, or if the corpus
  hash has drifted. Both are tested.
- **Walk-forward evaluation with the controls you asked for** — coin flip, home base rate and
  favourites-only sit on the same board as the model, with intervals, not in a footnote.
- **Origination in the order you specified** — side, then total, then moneyline, for 13 unplayed
  Week 11 fixtures. Our number, the market number and the residual are separate columns. Market
  and residual are **blank**, because no price source exists and a blank is not zero disagreement.
- **The removal of luck** — **31 %** of the dispersion in club win totals is consistent with the
  Bernoulli variance implied by the model's own probabilities. Published with n = 32 and a caveat
  that this is not "true skill".
- **Calibration including the embarrassing bins** — six probability bands, thin bins published
  and marked *too small to read* rather than dropped.
- **Correlations from official numbers only** — four pairs, each with n, a Fisher interval and a
  caveat. Example: net points vs wins r = +0.845 (n = 32, 95 % CI +0.704 to +0.922).
- **Registers** — 67 requirement rows (21 done, 10 partial, 36 blocked, each with the gate that
  blocks it and the number that would clear it), 35 questions with discovery actions, 20 two-sided
  suggestions, 12 flags.

## 5. What is deliberately refused

The brief asks for depth and injury features. Three things that would make them possible do not
exist in any form obtainable here:

- an official depth ordering (the league route 404s),
- official snap counts (the league route 404s),
- a dated availability series (the report is a current-state page).

Rather than reconstruct these from roster status, jersey numbers, salary or experience — all of
which the brief explicitly rejects — the dependent requirements are marked **blocked** with the
exact number that would clear them. The depth and replacement columns are blank everywhere on the
site. This is the single largest honest gap, and it is visible rather than buried.

## 6. The one decision that matters most

**Price data.** Without a licensed or official price series with a stated closing definition,
there is no ROI, no closing-line value, no vig decomposition and no residual against a market. The
policy was decided **before** any backtest was published: blanks stay blank and are flagged. The
number that would clear it: two vendor evaluations in writing, one reuse grant, one fixed
closing-snapshot definition.

The second most valuable action is **adding a second season**. It is the only thing on the
suggestion list that can move the failing interval, and it costs nothing but time.

## 7. Verification you can run yourself

```bash
python3 official-verify/scripts/check_prereg.py    # registration precedes HEAD; corpus hash matches
python3 official-verify/scripts/verify_corpus.py   # 192 official club-field comparisons
python3 official-verify/scripts/evaluate.py        # re-derives every leaderboard number
python3 official-verify/scripts/analysis.py        # re-derives luck, calibration, correlations
python3 official-verify/scripts/originate.py       # re-derives every originated line
python3 official-verify/scripts/build_site.py      # rebuilds all 10 pages from the data
python3 official-verify/scripts/check_site.py      # fails on any unsourced row or broken link
python3 tests/test_official_verify.py              # 35 regression tests
```

## 8. Sources

Eighteen official sources are registered at
[`official-verify/sources.html`](official-verify/sources.html), each with the URL, what it was used
for, how it was checked and the evidence recorded. The four things that could not be obtained are
listed on the same page with the reason. Every one of the 384 table rows on the site links to an
official NFL host, and the site gate fails the build if that stops being true.
