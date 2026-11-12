# Executive summary — NFL3 canonical decision lab

Updated: 2026-11-12 UTC. Research-only; not betting advice or an approved wagering system.

## Bottom line

The repository now has a publishable, source-first decision dashboard. It is **not** a validated betting system. The highest-value improvement is governance: separate official evidence, community exploration, model proposals and approved decisions before implementing changes.

| Detail | Status | Decision implication | Official source |
|---|---|---|---|
| Clean GitHub Pages dashboard and category tables | Implemented | Use `decision-lab/index.html` as the canonical entry point. | [GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) |
| Requirements, questions and suggestions registers | Implemented | Blocking answers stay blank; suggestions can be reviewed/exported before implementation. | [NFL odds-widget boundary](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) |
| Official injury snapshot | Captured: 254 rows + 4 no-injury sections | Injury status is evidence, not confirmed active status, depth order or workload. | [NFL injury report](https://www.nfl.com/injuries/) |
| Club depth evidence | Captured: 1,745 rows / 30 club labels; 2 probes flagged | Published rank is not confirmed starter, replacement assignment or snaps. | [Commanders depth](https://www.commanders.com/team/depth-chart), [Giants depth](https://www.giants.com/team/depth-chart), [Colts unofficial depth](https://www.colts.com/news/colts-release-unofficial-depth-chart-for-week-10) |
| Independent line origination | Blocked | No official-only verified forecast ledger or permissioned market benchmark; current line cells blank. | [NFL odds-widget FAQ](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) |
| Signals, parlays and player-prop combos | Hypotheses only | Singles first; combos require joint outcomes, dependence and settlement evidence. | [Next Gen Stats glossary](https://nextgenstats.nfl.com/glossary), [scikit-learn calibration](https://scikit-learn.org/stable/modules/calibration.html) |
| Validation gates and leaderboard | Implemented fail-closed; 0 eligible strategies | Rank only gate-passing strategies; rewards withheld without policy/funding. | [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm), [TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) |
| Luck removal | Not possible as stated | Quantify uncertainty and reduce false confidence; do not call residual variance pure luck. | [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm) |
| Community-data mislabeling | Flagged critical | nflverse GitHub digests prove bytes, not NFL authorship; exclude from official-only decisions. | [NFL odds-widget boundary](https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL) |

## Recommended path

1. **Approve Path A foundation:** official-only evidence contract, immutable captures, conflict flags, recognition-only leaderboard.
2. **Close data-rights questions:** permissioned odds/prop history, official outcome mapping, settlement and retention terms.
3. **Automate availability evidence:** scheduled NFL/club captures, freshness checks and conflict abstention.
4. **Run Path B only after gates:** pre-registered singles shadow baseline, personnel ablations, then joint-probability combo research.

## Verification performed

- 15 offline unit tests passed for capture parsing, blank preservation, odds/vig math, multiplicity, small-sample failure, community-source rejection, future-leak rejection, combo joint evidence and reward withholding.
- Canonical lab build produced 13 pages; every lab table row has an official-source link and local links/fragments pass.
- The 254 parsed NFL injury rows matched the existing dashboard CSV on key status fields with 0 differences.
- Independent repository audit flags preserved community-source authority issues and sourceless rows elsewhere; these are published for review and do not block site publication.

## Hard blockers before any betting decision

Licensed market history, official-only settlement mapping, confirmed replacement workload, empirical correlation/joint calibration, prospective shadow evidence, reward funding and legal approval remain unverified. The site leaves those values blank rather than inferring them.
