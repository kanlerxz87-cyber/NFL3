#!/usr/bin/env python3
"""Build the decision-readiness table, the repo-review page and the flagged-review rows.

Every row is written by hand from a fact checked in this session (see the `checked`
notes). The script does not fetch anything: it renders the table and fails closed if
a row is missing a state, a blocking gate, a number, a repo evidence path or an
official source key, or if a repo evidence path does not exist.

    python3 scripts/build_readiness.py            # rewrite index.html block, repo-review.html, review.html rows
    python3 scripts/build_readiness.py --check    # fail if any output would change

Official source keys point only at nfl.com / operations.nfl.com pages. Pages marked
"opened" were fetched with the fetch tool on 2026-11-15; the rest are links already cited
in the repository and were not re-opened in this session (see the page notes).
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
REVIEW_HTML = ROOT / "review.html"
REPO_REVIEW = ROOT / "repo-review.html"
GITHUB = "https://github.com/kanlerxz87-cyber/NFL3"

GENERATED = {"repo-review.html"}  # written by this script

START, END = "<!-- READINESS:START -->", "<!-- READINESS:END -->"
FLAG_START, FLAG_END = "<!-- REVIEW-FLAGS:START -->", "<!-- REVIEW-FLAGS:END -->"

# key -> (label, url, opened_this_session)
OFFICIAL = {
    "injuries": ("NFL injury report", "https://www.nfl.com/injuries/", True),
    "transactions": ("NFL transactions log", "https://www.nfl.com/transactions/", True),
    "injury_policy": ("NFL competition committee: injury report revisions", "https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693", True),
    "week10_news": ("NFL Week 10 injury-report article (cited as venue source)", "https://www.nfl.com/news/nfl-week-10-injury-report-2026-season", False),
    "teams": ("NFL team directory", "https://www.nfl.com/teams/", False),
    "standings": ("NFL standings", "https://www.nfl.com/standings/", False),
    "schedule": ("NFL 2026 schedule, week 10", "https://www.nfl.com/schedules/2026/by-week/week-10", False),
    "gamecentre": ("NFL game centre (example page cited in repo)", "https://www.nfl.com/games/patriots-at-seahawks-2026-reg-1", False),
    "rulebook": ("2026 NFL rulebook", "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/", False),
    "odds": ("NFL odds page", "https://www.nfl.com/odds/", False),
    "stats": ("NFL stats", "https://www.nfl.com/stats/", False),
    "ops": ("NFL operations site", "https://operations.nfl.com/", False),
}

# Readiness rows: (id, area, requirement, state, blocking gate, now -> clears, repo evidence path, official key)
ROWS = [
    # ---- Prices and outcomes
    ("R01", "Prices & results", "Price-snapshot store: opening and closing numbers for every market we originate", "Blocked",
     "No permitted price source and no price-data policy (see R08). Opening prices are not in any file.",
     "Opening prices: 0 stored. Community file has spread/total/moneyline columns (timing not documented): 7,439 spread rows, 5,458 moneyline rows. Clears: opening + closing for 100% of originated markets in the test window.",
     "data/raw/games.csv", "odds"),
    ("R02", "Prices & results", "Verified results feed so backtests and ROI can be computed", "Partial",
     "ROI needs prices (R01). Results alone do not compute ROI.",
     "Official 2026 game rows with scores: 136 (decision-desk/data/games_2026.csv). Clears: every backtest game matched to an official final AND a price row.",
     "decision-desk/data/games_2026.csv", "standings"),
    ("R03", "Prices & results", "Originate the side first, then the total, then the moneyline", "Not built",
     "No origination engine in the repository; no market prices (R01).",
     "Markets originated in the given order: 0 of 3. Clears: a pre-registered run that logs side, then total, then moneyline for each game.",
     "engine/lines.py", "rulebook"),
    ("R04", "Prices & results", "Publish model fair line, market line and the difference as separate columns", "Blocked",
     "No market line (R01). The difference column cannot be computed without it.",
     "Market lines published: 0. Fair lines published: 0. Clears: a market line row for every published fair line.",
     "decision-lab/lines.html", "odds"),
    ("R05", "Prices & results", "Vig-free market consensus vs originated fair-line decomposition", "Blocked",
     "Needs at least two priced books per market (R01).",
     "Books with prices in repo: 0. Clears: ≥2 books per market with timestamps.",
     "decision-lab/lines.html", "odds"),
    ("R06", "Prices & results", "Price a line ourselves and publish the residual against the market on a schedule from day one", "Blocked",
     "No market line (R01) and no scheduled residual job. Verified: 0 workflow files mention 'residual'.",
     "Scheduled residual publications: 0. Clears: first scheduled residual with its n and timestamp.",
     ".github/workflows/pages.yml", "odds"),
    ("R07", "Prices & results", "Turn the 136-game log into the pre-registered backtest corpus", "Partial",
     "Corpus window not frozen; no prices (R01); pre-registration not shown to precede results (R09).",
     "Games in log: 136. Priced games: 0. Clears: a frozen corpus definition with a price row for each game.",
     "decision-desk/data/games_2026.csv", "standings"),
    ("R08", "Prices & results", "Decide the price-data policy before any backtest is published", "Blocked",
     "Decision not taken. No licence, retention or redistribution terms are in the repository.",
     "Written policy decisions: 0. Open flag: F-02 (ops/flagged). Clears: a recorded decision naming the permitted source, retention and reuse terms.",
     "review.html", "odds"),
    ("R09", "Prices & results", "Pre-register every strategy and forbid backtest numbers on the leaderboard", "Partial",
     "Registration is not provably frozen (git: the registration, engine code and computed results were committed together in c25ae53). No automated leaderboard rule test found.",
     "Pre-registered strategies: 9 (S1–S9). Commits containing both registration and results: 1 (c25ae53). Clears: a registration commit that precedes the first results commit, plus a test that blocks backtest numbers on the leaderboard.",
     "docs/PRE_REGISTRATION.md", "rulebook"),
    ("R10", "Prices & results", "Freeze a rule before it sees data: rule text, sample window and gates committed; the commit hash is the registration", "Partial",
     "Same as R09: no earlier commit exists for the rule text.",
     "Registration commits that precede results: 0 verified. Clears: one commit containing rule text, window and gates, dated before the results commit.",
     "docs/PRE_REGISTRATION.md", "rulebook"),
    ("R11", "Prices & results", "Split data into train, validation and final holdout seasons", "Partial",
     "Walk-forward test exists, but no named season split is pre-registered.",
     "Named holdout seasons: 0. Walk-forward summary present in analysis.json. Clears: named train/validation/holdout seasons written before evaluation.",
     "decision-desk/data/analysis.json", "standings"),
    # ---- Models and validation
    ("R12", "Models & validation", "Store every model output as a probability plus its inputs, not just a pick", "Not built",
     "No per-game probability-and-input ledger found by search of the repository.",
     "Per-game ledger rows: 0. Brier summary exists (model 0.2138; home base rate 0.2445; coin flip 0.2472). Clears: a ledger row per game with probability and every input.",
     "decision-desk/data/analysis.json", "standings"),
    ("R13", "Models & validation", "Ingest game-level results to make ratings opponent-aware", "Partial",
     "Limited to the 2026 season to date; history not ingested.",
     "Opponent-adjusted games: 136 (2026, weeks 1–9 per the decision desk). Clears: every game in the rating window ingested.",
     "decision-desk/data/games_2026.csv", "standings"),
    ("R14", "Models & validation", "Fixture-context feature set built only from published schedule facts", "Partial",
     "Schedule facts exist, but the feature set is not built.",
     "Fixtures with kickoff, slot, neutral-site fields: 136. Feature sets built: 0. Clears: one feature row per fixture with its source link.",
     "decision-desk/data/games_2026.csv", "schedule"),
    ("R15", "Models & validation", "Stadium roof / surface and NWS hourly wind and precipitation overlay (90-minute roof designation)", "Not built",
     "No official roof designation captured; no NWS grid captured.",
     "Official roof designations captured: 0 of 136 logged games. Clears: an official designation per game plus an NWS forecast row per hour.",
     "data/raw/games.csv", "ops"),
    ("R16", "Models & validation", "Singles-only shadow baseline, pre-registered, versions frozen, forecasts recorded before kickoff", "Not built",
     "No shadow model has run; no pre-kickoff forecast log.",
     "Forecasts recorded before kickoff: 0. Clears: a timestamped forecast for every game in the window, recorded before its kickoff.",
     "docs/PRE_REGISTRATION.md", "schedule"),
    ("R17", "Models & validation", "Injury and personnel ablations: same model with and without personnel features, difference with uncertainty", "Not built",
     "No model with and without the feature set has been fitted.",
     "Ablation runs: 0. Clears: a paired difference and interval for each ablation.",
     "decision-lab/validation.html", "injuries"),
    ("R18", "Models & validation", "Injury and depth ablations with chronological holdouts (identical models, with and without verified availability)", "Not built",
     "Depends on R17 and on verified availability (R29–R31).",
     "Chronological holdout ablations: 0. Clears: ablation runs on the named holdout seasons (R11).",
     "decision-lab/validation.html", "injuries"),
    ("R19", "Models & validation", "Correlations computed only from official numbers, with n published", "Blocked",
     "No official leg-outcome sample exists in the repository.",
     "Correlation values published: 0 (cells blank). Clears: an official-only leg sample with n ≥ the pre-registered minimum (minimum not yet set).",
     "decision-lab/requirements.html", "stats"),
    ("R20", "Models & validation", "Joint probability gate for parlays and prop combos (no multiplying marginal probabilities)", "Partial",
     "Gate text exists; no directly validated joint probability and no void/push rule per operator.",
     "Combos with a validated joint probability: 0. Clears: a joint-probability test on held-out combinations plus the operator's void/push rules.",
     "engine/gates.py", "rulebook"),
    ("R21", "Models & validation", "Proper-score leaderboard divisions: singles, game parlays, same-game parlays, prop combos", "Partial",
     "Divisions are named in pages; no division has eligible entries.",
     "Eligible entries across divisions: 0. Clears: ≥1 pre-registered entry per division scored on prospective data.",
     "ops-center/leaderboard.html", "standings"),
    ("R22", "Models & validation", "Rank by benchmark-relative Brier skill, with a game-cluster lower bound and a multiplicity adjustment", "Partial",
     "Brier computed for one model; no game-cluster lower bound and no multiplicity adjustment in code.",
     "Brier skill with cluster lower bound: 0 published. Clears: skill vs benchmark with cluster bootstrap bound and trial-count adjustment.",
     "decision-desk/data/analysis.json", "standings"),
    ("R23", "Models & validation", "Control baseline (random picks; favourites only) on every leaderboard run", "Not built",
     "No leaderboard run exists to attach it to.",
     "Control runs: 0. Clears: a random and a favourites-only baseline in every run.",
     "ops-center/leaderboard.html", "standings"),
    ("R24", "Models & validation", "Two-stage skill leaderboard: Brier qualification, then prospective CLV/ROI escrow", "Blocked",
     "CLV needs closing prices (R01); no reward funding recorded.",
     "Entries with a prospective CLV sample: 0. Escrow funded: 0. Clears: ≥1 entry with a prospective sample and funding confirmed.",
     "decision-hub/data/origination_leaderboard.json", "odds"),
    ("R25", "Models & validation", "Publish every model total twice (two estimators, gap column) until a walk-forward test picks one", "Not built",
     "No totals are published.",
     "Totals published with two estimators: 0. Clears: both estimators and their gap on each published total.",
     "line-lab/data/strategies.json", "standings"),
    ("R26", "Models & validation", "Strategy's two-sided 'what would change our mind' field", "Not built",
     "Field not present in the registered strategies.",
     "Strategies with the field: 0 of 9. Clears: both sides written before results for each strategy.",
     "docs/PRE_REGISTRATION.md", "rulebook"),
    ("R27", "Models & validation", "Demotion gate that sends a live strategy back to paper", "Not built",
     "No rule text exists (0 matches for 'demot' in the repository). No live strategy exists.",
     "Demotion rules written: 0. Clears: a written rule with its trigger and a test.",
     "docs/PRE_REGISTRATION.md", "rulebook"),
    ("R28", "Models & validation", "Remove luck and build selectively skill-based strategies", "Partial",
     "Luck cannot be removed; only split and bounded. The luck/skill split exists for the decision desk only.",
     "Luck/skill panel: decision-desk only. Strategies passing all gates: 0. Clears: ≥1 strategy with a lower bound above the benchmark on prospective data.",
     "decision-desk/luck.html", "standings"),
    # ---- Injuries and availability
    ("R29", "Injuries & availability", "Store every injury-hub read with its clock time; publish the delta, never the level", "Partial",
     "Each capture is stored with its time, but no delta is published and only one capture is committed.",
     "Captures in git: 1 (2026-11-12T06:32Z). Published-site capture: 2026-11-15T06:33Z (not in git). Clears: ≥2 committed captures per report with a published delta.",
     "decision-lab/data/official_snapshot.json", "injuries"),
    ("R30", "Injuries & availability", "Treat the injury report as a timestamped series: capture daily from Wednesday to kickoff", "Partial",
     "Capture runs in CI on deploy with continue-on-error and results are not committed (RR-01).",
     "Dated daily captures in git for Week 10: 1 (plus one 2026-11-13 folder in integration/). Clears: one committed capture per day, Wednesday to kickoff.",
     "integration/data/captures/2026-11-13-nfl-injuries/manifest.json", "injuries"),
    ("R31", "Injuries & availability", "Snapshot the NFL injury report every Wednesday, Thursday and Friday and keep a dated history", "Partial",
     "Same as R30: history is not retained in git.",
     "Dated Wed/Thu/Fri snapshots in git: 0 of 3 for Week 10. Clears: three dated, hashed snapshots per week.",
     ".github/workflows/pages.yml", "injuries"),
    ("R32", "Injuries & availability", "Immutable official availability snapshots with raw hashes, timestamps and conflict flags", "Partial",
     "Hashes and timestamps exist. No conflict flags across captures.",
     "Captures with a hash: 1. Conflict-flag fields across captures: 0. Clears: a conflict flag for every row that differs between two captures.",
     "decision-lab/data/official_snapshot.json", "injuries"),
    ("R33", "Injuries & availability", "Re-capture and republish the Week 10 injury tables", "Partial",
     "Committed snapshot is older than the published page; counts disagree across pages (RR-01, RR-15).",
     "Committed rows: 254 (4 no-injury sections). Published page: 347 rows (captured 2026-11-15). Clears: committed row count equal to the official report count, with a hash.",
     "decision-lab/injuries.html", "injuries"),
    ("R34", "Injuries & availability", "Fix the Lions game-status designations (Kerby Joseph, Cade Mays, D.J. Reed)", "Partial",
     "Fixed on the published page; not in git.",
     "Official page (opened 2026-11-15): Joseph, Mays and Reed each 'Out'. Published page: 3 of 3 'Out'. Committed snapshot: 0 of 3 populated (Joseph still 'Limited'). Clears: the committed snapshot shows 3 of 3.",
     "decision-lab/data/official_snapshot.json", "injuries"),
    ("R35", "Injuries & availability", "Capture official inactive lists", "Blocked",
     "No inactive list has been captured from an official source.",
     "Official inactive lists captured: 0 of 136 logged games. Clears: an inactive list per game with its source and time.",
     "data/raw/injuries_2025.csv", "ops"),
    ("R36", "Injuries & availability", "Capture reserve lists so 'not listed' never means 'available'", "Not built",
     "No reserve-list capture. The official transactions log has a reserve-list view.",
     "Reserve-list captures: 0 of 32 clubs. Clears: a reserve-list capture per club with date and source.",
     "decision-lab/availability.html", "transactions"),
    ("R37", "Injuries & availability", "Score injury-designation reliability before using the label as a feature", "Blocked",
     "Needs inactive lists (R35) and joins to play/inactive outcomes.",
     "Designation-to-outcome joins: 0. Clears: play rate per designation with confidence intervals across ≥1 season.",
     "data/raw/injuries_2025.csv", "injury_policy"),
    ("R38", "Injuries & availability", "Calibrate what 'Questionable' means empirically (official text gives no percentages)", "Blocked",
     "Official definitions verified (Questionable = uncertain; Doubtful = unlikely; Out = will not play). No percentage in the text. The only percentage (about 95% of 'Probable' players playing) refers to a category since removed.",
     "Seasons of designations joined to outcomes: 0 (community injury files for 2021–2025 exist but are not joined to official inactives). Clears: the join in R37.",
     "data/raw/injuries_2025.csv", "injury_policy"),
    ("R39", "Injuries & availability", "Injury signal as a surprise (change between reads), never a level", "Not built",
     "Needs two or more reads per player (R29).",
     "Reads per player with a delta: 0. Clears: a delta series for each player from Wednesday to kickoff.",
     "decision-lab/injuries.html", "injuries"),
    ("R40", "Injuries & availability", "Roster turnover as a first-class data event; depth versioned to the last official roster event", "Not built",
     "No versioning. Two Colts receivers were traded on 11/10 (verified on the official log), and the depth rows are not tied to any event.",
     "Depth rows versioned to a roster event: 0 of 1,745. Official 11/10 Colts trades found: 2 (Keenan Allen; Josh Downs). Clears: each depth row carries the last event date.",
     "decision-lab/depth.html", "transactions"),
    ("R41", "Injuries & availability", "Flag stale depth rows against the official transactions log", "Not built",
     "No join between depth rows and the transactions log.",
     "Rows checked against transactions: 0. Clears: a join with a flag per stale row.",
     "decision-lab/depth.html", "transactions"),
    ("R42", "Injuries & availability", "Point-in-time ledger for injuries, depth charts and inactives (no lookahead)", "Not built",
     "No as-of ledger exists.",
     "Ledger rows with an as-of time: 0. Clears: every value keyed by its capture time.",
     "decision-lab/data/official_snapshot.json", "injuries"),
    ("R43", "Injuries & availability", "Availability graph as a first-class dataset: who was expected to start and who actually did", "Blocked",
     "No official expected-starter source; game books not captured (R45).",
     "Expected-starter records: 0. Actual-starter records: 0. Clears: both sets for every game in the window.",
     "decision-desk/data/availability.json", "ops"),
    ("R44", "Injuries & availability", "Announced-starter evidence field (dated official starter changes), not an inferred replacement", "Not built",
     "No field; no dated announcement captured.",
     "Announced-starter rows: 0. Clears: a dated official source per row.",
     "decision-lab/availability.html", "transactions"),
    ("R45", "Injuries & availability", "Official NFL Game Books for actual starters and game-day status; no inferred depth rank or snaps", "Blocked",
     "No Game Book captured. The exact Game Book URL has not been located from the official site in this session.",
     "Game Books captured: 0 of 136 logged games. Clears: one Game Book per game with its URL and hash.",
     "decision-lab/availability.html", "ops"),
    ("R46", "Injuries & availability", "Inject venue of every fixture from the official game centre and publish it", "Partial",
     "The Week 10 venues cite a news article, not the game centre (RR-05). No venue column in the 2026 log.",
     "Week 10 fixtures with a venue: 14 of 14, but 0 of 14 cite a game-centre page. Clears: a game-centre link per fixture.",
     "decision-desk/data/week10_slate.csv", "week10_news"),
    ("R47", "Injuries & availability", "Publish the league's dated schedule announcement beside the live schedule page", "Not built",
     "No announcement captured.",
     "Dated announcements captured: 0. Clears: one dated announcement link next to each schedule page.",
     "decision-desk/data/games_2026.csv", "schedule"),
    ("R48", "Injuries & availability", "Snap counts as the starter proxy when the depth chart is unavailable", "Blocked",
     "No official snap-count source verified; community snap file only.",
     "Official snap-count sources verified: 0. Community snap file: data/raw/snap_counts_2026.csv. Clears: an official source for all 32 clubs.",
     "data/raw/snap_counts_2026.csv", "stats"),
    ("R49", "Injuries & availability", "Per-team view: starters out, replacements named, net injury count", "Partial",
     "A sub-site view exists; not on the root site.",
     "Teams covered by the sub-site view: 32 claimed in workspace; 30 in committed depth rows. Clears: a root-site row per team (32).",
     "dashboard/starters-backups.html", "teams"),
    ("R50", "Injuries & availability", "Injury/personnel signal enters only as a verified availability feature", "Partial",
     "No model consumes it yet; see R17–R18.",
     "Models using verified availability: 0. Clears: the ablation runs in R17–R18.",
     "decision-lab/availability.html", "injuries"),
    # ---- Depth and starters
    ("R51", "Depth & starters", "Depth from playing time, not jersey order", "Partial",
     "Policy adopted; no playing-time source verified (R48).",
     "Rows ranked by playing time: 0. Rank basis present: explicit tier header 896, published column order 817, published list order 32 (1,745 rows). Clears: a verified snap source per club.",
     "decision-lab/depth.html", "teams"),
    ("R52", "Depth & starters", "Reject deriving depth order from jersey number, experience or salary", "Done",
     "Rule text in the committed snapshot: a published depth rank is order, not confirmed starter status.",
     "Rows ranked by jersey, experience or salary: 0 (rank_basis values present: explicit tier header 896, published column order 817, published list order 32). Clears: n/a (policy in force).",
     "decision-lab/data/official_snapshot.json", "teams"),
    ("R53", "Depth & starters", "Model depth slots as groups, not a single starter", "Partial",
     "Group model not built; the grouping problem is measured (see the next column).",
     "Team-unit-position slots: 676. Slots with more than one rank-1 player: 149 (recomputed from the committed snapshot; matches the brief's 149). Clears: group-aware features for all 149 slots.",
     "decision-lab/depth.html", "teams"),
    ("R54", "Depth & starters", "Represent shared and empty depth slots faithfully", "Partial",
     "22 rows are flagged needs_split and are not split. Empty slots are not modelled.",
     "Rows flagged needs_split: 22. Clears: 0 flagged rows after a fresh capture.",
     "decision-lab/depth.html", "teams"),
    ("R55", "Depth & starters", "Official depth-chart register with date and source on every row", "Partial",
     "Rows have source, time and hash; 2 clubs failed to parse.",
     "Depth rows with source, time and hash: 1,745 of 1,745. Clubs parsed: 30 of 32. Clears: 32 of 32 clubs.",
     "decision-lab/depth.html", "teams"),
    ("R56", "Depth & starters", "Resolve the depth-order source before building the backup-deficiency feature (route a: per-club pages for all 32 clubs)", "Blocked",
     "30 of 32 clubs verified.",
     "Clubs verified: 30 of 32. Clears: 32 of 32 verified.",
     "decision-lab/depth.html", "teams"),
    ("R57", "Depth & starters", "Fix the two depth-parsing failures before widening coverage (Houston Texans image; Green Bay Packers jersey prefixes)", "Partial",
     "Packers parser fix is recorded but the committed snapshot still fails for both clubs. The Texans depth is an image: needs an authorised structured source.",
     "Failures still listed in committed snapshot: 2 (Texans, Packers). Clears: both parse from a fresh capture, with the Texans source authorised.",
     "decision-lab/data/official_snapshot.json", "teams"),
    ("R58", "Depth & starters", "Backup-deficiency flag: a 2nd/3rd/4th-string backup replacing a starter, offense and defense", "Blocked",
     "Needs starters (R45 Game Books or R48 snaps) and a verified depth route (R56).",
     "Confirmed starters in the depth rows: 0 (confirmed_starter is blank on all 1,745 rows). Clears: confirmed starters from an official source.",
     "decision-desk/data/availability.json", "teams"),
    ("R59", "Depth & starters", "Matchup deficiency matrix (1st–4th string, offense vs defense)", "Not built",
     "Depends on R53–R58.",
     "Matrix cells: 0. Clears: a rendered matrix with a source link per cell.",
     "decision-desk/data/availability.json", "teams"),
    ("R60", "Depth & starters", "Injury-designation depth: a point-in-time view of who replaced whom", "Not built",
     "Needs R42 and R45.",
     "Replacement chains published: 195 (ops-centre), with 43 absent from the club's own chart. Clears: each chain linked to a dated official source.",
     "ops-center/data/derived.json", "teams"),
    # ---- Site and governance
    ("R61", "Site & governance", "Decision-readiness table on the landing page (one row per requirement)", "Done",
     "Generated by scripts/build_readiness.py from the rows on this page.",
     "Rows on the landing page: one per requirement in this table.", "scripts/build_readiness.py", "ops"),
    ("R62", "Site & governance", "Repo review: every irregularity found line by line, with links", "Done",
     "Review rows are published with evidence; several are unresolved.",
     "Irregularities published: see repo-review.html. Unresolved: most of them.", "repo-review.html", "ops"),
    ("R63", "Site & governance", "Suggestions section reviewed before implementation", "Done",
     "Decision is taken by the reviewer; nothing is implemented from the list.",
     "Suggestions on the board: 75 (landing page count). Implemented: 0.", "suggestions.html", "ops"),
    ("R64", "Site & governance", "Questions register: known information, missing answers, discovery actions", "Done",
     "Answers stay blank unless a source supplies them.",
     "Questions: 100 (landing count). Answered from official sources: see the register.", "ops-center/questions.html", "ops"),
    ("R65", "Site & governance", "Executive summary", "Done",
     "Refreshed 2026-11-15 with the readiness and review links.", "Summary sections: see EXECUTIVE_SUMMARY.md.",
     "EXECUTIVE_SUMMARY.md", "ops"),
    ("R66", "Site & governance", "Clean GitHub Pages site with category subpages; every table row cites an official source", "Partial",
     "Validators pass, but the ops-centre gate reports 8 secondary or community sources.",
     "Validator failures: 0. Ops-centre warnings: 8 (secondary or community sources; 10 before PR #66). Clears: 0 warnings.",
     "ops-center/sources.html", "ops"),
    ("R67", "Site & governance", "Drift alarm for every scraper: fail loudly on a missing field or row count", "Partial",
     "Verification exists but ran offline; the committed record reports 'drift'; no alarm is wired to the deploy.",
     "Scrapers with a row-count alarm: 0 verified. Committed verification status: drift (offline-structural). Clears: a failing alarm on row-count or field drift.",
     "decision-lab/data/verification.json", "injuries"),
    ("R68", "Site & governance", "Durable snapshot storage outside the static site, freshness monitoring and alerts", "Not built",
     "No alert step in any workflow (0 matches for 'alert' in .github).",
     "Alert steps: 0. Freshness checks: 0. Clears: a freshness check and an alert on failure.",
     ".github/workflows/pages.yml", "ops"),
    ("R69", "Site & governance", "Split the site into a public analysis layer and a private raw-data layer", "Not built",
     "Raw extracts are committed and public; terms not yet read.",
     "Private raw-data stores: 0. Clears: a private store with only derived outputs published.",
     "data/raw/manifest.json", "ops"),
    ("R70", "Site & governance", "Weekly 'what changed' diff of rank, rating and availability", "Not built",
     "Needs at least two weekly snapshots of the same tables.",
     "Weekly snapshots of ranks/ratings in git: 1. Clears: two consecutive weekly snapshots and a diff column.",
     "decision-desk/data/analysis.json", "standings"),
    ("R71", "Site & governance", "Multi-session coordination on COORDINATION.md with claims, scopes and logged handoffs", "Partial",
     "Session-named branches are not available; this session uses the fixed Arena branch. Board is over 1,500 lines.",
     "Open claims: 1 (this session). Board size: see COORDINATION.md. Clears: a shorter board with one live status per task.",
     "COORDINATION.md", "ops"),
    ("R72", "Site & governance", "Pull request to main, merge without waiting for approval, GitHub Pages deploy verified", "In progress",
     "Requires the validators to pass and the deploy to succeed.",
     "Recorded in COORDINATION.md at merge time.", "COORDINATION.md", "ops"),
]

# Repo-review findings: (id, severity, finding, evidence, action, official key or None, repo path, github-path)
REVIEW = [
    ("RR-01", "High",
     "The published injury page and the committed data disagree. Committed snapshot: 254 rows, observed 2026-11-12T06:32:36Z. Published page: '347 of 347 rows', captured 2026-11-15T06:33:06Z. The published page is built from a CI capture that is never committed, so git cannot reproduce it.",
     "decision-lab/data/official_snapshot.json (observed_at, injury_rows) vs decision-lab/injuries.html (capture line). Deploy job in .github/workflows/pages.yml runs capture_official.py and does not commit the result.",
     "Commit each capture with its hash and time, and have the page cite that hash.", "injuries", "decision-lab/data/official_snapshot.json"),
    ("RR-02", "High",
     "Lions designations: the committed snapshot has Kerby Joseph 'Limited Participation' with a blank game status, and Cade Mays and D.J. Reed with a blank game status. The official page (opened 2026-11-15) lists Joseph 'Did Not Participate' / Out (Knee), Mays 'Did Not Participate' / Out (Ankle), Reed 'Did Not Participate' / Out (Hip).",
     "Official page: https://www.nfl.com/injuries/ (Lions block, NE @ DET). Committed: decision-lab/data/official_snapshot.json (injury_rows, team = Lions).",
     "Re-capture; keep the old and new rows both, with the time of each.", "injuries", "decision-lab/data/official_snapshot.json"),
    ("RR-03", "High",
     "Depth parsing still fails for two clubs in the committed snapshot: Houston Texans ('no depth table parsed'; depth is published as an image) and Green Bay Packers ('no depth table parsed'). The snapshot also records parser_fixed = true, so the record contradicts itself.",
     "decision-lab/data/official_snapshot.json (depth_directory_failures; depth_cell_integrity.parser_fixed).",
     "Fix the Packers parse and keep the Texans row unverified until an authorised structured source is found.", "teams", "decision-lab/data/official_snapshot.json"),
    ("RR-04", "High",
     "The pre-registration cannot be shown to precede the results. docs/PRE_REGISTRATION.md was first committed in c25ae53 (2026-11-12), in the same commit as engine code changes, lab/results/computed.json (about 9,000 changed lines) and a README 'with published findings'. The document says it was 'written before the out-of-sample results were inspected'; git does not show that.",
     "git show --stat c25ae53; commit: https://github.com/kanlerxz87-cyber/NFL3/commit/c25ae53",
     "Treat the nine strategies as unregistered until a registration commit precedes the results commit. Record the reason in COORDINATION.md.", None, "docs/PRE_REGISTRATION.md"),
    ("RR-05", "Medium",
     "Venue source does not match the brief. All 14 Week 10 venues in decision-desk/data/week10_slate.csv cite the NFL Week 10 injury-report article, not a game-centre page. The 2026 game log has no venue column.",
     "decision-desk/data/week10_slate.csv (source_url column, 14 of 14 rows).",
     "Open each fixture's game-centre page and cite it, or mark the venue unverified.", "week10_news", "decision-desk/data/week10_slate.csv"),
    ("RR-06", "High",
     "The committed verification record changed meaning. Before PR #66 it was a live run (2026-11-13, mode live, 62 sources unreachable, 32,142 bytes). It is now an offline structural run (2026-11-15T12:12Z, mode offline-structural, 3 checks, status 'drift', 2,428 bytes). The live field-by-field evidence is no longer in git.",
     "git show be4d611^:decision-lab/data/verification.json vs decision-lab/data/verification.json; PR #66 merge 25dc2c4.",
     "Commit the live run with its unreachable list, separately from the offline run.", "injuries", "decision-lab/data/verification.json"),
    ("RR-07", "High",
     "Three different injury-row counts for the same Week 10 report appear on published pages: 254 (README and committed snapshot), 279 (landing page 'injury rows'), 347 (published injury page).",
     "README.md ('185 of 254 report rows joined'); index.html (INJURY ROWS); decision-lab/injuries.html ('347 of 347 rows').",
     "Use one count, derived from one hashed capture; update every page from it.", "injuries", "README.md"),
    ("RR-08", "High",
     "No alerting, no residual job and continue-on-error on the capture and verification steps. A failed capture does not stop the deploy, and no workflow mentions 'residual' or 'alert'.",
     ".github/workflows/pages.yml (continue-on-error on the capture and live verification steps); grep of .github for 'residual' and 'alert' returns 0 matches.",
     "Fail the deploy, or raise an alert, when a capture is missing or stale.", "ops", ".github/workflows/pages.yml"),
    ("RR-09", "Medium",
     "Nine separate flagged.html pages across nine workspaces (dashboard, decision-desk, decision-hub, decision-lab, root, line-lab, ops-center, research-desk, research-workspace). Items can be updated in one and not the others.",
     "find . -name 'flagged*.html' returns 9 files.",
     "Keep one register and generate the others from it.", "ops", "flagged.html"),
    ("RR-10", "High",
     "The historical data the models and the depth join rely on is community-maintained (nflverse GitHub assets: games, injuries 2021–2026, depth charts, snap counts, players, roster). The repository's own README says this is not established as official NFL data, so official-only gates cannot use it.",
     "data/raw/manifest.json (asset URLs under github.com/nflverse); README.md 'Source-authority boundary'.",
     "Keep community data out of official-only gates; source official replacements (game books, official snap data).", "stats", "data/raw/manifest.json"),
    ("RR-11", "Medium",
     "The price columns in the community games file have no documented timing. The file cannot be used as an opening-line store, and its licence and terms are not recorded in the repository.",
     "data/raw/games.csv (spread_line, total_line, moneyline columns; 7,548 rows, 1999–2026).",
     "Record the file's terms and timing before any backtest uses it (R08).", "odds", "data/raw/games.csv"),
    ("RR-12", "Low",
     "COORDINATION.md is over 1,500 lines with more than a dozen claim sections. Several tasks are 'done — needs review' with no evidence link in the same entry.",
     "wc -l COORDINATION.md.",
     "Move closed claims to an archive file; keep one live table at the top.", "ops", "COORDINATION.md"),
    ("RR-14", "Medium",
     "Designations move within the week, and the records disagree about when. The independent baseline (verification_baseline.json, transcribed 2026-11-12) records Kerby Joseph as 'Full Participation' with game status 'Out'. The official page read on 2026-11-15 records 'Did Not Participate' with 'Out'. The verifier reports this as source_updated, not as a mismatch, and no timestamped capture shows when the change happened.",
     "decision-lab/data/verification_baseline.json (transcribed_at 2026-11-12); python3 decision-lab/scripts/verify_sources.py (SOURCE-UPDATED rows); official page https://www.nfl.com/injuries/ (read 2026-11-15).",
     "Store each capture with its time so a change can be dated; re-transcribe the baseline from a stored capture.", "injuries", "decision-lab/data/verification_baseline.json"),
    ("RR-13", "Low",
     "Branch rule: the brief asks for session-named branches (session-<id>/<task>). This session runs on the Arena-fixed branch arena/ecdea533-nfl3, so each task is a commit on that branch, not its own branch.",
     "Branch note in the session brief; COORDINATION.md claim section.",
     "Note in the board; the integration session records the branch used for each task.", "ops", "COORDINATION.md"),
]

VERIFIED = [
    ("V-01", "Official injury page read on 2026-11-15, Thursday WAS @ NYG and Sunday NE @ DET blocks: the three Lions 'Out' designations and the 8:15 PM and 9:30 AM ET headers. The committed snapshot does not match the Lions rows (RR-02); this is a read of the official page, not a match.", "injuries"),
    ("V-02", "Official transactions log (opened 2026-11-15): November 2026 trades dated 11/10 include Keenan Allen (Colts to 49ers) and Josh Downs (Colts to Chiefs).", "transactions"),
    ("V-03", "Official injury-policy article (opened 2026-11-15): Practice report uses Did Not Participate, Limited and Full Participation; Game Status uses Questionable, Doubtful and Out; 'Probable' removed; no percentage defines Questionable.", "injury_policy"),
    ("V-04", "Depth rows in the committed snapshot: 676 team-unit-position slots; 149 with more than one rank-1 player. Recomputed in this session; matches the brief.", "teams"),
    ("V-05", "Week 10 slate: 14 fixtures with kickoff date, kickoff time and slot. Thursday 8:15 PM and Sunday 9:30 AM match the official page headers. Venues are not verified (RR-05).", "week10_news"),
]


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def official_link(key: str, css_source: bool = True) -> str:
    label, url, opened = OFFICIAL[key]
    cls = ' class="source"' if css_source else ""
    mark = " (opened 2026-11-15)" if opened else " (cited in repo)"
    return f'<a{cls} href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}{esc(mark)} ↗</a>'


def repo_link(path: str, prefix: str = "") -> str:
    target = Path(prefix + path)
    if path not in GENERATED and not (ROOT / path).exists():
        raise SystemExit(f"repo evidence path missing: {path}")
    return f'<a href="{esc(prefix + path)}">{esc(path)}</a>'


def validate_rows() -> None:
    ids = set()
    states = {"Done", "Partial", "Blocked", "Not built", "In progress"}
    for row in ROWS:
        rid, area, req, state, gate, now, path, key = row
        if rid in ids:
            raise SystemExit(f"duplicate id {rid}")
        ids.add(rid)
        if state not in states:
            raise SystemExit(f"{rid}: unknown state {state}")
        if not all([area, req, gate, now]):
            raise SystemExit(f"{rid}: empty field")
        if key not in OFFICIAL:
            raise SystemExit(f"{rid}: unknown official key {key}")
        if path not in GENERATED and not (ROOT / path).exists():
            raise SystemExit(f"{rid}: evidence path missing {path}")
    for rid, sev, finding, evidence, action, key, path in REVIEW:
        if key is not None and key not in OFFICIAL:
            raise SystemExit(f"{rid}: unknown official key {key}")
        if not (ROOT / path).exists():
            raise SystemExit(f"{rid}: evidence path missing {path}")


def counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for row in ROWS:
        out[row[3]] = out.get(row[3], 0) + 1
    return out


def render_readiness() -> str:
    c = counts()
    summary = " · ".join(f"{k} {c.get(k, 0)}" for k in ["Done", "Partial", "Blocked", "Not built", "In progress"])
    body = []
    for rid, area, req, state, gate, now, path, key in ROWS:
        body.append(
            "<tr>"
            f"<td>{esc(rid)}</td>"
            f"<td>{esc(area)}</td>"
            f"<td>{esc(req)}</td>"
            f"<td><strong>{esc(state)}</strong></td>"
            f"<td>{esc(gate)}</td>"
            f"<td>{esc(now)}</td>"
            f"<td>{repo_link(path)}</td>"
            f"<td>{official_link(key)}</td>"
            "</tr>"
        )
    return (
        f"{START}\n"
        '<section class="readiness" id="readiness">'
        '<div class="section-head"><div class="section-label">DECISION READINESS</div>'
        "<h2>One row per requirement: the gate that blocks it and the number that would clear it.</h2>"
        "<p>Each row is a requirement from the brief. The state is what the repository and the official page support today; "
        "the 'now → clears' column gives the current count and the count that would clear the gate. Thresholds are not chosen here; "
        "where a number is not yet set, the cell says so. Blank means not verified.</p></div>"
        f'<div class="notice" role="note">Rows: {len(ROWS)} · {esc(summary)} · Generated by <code>scripts/build_readiness.py</code>. Full list of findings: <a href="repo-review.html">Repo review</a> · <a href="review.html">Flagged for review</a>.</div>'
        '<div class="table-wrap"><table><thead><tr>'
        '<th scope="col">#</th><th scope="col">Area</th><th scope="col">Requirement</th><th scope="col">State</th>'
        '<th scope="col">Blocking gate</th><th scope="col">Now → clears</th><th scope="col">Repo evidence</th><th scope="col">Official source</th>'
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
        '<p class="small">Official source column: pages marked "opened 2026-11-15" were fetched and read for this table. Pages marked "cited in repo" are links already present in the repository and were not re-opened here. Blank cells are unverified.</p>'
        "</section>\n"
        f"{END}"
    )


def replace_block(text: str, start: str, end: str, block: str) -> str:
    if start in text and end in text:
        head, rest = text.split(start, 1)
        _, tail = rest.split(end, 1)
        return head + block + tail
    return text


def patch_index(text: str) -> str:
    block = render_readiness()
    if START in text:
        return replace_block(text, START, END, block)
    anchor = '<div class="callout"><div><div class="section-label">THE SHORT VERSION</div>'
    if text.count(anchor) != 1:
        raise SystemExit("index.html anchor for readiness block not found exactly once")
    return text.replace(anchor, block + "\n" + anchor, 1)


def render_repo_review() -> str:
    review_rows = []
    for rid, sev, finding, evidence, action, key, path in REVIEW:
        official = official_link(key) if key else '<span class="badge warn">No official page for this item</span>'
        review_rows.append(
            "<tr>"
            f"<td>{esc(rid)}</td>"
            f'<td><span class="badge {"danger" if sev == "High" else "warn"}">{esc(sev)}</span></td>'
            f"<td>{esc(finding)}</td>"
            f"<td>{esc(evidence)}</td>"
            f"<td>{esc(action)}</td>"
            f"<td>{official}<br>{repo_link(path)} · <a href=\"{esc(GITHUB + '/blob/main/' + path)}\">GitHub ↗</a></td>"
            "</tr>"
        )
    verified_rows = []
    for vid, text, key in VERIFIED:
        verified_rows.append(f"<tr><td>{esc(vid)}</td><td>{esc(text)}</td><td>{official_link(key)}</td></tr>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Repo review | NFL3</title><link rel="stylesheet" href="assets/site.css"></head><body><header id="site-header"></header><main class="wrap">
<div class="hrow"><div><p class="eyebrow">Line-by-line review</p><h1>Repo review</h1></div><span class="badge danger">Irregularities open</span></div>
<p class="intro">Every irregularity below was checked against the repository in this session, and against the official NFL page where the fact is public. Each row has a repo path and a link. Blank cells mean not verified. Nothing here changes a published value; the owner of each file decides the fix.</p>
<div class="callout"><strong>How this review was done.</strong> The official injury report, the transactions log and the injury-policy article were opened with a fetch on 2026-11-15. Other official links are cited from the repository and were not re-opened. Git history was read with a full clone (unshallowed) so commit claims could be checked.</div>
<section class="section"><h2>Irregularities</h2><p class="small">Severity is the reviewer's view of the impact on a decision, not a legal finding.</p><div class="tablewrap"><table><thead><tr><th>ID</th><th>Severity</th><th>Finding</th><th>Evidence</th><th>Action</th><th>Source and file</th></tr></thead><tbody>
{''.join(review_rows)}
</tbody></table></div></section>
<section class="section"><h2>Checked and found consistent</h2><p class="small">These checks passed in this session. A pass does not make a value complete; it means the stated fact matched its source.</p><div class="tablewrap"><table><thead><tr><th>ID</th><th>Check</th><th>Source</th></tr></thead><tbody>
{''.join(verified_rows)}
</tbody></table></div></section>
<section class="section"><h2>Commands to repeat the checks</h2><div class="tablewrap"><table><thead><tr><th>Check</th><th>Command</th><th>Result this session</th><th>Source</th></tr></thead><tbody>
<tr><td>Site links and table citations</td><td><code>python3 scripts/validate_site.py</code></td><td>Pass</td><td><a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/scripts/validate_site.py">scripts/validate_site.py ↗</a></td></tr>
<tr><td>Readiness table and review are current</td><td><code>python3 scripts/build_readiness.py --check</code></td><td>Pass after build</td><td><a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/scripts/build_readiness.py">scripts/build_readiness.py ↗</a></td></tr>
<tr><td>Ops centre gate</td><td><code>python3 ops-center/scripts/verify.py</code></td><td>0 failures, 8 warnings (secondary or community sources; 10 on the earlier base 3db9a64, before PR #66)</td><td><a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/ops-center/scripts/verify.py">ops-center/scripts/verify.py ↗</a></td></tr>
<tr><td>Build reproducibility</td><td><code>python3 decision-lab/scripts/build.py &amp;&amp; git status</code></td><td>No change on this branch</td><td><a href="https://github.com/kanlerxz87-cyber/NFL3/blob/main/decision-lab/scripts/build.py">decision-lab/scripts/build.py ↗</a></td></tr>
<tr><td>Pre-registration history</td><td><code>git log --format='%h %ad %s' -- docs/PRE_REGISTRATION.md</code></td><td>One commit: c25ae53</td><td><a href="https://github.com/kanlerxz87-cyber/NFL3/commit/c25ae53">commit c25ae53 ↗</a></td></tr>
</tbody></table></div></section>
</main><footer id="site-footer"></footer><script src="assets/site.js"></script></body></html>
"""


