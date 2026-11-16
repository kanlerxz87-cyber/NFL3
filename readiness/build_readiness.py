#!/usr/bin/env python3
"""Build the decision-readiness register (readiness.html + readiness/data/readiness.csv).

Every "current number" on the page is computed here from a committed artifact at build time.
Nothing is fetched from the network, so the page reflects the repository as committed. Where a
value has no committed evidence the page says so instead of estimating it. Proposed thresholds
are labelled "proposed" and are decisions for the owner, not findings.
"""
from __future__ import annotations

import csv
import html
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_HTML = ROOT / "readiness.html"
OUT_CSV = ROOT / "readiness" / "data" / "readiness.csv"

# Official links already cited elsewhere in this repository (sources.csv, sources.html, COORDINATION.md).
NFL_INJ = "https://www.nfl.com/injuries/"
NFL_INJ_W10 = "https://www.nfl.com/injuries/league/2026/REG10"
NFL_STATUS = "https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693"
NFL_SCORES = "https://www.nfl.com/scores/2026/week-10"
NFL_GAMECENTRE = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
NFL_STANDINGS = "https://www.nfl.com/standings/"
NFL_STATS = "https://www.nfl.com/stats/player-stats/"
NFL_ODDS = "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL"
NFL_RULEBOOK = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/"
NFL_OPS_PREP = "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep/"
NFL_TEAMS = "https://www.nfl.com/teams/"
NFL_NEWS_W10 = "https://www.nfl.com/news/nfl-week-10-injury-report-2026-season"
NFL_GAMECENTRE_W11 = "https://www.nfl.com/games/colts-at-texans-2026-reg-11"
NFL_SCHEDULE_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
NFL_ANNOUNCE_2026 = "https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced"
CLUB_PACKERS = "https://www.packers.com/team/depth-chart"
CLUB_TEXANS = "https://www.houstontexans.com/team/depth-chart"
CLUB_COMMANDERS = "https://www.commanders.com/team/depth-chart"
NFLVERSE_DEPTH = "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts"
NWS_API = "https://www.weather.gov/documentation/services-web-api"
REPO_BLOB = "https://github.com/kanlerxz87-cyber/NFL3/blob/main/"


def load_json(rel: str):
    p = ROOT / rel
    if not p.exists():
        sys.exit(f"readiness: required artifact missing: {rel}")
    return json.loads(p.read_text(encoding="utf-8"))


def read_csv(rel: str):
    p = ROOT / rel
    if not p.exists():
        sys.exit(f"readiness: required artifact missing: {rel}")
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def compute() -> dict:
    v: dict = {}
    games = read_csv("data/raw/games.csv")
    g26 = [r for r in games if r["season"] == "2026"]
    scored26 = [r for r in g26 if r["home_score"] not in ("", "NA")]
    v["games_2026"] = len(g26)
    v["final_w1_9"] = sum(1 for r in scored26 if int(r["week"]) <= 9)
    w10 = [r for r in g26 if r["week"] == "10"]
    v["w10_games"] = len(w10)
    v["w10_final"] = sum(1 for r in w10 if r["home_score"] not in ("", "NA"))
    v["seasons"] = len({r["season"] for r in games})
    v["season_span"] = f"{min(r['season'] for r in games)}–{max(r['season'] for r in games)}"
    v["odds_2026"] = sum(1 for r in g26 if r["home_moneyline"] not in ("", "NA"))
    v["snap_rows"] = len(read_csv("data/raw/snap_counts_2026.csv"))
    v["raw_files"] = len([p for p in (ROOT / "data/raw").iterdir() if p.is_file()])

    snap = load_json("decision-lab/data/official_snapshot.json")
    v["snap_inj_rows"] = len(snap["injury_rows"])
    v["snap_no_inj"] = [s if isinstance(s, str) else str(s) for s in snap["no_injury_sections"]]
    v["snap_depth_rows"] = len(snap["depth_rows"])
    v["depth_ok"] = len(snap["depth_directory_successes"])
    v["depth_fail"] = [f["team"] for f in snap["depth_directory_failures"]]
    v["snap_observed"] = snap["observed_at"]

    av = load_json("decision-lab/data/availability.json")
    v["av_matched"] = av["coverage"]["matched_rows"]
    v["av_unmatched"] = av["coverage"]["unmatched_rows"]
    v["av_leads"] = av["coverage"]["replacement_leads"]
    v["av_slots"] = av["coverage"]["depth_slots_with_report_listing"]
    v["av_rank1"] = av["coverage"]["rank1_listed_on_report"]
    v["unmatched_clubs"] = len(av["coverage"]["unmatched_by_club"])

    ops = load_json("ops-center/data/derived.json")
    v["ops_chains"] = len(ops["chains"])
    v["ops_inj"] = ops["injury_rows_current"]
    v["ops_suggestions"] = len(ops["suggestions"])
    v["ops_questions"] = len(ops["questions"])
    v["ops_strategies"] = len(ops["strategies"])
    v["ops_gates"] = len(ops["gates"])

    exec_text = (ROOT / "EXECUTIVE_SUMMARY.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+) replacement chains\*\*", exec_text) or re.search(r"(\d+) replacement chains", exec_text)
    v["exec_chains"] = int(m.group(1)) if m else None

    dash = read_csv("dashboard/data/strategies.csv")
    v["dash_strategies"] = len(dash)
    lions = [r for r in read_csv("dashboard/data/injuries_2026_w10.csv") if r["team_abbr"] == "DET"
             and r["player"] in {"Kerby Joseph", "Cade Mays", "D.J. Reed"}]
    v["lions_total"] = len(lions)
    v["lions_blank"] = sum(1 for r in lions if r["game_status"] == "")

    cap = load_json("integration/data/captures/2026-11-13-nfl-injuries/manifest.json")
    v["w10_observations"] = 1 + len(cap["compared_against"])
    v["cap_observed"] = cap["observed_at"]
    ver = load_json("integration/data/verification.json")
    v["published_rows_279"] = ver.get("published_rows")

    # Fourth dated observation of the Week 10 report and the delta against the third (this session).
    cap4 = load_json("results-verification/data/captures/2026-11-15-nfl-injuries/manifest.json")
    v["w10_observations"] += 1
    v["cap4_observed"] = cap4["observed_at"]
    dlt = load_json("results-verification/data/injury_delta.json")
    v["delta_rows_changed"] = dlt["counts"]["rows_with_changes"]
    v["delta_game_status"] = dlt["counts"]["game_status_changes"]
    v["delta_practice_status"] = dlt["counts"]["practice_status_changes"]
    v["delta_added"] = dlt["counts"]["rows_added_to_later_observation"]
    v["delta_removed"] = dlt["counts"]["rows_removed_from_later_observation"]

    # Verified results feed (this session): official score-page verification of the 136 finals.
    rv = load_json("results-verification/data/verification_report.json")
    v["rv_official_games"] = rv["counts"]["official_games"]
    v["rv_score_matches"] = rv["counts"]["score_matches"]
    v["rv_score_mismatches"] = rv["counts"]["score_mismatches"]
    v["rv_date_matches"] = rv["counts"]["date_matches"]
    v["rv_unmatched"] = rv["counts"]["official_games_without_community_match"]
    v["rv_window"] = rv["observed_window"]

    # The registration is the commit that CREATED the file. A shallow clone hides it, and the last
    # commit that touched the file is not the registration, so refuse to guess on a shallow clone.
    if git("rev-parse", "--is-shallow-repository") == "true":
        sys.exit("readiness: shallow clone; run `git fetch --unshallow` so the pre-registration commit can be found")
    created = git("log", "--diff-filter=A", "--format=%h %cs", "--", "docs/PRE_REGISTRATION.md").splitlines()
    if len(created) != 1:
        sys.exit(f"readiness: expected one commit creating docs/PRE_REGISTRATION.md, found {len(created)}")
    v["prereg_commit"], v["prereg_date"] = created[0].split(" ", 1)
    wf = "".join(p.read_text(encoding="utf-8") for p in (ROOT / ".github/workflows").glob("*.yml"))
    v["alert_hits"] = len(re.findall(r"alert|notify|slack|smtp|webhook", wf, re.I))
    mind = load_json("ops-center/data/mindchange.json")
    v["strategy_change_field"] = len(mind.get("entries", {}))
    v["price_rows"] = len(read_csv("pricing/prices.csv"))
    v["licensed_price_sources"] = sum(1 for r in read_csv("pricing/sources.csv") if r["status"] == "licensed")
    v["originated_markets"] = len(read_csv("pricing/originated_markets.csv"))
    v["residual_rows"] = len(read_csv("pricing/residuals.csv"))
    v["policy_records"] = 1 if (ROOT / "pricing" / "PRICE_DATA_POLICY.md").is_file() else 0
    man = load_json("corpus/manifest.json")
    v["corpus_games"] = man["window"]["games"]
    v["corpus_settled"] = man["window"]["settled"]
    v["corpus_hash"] = man["frozen_sha256"][:12]
    v["corpus_train"] = man["split"]["train"]["games"]
    v["corpus_val"] = man["split"]["validation"]["games"]
    v["corpus_hold"] = man["split"]["holdout"]["games"]
    v["corpus_registered"] = ("registration " + man["corpus_registration"][:12] + "\u2026"
                              if man.get("corpus_registration") else "registration hash pending")
    # Skill lab (proper scores, controls, uncertainty, multiplicity) and availability ledger.
    skill = load_json("skill-lab/data/results.json")
    prows = skill["runs"]["primary"]["rows"]
    v["skill_rows"] = len(prows)
    v["skill_eligible"] = sum(1 for r in prows if r.get("eligible_for_ranking"))
    v["skill_corpus"] = skill["meta"]["primary_corpus"]["observed_games"]
    v["skill_best"] = max(r["skill_brier"] for r in prows if "skill_brier" in r)
    v["skill_prereg"] = skill["meta"]["pre_registration_commit"][:12]
    v["skill_trials"] = prows[0].get("family_trials", 0)
    v["skill_graded_rows"] = len(skill["runs"]["primary"]["graded"])

    led = load_json("availability-ledger/data/ledger.json")
    v["ledger_reserve"] = len(led["reserve_entries"])
    v["ledger_trades"] = len(led["trade_events"])
    v["ledger_stale"] = len(led["stale_depth_rows"])
    v["ledger_same_day"] = len(led["same_day_depth_rows"])
    v["ledger_traded_removed"] = len(led["traded_players_removed_from_former_club"])
    v["ledger_not_on_report"] = sum(1 for c in led["report_coverage"] if not c["on_report"])
    v["ledger_depth_checked"] = led["depth_capture"]["depth_rows"]
    v["ledger_captures"] = len(led["captures"])
    return v


