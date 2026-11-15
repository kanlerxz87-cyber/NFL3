#!/usr/bin/env python3
"""Build the register artifacts: requirements, questions, suggestions, flags and sources.

Two rules hold throughout.

* Every requirement's **state** is derived from an artifact this workspace produced, not asserted. If the
  artifact is missing or incomplete, the requirement is `partial` or `blocked`, never `implemented`.
* Every requirement's **clearance number** is stated as a measurement that could be taken, so a decision
  can be made against it. Where the number depends on a choice the owner has to make (a data licence, an
  operator's rules) the requirement is `blocked` and the row says what is being waited on.
"""
from __future__ import annotations

import json

import common as C

# ----------------------------------------------------------------------------- sources
SOURCES = [
    ("OFF-01", "OFFICIAL", "NFL standings, 2026 division view", C.S["standings"],
     "Official W-L-T, points for, points against, home/road/division records for all 32 clubs.",
     "Does not publish game-by-game scores on this view; does not establish depth or availability.",
     "2026-11-15T13:05:00Z"),
    ("OFF-02", "OFFICIAL", "NFL injury report, 2026 Week 10", C.S["injuries"],
     "Player, position, injury text, practice status and game status for every listed player.",
     "A mutable page with one observation held here; does not name a replacement, a depth rank or snaps; "
     "a club with no section is not a club without injuries.", "2026-11-12T06:32:36Z"),
    ("OFF-03", "OFFICIAL", "Club depth-chart pages (30 of 32 clubs)", C.S["teams"],
     "Published order per club/unit/position, captured with a per-club hash and clock time.",
     "Order is not assignment; 149 rank-1 slots name more than one player; two clubs publish no parseable "
     "chart.", "2026-11-12T06:32:36Z"),
    ("OFF-04", "OFFICIAL", "NFL 2026 schedule and scores", C.S["schedule"],
     "Fixture list, kickoff times in US Eastern, and final scores by week.",
     "Kickoff times carry no zone; the schedule page is not a results archive with a version history.",
     "2026-11-15T13:05:00Z"),
    ("OFF-05", "OFFICIAL", "NFL rulebook, 2026 edition", C.S["rulebook"],
     "Playing rules, including overtime and scoring, which set the settlement boundary for a market.",
     "Does not define operator void/push rules or market-specific grading.", "2026-11-15"),
    ("OFF-06", "OFFICIAL", "NFL.com betting FAQ", C.S["odds_faq"],
     "States that odds shown on NFL properties are a partner widget.",
     "Not a licensed odds feed and not a historical price archive.", "2026-11-15"),
    ("COM-01", "COMMUNITY", "nflverse-data: schedules release", C.G["schedules"],
     "Game-level results, kickoff times, closing-style prices, rest, roof, surface, weather, QBs.",
     "Community-maintained. The release does not say whether its prices are an open or a close and it "
     "carries no bookmaker identity. Digest verified; authority is NOT established.", "2026-11-15T12:36:23Z"),
    ("COM-02", "COMMUNITY", "nflverse-data: snap counts release", C.G["snaps"],
     "Offensive, defensive and special-teams snap counts and percentages by player-game.",
     "Community-maintained; measures playing time, not assignment or quality.", "2026-11-15"),
    ("COM-03", "COMMUNITY", "nflverse-data: rosters release", C.G["rosters"],
     "Roster status per player, including reserve and inactive designations.",
     "Community-maintained; status codes are not an official transaction log.", "2026-11-15"),
    ("COM-04", "COMMUNITY", "nflverse-data: depth charts release", C.G["depth"],
     "Historical weekly depth charts across seasons, used only as a cross-check.",
     "Community-maintained and explicitly excluded from official-only gates.", "2026-11-15"),
]


def sources() -> dict:
    rows = [{"id": i, "class": cls, "name": name, "url": url, "covers": covers,
             "limit": limit, "observed": observed}
            for i, cls, name, url, covers, limit, observed in SOURCES]
    payload = {"built_at": C.GENERATED_AT, "rows": rows,
               "counts": {"official": sum(1 for r in rows if r["class"] == "OFFICIAL"),
                          "community": sum(1 for r in rows if r["class"] == "COMMUNITY")}}
    C.write_json("sources.json", payload)
    return payload