def render_flags() -> str:
    rows = []
    for rid, sev, finding, evidence, action, key, path in REVIEW:
        if sev != "High":
            continue
        fid = "F-" + rid.replace("-", "")
        official = official_link(key) if key else "<span class=\"badge warn\">No official page for this item</span>"
        github = f'<a href="{esc(GITHUB + "/blob/main/" + path)}">{esc(path)} on GitHub ↗</a>'
        rows.append(
            f"<tr><td>{esc(fid)}</td><td><span class=\"badge danger\">Repo review {esc(rid)}</span></td>"
            f"<td>{esc(finding)}</td><td>{esc(evidence)}</td><td>{esc(action)}</td><td>{official}<br>{github}</td></tr>"
        )
    return FLAG_START + "\n" + "\n".join(rows) + "\n" + FLAG_END


def patch_review(text: str) -> str:
    block = render_flags()
    if FLAG_START in text:
        return replace_block(text, FLAG_START, FLAG_END, block)
    marker = "</tbody></table></div></section>"
    if text.count(marker) < 1:
        raise SystemExit("review.html: flagged table end not found")
    return text.replace(marker, block + "\n" + marker, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate_rows()
    outputs = {
        INDEX: patch_index(INDEX.read_text(encoding="utf-8")),
        REVIEW_HTML: patch_review(REVIEW_HTML.read_text(encoding="utf-8")),
        REPO_REVIEW: render_repo_review(),
    }
    changed = [p.name for p, text in outputs.items() if (not p.exists()) or p.read_text(encoding="utf-8") != text]
    if args.check:
        if changed:
            print("would change:", ", ".join(changed))
            return 1
        print(f"readiness, repo review and flags are current ({len(ROWS)} rows, {len(REVIEW)} findings)")
        return 0
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(ROWS)} readiness rows, {len(REVIEW)} review findings; changed: {', '.join(changed) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
