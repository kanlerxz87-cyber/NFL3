#!/usr/bin/env python3
"""Build the repo-review page and the repo-review flag rows for Flagged for review.

Scope: the irregularities found while reviewing this repository in session arena/ecdea533-nfl3.
The requirements register is NOT built here; it is owned by readiness/build_readiness.py (PR #67).

    python3 scripts/build_repo_review.py          # rewrite repo-review.html and the F-RR rows in review.html
    python3 scripts/build_repo_review.py --check  # fail if either would change

Nothing is fetched from the network. Findings are written by hand from facts checked in this session.
Official links are used only where the page was opened this session or is already cited in the repo.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_HTML = ROOT / "review.html"
REPO_REVIEW = ROOT / "repo-review.html"
GITHUB = "https://github.com/kanlerxz87-cyber/NFL3"
GENERATED = {"repo-review.html"}
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
    "week11_schedule": ("NFL 2026 Week 11 schedule page", "https://www.nfl.com/schedules/2026/by-week/week-11", True),
    "scores_w11": ("NFL 2026 Week 11 scores page", "https://www.nfl.com/scores/2026/week-11", True),
    "gamecentre_w11": ("NFL game centre: Colts at Texans, 2026 Week 11", "https://www.nfl.com/games/colts-at-texans-2026-reg-11", True),
    "gamecentre_w2": ("NFL game centre: Commanders at Cowboys, 2026 Week 2", "https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2", True),
    "sched_week1": ("NFL 2026 Week 1 schedule page", "https://www.nfl.com/schedules/2026/by-week/week-1", True),
    "injuries_hist": ("NFL injury report at a past-season URL (2024, REG 4)", "https://www.nfl.com/injuries/league/2024/REG4", True),
}

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
    ("RR-15", "High",
     "The committed 2026 game log leaves one fixture without a score (Week 2, Washington at Dallas, recorded on "
     "2026-11-12 as a 'Hidden Score'). The official game centre published the final on 2026-11-15: Washington 20, "
     "Dallas 37, with quarter scores that sum to the final. Every page that calls the corpus '136 games' is one "
     "game short of what it can grade.",
     "decision-desk/data/games_2026.csv (week 2 WAS@DAL row: blank scores, verification note). Official read: "
     "https://www.nfl.com/games/commanders-at-cowboys-2026-reg-2 on 2026-11-15.",
     "The log owner fills the two cells from the game centre and records the read time. Until then any count must "
     "say 135 graded of 136.", "gamecentre_w2", "decision-desk/data/games_2026.csv"),
    ("RR-16", "Medium",
     "Venue provenance conflicts between two official pages for the same fixture. The Week 11 game centre's Game "
     "Info block says RELIANT STADIUM for Indianapolis at Houston, while the same fixture's club travel link on the "
     "Week 11 schedule page says NRG Stadium. The Cincinnati at Washington travel link says FedEx Field and was not "
     "checked against its game centre in this pass.",
     "shadow-board/data/fixtures_2026_w11.csv (venue_game_centre vs venue_schedule_page columns; 2 of 13 fixtures "
     "carry a game-centre read, 11 are blank by design).",
     "Decide which official field is authoritative for venue before any roof, surface or travel feature is built; "
     "blank the venue rather than choosing by preference.", "gamecentre_w11", "shadow-board/data/fixtures_2026_w11.csv"),
    ("RR-17", "High",
     "The official injury report is queryable for past seasons at nfl.com/injuries/league/{season}/REG{week}, but "
     "the win-loss records printed beside each past-week table are end-of-season values (the 2024 Week 4 page shows "
     "Dallas 7-10 and the New York Giants 3-14). The page therefore is a re-rendered query, not the report as it "
     "stood, so it is not point-in-time safe.",
     "https://www.nfl.com/injuries/league/2024/REG4 (opened 2026-11-15); the selector offers seasons 1965-2026 and "
     "weeks 1-18 plus playoffs.",
     "Either use the archive with an explicit lookahead flag on every row, or wait for dated captures. Do not "
     "describe it as a point-in-time archive, and do not calibrate 'Questionable' against inactives from it.",
     "injuries_hist", "shadow-board/sources.html"),
    ("RR-18", "Low",
     "The injury-report page's title states a different week from its own body header: 'Week 10 of the 2026 Season' "
     "sits above 'Injuries - WEEK 9', and the 2024 Week 4 page repeats the pattern. A parser keyed on the title "
     "would mislabel every capture by a week.",
     "Both pages opened 2026-11-15; the same mismatch was independently recorded by an earlier session for the "
     "Week 9 URL.",
     "Key captures on the request URL and the body header, and assert the two agree in the drift alarm.",
     "injuries_hist", "shadow-board/sources.html"),
    ("RR-19", "Medium",
     "Pre-registration is now demonstrated in one place only. shadow-board/PREREGISTRATION.md is registered by "
     "commit f7f6c18 (2026-11-15T13:00:32Z) with every artifact of that workspace committed after it, and its gate "
     "refuses a build whose artifacts predate the rule file. The nine research-desk strategies described in "
     "docs/PRE_REGISTRATION.md remain in the RR-04 state.",
     "git log --format=%H\ %cI -- shadow-board/PREREGISTRATION.md; python3 shadow-board/scripts/check.py; RR-04.",
     "Either re-register the research-desk family in a commit that precedes its results, or keep its 'written "
     "before results were inspected' sentence off the published pages.", None, "shadow-board/PREREGISTRATION.md"),
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
    ("V-06", "Week 11 slate (read 2026-11-15 from two official pages): 13 fixtures with date, kickoff time in ET, network, both clubs' published records, and 6 clubs on bye (ATL, CLE, GB, LA, NE, SEA). The schedule page and the scores page agree on the matchup list.", "scores_w11"),
    ("V-07", "Week 2 Washington at Dallas is now published as WAS 20, DAL 37, with quarter scores 0/10/3/7 and 10/7/10/10 summing to each final - an internal consistency check of the official page.", "gamecentre_w2"),
    ("V-08", "The dated schedule announcement (media.nfl.com, '2026 NFL Schedule Announced', 14 May 2026) states an 18-week, 272-game regular season kicking off Wednesday, 9 September in Seattle, with nine international games including Week 11 in Mexico City. This closes the earlier note that a Wednesday Week 1 kickoff date was anomalous. Press-release URL recorded as text: https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced (a non-official-host link in the root validator's allowlist, so it is not cited as a source link).", "sched_week1"),
    ("V-10", "The price-data policy and the frozen corpus are now in the repository and this workspace is wired to both: pricing/PRICE_DATA_POLICY.md is adopted with a fail-closed rule and a source register in which no source carries a permitted-use grant (0 price rows, 0 residual rows), and corpus/manifest.json freezes the 136-game 2026 log at SHA-256 4632744b44d59ff2c482c219ed65c6f6cf4924079013b82021933e91c2f6c9f7. Recomputed in this session: decision-desk/data/games_2026.csv hashes to that same value, so the market and residual columns stay blank by rule and the published forecasts are pinned to the bytes they were issued against.", "schedule"),
    ("V-09", "19 of 21 values read off official pages reproduce the committed 2026 game log exactly (Week 1, 5, 7, 8 and 9 samples); the other 2 are the Week 2 blank cells described in RR-15. No value disagreed.", "gamecentre_w2"),
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


def replace_block(text: str, start: str, end: str, block: str) -> str:
    if start in text and end in text:
        head, rest = text.split(start, 1)
        _, tail = rest.split(end, 1)
        return head + block + tail
    return text


def patch_review(text: str) -> str:
    block = render_flags()
    if FLAG_START in text:
        return replace_block(text, FLAG_START, FLAG_END, block)
    marker = "</tbody></table></div></section>"
    if text.count(marker) < 1:
        raise SystemExit("review.html: flagged table end not found")
    return text.replace(marker, block + "\n" + marker, 1)


def validate() -> None:
    for rid, sev, finding, evidence, action, key, path in REVIEW:
        if key is not None and key not in OFFICIAL:
            raise SystemExit(f"{rid}: unknown official key {key}")
        if path not in GENERATED and not (ROOT / path).exists():
            raise SystemExit(f"{rid}: evidence path missing {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validate()
    outputs = {
        REVIEW_HTML: patch_review(REVIEW_HTML.read_text(encoding="utf-8")),
        REPO_REVIEW: render_repo_review(),
    }
    changed = [p.name for p, text in outputs.items() if (not p.exists()) or p.read_text(encoding="utf-8") != text]
    if args.check:
        if changed:
            print("would change:", ", ".join(changed))
            return 1
        print(f"repo review is current ({len(REVIEW)} findings)")
        return 0
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    print(f"wrote {len(REVIEW)} findings; changed: {', '.join(changed) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
