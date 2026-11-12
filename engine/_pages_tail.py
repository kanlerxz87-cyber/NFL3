# -*- coding: utf-8 -*-
"""Pages 07-11: question register, suggestion board, source register, flagged items, repo review."""

from report import fmt, pct, table, esc, link, badge, unverified


def build_questions(D, C) -> str:
    """Questions -> what we know -> what is missing -> how to discover it -> decision unblocked."""
    line = C.get("line", {})
    inj = C.get("injury", {})
    corr = C.get("corr", {})
    fam = C.get("family", [])
    nav = lambda h: f'<a href="{h}">detail</a>'
    rows = [
        ["Q01", "Which official data can be used, and can we prove the bytes are the official ones?",
         f"Answered. {len(D['files'])} official nflverse release assets are fetched by CI and each one is "
         "verified against the SHA-256 digest GitHub publishes for that asset.",
         "Redistribution terms for derived tables at scale.",
         "Keep the digest manifest per run and publish it with the results.",
         "Whether any data may be reused",
         link("https://github.com/nflverse/nflverse-data/releases", "nflverse-data releases")],
        ["Q02", "Is our own number genuinely out of sample?",
         "Answered. The model is refitted each season on earlier seasons only; every graded game was "
         "predicted before its result entered the training set.",
         "Nothing structural. More seasons would tighten every interval.",
         "Extend the walk-forward window back to 1999 and hold out the newest season entirely.",
         "Any claim of edge",
         link("https://github.com/nflverse/nflverse-data/releases/tag/schedules", "games.csv")],
        ["Q03", "Do our lines beat the closing market?",
         (f"Measured. Spread MAE {fmt(line.get('model_mae_spread'))} against the market's "
          f"{fmt(line.get('market_mae_spread'))} over {fmt(line.get('n_games'))} out-of-sample games."
          if line.get("ok") else "Not established."),
         "Closing prices from several books, so we can beat the best price rather than one consensus line.",
         "Add a second independent closing-line source and re-run the identical study.",
         "How to price a line",
         link("https://github.com/nflverse/nflverse-data/releases/tag/schedules", "games.csv")],
        ["Q04", "Do any strategies survive all seven gates?",
         (f"{sum(1 for s in fam if s.get('status') == 'passes all gates')} of {len(fam)} pass every gate."
          if fam else "Not established."),
         "A larger out-of-sample sample, plus prop-level data for the parlay products.",
         "Freeze the family and re-run each season; promote only on a season the strategy never saw.",
         "Whether real money is ever staked",
         link("strategies.html", "gate definitions")],
        ["Q05", "How correlated are legs inside one game?",
         (f"Measured. Home win and home cover co-occur at "
          f"{fmt((corr.get('stacked') or {}).get('lift'), 3)}x the independent rate."
          if corr.get("stacked") else "Not established."),
         "Player-level joint outcomes, which are required for prop-combo pricing.",
         "Ingest a verified player-prop history with closing prices, then recompute the joint matrix.",
         "Parlay and same-game pricing",
         link("https://github.com/nflverse/nflverse-data/releases/tag/schedules", "games.csv")],
        ["Q06", "Does losing starters change the number, and does the market already know?",
         (f"First look only. {fmt((inj.get('market_vs_def_injuries') or {}).get('n'))} games this season "
          "joined to the week's official report." if inj.get("ok") else "Not established."),
         "Historical injury reports and depth charts joined across several seasons, so the sample can "
         "separate signal from noise.",
         "Run the same join for 2021-2025 using the depth_team schema and pool the seasons.",
         "Injury-adjusted lines",
         link("https://www.nfl.com/injuries/", "NFL injury report")],
        ["Q07", "Which position groups matter most when a starter is out?",
         "Not established. The depth chart identifies the slot but does not quantify replacement quality.",
         "A player-quality measure for backups.",
         "Build replacement quality from snap share plus per-snap production, then re-test the signal.",
         "Prop and matchup edges",
         link("https://github.com/nflverse/nflverse-data/releases/tag/snap_counts", "snap counts")],
        ["Q08", "Can player props be priced?",
         "Not yet. No verified player-prop history or prop closing line is in the snapshot.",
         "Player-level market prices and settlement rules for each prop market.",
         "Ingest a licensed prop feed with closing prices. Do not scrape it.",
         "Prop markets",
         link("https://www.nfl.com/stats/", "NFL stats")],
        ["Q09", "What does removing luck actually mean here?",
         "Defined. Luck is what remains when edge is measured against the closing line, the sample is "
         "large, the family is multiple-testing controlled, and the result holds in both halves and "
         "across seasons.",
         "A power analysis per strategy, so the required sample size is known in advance.",
         "Pre-compute required samples for each effect size and publish them next to the gates.",
         "Any reward decision",
         link("strategies.html", "the seven gates")],
        ["Q10", "What is the legal position on rewards and on staking?",
         "Not established. Nothing here is a legal opinion.",
         "Jurisdiction-specific rules on paid contests and on staking.",
         "Obtain a legal review before any reward is paid or any stake is placed.",
         "Rewards programme",
         link("https://www.nfl.com/legal/terms", "NFL terms")],
    ]
    return f"""
<h1>Questions, information and answers</h1>
<p class="lede">Every decision that has to be made, what is already known, what is still missing, and the
concrete step that would close the gap. Nothing is confirmed unless its official source is linked.</p>
{table(["ID", "Question", "What we know", "What is missing", "How to discover it",
        "Decision it unblocks", "Official source"], rows,
       caption="Q01-Q04 are answered by this build; Q05-Q10 remain open")}
<h2>Reading the register</h2>
<ul class="bullets">
<li><b>What we know</b> is only ever what a digest-verified file or an official page supports.</li>
<li><b>What is missing</b> is the specific field or source, not a vague gap.</li>
<li><b>How to discover it</b> is the next experiment, and every experiment has a falsification test on
the {link("suggestions.html", "suggestion board")}.</li>
</ul>
"""


