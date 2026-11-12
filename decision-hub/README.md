# NFL3 Decision & Line Origination Hub (`decision-hub/`)

A zero-hallucination, line-by-line source-verified static dashboard published under `/NFL3/decision-hub/` on GitHub Pages (`arena-40c7529f` / branch `arena/40c7529f-nfl3`).

## Pages Organized by Category

1. **`index.html` — Command Overview & Master Requirements Matrix**: Project status KPIs, category directory, cross-workspace links, and full requirements traceability matrix.
2. **`executive-summary.html` — Executive Summary**: Core findings across market hold benchmarks (Nevada Gaming Control Board), NFL roster/inactive rules, 1st–4th string replacement mechanics, 2026 Rulebook shifts, and anti-luck governance.
3. **`suggestions.html` — Suggestions Review Center**: Dedicated decision-review hub comparing Path A vs. Path B trade-offs with client-side path selection and JSON export before any code implementation.
4. **`questions.html` — Pre-Decision Questions & Discovery Plan**: Explicit matrix of what we have vs. what we do not have, leaving unconfirmed answers strictly blank (`""`) alongside discovery protocols.
5. **`origination.html` — Line Origination, Validation Gates, Correlations & Skill Leaderboard**: Candidate strategies across Single Bets, Parlays, and Player Prop Bet Combos; Mandatory Validation Gates `G1–G8`; Pairwise Correlation Matrix (empirical cells blank pending data); and Anti-Luck Reward Governance.
6. **`depth-injuries.html` — Injury Tracking & 1st–4th String Offense/Defense Deficiencies**: Official NFL roster/elevation/T-90m rules (`operations.nfl.com`) + 16 line-by-line verified 2026 offense and defense 1st–4th string replacement chains from 7 official NFL club domains cross-checked against `nfl.com/injuries/`.
7. **`repo-audit.html` — Line-by-Line Repository Audit & Official Source Registry**: Full audit of initial commit `83b6ce2` and concurrent workspaces plus 17 verified official sources inspected on 2026-11-12 UTC.
8. **`flagged.html` — Flagged for Review**: Complete register of 12 verified official/repo irregularities and all intentionally blank (`""`) unverified fields.

## Reproducible Build & Verification

```bash
python3 decision-hub/scripts/build_hub.py
python3 decision-hub/scripts/verify_hub.py
```
