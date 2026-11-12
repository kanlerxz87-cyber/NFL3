# Coordination board

Session identifier: `c56ed83b-nfl3` (current Arena branch suffix). This session is the only session visible in the repository; no other claims existed at start.

| Task | Status | Owner | Files in scope | Notes |
|---|---|---|---|---|
| Site foundation, evidence register, decision framework, review flags | in progress | c56ed83b-nfl3 | `index.html`, `README.md`, `COORDINATION.md`, `.github/workflows/pages.yml` | Integration work is constrained to this active Arena branch; cannot create/switch to the requested session branch. |

## Evidence and verification

- Initial repository inspection: only `README.md` existed; it contained a single heading and no NFL dataset, code, build system, or requirements to verify.
- Official NFL injury-report page inspected: https://www.nfl.com/injuries/ . The retrieved page labels itself 2026 Week 10 and contains internally implausible/inconsistent roster/game information in the tool snapshot. It is therefore not used as a factual data feed; flagged for manual source/data-quality review. No current player or injury values have been populated.
- No statistical results, lines, correlations, or strategy performance claims are represented as verified. They require a specified dataset, timestamped odds, bet settlement definitions, and out-of-sample validation.

## Irregularities / review items

1. No prior data or implementation exists in this checkout, so there is no line-by-line underlying data to validate.
2. The NFL injury page retrieval showed future-season and roster discrepancies; no data ingested pending validation of official reports and date context.
3. Automated official data feeds, licensing/terms, odds source, jurisdiction, bankroll constraints, and evaluation period are unspecified.
4. The user asks for a live GitHub Pages deployment, but repository permissions / Pages configuration and deployment result must be checked; none is asserted here unless verified.

## Source policy

Use direct official league/team/statute/venue sources for factual entries. Each data row must have a source URL and captured-at time. Leave unconfirmed values blank and show them on Flagged for Review. Model outputs are explicitly estimates, never official facts.