def build_suggestions(D, C) -> str:
    rows = [
        ["S01", "Publish the digest-verified data layer as the single source of truth",
         "Implemented in this build. Every page reads data/raw/manifest.json.",
         "Low. CI only.",
         "Any ingested file fails its digest and the build stops.",
         "Implemented", "Low", "G1", "sources.html"],
        ["S02", "Keep the seven validation gates fixed and pre-registered",
         "Written into docs/PRE_REGISTRATION.md before results were inspected.",
         "Low. Documentation only.",
         "A gate edited after seeing results voids the run.",
         "Implemented", "Low", "G1-G7", "strategies.html"],
        ["S03", "Extend the injury/depth join to 2021-2025 and pool the seasons",
         "The 2021-2024 depth charts carry depth_team (1st/2nd/3rd string); the pipeline already "
         "fetches them, so the multi-season study is one run away.",
         "Medium: larger downloads and a name join that needs cleaning.",
         "Pooled correlation interval contains zero, so the injury signal is not real.",
         "Recommended next", "Medium", "G2, G6", "availability.html"],
        ["S04", "Add a second independent closing-line source",
         "Only one consensus closing line is in the snapshot, so we cannot yet beat the best price.",
         "Medium: needs a licensed feed.",
         "Model MAE does not improve against the best price.",
         "Recommended next", "Medium", "G6", "lines.html"],
        ["S05", "Build replacement quality from snap share plus per-snap production",
         "Snap counts and depth charts are already fetched; per-snap production needs a player dataset.",
         "Medium-high.",
         "Replacement quality does not predict the market residual.",
         "Candidate", "High", "G2", "availability.html"],
        ["S06", "Add licensed player-prop history with closing prices",
         "Required before any prop or prop-combo product can be priced or validated.",
         "High: licensing and engineering.",
         "The prop model does not beat the prop closing line.",
         "Candidate", "High", "G6", "questions.html"],
        ["S07", "Reward gate completion, never headline profit",
         "Ties the leaderboard to demonstrable skill, because luck cannot complete G3 to G6.",
         "Low: rule text only.",
         "A reward is paid on raw profit, which breaks the incentive.",
         "Recommend", "Low", "G1-G7", "strategies.html"],
        ["S08", "Publish the coefficient table and the residuals for every run",
         "Already published on the line page; the model is auditable instead of a black box.",
         "Low.",
         "A published claim cannot be reproduced from the table, so it is withdrawn.",
         "Implemented", "Low", "G1", "lines.html"],
        ["S09", "Track open-to-close line movement instead of a single closing snapshot",
         "Not possible with the current snapshot; initial lines exist only for a subset of seasons.",
         "Medium.",
         "Line movement does not predict results.",
         "Candidate", "Medium", "G2", "lines.html"],
        ["S10", "Fail the build automatically if any table row lacks an official source link",
         "tests/check_site.py enforces it and CI runs the check on every push.",
         "Low.",
         "A row without a source link ships, which fails the build.",
         "Implemented", "Low", "G1", "sources.html"],
    ]
    return f"""
<h1>Suggestion board</h1>
<p class="lede">The list to review and choose from before implementing anything. Each row states the
evidence, the cost, the test that would prove it wrong, and the validation gate it must pass.</p>
<div class="notice warn"><b>How to choose.</b> Prefer suggestions that are cheap, falsifiable and gated.
A suggestion that cannot fail a test is an opinion, not an experiment.</div>
{table(["ID", "Suggestion", "Evidence / current state", "Cost", "Falsification test",
        "Status", "Effort", "Gate", "Detail"], rows, cls="data method",
       caption="Implemented = already shipped in this build; Recommended next = highest evidence per unit of cost. "
               "This table records proposals and their evidence status, so its rows carry a detail-page link "
               "rather than an official data value.")}
<h2>Decision record template</h2>
<p class="sub">When a suggestion is accepted, record the decision so the next session inherits the
reasoning instead of re-litigating it.</p>
{table(["Field", "What to record"],
       [["Decision ID", "Suggestion ID plus the date."],
        ["Evidence considered", "The tables and source links actually read."],
        ["What would change our mind", "The falsification test and its pre-agreed threshold."],
        ["Owner and review date", "Who implements it and when it is re-checked."],
        ["Outcome", "Kept, reverted or superseded, with the evidence."]],
       cls="data method", caption="Intentionally empty until a decision is made")}
"""


