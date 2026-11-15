# Price-data policy (pre-registration record)

**Status:** adopted. **Adopted:** 2026-11-15 UTC, by session `arena/ba6c5155-nfl3`, at the direction of
the project brief ("Decide the price-data policy before any backtest is published").
**Registration:** this file's creating commit is the registration. The hash is recorded in
`corpus/manifest.json` under `policy_registration` by the commit immediately following creation.
**Amendments:** any change is a dated addendum appended below, committed **before** the change is used.
A change applied after results were seen invalidates every evaluation that used it.

This record is a project governance decision, not an NFL fact. It exists so that no backtest, ROI,
closing-line-value or ranking number can be published before the data rights and timing questions
below are answered in writing.

---

## 1. Fail-closed rule (the decision)

**No price-dependent number is published unless every price row behind it carries (a) a named source,
(b) a named licence with permitted use, and (c) both the price's own as-of time and the capture clock
time.** If any of the three is missing, the row does not enter the store, and any number computed
from it is not published. Backtest and ROI output is additionally barred until this policy has been
satisfied for the whole evaluation sample — there is no partial-sample shortcut.

What this forbids today, concretely:

- No backtest, ROI, CLV, edge or rank is published anywhere on this site. The leaderboard's result
  cells are blank by construction (`ops-center/leaderboard.html`).
- The undated moneyline columns in the community file `data/raw/games.csv` are **not** price data for
  this policy: they carry no opening/closing pair, no as-of time, and no licence grant. They remain
  labelled community data and are excluded.
- Odds visible on NFL surfaces are supplied by partner bookmakers and redirect to them
  ([NFL Support, odds FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL)).
  That is not an NFL-authored, machine-readable, historical price archive. Scraping a book's public
  page without written terms is not an acceptable source under this policy.

## 2. Source register and permitted use

Each candidate price source must be entered here with its terms **before** any row from it is stored.
Unknown licence cells stay blank; a blank licence means the source may not be used.

| Source class | Example | Terms in writing? | Permitted use | Status |
|---|---|---|---|---|
| Licensed operator feed (two-sided, timestamped) | agreement with a book or odds vendor | not obtained | store open/close quotes; compute residuals, CLV, backtests | **0 sources licensed** |
| NFL-surface odds widgets (partner books) | FanDuel, Caesars, DraftKings per the [NFL Support FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) | no reuse grant located | viewing only; no machine capture, no republication | not usable for the store |
| Community game file moneyline columns | nflverse releases ([community source](https://github.com/nflverse/nflverse-data/releases)) | no licence grant located; undated prices | none under this policy | excluded |
| Public book web pages | book odds pages | no terms obtained | none under this policy | excluded |

The single blocking question for the store is unchanged by this policy: **obtain one licensed,
timestamped two-sided price source with written permitted use.** The number that would clear it is
one signed agreement naming the feed, the fields (open/close, side/total/moneyline), the historical
depth and the publication rights.

## 3. What the store records (schema)

Full schema: [`pricing/schema.json`](schema.json). Every market we originate gets one immutable
append-only row at the open and one at the close of its market:

| Field | Meaning |
|---|---|
| `market_id` | `season-week-game-market_type-side` (stable key) |
| `market_type` | `side`, `total`, `moneyline` — originated in that order (side first, then total, then moneyline) |
| `price` / `price_format` | the number itself, with its format (`american` / `decimal`) stated |
| `price_as_of` | the source's own timestamp for the quote, when the source gives one (blank when it does not) |
| `fetched_at_utc` | the capture clock time, recorded at fetch, to the second |
| `source_id` / `licence_id` | links into the register above; both required |
| `capture_hash` | SHA-256 of the raw captured payload |
| `supersedes` | pointer to a corrected row; corrections are new rows, never edits |

Ingestion is fail-closed: `pricing/ingest.py` refuses any payload without source, licence, capture
time and hash. Snapshots live under `pricing/snapshots/` as append-only JSONL files. Today the store
holds **0 rows**, because 0 sources are licensed. That is the correct state.

## 4. Publication gates tied to this policy

| Gate | Blocks | Clears when |
|---|---|---|
| Backtest/ROI/CLV publication | any backtest number anywhere on the site | store rows cover the whole evaluation sample under a licence that permits derived publication, and settlement comes from an official results source |
| Residual publication (`pricing/residuals.csv`) | the "market line" and "difference" columns | each residual row's market line has a licensed store row at the stated run time |
| Leaderboard ranking | any rank, reward or edge cell | the strategy passed the pre-registered gates on prospective results; corpus backtests may never fill these cells |
| Vig-free consensus (P5) | the decomposition view | at least two licensed two-sided sources at the same capture time |

## 5. Residual schedule (decided)

"We price a line ourselves and publish the residual against the market, on a schedule, from day one."
The schedule is decided now; rows appear as soon as one licensed source exists.

| Run | Time (UTC) | What is captured | What is published |
|---|---|---|---|
| Pre-kickoff | T−24h of each game's kickoff | market quote + our fair line | residual row (fair, market, difference) |
| Final pre-kickoff | T−1h | market quote + our fair line | residual row |
| Market close | first capture ≥ 30 min after the game's scheduled kickoff | closing quote | closing residual row; the close also writes the store's `close_price` |
| Weekly summary | Tuesdays 14:00 | the week's rows | one diff row per originated market |

Until a licensed source exists, `pricing/residuals.csv` publishes header-only and the page
`pricing.html` says so. A scheduled run that finds no licensed source writes no rows and raises a
missing-source flag; it never substitutes another number.

## 6. Explicitly not decided here

Book selection, subscription budget, redistribution rights, and the operator void/push rules for
combo settlement are **open questions**, each with a named blocking gate in
[`readiness.html`](readiness.html). They are decisions for the owner, and this record does not
invent them.