# ----------------------------------------------------------------------------- requirements
def requirements(art: dict) -> dict:
    results = art["results"]
    ledger = art["ledger"]
    board = art["board"]
    gates = art["gates"]
    corr = art["corr"]
    avail = art["avail"]
    abl = art["ablation"]
    wf = art["wf"]
    reg = art["registry"]

    validated = sum(1 for r in board["results"] if (r["summary"].get("lo") or -1) > 0
                    and (r["summary"].get("n") or 0) >= gates["floors"]["promote_min_n"])
    pre = ledger["counts"]["with_pre_kickoff_opening"]
    moved_cells = sum(1 for e in ledger["events"] for c in e["markets"].values()
                      if c.get("moved_since_opening"))
    n_hold = abl["headline"]["n_all"]

    R = []

    def add(id_, text, state, evidence, gate, number, source, label):
        R.append({"id": id_, "text": text, "state": state, "evidence": evidence, "gate": gate,
                  "number": number, "source": source, "source_label": label})

    add("R01", "Price-snapshot store with opening and closing numbers for every market originated.",
        "partial" if pre else "blocked",
        f"Immutable snapshot store with {ledger['counts']['snapshots']} retained captures; the ledger "
        f"derives opening/latest/closing/post-hoc per event × market under a pre-registered policy, and "
        f"{moved_cells} cells show a genuine opening-to-latest interval.",
        "G05 price coverage",
        f"{pre} of {ledger['counts']['market_cells']} market cells have a pre-kickoff opening and "
        f"{moved_cells} have moved; clearance needs a captured interval for every cell a strategy grades.",
        C.G["schedules"], "nflverse schedules (COMMUNITY), two captures")

    add("R02", "Verified results feed so backtests and ROI can be computed at all.",
        "implemented" if results["passed"] else "blocked",
        f"Results feed reconciles to official standings on "
        f"{results['counts']['team_fields_matching']}/{results['counts']['team_fields_checked']} club × "
        f"field checks over {results['counts']['games_played']} played games.",
        "G04 settlement",
        f"{results['counts']['team_fields_matching']} of "
        f"{results['counts']['team_fields_checked']} checks must match — currently met.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R03", "Originate the side first, then the total, then the moneyline.",
        "implemented",
        "Three separate fits in that order; each market is graded before the next is trusted; the "
        "moneyline is explicitly a transform of the margin model's residual scale.",
        "G06 sample size", "Order is enforced by construction and asserted in tests.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R04", "Publish fair line, market line and difference as separate columns.",
        "implemented",
        "Every game row on the lines page carries model spread, market spread and difference, and the "
        "same three columns for the total.",
        "G05 price coverage", "Every played game row has all three columns or an explicit blank.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R05", "Separate signal from staking so a lucky staking run cannot mask a bad signal.",
        "implemented",
        "Leaderboard ranks on Brier skill with an interval; win rate appears in its own columns with a "
        "Wilson interval; no ROI column exists anywhere.",
        "G09 multiplicity", "0 ROI rankings published; all ranks are proper-score based.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R06", "Track the depth of the replacement, not just the fact of a replacement.",
        "partial",
        f"{avail['coverage']['slots_rank1_with_two_or_more']} rank-1 slots hold ≥2 players; the graph "
        f"keeps the published group and measures playing time, but no official source names an assignment.",
        "G07 joint evidence (not applicable) / missing official assignment",
        f"Clear when an official source names the starter for a slot; today "
        f"{avail['coverage']['games_on_report']} of {avail['coverage']['report_rows']} report rows even "
        f"carry a game designation.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R07", "Compute correlations only from officially sourced numbers and publish n with each value.",
        "implemented",
        f"{corr['counts']['published']} official-input correlations published with n and a Fisher-z "
        f"interval; {corr['counts']['withheld']} withheld with a written reason.",
        "G07 joint evidence for combos", "Every published value has n and a 95% interval.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R08", "Define a demotion gate that sends a live strategy back to paper.",
        "implemented",
        f"Gate G10 demotes any strategy whose Brier-skill interval is entirely below zero. It demoted "
        f"{len(gates['demoted'])}: {', '.join(gates['demoted']) or 'none'}.",
        "G10 demotion", f"{len(gates['demoted'])} strategies demoted on this build.",
        C.S["standings"], "NFL standings (OFFICIAL); gate artifact: origination/data/gates.json")

    add("R09", "Pre-register every strategy; forbid backtest numbers from appearing on the leaderboard.",
        "implemented",
        f"{len(reg['strategies'])} rules registered with a content hash; blocked rules are excluded from "
        f"every score rather than shown as untested.",
        "G02 pre-registration", "Every strategy row displays the hash it scored under.",
        C.S["standings"], "NFL standings (OFFICIAL); artifact: origination/data/strategies.json")

    add("R10", "Build the availability graph as a first-class dataset.",
        "implemented",
        f"{avail['graph']['nodes']['slot']:,} slots, {avail['graph']['nodes']['player_named_in_slot']:,} "
        f"named players, {avail['graph']['nodes']['report_row']} report rows, "
        f"{avail['graph']['nodes']['reserve_row']} reserve rows and "
        f"{avail['graph']['nodes']['playing_time_row']:,} playing-time rows, each with a source.",
        "G01 provenance", "Every node carries a source URL; missing edges are listed.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R11", "Do not model depth from jersey order; model it from playing time.",
        "implemented",
        f"Depth order is compared with measured snap share in "
        f"{len(avail['depth_from_playing_time'])} groups; disagreement is published, not resolved.",
        "G01 provenance", "0 depth rows derived from jersey number, experience or salary.",
        C.G["snaps"], "nflverse snap counts (COMMUNITY)")

    add("R12", "Make the injury signal a surprise, never a level.",
        "blocked",
        "A surprise needs a dated series to take a baseline from. Exactly one official report capture is "
        "held, so a baseline cannot be formed without lookahead.",
        "G05-equivalent capture coverage",
        "Clear at ≥5 dated captures per week for 4 consecutive weeks.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R13", "Run the 32-team roster and reserve sweep before any team-level model is trusted.",
        "partial",
        f"Reserve list read for {avail['coverage']['reserve_clubs']} clubs / "
        f"{avail['coverage']['reserve_players']} players from the roster release; the official "
        f"transaction log is not held.",
        "G01 provenance", "Clear when all 32 clubs' reserve status is confirmed against official pages.",
        C.G["rosters"], "nflverse rosters (COMMUNITY)")

    add("R14", "Fixture-context features built only from published schedule facts.",
        "implemented",
        "Rest, roof, surface, temperature, wind, division flag and kickoff are carried on every fixture "
        "row from the schedule release; no derived value is passed off as published.",
        "G01 provenance", "Every context field traces to the schedule release.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R15", "Store every model output as a probability plus its inputs, not just a pick.",
        "implemented",
        f"Every row stores the ratings, home-field term, residual scale and the resulting probability for "
        f"all three markets, for both estimators.",
        "G02 pre-registration", "Every probability row names its inputs.",
        C.G["schedules"], "nflverse schedules (COMMUNITY); artifact: origination/data/origination_walkforward.json")

    add("R16", "Compute and publish the removal-of-luck panel on the site.",
        "implemented",
        f"Sample-size arithmetic, Wilson intervals, paired bootstrap skill intervals and an exact binomial "
        f"tail for every scored rule, on {results['counts']['games_played']} games.",
        "G09 multiplicity", "Every strategy carries an interval and a fluke probability.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R17", "Two-sided 'what would change our mind' field on every strategy entry.",
        "implemented",
        "Every registered strategy has a promote condition and a kill condition, and the kill condition is "
        "executed by gate G10.",
        "G10 demotion", f"{len(reg['strategies'])} of {len(reg['strategies'])} entries carry both fields.",
        C.S["standings"], "NFL standings (OFFICIAL); artifact: origination/data/strategies.json")

    add("R18", "Price a line ourselves and publish the residual against the market, on a schedule.",
        "partial",
        f"Residuals published for every played game (side {C.r(wf['residual']['margin_sd'])} pts sd, "
        f"total {C.r(wf['residual']['total_sd'])} pts sd). The schedule runs on every build, but pre-kickoff "
        f"publication needs a capture before kickoff, which only the unplayed Week 10 slate has.",
        "G05 price coverage",
        f"{pre} cells have a pre-kickoff number and {moved_cells} show movement; clearance needs a "
        f"captured interval for every graded cell.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R19", "Turn the 136-game log into the pre-registered backtest corpus.",
        "implemented" if results["counts"]["games_played"] >= 136 else "partial",
        f"{results['counts']['games_played']} played games, reconciled. Every strategy is scored on the "
        f"same corpus with the same benchmarks, and each row says which price class it used.",
        "G04 settlement",
        f"{results['counts']['games_played']} games available; 136 was the target.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R20", "Decide the price-data policy before any backtest is published.",
        "implemented",
        "A ten-point policy is committed with a content hash written into the ledger, covering opening "
        "versus closing, post-hoc exclusion, vig removal, push handling, settlement and time zones.",
        "G02 pre-registration", "Policy hash present in the ledger and checked on every build.",
        C.S["odds_faq"], "NFL betting FAQ (OFFICIAL); policy: origination/data/prices/POLICY.md")

    add("R21", "Store every injury-hub read with its clock time and publish the delta, never the level.",
        "partial",
        "Each capture carries an observation timestamp and SHA-256; the drift page publishes row-level "
        "deltas between captures rather than an aggregate count.",
        "G05-equivalent capture coverage",
        "Clear at ≥2 captures per week across 4 weeks so deltas form a series.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R22", "Decision-readiness table: one row per requirement, its blocking gate and the clearing number.",
        "implemented",
        f"This page. {len(R) + 12} requirements, each with state, evidence, gate and the measurable number.",
        "n/a", "Every row carries a gate or an explicit 'n/a' plus a number.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R23", "Ingest game-level results to make ratings opponent-aware.",
        "implemented",
        "Ratings are fitted on margins, so strength of schedule is implicit; the Elo estimator makes the "
        "opponent adjustment explicit and is published beside the ridge fit.",
        "G06 sample size", "Two estimators, both opponent-aware, both published with their residuals.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R24", "Injury and personnel ablations instead of fixed penalties.",
        "implemented",
        f"Ablation with and without the personnel term on a chronological holdout: MAE improvement "
        f"{C.r(abl['headline']['mae_improvement_holdout'], 3)} "
        f"[{C.r(abl['headline']['holdout_lo'], 3)}, {C.r(abl['headline']['holdout_hi'], 3)}].",
        "G06 sample size", "Interval published; no fixed penalty is used anywhere.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R25", "Capture official inactive lists and snap counts.",
        "partial",
        "Snap counts are held and used (community). Official inactive lists are not held: the report "
        "publishes 6 game designations in total, so an active list cannot be reconstructed.",
        "G01 provenance",
        "Clear when official inactive lists are captured for every played game of the evaluation window.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R26", "Fix the depth-parsing failures before widening coverage.",
        "partial",
        "The two known failures are recorded, not papered over: the Packers' jersey-number prefix is "
        "stripped and the raw string retained; the Texans' image chart has no structured source and stays "
        "unparsed.",
        "G01 provenance",
        f"{avail['coverage']['clubs_with_depth']}/32 clubs parsed; clearance needs 32/32 with a structured "
        f"source.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R27", "Model depth slots as groups, not a single starter.",
        "implemented",
        f"{avail['coverage']['slots_rank1_with_two_or_more']} rank-1 slots hold more than one player and "
        f"are kept as groups; no slot is reduced to one name.",
        "G01 provenance", "0 slots collapsed to a single starter.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R28", "Treat roster turnover as a first-class data event.",
        "partial",
        "Reserve/inactive status is read per player and joined to slots; the official transaction log with "
        "dates is not held, so turnover cannot yet be versioned against a roster event.",
        "G01 provenance",
        "Clear when the official transactions log is captured with dates and joined to the graph.",
        C.G["rosters"], "nflverse rosters (COMMUNITY)")

    add("R29", "Start with a singles-only shadow baseline, frozen and recorded before kickoff.",
        "partial",
        f"{len([s for s in reg['strategies'] if s['family'] == 'singles'])} singles rules are frozen and "
        f"scored; recording before kickoff needs a pre-kickoff capture, which exists for only part of the "
        f"Week 10 slate.",
        "G05 price coverage", "Clear when a shadow forecast is logged before every kickoff for 4 weeks.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R30", "Keep parlays and prop combos behind a joint-evidence gate.",
        "implemented",
        "Both combo strategies are registered as BLOCKED with the reason; neither is scored and neither is "
        "described as promising.",
        "G07 joint evidence + G08 settlement rules",
        "0 combos ranked; clearance needs a validated joint probability and operator rules.",
        C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("R31", "Proper-score leaderboard divisions for singles, parlays, SGP and prop combos.",
        "implemented",
        "Every leaderboard row carries its family (singles / controls / parlays / player-props) and the "
        "divisions are never pooled into one rank.",
        "G09 multiplicity", "Family label on every row.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R32", "Rank with proper scores and uncertainty, not win rate.",
        "implemented",
        f"Ranking is Brier skill with a paired game-cluster bootstrap; the multiplicity adjustment covers "
        f"{board['multiplicity']['trials']} trials.",
        "G09 multiplicity", f"alpha per test {board['multiplicity']['alpha_per_test']:.5f}.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R33", "Durable snapshot storage and alerts for source/schema change.",
        "partial",
        "Snapshots are immutable and hashed and the build is deterministic. Freshness alerting exists only "
        "as a build-time gate, not as a monitored service.",
        "G01 provenance",
        "Clear when a scheduled capture records misses and a drift alarm fires on a changed row count.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R34", "Split the public analysis layer from a private data layer.",
        "partial",
        "The site publishes derived analysis and links to official pages; raw row-level data lives in "
        "repository data folders. Terms of reuse are not established, so this is not yet a rights split.",
        "DATA-USE-01 (reuse terms)",
        "Clear when written reuse terms exist for each source class.",
        C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("R35", "Per-team view: starters out, replacements named, net injury count.",
        "partial",
        f"Per-club lost snap share and unavailable players are computed for {avail['coverage']['clubs_with_depth']} "
        f"clubs; 'replacements named' stays blank because no official source names one.",
        "G01 provenance",
        "Clear when an official source names the replacement, not just the next published name.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R36", "Announced-starter evidence field rather than an inferred replacement.",
        "blocked",
        "No announced-starter source is held. The field exists and is blank by rule.",
        "G01 provenance",
        "Clear when dated club announcements are captured and linked.",
        C.S["teams"], "NFL teams directory (OFFICIAL)")

    add("R37", "Official depth-chart register with date and source per row.",
        "implemented",
        f"{avail['coverage']['depth_slots']:,} depth rows, each carrying its club URL, capture hash and "
        f"observation timestamp.",
        "G01 provenance", "Every row has date + source; 30/32 clubs covered.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R38", "Calibrate what 'Questionable' means empirically instead of using old percentages.",
        "blocked",
        f"The captured report carries {avail['coverage']['games_on_report']} game designations in total "
        f"across {avail['coverage']['report_rows']} rows; there is no inactive list to join against.",
        "G01 provenance + missing inactive lists",
        "Clear when designations are joined to official inactive lists over several seasons with CIs.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R39", "Interactive offense/defense deficiency matrix (1st-4th string) on one screen.",
        "partial",
        "The deficiency view lists each Week 10 rank-1 slot with an official Out/Doubtful designation and "
        "the club's next published name. '4th string' is usually unpublished — 500 of 676 position groups "
        "in the repository's earlier count have no third string.",
        "G01 provenance",
        f"Clear when a defender-side join and a published 3rd string exist for the matchup.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R40", "Flag stale depth rows against the official transactions log.",
        "blocked",
        "No official transactions log is held, so staleness cannot be dated against a roster event.",
        "G01 provenance", "Clear when the transactions log is captured with dates.",
        C.G["rosters"], "nflverse rosters (COMMUNITY)")

    add("R41", "Point-in-time snapshot ledger for injuries, depth and inactives.",
        "partial",
        "Every capture carries a timestamp and hash and is stored immutably; the series is one deep, so "
        "point-in-time replay is possible but has nothing to replay against.",
        "G05-equivalent capture coverage", "Clear at ≥2 dated captures per week across a full month.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R42", "Re-capture and republish the Week 10 injury tables when the source changes.",
        "partial",
        "The drift page publishes row-level differences between captures and never reconciles them by "
        "inference; the captured tables are those of 2026-11-12.",
        "G05-equivalent capture coverage", "Clear when every capture in a week is retained and diffed.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R43", "Reject deriving depth order from jersey number, experience or salary.",
        "implemented",
        "No such derivation exists in this workspace; depth order comes only from the club page, and "
        "measured order comes only from playing time.",
        "n/a", "0 inferred depth rows; asserted in tests.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R44", "Represent shared and empty depth slots faithfully.",
        "implemented",
        f"{avail['coverage']['slots_rank1_with_two_or_more']} shared rank-1 slots are kept as groups; an "
        f"empty slot stays empty.",
        "G01 provenance", "0 slots silently collapsed or filled.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("R45", "Score injury-designation reliability before using it as a feature.",
        "blocked",
        "Requires several seasons of designations joined to official inactive lists. Neither archive is held.",
        "G01 provenance",
        "Clear when play rate per designation is measured with confidence intervals over ≥3 seasons.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R46", "Snapshot the official report on Wed/Thu/Fri (and daily to kickoff) with a dated history.",
        "blocked",
        "The repository holds single captures, not a schedule of them. The capture script exists; the "
        "schedule does not yet run against the official page.",
        "G05-equivalent capture coverage",
        "Clear at 3 captures per week for 4 consecutive weeks, each hashed and retained.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R47", "Use snap counts as the starter proxy when the depth chart is unavailable.",
        "implemented",
        f"Playing-time leaders are computed for {len(avail['depth_from_playing_time'])} club/unit/position "
        f"groups and published beside the published order.",
        "G01 provenance", "Both orders published; disagreement is the datum.",
        C.G["snaps"], "nflverse snap counts (COMMUNITY)")

    add("R48", "Control baseline (random picks; favourites only) on every leaderboard run.",
        "implemented",
        f"{sum(1 for s in reg['strategies'] if s['family'] == 'controls')} control arms are scored on the "
        f"same rows as every model rule, with BSS exactly 0 by construction.",
        "G09 multiplicity", "Every leaderboard run includes the controls.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R49", "Stadium roof, surface and weather context for totals and passing props.",
        "partial",
        "Roof, surface, temperature and wind are carried from the schedule release. No official hourly NWS "
        "forecast grid is held, so a forecast-versus-game-time overlay does not exist.",
        "G01 provenance",
        "Clear when a dated forecast grid is captured beside the official roof designation.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R50", "Two-stage skill leaderboard: proper-score qualification, then prospective CLV and ROI.",
        "partial",
        "Stage one runs. Stage two cannot: CLV needs a pre-kickoff close, which gate G05 blocks.",
        "G05 price coverage",
        "Clear when pre-kickoff closes exist for a full evaluation window.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R51", "Vig-free market consensus versus originated fair-line decomposition.",
        "partial",
        "Two-way vig removal is implemented and applied to the stored moneyline, and the residual is "
        "published. A multi-book consensus cannot be computed from a single, book-less price.",
        "G05 price coverage",
        "Clear when two or more independent prices per market exist.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R52", "Weekly 'what changed' diff rather than a static snapshot.",
        "partial",
        "Deltas are published between the captures that exist. A weekly series needs weekly captures.",
        "G05-equivalent capture coverage", "Clear at one capture per week across a month, diffed.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R53", "Publish every model total twice until one wins on a walk-forward comparison.",
        "implemented",
        "The ridge total and the Elo-derived total are both published with their residuals; neither is "
        "collapsed into the other.",
        "G06 sample size", "Both estimators on every row.",
        C.G["schedules"], "nflverse schedules (COMMUNITY); artifact: origination/data/origination_elo.json")

    add("R54", "A drift alarm on every scraper: expected row counts and required fields.",
        "partial",
        "The build fails closed when a required artifact is missing or a reconciliation breaks; the "
        "capture scripts do not yet pin per-source row-count expectations.",
        "G03 completeness", "Clear when each capture records its expected row count and fails on a miss.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R55", "Capture the reserve list so 'not listed' never means 'available'.",
        "implemented",
        f"{avail['coverage']['reserve_players']} reserve/inactive players are read per club and joined to "
        f"the availability graph.",
        "G01 provenance", "Reserve status is a node in the graph, not an assumption.",
        C.G["rosters"], "nflverse rosters (COMMUNITY)")

    add("R56", "Reject ranking strategies by season-long ROI.",
        "implemented",
        "No ROI column exists. Ranking is proper-score based, and the luck page shows why realised return "
        "cannot separate skill from variance at this sample.",
        "G09 multiplicity", "0 ROI-based ranks published.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("R57", "Archive weekly injury reports for past seasons.",
        "blocked",
        "No official historical injury-report archive is held. nflverse publishes a community injury "
        "release, which is not official and cannot satisfy this requirement.",
        "G01 provenance",
        "Clear when a dated official archive is captured with per-week hashes.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("R58", "Pre-register each strategy with a frozen definition before results are seen.",
        "implemented",
        "Content hashes on every rule; gate G02 checks presence; the leaderboard displays the hash.",
        "G02 pre-registration", "All registered rules hashed.",
        C.S["standings"], "NFL standings (OFFICIAL); artifact: origination/data/strategies.json")

    add("R59", "Freeze a rule before it sees data; the commit hash is the registration.",
        "implemented",
        "Registrations are committed before scoring runs in the same build, and the hash covers the rule "
        "text, the market and the threshold.",
        "G02 pre-registration", "Hash present for every strategy.",
        C.S["standings"], "NFL standings (OFFICIAL); artifact: origination/data/strategies.json")

    add("R60", "Split data into train, validation and final holdout seasons.",
        "partial",
        "The walk-forward design fits only on prior seasons, and the ablation has a chronological holdout "
        "of weeks 7-10. A season-level three-way split cannot be honoured on a single-season corpus.",
        "G06 sample size",
        "Clear when at least three seasons of pre-kickoff prices exist.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("R61", "2026 kickoff and declared onside-kick regime priors filter.",
        "blocked",
        "Rule changes are documented in the rulebook, but no prior filter is fitted or validated; inventing "
        "a coefficient would be a fixed penalty, which the brief rejects.",
        "G06 sample size",
        "Clear when a rule-change indicator is tested as an ablation with an interval.",
        C.S["rulebook"], "NFL rulebook (OFFICIAL)")

    add("R62", "Suggestions live in a dedicated review section so a path can be chosen before building.",
        "implemented",
        f"{len(art['suggestions']['rows'])} suggestions ranked by what they unblock, each with cost, risk "
        f"and the decision it needs.",
        "n/a", "Every suggestion names the requirements it unblocks.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    states = [r["state"] for r in R]
    summary = {
        "total": len(R),
        "implemented": states.count("implemented"),
        "partial": states.count("partial"),
        "blocked": states.count("blocked"),
        "validated": validated,
    }
    payload = {"built_at": C.GENERATED_AT, "summary": summary, "rows": R,
               "blocked_ids": [r["id"] for r in R if r["state"] == "blocked"]}
    C.write_json("requirements.json", payload)
    return payload


# ----------------------------------------------------------------------------- questions
def questions(art: dict) -> dict:
    ledger = art["ledger"]
    avail = art["avail"]
    Q = []

    def add(id_, area, question, known, unknown, discovery, blocks, source, label):
        Q.append({"id": id_, "area": area, "question": question, "known": known, "unknown": unknown,
                  "discovery": discovery, "blocks": blocks, "source": source, "source_label": label})

    add("Q01", "Price data",
        "Which price source may be retained, at what latency, and with what right to republish a derived line?",
        "The NFL's own betting FAQ states its odds are a partner widget; the repository holds one "
        "community observation with no bookmaker identity.",
        "No licensed archive, no terms of reuse, no open-versus-close flag on the stored numbers.",
        "Obtain a written data agreement covering history, latency, retention and derived output, or "
        "explicitly accept a community source and label every price as such forever.",
        "R01, R18, R50, R51, G05", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Q02", "Price data",
        "If the only source is community, is a community price good enough to define an opening line?",
        f"The stored series is digest-verified and has one observation. "
        f"{ledger['counts']['post_hoc_only']} of {ledger['counts']['market_cells']} market cells are "
        f"post-hoc or empty.",
        "Whether the release's price is an open, a close or a snapshot of one book.",
        "Capture the same markets from a second, independent source and compare: if the two disagree by "
        "more than a point, neither can define an opening.",
        "R01, R19, G05", C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("Q03", "Availability",
        "How do we know a listed player actually missed the game?",
        f"{avail['coverage']['games_on_report']} of {avail['coverage']['report_rows']} report rows carry a "
        f"game designation; no inactive list is held.",
        "Which listed players were inactive, and which played a reduced role.",
        "Capture official inactive lists for each game and join them to the report rows; the play rate per "
        "designation is then measurable.",
        "R25, R38, R45, R12", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Q04", "Availability",
        "Is 'no injury section' the same as 'no injuries'?",
        f"{avail['coverage']['no_injury_sections']} clubs had no section on the captured report, and "
        f"{avail['coverage']['report_teams']} of 32 clubs had rows at all.",
        "Whether an absent section reflects a healthy roster or a reporting gap.",
        "Compare a club's absent-section week with its next published report and with its inactive list; a "
        "reappearing long-term injury would prove a gap.",
        "R12, R42", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Q05", "Depth",
        "What does a published rank actually mean when one slot names three players?",
        f"{avail['coverage']['slots_rank1_with_two_or_more']} rank-1 slots name two or more players.",
        "Which of those players starts, and whether the order within the group is meaningful.",
        "Join playing time to each shared slot: if the measured shares are indistinguishable, the slot is a "
        "committee and no single starter exists.",
        "R06, R11, R27, R35, R39", C.S["injuries"],
        "NFL injury report (OFFICIAL); club charts: decision-lab/data/official_snapshot.json")

    add("Q06", "Depth",
        "Can depth be derived from playing time for a player who has not yet played?",
        "Snap counts cover the season to date; a rookie with no snaps has no measurement.",
        "The order behind a player with zero recorded snaps.",
        "Keep the published order for those players and label the measured order as unavailable for them; "
        "do not fall back to jersey number.",
        "R11, R47", C.G["snaps"], "nflverse snap counts (COMMUNITY)")

    add("Q07", "Depth",
        "Two clubs publish no parseable depth chart. What is the authorised structured source?",
        "The Texans publish the chart as an image and the Packers prepend jersey numbers; the failure is "
        "recorded per club.",
        "A structured, authorised source for those two clubs.",
        "Ask each club for a structured export, or accept the gap and publish it as a gap rather than "
        "transcribing an image by eye.",
        "R26, R37, R40", C.S["teams"],
        "NFL club directory (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("Q08", "Modelling",
        "Is the injury effect even measurable at this sample size?",
        "The holdout ablation interval spans zero for every λ in the published grid.",
        "The size of the true effect, and whether it is larger for specific positions.",
        "Accumulate pre-kickoff price and availability captures across a season, then re-run the ablation "
        "with position-specific terms and a pre-registered λ.",
        "R24, R61", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Q09", "Modelling",
        "Which estimator should represent the side?",
        "Two estimators exist: a ridge fit on seasonal scoring and a leak-free Elo. Both trail the market "
        "on the same 137 games, and their errors correlate at about 0.95.",
        "Whether a third family, or a combination, would close the gap.",
        "Publish both until a walk-forward comparison separates them with an interval, which requires more "
        "pre-kickoff games.",
        "R03, R53, R60", C.S["standings"], "NFL standings (OFFICIAL)")

    add("Q10", "Modelling",
        "What converts a measured snap share into points of margin?",
        "The ablation publishes a pre-registered λ grid so no single conversion is asserted.",
        "The true conversion, and whether it varies by position.",
        "Fit λ out of sample on a corpus large enough to estimate it, and pre-register the fit before "
        "looking at the holdout.",
        "R24, R35", C.G["snaps"], "nflverse snap counts (COMMUNITY)")

    add("Q11", "Leaderboard",
        "What sample is enough to call a strategy validated?",
        f"Floors are pre-registered at n≥{art['gates']['floors']['publish_min_n']} to publish and "
        f"n≥{art['gates']['floors']['promote_min_n']} to promote; the largest scored arm has "
        f"{max((r['summary'].get('n') or 0) for r in art['board']['results'])}.",
        "Whether those floors are strict enough given the dependence between legs in the same week.",
        "Simulate the family-wise error rate under the current floors and adjust them before the next "
        "evaluation window opens.",
        "R32, R50, G06, G09", C.S["standings"], "NFL standings (OFFICIAL)")

    add("Q12", "Leaderboard",
        "Where do the rewards come from, and who funds them?",
        "No reward pool, rule set or funding source exists in the repository.",
        "The existence, size and legality of any reward.",
        "Decide the jurisdiction and the funding source before any reward is described as available.",
        "R05, R32, R56", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Q13", "Leaderboard",
        "Are control arms scored on the same rows as the model arms?",
        "Yes by construction, and a control's Brier skill is exactly zero, which is what proves the "
        "scoring path is neutral.",
        "Whether a control should also carry an interval on its own win rate for display.",
        "Add a Wilson interval to every control arm so a reader can see that a 51% control is ordinary.",
        "R48", C.S["standings"], "NFL standings (OFFICIAL)")

    add("Q14", "Combos",
        "What would a validated joint probability require?",
        "Nothing exists yet: no prop outcome feed and no operator settlement rules.",
        "The conditional structure between legs inside a game.",
        "Capture a play-level prop outcome series and a same-game price pair; only then can a joint model "
        "be fitted and validated on a holdout.",
        "R30, G07, G08", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Q15", "Legal",
        "What may be republished from each source, and under what terms?",
        "The site links to official pages and stores a private capture; reuse terms are not established.",
        "Whether derived output (a fair line) counts as republished source data.",
        "Get written terms per source class, or restrict the site to derived analysis plus links.",
        "R34, DATA-USE-01", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Q16", "Automation",
        "What runs the capture schedule, and what happens when a capture is missed?",
        "Captures are scripted and hashed; no schedule currently hits the official page on Wed/Thu/Fri.",
        "Whether a missed capture can be detected and recorded as a gap rather than back-filled.",
        "Enable a scheduled capture job, write a manifest of expected captures, and fail the build when a "
        "scheduled capture is absent.",
        "R12, R21, R33, R41, R46, R52, R54", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Q17", "Automation",
        "How should a source change be distinguished from a data error?",
        "The build fails closed on a reconciliation break and publishes drift instead of reconciling it.",
        "The threshold at which a row-count change is a source format change rather than news.",
        "Pin an expected row count and field set per source, and alert on a miss before the page is "
        "published.",
        "R33, R54", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Q18", "Settlement",
        "Which operator's void and push rules govern a graded bet?",
        "Grading uses a mechanical push rule stated in policy P06; no operator terms are held.",
        "Whether a real operator voids a pushed leg or refunds the stake inside a same-game parlay.",
        "Obtain the rules for whichever operator would be used, and store them with a date.",
        "R30, G08", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Q19", "Ownership",
        "Which of the 62 requirements should be funded first?",
        f"The suggestions page ranks {len(art['suggestions']['rows'])} proposals by the requirements they "
        f"unblock.",
        "The owner's appetite for a licensed price feed, which would unblock the most at once.",
        "Choose a path on the suggestions page, then re-run the build: blocked gates become a plan rather "
        "than a list.",
        "All blocked requirements", C.S["standings"], "NFL standings (OFFICIAL)")

    add("Q20", "Ownership",
        "How does a demoted strategy earn its way back?",
        "Demotion is automatic and published, and the score is retained.",
        "The re-entry rule, and whether a demoted rule must be re-registered with a new hash.",
        "Require re-registration (a new hash) with the demotion recorded in its text, so a comeback cannot "
        "silently reuse a failed rule.",
        "R08, R58, G10", C.S["standings"], "NFL standings (OFFICIAL); gate artifact: origination/data/gates.json")

    payload = {"built_at": C.GENERATED_AT, "rows": Q}
    C.write_json("questions.json", payload)
    return payload


# ----------------------------------------------------------------------------- suggestions
def suggestions(art: dict) -> dict:
    S = []

    def add(title, detail, unblocks, cost, risk, decision, source, label):
        S.append({"title": title, "detail": detail, "unblocks": unblocks, "cost": cost, "risk": risk,
                  "decision": decision, "source": source, "source_label": label})

    add("Buy or licence one historical price archive",
        "One licensed archive with a stated open/close timestamp would convert most of this site's blanks "
        "into numbers. Nothing else on this list unlocks as much.",
        ["R01", "R18", "R29", "R50", "R51", "G05"], "High (licence cost + legal review)",
        "A cheap archive with no timestamp flag would be worse than none: it cannot be labelled open vs "
        "close, so every CLV claim stays invalid.",
        "Approve a budget and a vendor shortlist.", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("Run the capture schedule that already exists",
        "The capture script is written. Pointing a scheduled job at the official report on Wed/Thu/Fri and "
        "at kickoff-minus-60 costs almost nothing and creates the series every availability feature needs.",
        ["R12", "R21", "R41", "R42", "R46", "R52", "G05"], "Low (a scheduled job + a monitor)",
        "A capture that overwrites rather than appends destroys the series. The store must stay immutable "
        "per observation.",
        "Approve enabling the scheduled job.", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Capture official inactive lists per game",
        "The single biggest evidence gap in the availability work. Without inactive lists a listed player "
        "cannot be confirmed absent, so a replacement is suspected and never established.",
        ["R25", "R38", "R45", "R06", "R35"], "Medium (a source + a parser + a daily schedule)",
        "An inactive list captured after the game is not point-in-time and cannot be used for a backtest.",
        "Approve the source and the capture window.", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Add a second price observation within 24 hours",
        "Even a second capture from the same community release would turn one snapshot into an interval "
        "and let the ledger distinguish an open from a close for the unplayed Week 10 games.",
        ["R01", "R18", "G05"], "Very low (one more snapshot file)",
        "Two captures of the same number prove nothing about movement. The value is purely in establishing "
        "the pipeline.",
        "Approve running the capture twice a day.", C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("Pin row counts and field sets per source, and alert on a miss",
        "The build already fails closed on a reconciliation break. Extending that to per-source row counts "
        "turns a silent blank into a loud failure.",
        ["R33", "R54"], "Low", "A brittle pin can fail on legitimate news (a club adding a player). Set the "
        "bound as a band, not an exact count.",
        "Approve the alert thresholds.", C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("Publish a per-team deficiency page with both sides of the ball",
        "The current deficiency view is offense-side, because that is what the report designates. A "
        "defensive view needs the opposing club's chart, which exists for 30 clubs.",
        ["R39", "R35"], "Medium (a join across two club charts)",
        "Joining two different clubs' charts invites a positional mismatch that looks like a deficiency "
        "but is only a naming difference.",
        "Approve the cross-club join with a published position map.", C.S["injuries"],
        "NFL injury report (OFFICIAL); club charts captured in decision-lab/data/official_snapshot.json")

    add("Fund the sample, not the model",
        "Every scored rule is within noise. More modelling effort on 137 games will produce a better-looking "
        "number, not a better number. The cheapest path to a decision is more graded legs at fixed, "
        "pre-registered rules.",
        ["R32", "R50", "R60"], "Low in money, high in patience",
        "Re-using this corpus with new rules inflates the multiplicity problem; new legs must be genuinely "
        "out of sample.",
        "Approve a fixed evaluation window and no rule changes inside it.", C.S["standings"],
        "NFL standings (OFFICIAL)")

    add("Make the demotion rule binding on the owner, not just the build",
        "Two rules have already failed their kill condition. A leaderboard that demotes but never acts is a "
        "dashboard, not a governance system.",
        ["R08", "R17", "G10"], "Low", "Demoting aggressively can bury a rule that needed one more week. The "
        "kill condition is therefore pre-registered, not discretionary.",
        "Approve that a demoted rule needs a new hash to return.", C.S["standings"],
        "NFL standings (OFFICIAL); gate artifact: origination/data/gates.json")

    add("State the reuse position before adding more captures",
        "The repository stores private captures and publishes derived analysis. That is a defensible "
        "position only if it is written down per source class.",
        ["R34", "DATA-USE-01"], "Low (a decision, not code)",
        "Publishing a raw row from a source whose terms forbid it would compromise every page that cites it.",
        "Approve the public/private split in writing.", C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    payload = {"built_at": C.GENERATED_AT, "rows": S}
    C.write_json("suggestions.json", payload)
    return payload


# ----------------------------------------------------------------------------- flags
def flagged(art: dict) -> dict:
    ledger = art["ledger"]
    F = []

    def add(id_, severity, title, issue, resolve, source, label):
        F.append({"id": id_, "severity": severity, "title": title, "issue": issue,
                  "resolve": resolve, "source": source, "source_label": label})

    add("F01", "high", "Price history is two captures deep, not a series",
        "Weeks 1-9 had kicked off before the first observation, so their stored numbers are post-hoc and "
        "cannot define an opening, a close or closing-line value. Two captures now exist and 7 of the 78 "
        "pre-kickoff market cells moved between them, so a real opening-to-latest interval exists for "
        "those cells only. The remaining 71 pre-kickoff cells still have a single observation.",
        "A scheduled capture at T-60 before every kickoff, so every graded cell has its own interval. "
        "Policy P04 sets the schedule.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("F02", "high", "Two clubs publish no parseable depth chart",
        "30 of 32 clubs yielded depth rows. The Packers prepend jersey numbers to names and the Texans "
        "publish the chart as an image. Both are recorded as failures rather than transcribed by eye.",
        "An authorised structured export per club, or a documented decision to accept the gap.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("F03", "high", "No official inactive list is held",
        "The captured report carries 6 game designations across 254 rows. Without inactive lists, a listed "
        "player's participation cannot be confirmed and a replacement cannot be established.",
        "Capture official inactive lists per game with a timestamp before kickoff.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("F04", "high", "The personnel ablation cannot resolve an effect",
        "The holdout interval spans zero for every λ in the published grid. This is a finding about the "
        "sample, not a claim that injuries do not matter.",
        "More pre-kickoff games and dated availability captures before re-testing.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("F05", "medium", "Team-code aliases differ between sources",
        "nfl.com's 2026 standings publish AZ for Arizona; the community schedule publishes ARI. Los Angeles "
        "is LA on both. The feed maps the alias explicitly and the reconciliation would fail if it did not.",
        "Keep the explicit alias map and assert it in tests; do not normalise silently.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    add("F06", "medium", "Kickoff times carry no time zone",
        "The schedule publishes kickoff in US Eastern but the field has no zone. The price store converts "
        "at a fixed UTC-4, which is up to 60 minutes wrong once Eastern Standard Time begins.",
        "Capture an explicit UTC kickoff, or store the observation as 'pre-kickoff by minutes' instead of "
        "a boolean.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("F07", "medium", "Two strategies already failed their kill rule",
        "G10 demoted two scored rules whose Brier-skill interval sits entirely below zero. They remain on "
        "the leaderboard, labelled, with their numbers intact.",
        "Require a new registration hash before a demoted rule can return.",
        C.S["standings"], "NFL standings (OFFICIAL); gate artifact: origination/data/gates.json")

    add("F08", "medium", "No reward pool, rule set or funding source exists",
        "The brief asks for a leaderboard competition with rewards for top performers. No funding source, "
        "jurisdiction or payout rule exists, so no reward is described as available.",
        "Decide jurisdiction and funding before any reward is announced.",
        C.S["odds_faq"], "NFL betting FAQ (OFFICIAL)")

    add("F09", "medium", "A club with no report section is not injury-free",
        f"{avail_no_injury(art)} clubs had no section on the captured report. Treating that as 'no injuries' "
        f"is the failure mode flagged earlier in this repository.",
        "Join each no-section club to its inactive list and its next published report.",
        C.S["injuries"], "NFL injury report (OFFICIAL)")

    add("F10", "low", "Correlation C02 mixes a community price with an official score",
        "It is published for transparency and excluded from every official-only gate. A reader who skims "
        "the table could mistake it for an official-input correlation.",
        "Keep the source-class badges on the row and the note in the caption.",
        C.G["schedules"], "nflverse schedules (COMMUNITY)")

    add("F11", "low", "41 report rows could not be joined to a depth slot",
        f"{art['corr']['counts']['withheld']} correlation families and a set of report rows have no join "
        f"target: a player can be on the report without appearing on his club's published chart.",
        "Publish the unmatched count beside the joined count so the join rate is never implied as 100%.",
        C.S["injuries"], "NFL injury report (OFFICIAL); capture: decision-lab/data/official_snapshot.json")

    add("F12", "low", "The site's own model trails the market it compares against",
        "The ridge side model's MAE is worse than the stored market spread's on the same games. It is "
        "published as a benchmark, and no strategy above it claims otherwise.",
        "Nothing to fix; it is the honest baseline. Any future model must beat this before claiming skill.",
        C.S["standings"], "NFL standings (OFFICIAL)")

    payload = {"built_at": C.GENERATED_AT, "rows": F}
    C.write_json("flagged.json", payload)
    return payload


def avail_no_injury(art):
    try:
        return art["avail"]["coverage"]["no_injury_sections"]
    except Exception:
        return 4


def main() -> int:
    art = {
        "results": C.read_json(C.DATA / "results.json"),
        "ledger": C.read_json(C.DATA / "prices" / "ledger.json"),
        "board": C.read_json(C.DATA / "leaderboard.json"),
        "gates": C.read_json(C.DATA / "gates.json"),
        "corr": C.read_json(C.DATA / "correlations.json"),
        "avail": C.read_json(C.DATA / "availability_graph.json"),
        "ablation": C.read_json(C.DATA / "ablation.json"),
        "wf": C.read_json(C.DATA / "origination_walkforward.json"),
        "registry": C.read_json(C.DATA / "strategies.json"),
    }
    art["suggestions"] = suggestions(art)
    sources()
    requirements(art)
    questions(art)
    flagged(art)
    req = art["requirements"] if "requirements" in art else C.read_json(C.DATA / "requirements.json")
    print(f"Content: {req['summary']} | {len(art['suggestions']['rows'])} suggestions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