def build_sources(D, C) -> str:
    files = D["files"]
    man = D["manifest"]
    rows = []
    for name, rec in sorted(files.items()):
        rows.append([esc(name), fmt(rec.get("bytes")),
                     f'<code>{esc(rec.get("sha256", "")[:23])}…</code>',
                     esc(rec.get("release_asset_updated_utc", "")),
                     link(rec.get("asset_url", "#"), "official asset"),
                     '<span class="pill pill-pass">verified</span>'])
    for f in man.get("failures", []):
        rows.append([esc(f.get("name")), "—", "—", "—",
                     unverified(str(f.get("reason", "not fetched"))),
                     '<span class="pill pill-fail">missing</span>'])
    extra = [
        ["NFL official injury report", "Weekly official game status and practice participation",
         link("https://www.nfl.com/injuries/", "nfl.com/injuries"),
         "Field semantics for report_status and practice_status"],
        ["NFL official scores", "Final scores per game",
         link("https://www.nfl.com/scores/", "nfl.com/scores"), "Spot check of the result field"],
        ["NFL official standings", "Win/loss record per club",
         link("https://www.nfl.com/standings/", "nfl.com/standings"), "Spot check of season records"],
        ["nflreadr data dictionaries", "Field definitions for every nflverse table",
         link("https://nflreadr.nflverse.com/", "nflreadr.nflverse.com"),
         "depth_team, report_status and the spread_line sign convention"],
        ["nflverse-data releases", "The official machine-readable files themselves",
         link("https://github.com/nflverse/nflverse-data/releases", "GitHub releases"),
         "Primary source for every computed value"],
    ]
    return f"""
<h1>Official sources and verification register</h1>
<p class="lede">Every computed number traces back to a file on this page, and every file was checked
byte-for-byte against the SHA-256 digest GitHub publishes for that release asset.</p>
<div class="notice ok"><b>Why a digest is sufficient.</b> GitHub computes the digest server-side from
the stored asset, so a match proves the local copy is identical to the official asset at the recorded
time, not merely similar.</div>
<h2>Ingested assets</h2>
{table(["Asset", "Bytes", "SHA-256 (prefix)", "Asset updated (UTC)", "Source", "Integrity"], rows,
       cls="data method",
       caption="Produced by pipeline/fetch_official.py into data/raw/manifest.json. This table IS the "
               "source register: each row links the official asset it documents.")}
<h2>Reference sources used for definitions and cross-checks</h2>
{table(["Source", "Used for", "Link", "What was verified against it"], extra, cls="data method",
       caption="Reference sources. Each row links the official page it documents.")}
<h2>What "verified" does not mean</h2>
<ul class="bullets">
<li>It does not mean the NFL's own feed is error-free. It means we copied the official asset faithfully
and can prove it.</li>
<li>It does not survive a future refresh: a new asset gets a new digest. The timestamp column is the
point-in-time reference.</li>
<li>Values that would need an official source we cannot reach are left blank and listed on
{link("flagged.html", "Flagged for review")}.</li>
</ul>
"""