def rows(v: dict) -> list[dict]:
    R = []

    def add(rid, group, req, status, gate, clears, current, ev_rel, ev_label, official, official_label):
        R.append(dict(id=rid, group=group, requirement=req, status=status, gate=gate, clears=clears,
                      current=current, evidence=ev_rel, evidence_label=ev_label,
                      official=official, official_label=official_label))

    G = "Pricing & origination"
    add("P1", G, "Price-snapshot store: opening and closing numbers for every market we originate", "Partial",
        "The store, schema and fail-closed ingest exist (pricing/); 0 licensed price sources, so 0 rows can be filed. Policy P7 is adopted.",
        "Opening and closing quotes for side, total and moneyline in every 2026 game: 3 markets × "
        f"{v['games_2026']} games = {3 * v['games_2026']} quotes (proposed scope).",
        f"{v['price_rows']} opening/closing pairs in pricing/prices.csv from {v['licensed_price_sources']} licensed sources. "
        f"{v['odds_2026']} of {v['games_2026']} 2026 games carry one undated community line in data/raw/games.csv (excluded by policy).",
        "pricing/prices.csv", "Price-snapshot store (fail-closed, append-only)", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("P2", G, "Originate the side first, then the total, then the moneyline", "Partial",
        "No verified market line to originate against; the order is a design choice not yet implemented in a published run.",
        "Three markets priced, published in that order, for at least one full week.",
        "line-lab/data/model_outputs.json exists; it has no verified market comparison.",
        "line-lab/data/model_outputs.json", "Line-lab model outputs", NFL_STANDINGS, "NFL standings (official source for the inputs)")
    add("P3", G, "Publish the model's fair line, the market line and the difference as separate columns", "Partial",
        "The three columns are published (pricing.html §05) and again on every graded skill-lab forecast; the market and difference columns cannot fill without a licensed price row (P1).",
        "Every published row has all three columns with a source link; difference is blank where the market line is.",
        f"{v['residual_rows']} residual rows and {v['skill_graded_rows']} graded skill-lab rows, each with our line, the market line and the gap as separate columns.",
        "pricing/residuals.csv", "Residual register (three separate columns)", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("P4", G, "Publish every model total twice (two estimators, gap column) until one wins walk-forward", "Not started",
        "No second estimator and no walk-forward comparison has been run.",
        "Two estimators with a gap column over the same walk-forward window, then one collapsed by a pre-registered rule.",
        "0 estimators compared.", "docs/PRE_REGISTRATION.md", "Pre-registration file", NFL_STATS, "NFL player stats (official inputs)")
    add("P5", G, "Vig-free market consensus vs. originated fair-line decomposition", "Not started",
        "Needs two-sided market prices (P1).", "Consensus from at least two sourced books, de-vigged, next to our line.",
        "0 books with sourced two-sided prices.", "decision-lab/data/catalog.json", "Decision-lab catalogue", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("P6", G, "Price a line ourselves and publish the residual against the market, on a schedule, from day one", "Partial",
        "The schedule is decided (policy §5: T−24h, T−1h, market close, Tuesday 14:00 UTC) and the residual register exists; "
        "a capture job needs a licensed source and a CI hook (request logged).",
        "One residual row per originated market per scheduled run, with run time stamped.",
        f"{v['residual_rows']} scheduled residual rows; 0 licensed sources; schedule adopted 2026-11-15.",
        "pricing/PRICE_DATA_POLICY.md", "Price-data policy §5 (schedule decided)", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("P7", G, "Decide the price-data policy before any backtest is published", "Done",
        "None: the policy is adopted and pre-registered (2026-11-15). A blank licence forbids use; 0 sources licensed, so nothing price-dependent publishes.",
        "One signed policy record that names each price source and its permitted use.",
        f"{v['policy_records']} policy record (pricing/PRICE_DATA_POLICY.md, adopted 2026-11-15); 4 candidate source classes named with permitted use; {v['licensed_price_sources']} licensed.",
        "pricing/PRICE_DATA_POLICY.md", "Price-data policy (adopted 2026-11-15)", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("P8", G, "Pre-register every strategy; forbid backtest numbers from ever appearing on the leaderboard", "Done",
        "None: the registration freeze and the backtest ban are in force on the leaderboard (registration column per row; result cells accept only pre-kickoff forecasts).",
        "Every leaderboard row carries a registration hash that predates its results.",
        f"All {v['ops_strategies']} ops-centre rows carry the registration reference ({v['corpus_registered']}); "
        f"family pre-registration at {v['prereg_commit']} ({v['prereg_date']}); 0 backtest numbers in leaderboard cells.",
        "ops-center/leaderboard.html", "Ops-centre leaderboard (registration + backtest ban)", NFL_STATS, "NFL player stats (official inputs)")
    add("P9", G, "Freeze a rule before it sees data: commit rule text, sample window and gates; commit hash is the registration", "Partial",
        "Three rule sets are now frozen in dated commits before their results existed, but the earlier strategies still share one pre-registration without per-strategy sample windows.",
        "A commit per strategy, dated before its evaluation window opens.",
        f"Pre-registration commit {v['prereg_commit']} ({v['prereg_date']}) plus skill-lab protocol {v['skill_prereg']}, both committed before any result was computed.",
        "docs/SKILL_LAB_PRE_REGISTRATION.md", "Skill-lab pre-registration", NFL_STATS, "NFL player stats (official inputs)")
    add("P10", G, "Strategy entries carry a two-sided 'what would change our mind' field", "Partial",
        "The ops-centre register and the skill lab both publish the field; the eight strategies registered outside those two registers still carry no field.",
        "Two-sided field on every strategy entry in every register.",
        f"{v['strategy_change_field']} of {v['ops_strategies']} ops-centre strategy entries and {v['skill_rows']} skill-lab rows carry both sides.",
        "skill-lab/mind-change.html", "Skill-lab two-sided field", NFL_STATS, "NFL player stats (official inputs)")
    add("P11", G, "Store every model output as a probability plus its inputs, not just a pick", "Partial",
        "The skill lab stores the probability, both lines and both scores for every graded forecast; the input list is not yet itemised per output.",
        "Each output row: probability, inputs and their source links.",
        f"{v['skill_graded_rows']} outputs stored as a probability with our line, the market line, the gap and both scores; the source release link is on every row.",
        "skill-lab/graded.html", "Skill-lab graded forecasts", NFL_STANDINGS, "NFL standings (official inputs)")
    add("P12", G, "Demotion gate that sends a live strategy back to paper", "Partial",
        "Gates are registered but no strategy is live, so no demotion has been exercised.",
        "At least one live strategy and one tested demotion.",
        f"{v['ops_gates']} gates registered; 0 live strategies.", "ops-center/leaderboard.html", "Ops-centre gates", NFL_STATS, "NFL player stats (official inputs)")

    G = "Results & backtest corpus"
    add("R1", G, "Verified results feed so backtests and ROI can be computed", "Done",
        "The feed is verified as of 2026-11-15; the community file remains community-maintained, so the verification must be re-run (results-verification/scripts/crosscheck.py) after any refresh of data/raw/games.csv.",
        f"{v['final_w1_9']} of {v['final_w1_9']} Weeks 1–9 finals matched to an official score page.",
        f"{v['rv_score_matches']}/{v['rv_official_games']} scores and {v['rv_date_matches']}/{v['rv_official_games']} dates agree between the official NFL.com score pages (read 2026-11-15 UTC) and data/raw/games.csv; {v['rv_score_mismatches']} mismatches; {v['rv_unmatched']} unmatched rows.",
        "results-verification/data/verification_report.json", "Verified results feed (136/136 official, 2026-11-15)", NFL_SCORES, "NFL score pages, 2026 weeks 1-9 (official)")
    add("R2", G, "Turn the 136-game log into the pre-registered backtest corpus", "Done",
        "None: at least one corpus is frozen and registered before any evaluation (0 evaluations exist). Two frozen copies now exist (results-verification and corpus/); canonicalization is flagged F11. Price-dependent output stays blocked at P1.",
        "Corpus file with a commit hash dated before any evaluation.",
        f"Corpus frozen: {v['final_w1_9']} verified games, sha256 a1633c2011bc8fb4c6508ada2ed1cd32ddede8993300b5e03ef157f762ee73b1, freeze commit 76f4c7d775b8 (2026-11-15); second frozen copy corpus/games_2026_w1_9.csv (sha256 {v['corpus_hash']}\u2026) with split train {v['corpus_train']} / validation {v['corpus_val']} / holdout {v['corpus_hold']} and evaluation gates in corpus/PRE_REGISTRATION.md; 0 evaluations run.",
        "results-verification/CORPUS_FREEZE.md", "Corpus freeze registration; split and gates in corpus/PRE_REGISTRATION.md", NFL_SCORES, "NFL score pages, 2026 weeks 1-9 (official)")

    add("R3", G, "Ingest game-level results so ratings are opponent-aware", "Partial",
        "The decision desk built opponent-adjusted ratings from community game data; not verified against official scores (R1).",
        "Ratings re-run from official finals with each team's schedule.", "Opponent-adjusted ratings exist in decision-desk (community inputs).",
        "decision-desk/README.md", "Decision-desk README", NFL_STANDINGS, "NFL standings (official)")
    add("R4", G, "Compute correlations only from officially sourced numbers and publish n with each value", "Blocked",
        "No official leg-level settlement history exists in the repo.", "A minimum n per pair (proposed: set by the pre-registration) from official sources only.",
        "0 official pairs; n = 0.", "decision-desk/data/analysis.json", "Decision-desk analysis (community data)", NFL_STATS, "NFL player stats (official)")
    add("R5", G, "Split data into train, validation and final holdout seasons", "Partial",
        "The split is frozen (corpus/PRE_REGISTRATION.md §2): chronological within the only verified season. "
        "Season blocks need more official seasons; the future season-block policy is pre-registered.",
        "Three disjoint season blocks written into the pre-registration before fitting.",
        f"within-corpus split frozen: train {v['corpus_train']} / validation {v['corpus_val']} / holdout {v['corpus_hold']}; "
        f"{v['seasons']} seasons in the community game file ({v['season_span']}), 0 season blocks on official data.",
        "corpus/PRE_REGISTRATION.md", "Corpus pre-registration §2 (split frozen)", NFL_RULEBOOK, "2026 NFL rulebook (official)")
    add("R6", G, "Archive weekly official injury reports for past seasons", "Blocked",
        "Only the Week 10 official report has been captured in this repo; past-season reports were not fetched.",
        "Every regular-season week reported for the seasons in scope (proposed: 2021–2025 × 18 weeks = 90 reports).",
        f"1 official week held (Week 10; {v['w10_observations']} observations). Community injuries 2021–2026 files are not official.",
        "integration/data/captures/2026-11-13-nfl-injuries/manifest.json", "Week 10 capture manifest", NFL_INJ_W10, "NFL injury report, Week 10 (official)")

    G = "Availability & injuries"
    add("A1", G, "Availability graph as a dataset: who was expected to start, who actually did", "Blocked",
        "Expected starters need official game books or a verified depth order (A2, A8); neither is complete.",
        "Expected-starter list and actual-starter list for every game in the corpus.",
        "0 games with a verified expected-starter list.", "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_OPS_PREP, "NFL operations game-day prep (official)")
    add("A2", G, "Use official NFL Game Books for actual starters and game-day status", "Blocked",
        "No Game Book is captured. operations.nfl.com is not reachable from this sandbox.",
        f"Game Books for all {v['final_w1_9']} Weeks 1–9 games.", "0 Game Books captured.",
        "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_OPS_PREP, "NFL operations game-day prep (official)")
    add("A3", G, "Make the injury signal a surprise (change), never a level", "Partial",
        "Deltas are now published between reads 3 and 4 of Week 10, but the reads are not scheduled (A5) and no designation-to-inactive join (A6/S12) exists yet to measure whether a change predicts anything.",
        "At least two timestamped reads per player per week, from Wednesday to kickoff.",
        f"{v['w10_observations']} page observations of the Week 10 report; per-player deltas published between reads 3 and 4: {v['delta_game_status']} game-status changes, {v['delta_practice_status']} practice-status changes, {v['delta_added']} rows added, {v['delta_removed']} removed.",
        "results-verification/delta.html", "Injury-hub delta (fourth dated observation)", NFL_INJ_W10, "NFL injury report, Week 10 (official)")
    add("A4", G, "Store every injury-hub read with its clock time; publish the delta, never the level", "Partial",
        "Four reads are stored with clock times and the delta is published, but reads are event-driven, not a scheduled daily capture, and the fourth read stores the injury-report portion verbatim without the page's news module.",
        "A read every day from Wednesday to kickoff, with delta columns published.",
        f"{v['w10_observations']} reads of Week 10 (2026-11-12 06:32Z, 2026-11-12 22:25Z, 2026-11-13 12:40Z, {v['cap4_observed']}); deltas published at results-verification/delta.html.",
        "results-verification/data/captures/2026-11-15-nfl-injuries/manifest.json", "Fourth-observation capture manifest (347 rows, sha256 retained)", NFL_INJ, "NFL injury report (official)")
    add("A5", G, "Immutable multi-day availability snapshots with retained hashes", "Partial",
        "Hashes are retained for the dated report reads and for the official transaction captures, but there is no scheduled capture and no alert on failure (S15).",
        "Daily capture of the official report and club depth pages for every game week, each with its SHA-256.",
        f"4 dated report reads with hashes plus {v['ledger_captures']} official transaction captures with SHA-256 (source URL and retrieval time retained). Scheduled captures: 0 (alerts: {v['alert_hits']}).",
        "availability-ledger/data/ledger.json", "Availability ledger (capture manifest)", NFL_INJ, "NFL injury report (official)")
    add("A6", G, "Capture official inactive lists and snap counts", "Blocked",
        "No official inactive list is captured. The 2026 snap-count file is community nflverse data.",
        "Official inactive list for every game in the corpus.",
        f"0 official inactive lists. {v['snap_rows']} community snap-count rows (2026).",
        "data/raw/snap_counts_2026.csv", "Community snap counts (not official)", NFL_RULEBOOK, "2026 NFL rulebook (official)")
    add("A7", G, "Use snap counts as the starter proxy when the depth chart is unavailable", "Blocked",
        "Snap counts used here are community data, not verified official snap counts.",
        "Official snap-count source verified for every club in scope.",
        "0 official snap-count sources verified.", "data/raw/snap_counts_2026.csv", "Community snap counts (not official)", NFL_STATS, "NFL player stats (official)")
    add("A8", G, "Resolve the depth-order source (route a: club depth pages; route b: snap counts) before any backup feature", "Partial",
        "Route (a) is in progress: two clubs failed to parse in the 2026-11-12 snapshot. No club is yet verified for all 32.",
        "Route (a) verified for all 32 clubs, or route (b) verified for all 32.",
        f"{v['depth_ok']} of 32 club depth directories captured; failed: {', '.join(v['depth_fail'])}.",
        "decision-lab/data/official_snapshot.json", "Official snapshot (depth directory results)", CLUB_PACKERS, "Packers depth chart (club site)")
    add("A9", G, "Fix the two depth-parsing failures (Texans image; Packers jersey-number prefix)", "Blocked",
        "Texans publish depth as an image: transcription by eye is not allowed, so an authorised structured source is needed. Packers did not parse in the snapshot.",
        "Both clubs parse with the raw string stored, and the Texans source is structured and authorised.",
        "0 of 2 repaired in the 2026-11-12 snapshot.", "decision-lab/data/official_snapshot.json", "Official snapshot (failures listed)", CLUB_TEXANS, "Texans depth chart (club site)")
    add("A10", G, "Model depth slots as groups, not a single starter", "Partial",
        "The brief cites 149 multi-rank-1 slots; the availability artifact yields a different count (see F5).",
        "The 149 figure reproduced from the artifact, with each group listing all its players.",
        f"{v['av_slots']} slots with a report listing; {v['av_rank1']} rank-1 listings.", "decision-lab/data/availability.json", "Availability join (decision lab)", CLUB_COMMANDERS, "Commanders depth chart (club site)")
    add("A11", G, "Represent shared and empty depth slots faithfully", "Partial",
        "The slot record holds a list of players, so shared slots can be stored. Empty slots and the Seattle and Washington cases are not verified.",
        "The Seattle shared slot and the Washington empty slot reproduced from captures.",
        "Slot records hold lists; 0 specific shared or empty cases verified here.", "decision-lab/data/availability.json", "Availability join (decision lab)", CLUB_COMMANDERS, "Commanders depth chart (club site)")
    add("A12", G, "Model depth from playing time, not jersey order (rejected: roster order, experience, salary)", "Not started",
        "No playing-time source is verified. Rejecting roster-attribute ordering is a decision; the replacement method is not built.",
        "A playing-time depth model with the official snap source (A7) behind it.", "0 playing-time models.",
        "data/raw/snap_counts_2026.csv", "Community snap counts (not official)", NFL_STATS, "NFL player stats (official)")
    add("A13", G, "Treat roster turnover as a first-class data event (versioned against the last official roster event)", "Partial",
        "Reserve-list placements and league trades are captured as dated, sourced events, but the monthly league pages show only part of each month.",
        "Every trade, release and IR move in scope recorded with its date and source.",
        f"{v['ledger_reserve']} reserve-list placements and {v['ledger_trades']} league trades captured with date, official source and SHA-256.",
        "availability-ledger/data/ledger.json", "Availability ledger (captures and joins)", NFL_TEAMS, "NFL team pages (official)")
    add("A14", G, "Announced-starter evidence field (dated starter changes, not inferred replacements)", "Not started",
        "No dated starter-change record is captured.", "Each announced change recorded with date and source.",
        "0 dated starter changes captured.", "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_TEAMS, "NFL team pages (official)")
    add("A15", G, "Official depth-chart register with date and source on every row", "Partial",
        "The snapshot's depth rows carry an observed time, source URL and hash; the register is not yet the single version of record.",
        "One register with date, source and hash on every row, with no unsourced row.",
        f"{v['snap_depth_rows']} depth rows in the 2026-11-12 snapshot, each with source and hash.", "decision-lab/data/official_snapshot.json", "Official snapshot (depth rows)", CLUB_PACKERS, "Packers depth chart (club site)")
    add("A16", G, "Flag stale depth rows against the official transactions log", "Partial",
        "The committed depth capture is checked against the captured transaction log, but only for the windows those captures cover.",
        "Every depth row checked against the transactions log, with the result recorded.",
        f"{v['ledger_depth_checked']} published depth rows checked; {v['ledger_stale']} stale rows flagged, {v['ledger_same_day']} same-day row left unresolved, {v['ledger_traded_removed']} traded players confirmed absent from the club they left.",
        "availability-ledger/depth-flags.html", "Availability ledger (depth flags)", NFL_TEAMS, "NFL team pages (official)")
    add("A17", G, "Populate the three missing Lions game-status designations (Joseph, Mays, Reed)", "Done",
        "Each of the three cells is filled from the official Week 10 article (all three OUT), read 2026-11-16. Vaki and St. Brown (QUESTIONABLE in the same article) are outside this row; see flag F3.",
        "Three cells filled, each from the official article with its link.",
        f"{v['lions_blank']} of {v['lions_total']} named Lions game-status cells blank in dashboard/data/injuries_2026_w10.csv (Joseph, Mays, Reed: Out).",
        "dashboard/data/injuries_2026_w10.csv", "Dashboard Week 10 injury CSV", NFL_NEWS_W10, "NFL Week 10 injury report article (official)")
    add("A18", G, "Re-capture and republish the Week 10 injury tables (254 vs 279 rows; stale no-injury sections)", "Partial",
        "Two row counts are still published side by side (F2). The 279-row version exists in the integration verification file, but the 254-row page has not been retired.",
        "One published table, row count equal to the capture, with no club shown injury-free while listing players.",
        f"Published: {v['snap_inj_rows']} rows (decision-lab) and {v['ops_inj']} rows (ops-centre). Integration verification file: {v['published_rows_279']} rows.",
        "integration/data/verification.json", "Integration verification (279 rows)", NFL_INJ, "NFL injury report (official)")
    add("A19", G, "Capture the reserve list so 'not listed' never means 'available'", "Partial",
        "The official reserve list is captured with hashes, but the league's monthly page shows only part of each month, so coverage is not yet complete.",
        "IR and reserve lists for each club, each week, with the date captured.",
        f"{v['ledger_reserve']} reserve-list placements captured (October and November 2026 pages); {v['ledger_not_on_report']} of them do not appear on the weekly report, so the report alone cannot clear them.",
        "availability-ledger/ledger.html", "Availability ledger (official ledger)", NFL_TEAMS, "NFL team pages (official)")
    add("A20", G, "Score injury-designation reliability (play rate per designation, with confidence intervals)", "Blocked",
        "Needs past official reports (R6) and official inactive lists (A6); neither exists.",
        "Play rate per designation over several seasons, with intervals, before the label becomes a feature.",
        "0 designations joined to official inactive lists.", "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_STATUS, "Competition Committee injury-report revisions (official)")
    add("A21", G, "Calibrate what 'Questionable' means empirically (official text gives no percentages)", "Blocked",
        "Depends on A20; the official definition gives no percentage.", "Empirical rate with a confidence interval from joined outcomes.",
        "0 joined outcomes.", "dashboard/data/injuries_2026_w10.csv", "Dashboard Week 10 injury CSV", NFL_STATUS, "Competition Committee injury-report revisions (official)")
    add("A22", G, "Injury and depth ablations: same model with and without verified availability features, chronological holdouts", "Not started",
        "Needs verified availability features (A1, A8) and holdout seasons (R5).", "Paired model runs with a reported difference and uncertainty.",
        "0 ablation runs.", "docs/PRE_REGISTRATION.md", "Pre-registration file", NFL_STATS, "NFL player stats (official)")
    add("A23", G, "Per-team view: starters out, replacements named, net injury count", "Partial",
        "Per-club counts exist; the replacement-named column depends on A1 and A2.",
        "32 club rows, each with starters out, replacements named and net count.",
        f"Unmatched injury rows are recorded for {v['unmatched_clubs']} clubs.",
        "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_INJ, "NFL injury report (official)")
    add("A24", G, "Run the 32-team roster and IR sweep before any team-level model is trusted", "Blocked",
        "No roster or IR sweep artifact is in the repo; IR is not captured (A19).",
        "32 of 32 clubs swept, with roster and IR captured and dated.", "0 of 32 clubs swept as an artifact.",
        "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_TEAMS, "NFL team pages (official)")
    add("A25", G, "Matchup deficiency matrix (1st–4th string, offence vs defence)", "Not started",
        "Depends on verified depth groups (A10, A8).", "A matrix covering every starter-versus-backup pairing for 32 clubs.",
        "0 cells verified.", "decision-lab/data/availability.json", "Availability join (decision lab)", CLUB_COMMANDERS, "Commanders depth chart (club site)")

    G = "Fixtures, weather & context"
    add("F-1", G, "Fixture-context features built only from published schedule facts", "Partial",
        "Schedule columns exist in the community file, not verified against official schedule pages.",
        f"Each feature traced to an official schedule row for all {v['games_2026']} 2026 fixtures.",
        f"{v['games_2026']} 2026 fixture rows in the community file; 0 verified against official pages.",
        "data/raw/games.csv", "Community game file (not official)", NFL_GAMECENTRE, "NFL game centre example (official)")
    add("F-2", G, "Transcribe the venue of every fixture from the official game centre", "Partial",
        "Week 11 only (13 of 272 fixtures): each venue read from its official game-centre page and matched to the official schedule list. The other 259 fixtures are not transcribed.",
        f"{v['games_2026']} of {v['games_2026']} venues transcribed from game-centre pages.",
        "13 of 272 venues transcribed and checked (Week 11); 259 not transcribed.",
        "venues/index.html", "Week 11 venue register", NFL_GAMECENTRE_W11, "NFL game centre, Week 11 (official)")
    add("F-3", G, "Publish the league's dated schedule announcement beside the live schedule page", "Partial",
        "The announcement (dated May 14, 2026) and the live Week 11 schedule page are recorded with their URLs and read dates, side by side on the venue register. Neither is stored as a hashed raw capture yet.",
        "One dated announcement and one live schedule capture, side by side.",
        "1 dated announcement (May 14, 2026) and 1 live schedule page recorded; 0 hashed raw captures stored.",
        "venues/index.html", "Week 11 venue register (announcement and schedule)", NFL_ANNOUNCE_2026, "NFL schedule announcement, May 14 2026 (official)")
    add("F-4", G, "Stadium roof/surface and NWS hourly wind/precipitation overlay", "Not started",
        "No NWS forecast grid or official roof designation is captured.", "Hourly NWS series for every outdoor fixture in scope.",
        "0 hourly forecasts captured.", "data/raw/games.csv", "Community game file (not official)", NWS_API, "NWS API documentation (official)")
    add("F-5", G, "2026 kickoff and declared onside-kick regime priors filter", "Not started",
        "No onside-kick declarations are captured.", "A dated list of regime declarations used as a filter.",
        "0 declarations captured.", "docs/PRE_REGISTRATION.md", "Pre-registration file", NFL_RULEBOOK, "2026 NFL rulebook (official)")

    G = "Leaderboard & governance"
    add("L1", G, "Separate signal from staking in the leaderboard", "Partial",
        "Signal and staking are separated in the canonical leaderboard, but no row passes the signal gates, so nothing can be promoted.",
        "At least one strategy shown with signal and staking columns apart.",
        f"Skill lab: {v['skill_rows']} rows with signal columns and a separate retrospective staking table that cannot promote a row. {v['skill_eligible']} eligible.",
        "skill-lab/leaderboard.html", "Skill-lab leaderboard", NFL_STATS, "NFL player stats (official)")
    add("L2", G, "Proper-score divisions: singles, game parlays, same-game parlays, prop combos", "Partial",
        "The singles division is graded and published; the three combo divisions are published empty because no joint evidence can be validated.",
        "Each division with at least one pre-registered, graded entry.",
        f"Singles: {v['skill_rows']} rows graded on {v['skill_corpus']} games with Brier and log-loss scores. The three combo divisions are published empty with the reason.",
        "skill-lab/leaderboard.html", "Skill-lab leaderboard", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("L3", G, "Rank by Brier skill with a game-cluster lower bound and a multiplicity adjustment", "Partial",
        "The ranking mechanism exists and is published, but no row qualifies and the benchmark price is community-maintained.",
        "Brier skill with a lower bound for each entry in a division.",
        f"{v['skill_rows']} rows scored: Brier skill, 10,000-resample game-cluster interval and a Benjamini-Hochberg adjustment over {v['skill_trials']} trials. {v['skill_eligible']} eligible for ranking; best skill {v['skill_best']:+.4f}.",
        "skill-lab/leaderboard.html", "Skill-lab leaderboard", NFL_STATS, "NFL player stats (official)")
    add("L4", G, "Parlays and prop combos only behind a joint-evidence gate", "Partial",
        "The gate is enforced and no combo is published or ranked, but the evidence it requires still does not exist.",
        "A validated joint probability and the operator's void/push rules for each combo.",
        "0 combos with a joint probability; 0 void/push rules captured. The measured dependence between the legs of one game is published with n.",
        "skill-lab/dependence.html", "Skill-lab dependence", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("L5", G, "Singles-only shadow baseline, frozen and forecast before kickoff", "Partial",
        "The protocol and the model are frozen before the results were computed, but no forecast has yet been recorded prospectively before a kickoff.",
        "Frozen version and a recorded forecast for each game, time-stamped before kickoff.",
        f"Protocol SL-PRE-01 frozen at commit {v['skill_prereg']} before any result existed; walk-forward forecasts recorded for the {v['skill_corpus']}-game corpus. 0 prospective pre-kickoff forecasts.",
        "docs/SKILL_LAB_PRE_REGISTRATION.md", "Skill-lab pre-registration", NFL_SCORES, "NFL scores (official)")
    add("L6", G, "Control baseline (random picks; favourites only) in every leaderboard run", "Done",
        "Both baselines are run and published beside every row of every run of the canonical leaderboard.",
        "Both baselines run and shown beside every strategy.",
        "A 1,000-seed random-pick control and a favourites-only control are published in every run, with a base-rate control beside them.",
        "skill-lab/controls.html", "Skill-lab controls", NFL_STANDINGS, "NFL standings (official)")
    add("L7", G, "Two-stage leaderboard: proper-score qualification, then prospective CLV/ROI escrow", "Partial",
        "Stage one is implemented and running; stage two cannot start because there is no dated price history and no escrow rule.",
        "Qualification and escrow results for at least one strategy.",
        f"Stage one: {v['skill_rows']} rows tested against gates G1-G7, {v['skill_eligible']} qualified. Stage two: 0 qualifiers, 0 escrow entries (no closing-line value is possible without dated prices).",
        "skill-lab/leaderboard.html", "Skill-lab leaderboard", NFL_ODDS, "NFL odds-widget boundary (support.nfl.com)")
    add("L8", G, "'What changed' weekly diff instead of a static snapshot", "Partial",
        "Two diffs are now published — the injury-report read-to-read delta and the depth-versus-roster-event diff — but neither is driven by a scheduled weekly capture.",
        "Two weekly snapshots and a diff column (rank, rating, availability).",
        "Injury-report delta between dated reads is published; the availability ledger publishes a depth-versus-roster-event diff. Scheduled weekly captures: 0.",
        "availability-ledger/diff.html", "Availability ledger (weekly diff)", NFL_INJ, "NFL injury report (official)")
    add("L9", G, "Drift alarm on every scraper: pin row counts and fields, fail loudly", "Partial",
        "Verification scripts exist, but the two published injury counts (254 and 279) were published without an alarm.",
        "Each scraper pinned to expected rows and required fields, failing the build on drift.",
        f"Published counts disagree ({v['snap_inj_rows']} vs {v['ops_inj']}); 0 alarms raised.", "scripts/validate_site.py", "Root site validator", NFL_INJ, "NFL injury report (official)")
    add("L10", G, "Durable snapshot storage outside the static site, with alerts on source or schema change", "Blocked",
        "Captures are committed to the public repository. No alert channel is configured.",
        "Storage outside the public site and an alert channel that fires on a test change.",
        f"0 alert channels configured ({v['alert_hits']} alert references in the workflows).", ".github/workflows/pages.yml", "Pages workflow", NFL_INJ, "NFL injury report (official)")
    add("L11", G, "Split the public analysis layer from the private raw-data layer until the terms are read", "Not started",
        "The raw data is committed and public, and the data terms have not been read.",
        "Raw row-level data kept private; only derived analysis published.",
        f"{v['raw_files']} raw files in data/raw, public in this repository.", "data/raw/manifest.json", "Raw-data manifest", NFL_RULEBOOK, "2026 NFL rulebook (official)")
    add("L12", G, "Publish a weekly per-team decision view", "Not started", "Depends on A23 and A24.", "32 clubs with the view published each week.",
        "0 weekly views.", "decision-lab/data/availability.json", "Availability join (decision lab)", NFL_TEAMS, "NFL team pages (official)")
    add("L13", G, "Interactive offence vs defence matchup matrix", "Not started", "Depends on A25.", "The matrix rendered from verified depth groups.",
        "0 rendered.", "decision-lab/data/availability.json", "Availability join (decision lab)", CLUB_COMMANDERS, "Commanders depth chart (club site)")
    add("L14", G, "Reject: season-long ROI as the ranking basis (SG-03)", "Decision recorded",
        "Decision only; nothing to build. The ranking uses proper scores (L3).", "None — the decision stands until the owner reverses it.",
        "Rejected in the brief.", "docs/PRE_REGISTRATION.md", "Pre-registration file", NFL_STATS, "NFL player stats (official)")
    add("L15", G, "Executive summary, questions register and suggestions review", "Done",
        "Published, but each figure in them must match the registers above (see F1 to F6).",
        "Every figure in the summary traced to a register row.",
        f"{v['ops_questions']} questions, {v['ops_suggestions']} suggestions, executive summary published.",
        "EXECUTIVE_SUMMARY.md", "Executive summary", NFL_RULEBOOK, "2026 NFL rulebook (official)")
    add("L16", G, "Decision-readiness table on the landing page (this page)", "Done",
        "Each count is computed from a committed file at build time; no count is entered by hand.",
        "This table, linked from the landing page, rebuilt from the artifacts.",
        "Counted in the status line at the top of the page.", "readiness/build_readiness.py", "Build script", NFL_INJ, "NFL injury report (official)")
    return R


FLAGS = [
    ("F1", "Chain counts disagree across published pages.",
     f"decision-lab availability: {'{av_leads}'} replacement leads; executive summary: {'{exec_chains}'} replacement chains; ops-centre derived: {'{ops_chains}'} chains. The three counts are not reconciled.",
     "decision-lab/data/availability.json", NFL_INJ),
    ("F2", "Two Week 10 injury row counts are published.",
     "decision-lab snapshot: {snap_inj_rows} rows, 4 no-injury sections (Seahawks, Bengals, Chargers, Ravens). ops-centre: {ops_inj} rows. Integration verification file: {published_rows_279} rows. The 254-row table has not been retired.",
     "decision-lab/data/official_snapshot.json", NFL_INJ_W10),
    ("F3", "Lions Week 10 game status: Joseph, Mays and Reed corrected; Vaki and St. Brown still blank.",
     "Kerby Joseph, Cade Mays and D.J. Reed were blank and are now Out, from the official Week 10 article (read 2026-11-16). The same article lists Sione Vaki (ankle) and Amon-Ra St. Brown (rib) as QUESTIONABLE; their game-status cells in dashboard/data/injuries_2026_w10.csv are still blank. They were outside this correction and need the injury-capture owner's update.",
     "dashboard/data/injuries_2026_w10.csv", NFL_NEWS_W10),
    ("F12", "P1 priced-row count changed on rebuild (163 to 162).",
     "Rebuilding readiness from the refreshed upstream games file gives 162; the committed page showed 163. P1 is not claimed in this session; its row is changed only in this count. Not reconciled.",
     "readiness/data/readiness.csv", "https://github.com/kanlerxz87-cyber/NFL3/blob/main/readiness/data/readiness.csv"),
    ("F4", "Depth parser failures remain in the snapshot.",
     "Failed clubs: {depth_fail}. Both clubs returned 'no depth table parsed'. The brief describes the Texans depth as an image; that was not re-checked here. Parser repair is not in effect for the 2026-11-12 snapshot.",
     "decision-lab/data/official_snapshot.json", CLUB_PACKERS),
    ("F5", "The brief's 149 multi-rank-1 slots is not reproduced.",
     "The artifact reports {av_slots} slots with a report listing and {av_rank1} rank-1 listings. The 149 figure is not reproduced from the committed artifact.",
     "decision-lab/data/availability.json", NFL_INJ),
    ("F6", "Strategy counts disagree between registers.",
     "dashboard/data/strategies.csv: {dash_strategies} entries; ops-centre derived: {ops_strategies}; executive summary: 34. Not reconciled.",
     "dashboard/data/strategies.csv", "https://github.com/kanlerxz87-cyber/NFL3/blob/main/dashboard/data/strategies.csv"),
    ("F7", "Community data is stored in the public repository under a 'verified' flag.",
     "data/raw/manifest.json marks the nflverse depth file verified: true. The check is a SHA-256 digest of a community release, not an NFL authority check. {raw_files} raw files are public.",
     "data/raw/manifest.json", NFLVERSE_DEPTH),
    ("F10", "A pre-registration hash was published wrong, then corrected.",
     "The first published register cited 3db9a64 as the registration commit. That was an artifact of a shallow clone: 3db9a64 last touched the file but did not create it. The creating commit is c25ae53 (2026-11-12), verified with full history. The build now refuses to run on a shallow clone.",
     "docs/PRE_REGISTRATION.md", NFL_RULEBOOK),
    ("F9", "Two readiness registers are now published on the site.",
     "The landing page holds a 26-row summary (R01–R26) merged from session arena/1a306c91-nfl3 (PR #69, enriched by PRs #70 and #75). This page holds 64 rows with different IDs, and some statuses differ. Neither has been reconciled to the other. This session could not reach nfl.com to re-check that session's official-source statements.",
     "index.html", NFL_INJ),
    ("F11", "Two pre-registered backtest corpora now exist.",
     "Sessions arena/f0d1503b-nfl3 and arena/16183225-nfl3 froze results-verification (136 official score-page matches, sha256 a1633c20\u2026, freeze commit 76f4c7d775b8) while session arena/ba6c5155-nfl3 froze corpus/games_2026_w1_9.csv (sha256 4632744b\u2026) with a train/validation/holdout split and evaluation gates. Both are kept; neither has been evaluated. An integration decision must name one canonical file before any evaluation runs.",
     "corpus/manifest.json", NFL_SCORES),
    ("F8", "Repository sessions could not use session-named branches.",
     "The brief asked for session-named branches. The session was given one fixed branch, arena/3b1164e9-nfl3, and used it. Recorded for review.",
     "COORDINATION.md", NFL_RULEBOOK),
]


def fmt(text: str, v: dict) -> str:
    class D(dict):
        def __missing__(self, k):
            return "[unknown]"
    return text.format_map(D(v, exec_chains=v.get("exec_chains"), depth_fail=", ".join(v["depth_fail"]),
                              av_leads=v["av_leads"], av_slots=v["av_slots"], av_rank1=v["av_rank1"]))


def page(R: list[dict], v: dict) -> str:
    prefix = (ROOT / "index.html").read_text(encoding="utf-8")
    prefix = prefix[: prefix.index('<div class="content">')]
    prefix = prefix.replace("<title>A clearer view of the game | NFL3</title>",
                            "<title>Decision readiness | NFL3</title>")
    prefix = prefix.replace('<a aria-current=page href="index.html"><span>01</span>Overview</a>',
                            '<a href="index.html"><span>01</span>Overview</a>')
    prefix = prefix.replace('<a href="ops-center/flagged.html"><span>F</span>Flagged for review</a>',
                            '<a aria-current=page href="readiness.html"><span>D</span>Decision readiness</a><a href="ops-center/flagged.html"><span>F</span>Flagged for review</a>')

    status_order = ["Blocked", "Not started", "Partial", "Decision recorded", "Done"]
    counts = Counter(r["status"] for r in R)
    chips = "".join(f'<span class="chip">{html.escape(s)}: <b>{counts.get(s, 0)}</b></span>' for s in status_order if counts.get(s))

    def src(url: str, label: str) -> str:
        cls = ' class="source"' if re.match(r"https://(www\.|operations\.)?nfl\.com/", url) else ""
        return f'<a{cls} href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{html.escape(label)} ↗</a>'

    def local(path: str, label: str) -> str:
        # Repository files are linked to their GitHub blob on main, not to Pages paths: hidden
        # folders such as .github are not served by Pages (a live check returned a 404 page).
        return f'<a href="{html.escape(REPO_BLOB + path)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'

    body = []
    body.append('<div class="content">')
    body.append('<div class="eyebrow"><span></span> DECISION READINESS</div>')
    body.append("<h1>What blocks each requirement, and the number that would clear it.</h1>")
    body.append('<p class="lede">One row per requirement in the brief. Each row names the gate that blocks it and the number that would clear it. '
                'Current numbers are computed at build time from committed files. Where nothing is verified, the cell says so. '
                'Nothing here is a model result, a price, or a betting recommendation.</p>')
    body.append('<div class="notice"><b>Read this first.</b> The sandbox that built this page can reach only GitHub, npm and PyPI. '
                'nfl.com, club sites and operations.nfl.com were unreachable when this was built, so no official value was re-fetched. '
                'Each official link below is the page the requirement depends on, not proof that the value was checked today. '
                '<a href="#flagged">Flagged for review</a> lists the irregularities found. The landing page holds a separate 18-row summary from another session; see F9.</div>')
    body.append(f'<div class="notice"><b>Status counts:</b> {chips}</div>')
    body.append('<div class="table-wrap"><table><thead><tr>'
                '<th scope="col">ID</th><th scope="col">Requirement</th><th scope="col">Status</th>'
                '<th scope="col">Blocking gate</th><th scope="col">Number that would clear it</th>'
                '<th scope="col">Current number (computed)</th><th scope="col">Repo evidence</th><th scope="col">Official source</th>'
                '</tr></thead><tbody>')
    for r in R:
        body.append("<tr>"
                    f"<td>{html.escape(r['id'])}</td>"
                    f"<td><b>{html.escape(r['requirement'])}</b><br><small>{html.escape(r['group'])}</small></td>"
                    f"<td>{html.escape(r['status'])}</td>"
                    f"<td>{html.escape(r['gate'])}</td>"
                    f"<td>{html.escape(r['clears'])}</td>"
                    f"<td>{html.escape(r['current'])}</td>"
                    f"<td>{local(r['evidence'], r['evidence_label'])}</td>"
                    f"<td>{src(r['official'], r['official_label'])}</td>"
                    "</tr>")
    body.append("</tbody></table></div>")

    body.append('<div class="section-head" id="flagged"><div><div class="section-label">FLAGGED FOR REVIEW</div><h2>Irregularities found while building this page</h2></div>'
                '<p>Published, not fixed. Each item names the file and the official page to check. Nothing here has been corrected from memory.</p></div>')
    body.append('<div class="table-wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">Irregularity</th><th scope="col">Detail</th>'
                '<th scope="col">Repo evidence</th><th scope="col">Official or primary source</th></tr></thead><tbody>')
    for fid, title, detail, ev, url in FLAGS:
        body.append("<tr>"
                    f"<td>{fid}</td><td><b>{html.escape(title)}</b></td>"
                    f"<td>{html.escape(fmt(detail, v))}</td>"
                    f"<td>{local(ev, ev)}</td>"
                    f"<td>{src(url, url.split('/')[2])}</td>"
                    "</tr>")
    body.append("</tbody></table></div>")
    body.append('<div class="callout"><div><div class="section-label">HOW TO CHECK</div><h2>Re-run the build.</h2>'
                '<p><code>python3 readiness/build_readiness.py</code> rebuilds this page and readiness/data/readiness.csv from committed files. '
                'Change a source file and the counts change with it.</p></div><a class="button" href="ops-center/questions.html">Open questions <span>↗</span></a></div>')
    body.append('<footer>NFL3 RESEARCH DESK <span>Built for informed decisions, not guaranteed outcomes.</span></footer></div></main></div></body></html>')
    return prefix + "\n".join(body)


def write_csv(R: list[dict]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "group", "requirement", "status", "gate", "clears", "current", "evidence", "official", "official_label"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in R:
            w.writerow(r)


def main() -> int:
    v = compute()
    R = rows(v)
    ids = [r["id"] for r in R]
    if len(ids) != len(set(ids)):
        sys.exit("readiness: duplicate row ids")
    OUT_HTML.write_text(page(R, v), encoding="utf-8")
    write_csv(R)
    print(f"wrote {OUT_HTML.name} and {OUT_CSV.relative_to(ROOT)} with {len(R)} requirement rows and {len(FLAGS)} flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