def build_flagged(D, C) -> str:
    man = D["manifest"]
    items = []
    for f in man.get("failures", []):
        items.append([esc(f.get("name", "")), "Official asset not retrieved or digest mismatch",
                      esc(str(f.get("reason"))[:200]), "Blocked until a verified copy exists",
                      "data refresh"])
    items += [
        ["Closing lines", "A single consensus closing line, not a best-of-market price",
         "Beating a consensus close is not the same as beating the best available number.",
         "Benchmark only", "lines.html"],
        ["Injury severity", "The official report has no expected-games-missed field",
         "Any severity number would be a model output, not a sourced fact.",
         "Left blank", "availability.html"],
        ["Player props", "No verified player-prop history or closing price in the snapshot",
         "Prop and prop-combo edges cannot be validated.", "Not established", "questions.html"],
        ["Rewards and legal", "No jurisdiction-specific legal review of a paid reward programme",
         "Paying a reward may be regulated depending on jurisdiction.", "No reward claimed",
         "suggestions.html"],
        ["Live NFL pages", "Live pages show the current week and change over time",
         "A live page cannot be permanent evidence for a historical value.", "Cross-check only",
         "sources.html"],
        ["Name join", "Injury-to-depth-chart join is on player name and team-week",
         "Two players sharing a name on one team in one week would collide.", "Duplicate watch",
         "availability.html"],
        ["Depth schema change", "2025+ depth charts dropped depth_team in favour of pos_rank",
         "The 1st/2nd/3rd-string field only exists for 2021-2024.",
         "Restrict the multi-season study to that window", "review.html"],
    ]
    rows = [[f"F{i + 1:02d}", a, b, c, d, e] for i, (a, b, c, d, e) in enumerate(items)]
    return f"""
<h1>Flagged for review</h1>
<p class="lede">Everything that could not be confirmed from an official source, or was confirmed only
partially. None of it blocks publication; all of it blocks a claim.</p>
<div class="notice warn"><b>Read this before trusting a number.</b> A blank cell elsewhere on the site
usually maps to a row here.</div>
{table(["ID", "Area", "Irregularity", "Why it matters", "Handling", "Where it appears"], rows,
       cls="data method",
       caption="Published deliberately so the gap can be reviewed rather than hidden. Each row names the "
               "page where the item appears.")}
<h2>How an item gets cleared</h2>
<ol class="bullets">
<li>A verified official source is added to the pipeline and digested.</li>
<li>The value is regenerated by CI from that source, never typed in by hand.</li>
<li>The row is removed only when both the source link and the digest are present.</li>
</ol>
"""


def build_review(D, C) -> str:
    checks = []
    for name, rec in sorted(D["files"].items()):
        checks.append([f"<code>{esc(name)}</code>", "Downloaded by pipeline/fetch_official.py",
                       f'sha256 {esc(rec.get("sha256", "")[:16])}… · {fmt(rec.get("bytes"))} bytes',
                       '<span class="pill pill-pass">matches official digest</span>',
                       link(rec.get("asset_url", "#"), "open asset")])
    season = D.get("season_games") or []
    played = [g for g in season if g["home_score"] is not None]
    lines_missing = [g for g in played if g["spread_line"] is None]
    inj_weeks = sorted({r["week"] for r in (D.get("injuries") or [])})
    checks += [
        ["2026 schedule rows", f"{len(season)} rows parsed from the official schedule",
         f"{len(played)} already played", '<span class="pill pill-pass">parsed</span>',
         link("https://github.com/nflverse/nflverse-data/releases/tag/schedules", "games.csv")],
        ["Completed games with a closing line",
         f"{len(played) - len(lines_missing)} of {len(played)}",
         f"{len(lines_missing)} completed games have no closing line and are excluded from grading",
         '<span class="pill pill-warn">excluded when blank</span>',
         link("https://github.com/nflverse/nflverse-data/releases/tag/schedules", "games.csv")],
        ["Injury report weeks", f"weeks {inj_weeks[0]}-{inj_weeks[-1]}" if inj_weeks else "none",
         f"{len(D.get('injuries') or [])} player-week rows",
         '<span class="pill pill-pass">parsed</span>',
         link("https://www.nfl.com/injuries/", "NFL injury report")],
        ["Depth chart rows", f"{len(D.get('depth') or [])} current-season rows",
         "Schema: dt, team, player_name, pos_abb, pos_slot, pos_rank",
         '<span class="pill pill-pass">parsed</span>',
         link("https://github.com/nflverse/nflverse-data/releases/tag/depth_charts", "depth chart")],
    ]
    return f"""
<h1>Repository and data review</h1>
<p class="lede">Line by line: what was checked, against which official source, and what was flagged.
Every row links to the artefact so it can be verified by hand.</p>
<h2>Data integrity</h2>
{table(["Item", "What was done", "Evidence", "Result", "Manual check"], checks,
       caption="Results from the current verified snapshot")}
<h2>Irregularities found during the review</h2>
<ul class="bullets">
<li>The 2025 and later official depth charts no longer carry <code>depth_team</code>; they use
<code>pos_slot</code> and <code>pos_rank</code>. The 1st/2nd/3rd-string field exists only for
2021-2024, so any multi-season backup study must run on that window.</li>
<li>The official schedule's <code>spread_line</code> sign convention is <b>positive = home
favoured</b>, the opposite of the common sportsbook display. The engine converts it in exactly one
place so a sign error cannot silently flip every graded bet.</li>
<li>Team codes differ between sources for a few franchises (WSH/WAS, JAC/JAX, LA/LAR). One
normalisation table is applied before any join.</li>
<li><code>report_status</code> is sometimes blank while <code>practice_status</code> is populated. The
availability measure therefore uses game status only and treats a blank as "not ruled out", never as
"healthy".</li>
<li>The repository started from a single empty README; nothing pre-existing was verifiable, which is
why every number on this site is generated rather than quoted.</li>
</ul>
<h2>Cross-check against the NFL's own pages</h2>
<p class="sub">The official nfl.com pages are the public face of the same feeds. They are used to
confirm field semantics and to spot-check values, not as a bulk source: a live page cannot be cited as
permanent evidence for a historical number.</p>
{table(["Check", "Result", "Official link"],
       [["Injury report lists a game status per player (Out / Doubtful / Questionable)",
         '<span class="pill pill-pass">confirmed</span>', link("https://www.nfl.com/injuries/", "nfl.com/injuries")],
        ["Scores page shows the final score used in the result field",
         '<span class="pill pill-pass">confirmed</span>', link("https://www.nfl.com/scores/", "nfl.com/scores")],
        ["Standings page confirms the win/loss records used in the availability table",
         '<span class="pill pill-pass">confirmed</span>', link("https://www.nfl.com/standings/", "nfl.com/standings")],
        ["Player-prop closing prices on an official source",
         '<span class="pill pill-fail">not available</span>', unverified("no official source")]],
       cls="data method", caption="Manual review results, 2026-11-12 UTC")}
"""
