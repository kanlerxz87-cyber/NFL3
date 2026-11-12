#!/usr/bin/env python3
"""Deterministic static-site generator for NFL3 Decision & Line Origination Hub."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

HUB_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = HUB_ROOT / "data"

NAV_ITEMS = [
    ("index.html", "01", "Overview & Requirements"),
    ("executive-summary.html", "02", "Executive Summary"),
    ("suggestions.html", "03", "Suggestions Review"),
    ("questions.html", "04", "Pre-Decision Q&A"),
    ("origination.html", "05", "Line Origination & Lab"),
    ("depth-injuries.html", "06", "Depth & Injury Tracker"),
    ("repo-audit.html", "07", "Repo Audit & Sources"),
    ("flagged.html", "08", "Flagged for Review"),
]

SIBLING_LINKS = [
    ("../index.html", "R1", "Root NFL3 Site"),
    ("../dashboard/index.html", "R2", "Week 10 Dashboard"),
    ("../line-lab/index.html", "R3", "Quantitative Line Lab"),
    ("../research-workspace/index.html", "R4", "Research Workspace"),
]


def load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def badge(text: str) -> str:
    t = text.lower()
    if "unverified" in t or "pending" in t or "not run" in t or "locked" in t or "monitor" in t:
        cls = "badge-amber"
    elif "flag" in t or "critical" in t or "high" in t:
        cls = "badge-red"
    elif "proposed" in t or "specified" in t or "partially" in t:
        cls = "badge-blue"
    elif "verified" in t or "complete" in t or "healthy" in t or "resolved" in t:
        cls = "badge-green"
    else:
        cls = "badge-slate"
    return f'<span class="badge {cls}">{escape(text)}</span>'


def td_cell(val: str, is_blank_allowed: bool = False, as_badge: bool = False) -> str:
    if val == "":
        if is_blank_allowed:
            return '<td class="cell-blank" title="Unverified — intentionally left blank (no inference)"></td>'
        return "<td></td>"
    if as_badge:
        return f"<td>{badge(val)}</td>"
    return f"<td>{escape(val)}</td>"


def source_td(label: str, url: str) -> str:
    return (
        f'<td><a class="source-link" href="{escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{escape(label)} ↗</a></td>'
    )


def render_shell(filename: str, breadcrumb: str, eyebrow: str, title: str, lede: str, body_html: str) -> str:
    nav_html = "".join(
        f'<a class="nav-link"{(" aria-current=" + chr(34) + "page" + chr(34)) if href == filename else ""} href="{href}">'
        f'<span class="nav-num">{num}</span><span>{escape(label)}</span></a>'
        for href, num, label in NAV_ITEMS
    )
    sib_html = "".join(
        f'<a class="nav-link" href="{href}"><span class="nav-num">{num}</span><span>{escape(label)}</span></a>'
        for href, num, label in SIBLING_LINKS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="NFL3 Decision &amp; Line Origination Hub — Source-Verified NFL Analytics">
  <title>{escape(title)} | NFL3 Decision Hub</title>
  <link rel="stylesheet" href="assets/style.css">
  <script src="assets/app.js" defer></script>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="index.html">
        <span class="brand-badge">N3</span>
        <span>
          <span class="brand-title">NFL3 Decision Hub</span>
          <span class="brand-sub">Origination &amp; Depth Lab</span>
        </span>
      </a>
      <div class="nav-group-label">Decision Hub Categories</div>
      <nav class="nav-list" aria-label="Primary categories">
        {nav_html}
      </nav>
      <div class="nav-group-label">Repository Workspaces</div>
      <nav class="nav-list" aria-label="Sibling repository workspaces">
        {sib_html}
      </nav>
      <div class="sidebar-footer">
        <strong>Zero-Hallucination Mode</strong>
        Verified 2026-11-12 UTC (2026 Wk 10). Unconfirmed values remain strictly blank.
      </div>
    </aside>
    <div class="main-area">
      <header class="topbar">
        <div class="breadcrumb">NFL3 HUB / <strong>{escape(breadcrumb)}</strong></div>
        <div class="topbar-controls">
          <span id="filter-row-count" class="section-note" aria-live="polite"></span>
          <input id="global-table-search" class="search-input" type="search" placeholder="Filter table rows on this page..." aria-label="Filter table rows on this page">
          <span class="verified-pill">Verified 2026-11-12 UTC</span>
        </div>
      </header>
      <main id="main-content" class="page-container">
        <section class="page-hero">
          <div class="eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p class="hero-lede">{escape(lede)}</p>
        </section>
        {body_html}
        <footer class="site-footer">
          <span>NFL3 Decision &amp; Line Origination Hub · Session <code>arena-40c7529f</code></span>
          <span>Every table row cites a verified official source · <a href="flagged.html">Open Flagged for Review →</a></span>
        </footer>
      </main>
    </div>
  </div>
</body>
</html>
"""


def build_index(req_data: dict) -> str:
    rows_html = ""
    for r in req_data["requirements_matrix"]:
        rows_html += (
            f'<tr data-tag="{escape(r["status"].lower())}">'
            f'{td_cell(r["req_id"])}'
            f'{td_cell(r["category"])}'
            f'{td_cell(r["requirement"])}'
            f'{td_cell(r["current_state"])}'
            f'{td_cell(r["verified_metric"], is_blank_allowed=True)}'
            f'<td><a class="source-link" href="{escape(r["deliverable_page"], quote=True)}">{escape(r["deliverable_page"])} →</a></td>'
            f'{td_cell(r["status"], as_badge=True)}'
            f'{source_td(r["source_label"], r["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Strict Verification Policy Active:</strong> Every row in every table links directly to an official primary source (<code>nfl.com</code>, <code>operations.nfl.com</code>, <code>nextgenstats.nfl.com</code>, official NFL club depth charts, <code>gaming.nv.gov</code>, <code>itl.nist.gov</code>, <code>weather.gov</code>, <code>scikit-learn.org</code>, <code>kansspelautoriteit.nl</code>). Striped amber cells (<code>""</code>) denote values intentionally left blank because no verified official dataset establishes them yet.
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Official Domains Verified</div>
        <div class="kpi-value">17</div>
        <div class="kpi-sub">NFL, 7 Club Depth Charts, NGCB, NIST, NWS</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">1st–4th String Chains</div>
        <div class="kpi-value">16</div>
        <div class="kpi-sub">Offense &amp; Defense cross-checked vs. Wk 9/10</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Strategies &amp; Gates</div>
        <div class="kpi-value">8 / 8</div>
        <div class="kpi-sub">Singles, Parlays &amp; Props · 0/8 Gates Run</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Suggestions &amp; Flags</div>
        <div class="kpi-value">10 / 18</div>
        <div class="kpi-sub">Reviewable before any implementation</div>
      </div>
    </div>

    <div class="card-grid">
      <div class="info-card">
        <div class="eyebrow">02 · Briefing</div>
        <h3>Executive Summary</h3>
        <p>High-level synthesis of verified NFL roster/inactive rules, Nevada Gaming Control Board parlay vs. straight hold benchmarks, 2026 rule shifts, and go/no-go blockers.</p>
        <a class="card-link" href="executive-summary.html">Open Executive Summary →</a>
      </div>
      <div class="info-card">
        <div class="eyebrow">03 · Path Selection</div>
        <h3>Suggestions Review Center</h3>
        <p>Compare Path A vs. Path B trade-offs across 10 proposed site &amp; modeling upgrades and export a human review decision sheet prior to changing production code.</p>
        <a class="card-link" href="suggestions.html">Review Suggestions →</a>
      </div>
      <div class="info-card">
        <div class="eyebrow">04 · Epistemic Audit</div>
        <h3>Pre-Decision Q&amp;A &amp; Discovery</h3>
        <p>12 gating questions separating confirmed official facts from blank unverified answers, paired with concrete discovery actions.</p>
        <a class="card-link" href="questions.html">Inspect Questions &amp; Gaps →</a>
      </div>
      <div class="info-card">
        <div class="eyebrow">05 · Skill Over Luck</div>
        <h3>Line Origination, Gates &amp; Leaderboard</h3>
        <p>Single bets, parlays, and player prop combos governed by Gates G1–G8, copula correlation protocols, and anti-luck escrowed reward tiers.</p>
        <a class="card-link" href="origination.html">Explore Strategy Lab →</a>
      </div>
      <div class="info-card">
        <div class="eyebrow">06 · Lineup Deficiencies</div>
        <h3>1st–4th String Offense &amp; Defense Tracker</h3>
        <p>Official club depth charts (WAS, NYG, NE, DET, BAL, DEN, SEA) reconciled line-by-line against Week 9/10 NFL injury reports.</p>
        <a class="card-link" href="depth-injuries.html">Inspect Depth Chains →</a>
      </div>
      <div class="info-card">
        <div class="eyebrow">07 &amp; 08 · Verification</div>
        <h3>Repo Audit &amp; Flagged for Review</h3>
        <p>Line-by-line repository audit across all parallel workspaces plus every official source contradiction and intentionally blank value.</p>
        <a class="card-link" href="flagged.html">View Flagged Register →</a>
      </div>
    </div>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">Full Requirements Traceability</div>
          <h2>Master Project Requirements Matrix</h2>
        </div>
        <p class="section-note">Striped empty cells indicate unverified empirical metrics intentionally left blank.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Category</th>
              <th scope="col">Requirement</th>
              <th scope="col">Current Verified State</th>
              <th scope="col">Verified Metric</th>
              <th scope="col">Subpage</th>
              <th scope="col">Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "index.html",
        "Command Overview",
        "01 · NFL Decision & Line Origination Workspace",
        "Collect, Organize & Originate on Verified Evidence",
        "A clean, source-verified decision dashboard for NFL line origination, 1st–4th string offense and defense backup deficiency tracking, validation-gated strategy competitions, and pre-implementation path review.",
        body,
    )


def build_exec_summary(req_data: dict) -> str:
    rows_html = ""
    for f in req_data["executive_findings"]:
        rows_html += (
            f"<tr>"
            f'{td_cell(f["pillar"])}'
            f'{td_cell(f["verified_finding"])}'
            f'{td_cell(f["confirmed_benchmark"], is_blank_allowed=True)}'
            f'{td_cell(f["open_gap"])}'
            f'{source_td(f["source_label"], f["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="card-grid">
      <div class="info-card">
        <div class="eyebrow">Core Conclusion 01</div>
        <h3>Decision Readiness Precedes Line Execution</h3>
        <p>While official NFL rules, club 1st–4th string depth charts, Next Gen Stats definitions, and Nevada regulatory hold benchmarks are verified today, <strong>zero live originated lines or strategy edges are claimed</strong> until licensed historical odds, play-by-play archives, and jurisdictional approvals close Questions Q-01 through Q-12.</p>
      </div>
      <div class="info-card">
        <div class="eyebrow">Core Conclusion 02</div>
        <h3>Why Multi-Source Depth Tracking Is Mandatory</h3>
        <p>Cross-checking 2026 Week 9 &amp; Week 10 <code>nfl.com/injuries/</code> reports against 7 official NFL club depth charts proved that single-source trackers fail: IR stars (e.g., Lamar Jackson) drop off weekly injury tables while remaining 1st-string on club depth charts, and injured rotational players (Lucas Patrick, Malik Harrison, Kerby Joseph) can be omitted from club two-deeps.</p>
      </div>
      <div class="info-card">
        <div class="eyebrow">Core Conclusion 03</div>
        <h3>Controlling Variance vs. Skill in Parlays &amp; Combos</h3>
        <p>Statewide Nevada Gaming Control Board filings confirm Parlay Cards hold <strong>27.79%</strong> (Sep 2025) / <strong>8.31%</strong> (12-month) versus <strong>6.70%</strong> / <strong>5.05%</strong> on straight Football pools. Consequently, leaderboard rewards must rank strategies strictly by post-gate out-of-sample Brier Skill Score and vig-free Closing Line Value—never raw short-term ROI.</p>
      </div>
    </div>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">Executive Briefing Table</div>
          <h2>Six Pillars of Verified Evidence &amp; Open Blockers</h2>
        </div>
        <p class="section-note">All benchmarks verified directly on 2026-11-12 UTC; unestablished values remain blank.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Executive Pillar</th>
              <th scope="col">Verified Finding</th>
              <th scope="col">Confirmed Official Benchmark</th>
              <th scope="col">Open Blocker / Missing Input</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "executive-summary.html",
        "Executive Summary",
        "02 · Executive Summary",
        "Executive Summary: Architecture, Verified Facts & Go/No-Go Blockers",
        "An end-to-end briefing for stakeholders reviewing what official sources establish today, why single-source injury tracking and naive parlay multiplication fail, and what must be unlocked before live line origination.",
        body,
    )


def build_suggestions(sug_data: list[dict]) -> str:
    rows_html = ""
    for s in sug_data:
        sid = escape(s["id"], quote=True)
        rows_html += (
            f'<tr data-tag="{escape(s["category"].lower())}">'
            f'{td_cell(s["id"])}'
            f'{td_cell(s["category"])}'
            f'<td><strong>{escape(s["title"])}</strong><br><span class="section-note">{escape(s["problem"])}</span></td>'
            f'{td_cell(s["decision_improvement"])}'
            f'{td_cell(s["path_a"])}'
            f'{td_cell(s["path_b"])}'
            f'{td_cell(s["prerequisites"])}'
            f'<td>'
            f'<select class="path-select" data-sug-id="{sid}" aria-label="Choose path for {sid}">'
            f'<option value="Pending Review">Pending Review</option>'
            f'<option value="Path A">Approve Path A</option>'
            f'<option value="Path B">Approve Path B</option>'
            f'<option value="Defer">Defer / Hold</option>'
            f"</select>"
            f"</td>"
            f'{source_td(s["source_label"], s["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Review-Before-Implementation Gate:</strong> None of the 10 improvements below have been auto-applied to production pipelines. Use the <strong>Reviewer Path Selector</strong> column to record preferred options locally and export a JSON decision slip before authorizing engineering work.
      <div id="suggestion-selection-summary" style="margin-top:6px;font-weight:700;"></div>
    </div>

    <div class="filter-bar">
      <button class="filter-btn active" type="button" data-filter="all">All Suggestions (10)</button>
      <button class="filter-btn" type="button" data-filter="data">Data &amp; Hygiene</button>
      <button class="filter-btn" type="button" data-filter="line">Line &amp; Parlay Pricing</button>
      <button class="filter-btn" type="button" data-filter="validation">Validation &amp; Leaderboard</button>
      <button class="filter-btn" type="button" data-filter="lineup">Lineups &amp; Environment</button>
      <button id="export-decisions-btn" class="action-btn primary" type="button">Export Chosen Paths (.json)</button>
      <button id="reset-decisions-btn" class="action-btn" type="button">Reset Selections</button>
    </div>

    <section class="section-block" style="margin-top:14px;">
      <div class="section-header">
        <div>
          <div class="eyebrow">Decision-Support Backlog</div>
          <h2>Site &amp; System Improvement Proposals</h2>
        </div>
        <p class="section-note">Compare lightweight Path A against institutional Path B before implementing changes.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Category</th>
              <th scope="col">Suggestion &amp; Observed Gap</th>
              <th scope="col">How It Improves Decisions</th>
              <th scope="col">Path A (Lightweight)</th>
              <th scope="col">Path B (Institutional)</th>
              <th scope="col">Prerequisites</th>
              <th scope="col">Choose Path</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "suggestions.html",
        "Suggestions Review",
        "03 · Dedicated Suggestions Review Section",
        "Site & Architecture Improvement Suggestions",
        "Review concrete upgrades designed to strengthen decision quality, compare implementation paths side-by-side, and record path approvals before modifying the system.",
        body,
    )


def build_questions(q_data: list[dict]) -> str:
    rows_html = ""
    for q in q_data:
        tag = "verified" if q["verified_answer"] else "blank"
        rows_html += (
            f'<tr data-tag="{tag}">'
            f'{td_cell(q["q_id"] + " · " + q["domain"])}'
            f'{td_cell(q["question"])}'
            f'{td_cell(q["known_info"])}'
            f'{td_cell(q["verified_answer"], is_blank_allowed=True)}'
            f'{td_cell(q["missing_info"])}'
            f'{td_cell(q["discovery_suggestion"])}'
            f'{td_cell(q["status"], as_badge=True)}'
            f'{source_td(q["source_label"], q["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Epistemic Boundary:</strong> Eleven of twelve pre-decision questions depend on owner policy, commercial licensing, or uncollected historical feeds and therefore leave <strong>Confirmed Answer</strong> strictly blank (<code>""</code>). Only <code>Q-04</code> has a rule-confirmed league cutoff (T-90m Inactive List / T-60m roof lock).
    </div>

    <div class="filter-bar">
      <button class="filter-btn active" type="button" data-filter="all">All Questions (12)</button>
      <button class="filter-btn" type="button" data-filter="blank">Blank / Unverified Answers (11)</button>
      <button class="filter-btn" type="button" data-filter="verified">Rule-Confirmed Cutoff (1)</button>
    </div>

    <section class="section-block" style="margin-top:14px;">
      <div class="section-header">
        <div>
          <div class="eyebrow">Knowns vs. Unknowns</div>
          <h2>Pre-Decision Questions, Answers &amp; Missing-Information Discovery Plan</h2>
        </div>
        <p class="section-note">Address these items before committing capital, originating live lines, or funding leaderboard rewards.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">ID &amp; Domain</th>
              <th scope="col">Question Required Before Decision</th>
              <th scope="col">Information We Have (Verified)</th>
              <th scope="col">Confirmed Answer</th>
              <th scope="col">Information We Do Not Have</th>
              <th scope="col">Suggestion to Discover Missing Info</th>
              <th scope="col">Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "questions.html",
        "Pre-Decision Q&A",
        "04 · Questions, Knowns, Unknowns & Discovery",
        "Pre-Decision Questions & Missing Information Discovery Matrix",
        "A transparent accounting of every question, confirmed fact, missing input, and discovery protocol required before reasonable NFL modeling or betting decisions can be made.",
        body,
    )


def build_origination(orig_data: dict) -> str:
    reg_rows = ""
    for b in orig_data["regulatory_benchmarks"]:
        reg_rows += (
            f"<tr>"
            f'{td_cell(b["category"])}'
            f'{td_cell(b["locations_sep_2025"])}'
            f'{td_cell(b["win_amount_sep_2025_usd_k"])}'
            f'{td_cell(b["win_pct_sep_2025"])}'
            f'{td_cell(b["win_pct_3m_jul_sep_2025"])}'
            f'{td_cell(b["win_pct_12m_oct24_sep25"])}'
            f'{td_cell(b["origination_implication"])}'
            f'{source_td(b["source_label"], b["source_url"])}'
            f"</tr>"
        )

    strat_rows = ""
    for s in orig_data["strategies"]:
        strat_rows += (
            f'<tr data-tag="{escape(s["bet_structure"].lower())}">'
            f'{td_cell(s["strat_id"])}'
            f'{td_cell(s["bet_structure"])}'
            f'<td><strong>{escape(s["name"])}</strong><br><span class="section-note">{escape(s["signal_mechanism"])}</span></td>'
            f'{td_cell(s["gate_status"], as_badge=True)}'
            f'{td_cell(s["effective_n"], is_blank_allowed=True)}'
            f'{td_cell(s["oos_brier_skill"], is_blank_allowed=True)}'
            f'{td_cell(s["clv_bps"], is_blank_allowed=True)}'
            f'{td_cell(s["leaderboard_rank"], is_blank_allowed=True)}'
            f'{td_cell(s["reward_tier"])}'
            f'{source_td(s["source_label"], s["source_url"])}'
            f"</tr>"
        )

    gate_rows = ""
    for g in orig_data["validation_gates"]:
        gate_rows += (
            f"<tr>"
            f'{td_cell(g["gate_id"])}'
            f'{td_cell(g["objective"])}'
            f'{td_cell(g["pass_criteria"])}'
            f'{td_cell(g["current_status"], as_badge=True)}'
            f'{source_td(g["source_label"], g["source_url"])}'
            f"</tr>"
        )

    corr_rows = ""
    for c in orig_data["correlations"]:
        corr_rows += (
            f"<tr>"
            f'{td_cell(c["pair_id"])}'
            f'{td_cell(c["leg_a"])}'
            f'{td_cell(c["leg_b"])}'
            f'{td_cell(c["structural_driver"])}'
            f'{td_cell(c["empirical_rho"], is_blank_allowed=True)}'
            f'{td_cell(c["ci_95"], is_blank_allowed=True)}'
            f'{td_cell(c["estimator"])}'
            f'{td_cell(c["status"], as_badge=True)}'
            f'{source_td(c["source_label"], c["source_url"])}'
            f"</tr>"
        )

    gov_rows = ""
    for r in orig_data["reward_governance"]:
        gov_rows += (
            f"<tr>"
            f'{td_cell(r["rule_id"])}'
            f'{td_cell(r["mechanism"])}'
            f'{td_cell(r["anti_luck_effect"])}'
            f'{td_cell(r["status"], as_badge=True)}'
            f'{source_td(r["source_label"], r["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Selective Skill vs. Variance Note:</strong> Aleatoric in-game variance (fumble bounces, tipped interceptions, overtime coin tosses) cannot be deleted from single NFL contests, but <strong>luck in strategy ranking and reward allocation is systematically stripped out</strong> by enforcing Gates G1–G8, vig-free Closing Line Value (CLV), Murphy Brier decomposition, multiple-testing FDR haircuts, and 8-week prospective shadow lockouts. All empirical score, correlation (<code>rho</code>), and rank cells remain strictly blank (<code>""</code>) until licensed historical play-by-play and closing-odds feeds are connected.
    </div>

    <div class="formula-strip">
      <div class="formula-box">
        <div class="eyebrow">Fair Line Origination</div>
        <strong>Marginal Fair Decimal Price</strong>
        <code>O_fair = (1 - p_push) / p_win</code>
        <span class="section-note">Explicitly models push mass on NFL key numbers (3, 7, 10) before comparing against vig-stripped market consensus.</span>
      </div>
      <div class="formula-box">
        <div class="eyebrow">2-Leg Correlated Parlay / Combo</div>
        <strong>Exact Binary Joint Probability</strong>
        <code>P(A &amp; B) = P(A)P(B) + rho_AB * sqrt(P(A)(1-P(A))P(B)(1-P(B)))</code>
        <span class="section-note">Originate parlay/combo only if P(A &amp; B) at the lower 95% CI bound of rho_AB exceeds implied bookmaker SGP probability.</span>
      </div>
      <div class="formula-box">
        <div class="eyebrow">Skill Separation Gate</div>
        <strong>Brier Skill Score &amp; Cluster t-Stat</strong>
        <code>BSS = 1 - (BS_model / BS_market_vigfree),  t = mean(d_g) / (sd(d_g)/sqrt(G))</code>
        <span class="section-note">Clustered by independent game G so correlated same-game props never inflate sample size N_eff.</span>
      </div>
    </div>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">01 · Official Regulatory Hold Reality</div>
          <h2>Nevada Gaming Control Board Benchmarks: Straight Football vs. Parlay Cards</h2>
        </div>
        <p class="section-note">Verified verbatim from NGCB September 2025 Monthly Revenue Report (Form NGC-31, Statewide Nonrestricted).</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">NGCB Reporting Unit</th>
              <th scope="col">Sep 2025 Locs</th>
              <th scope="col">Sep 2025 Win</th>
              <th scope="col">Sep 2025 Win %</th>
              <th scope="col">3-Mo Win %</th>
              <th scope="col">12-Mo Win %</th>
              <th scope="col">Line Origination &amp; Strategy Implication</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {reg_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">02 · Strategy Competition Leaderboard</div>
          <h2>Candidate Line-Origination &amp; Signal Strategies (Singles, Parlays &amp; Prop Combos)</h2>
        </div>
        <p class="section-note">Filter by bet structure; empirical metrics &amp; ranks are intentionally blank until Gates G1–G8 execute on licensed data.</p>
      </div>
      <div class="filter-bar">
        <button class="filter-btn active" type="button" data-filter="all">All Candidates (8)</button>
        <button class="filter-btn" type="button" data-filter="single">Single Bets &amp; Single Props (5)</button>
        <button class="filter-btn" type="button" data-filter="parlay">Parlays (1)</button>
        <button class="filter-btn" type="button" data-filter="combo">Player Prop Combos (2)</button>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Bet Structure</th>
              <th scope="col">Strategy &amp; Signal Hypothesis</th>
              <th scope="col">Gate Status</th>
              <th scope="col">N_eff</th>
              <th scope="col">OOS Brier Skill</th>
              <th scope="col">CLV (bps)</th>
              <th scope="col">Rank</th>
              <th scope="col">Reward Eligibility</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {strat_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">03 · Qualification Protocol</div>
          <h2>Mandatory 8-Gate Validation Pipeline (G1–G8)</h2>
        </div>
        <p class="section-note">Every single, parlay, and player-prop combo strategy must clear all 8 sequential gates before ranking.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Validation Gate</th>
              <th scope="col">Core Objective</th>
              <th scope="col">Strict Pass Criteria</th>
              <th scope="col">Current Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {gate_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">04 · Joint Outcome Structure</div>
          <h2>Pairwise Leg Correlation Matrix &amp; Estimation Protocol</h2>
        </div>
        <p class="section-note">Empirical rho and 95% CI cells are left blank rather than guessed from folklore; structural drivers and estimators are specified.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Pair ID</th>
              <th scope="col">Leg A</th>
              <th scope="col">Leg B</th>
              <th scope="col">Structural Mechanism</th>
              <th scope="col">Empirical rho</th>
              <th scope="col">95% CI</th>
              <th scope="col">Statistical Estimator</th>
              <th scope="col">Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {corr_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">05 · Competition Incentives</div>
          <h2>Anti-Luck Leaderboard &amp; Escrowed Reward Governance</h2>
        </div>
        <p class="section-note">Rules preventing variance-seeking entries or multi-account trial mining from capturing competition rewards.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Rule ID</th>
              <th scope="col">Governance Mechanism</th>
              <th scope="col">How It Removes Luck From Strategy Selection</th>
              <th scope="col">Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {gov_rows}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "origination.html",
        "Line Origination & Leaderboard",
        "05 · Origination, Signals, Gates, Correlations & Rewards",
        "NFL Line Origination, Validation Gates & Skill Leaderboard",
        "Research framework for originating independent NFL lines and evaluating single bets, parlays, and player prop combos through 8 validation gates designed to reward repeatable forecasting skill over luck.",
        body,
    )


def build_depth_injuries(inj_data: dict) -> str:
    rule_rows = ""
    for r in inj_data["roster_rules"]:
        rule_rows += (
            f"<tr>"
            f'{td_cell(r["rule_id"])}'
            f'{td_cell(r["rule_name"])}'
            f'{td_cell(r["verified_specification"])}'
            f'{td_cell(r["lineup_deficiency_relevance"])}'
            f'{source_td(r["source_label"], r["source_url"])}'
            f"</tr>"
        )

    dep_rows = ""
    for d in inj_data["depth_deficiencies"]:
        tags = [d["side"].lower()]
        if d["string_4"]:
            tags.append("fourdeep")
        if "Out" in (d["string_1"] + d["string_2"]) or "DNP" in (d["string_1"] + d["string_2"]):
            tags.append("stressed")
        dep_rows += (
            f'<tr data-tag="{" ".join(tags)}">'
            f'{td_cell(d["chain_id"])}'
            f'{td_cell(d["side"], as_badge=True)}'
            f'{td_cell(d["club_week"])}'
            f'{td_cell(d["position"])}'
            f'{td_cell(d["string_1"])}'
            f'{td_cell(d["string_2"])}'
            f'{td_cell(d["string_3"], is_blank_allowed=True)}'
            f'{td_cell(d["string_4"], is_blank_allowed=True)}'
            f'{td_cell(d["deficiency_classification"], as_badge=True)}'
            f'{td_cell(d["epa_dropoff"], is_blank_allowed=True)}'
            f'{source_td(d["source_label"], d["source_url"])}'
            f"</tr>"
        )

    eng_rows = ""
    for e in inj_data["deficiency_engine_schema"]:
        eng_rows += (
            f"<tr>"
            f'{td_cell(e["stage"])}'
            f'{td_cell(e["inputs"])}'
            f'{td_cell(e["output_signal"])}'
            f'{source_td(e["source_label"], e["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Verified 1st–4th String Official Club Depth Charts:</strong> Unlike sibling sessions that searched only <code>nfl.com/teams/.../depth-chart</code> (404), this hub verified live 2026 depth charts directly on <strong>7 official NFL club domains</strong> (<code>baltimoreravens.com</code>, <code>patriots.com</code>, <code>detroitlions.com</code>, <code>commanders.com</code>, <code>giants.com</code>, <code>denverbroncos.com</code>, <code>seahawks.com</code>) and reconciled them line-by-line against <code>nfl.com/injuries/</code> (Weeks 9 &amp; 10, 2026). Note club disclaimers: published club charts are PR/media-compiled ("unofficial") and must be combined with 53-man/IR transactions and T-90m Game Day Inactives.
    </div>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">01 · League Roster &amp; Availability Mechanics</div>
          <h2>Verified Official NFL Roster, Elevation &amp; Pregame Inactive Rules</h2>
        </div>
        <p class="section-note">Verified from NFL Football Operations &amp; NFL Competition Committee policy texts.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Rule ID</th>
              <th scope="col">Official Mechanism</th>
              <th scope="col">Verified Specification</th>
              <th scope="col">Backup Deficiency Relevance</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {rule_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">02 · Starter vs. 2nd, 3rd &amp; 4th String Lineup Audit</div>
          <h2>Verified 2026 Offense &amp; Defense Depth-Chart Replacement Chains</h2>
        </div>
        <p class="section-note">3rd/4th string cells are blank where official club charts list only 2-deep/3-deep; EPA drop-off remains blank pending play-by-play feed.</p>
      </div>
      <div class="filter-bar">
        <button class="filter-btn active" type="button" data-filter="all">All Verified Chains (16)</button>
        <button class="filter-btn" type="button" data-filter="offense">Offense Only (11)</button>
        <button class="filter-btn" type="button" data-filter="defense">Defense Only (5)</button>
        <button class="filter-btn" type="button" data-filter="fourdeep">Full 4-String Verified (6)</button>
        <button class="filter-btn" type="button" data-filter="stressed">Starter/Backup Out or DNP (10)</button>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Unit</th>
              <th scope="col">Club &amp; Slate</th>
              <th scope="col">Pos</th>
              <th scope="col">1st String (Starter)</th>
              <th scope="col">2nd String Backup</th>
              <th scope="col">3rd String Backup</th>
              <th scope="col">4th String Backup</th>
              <th scope="col">Deficiency / Status Audit</th>
              <th scope="col">EPA Delta</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {dep_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">03 · Target Ingestion Pipeline</div>
          <h2>5-Stage Automated Offense &amp; Defense Deficiency Detection Architecture</h2>
        </div>
        <p class="section-note">Designed to solve every cross-source lag uncovered during our Week 9 &amp; Week 10 audit.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Pipeline Stage</th>
              <th scope="col">Official Inputs Required</th>
              <th scope="col">Deficiency Signal Produced</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {eng_rows}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "depth-injuries.html",
        "Depth & Injury Tracker",
        "06 · Offense & Defense 1st–4th String Availability Intelligence",
        "Injury Tracking & 1st–4th String Offense/Defense Backup Deficiencies",
        "Line-by-line verification of how starter absences cascade into 2nd, 3rd, and 4th string offensive and defensive replacements across official 2026 NFL injury reports and club depth charts.",
        body,
    )


def build_repo_audit(audit_data: dict) -> str:
    aud_rows = ""
    for a in audit_data["repo_audit"]:
        aud_rows += (
            f"<tr>"
            f'{td_cell(a["audit_id"])}'
            f'{td_cell(a["file_path"])}'
            f'{td_cell(a["inspected_scope"])}'
            f'{td_cell(a["verification_result"])}'
            f'{td_cell(a["audit_status"], as_badge=True)}'
            f'{source_td(a["source_label"], a["source_url"])}'
            f"</tr>"
        )

    src_rows = ""
    for s in audit_data["official_sources"]:
        src_rows += (
            f"<tr>"
            f'{td_cell(s["src_id"])}'
            f'{td_cell(s["publisher"])}'
            f'{td_cell(s["title"])}'
            f'{td_cell(s["verified_scope"])}'
            f'{td_cell(s["limitation"])}'
            f'{source_td(s["source_label"], s["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <section class="section-block" style="margin-top:0;">
      <div class="section-header">
        <div>
          <div class="eyebrow">01 · Line-by-Line Repository Review</div>
          <h2>Audit of Baseline Commit &amp; Concurrent Repository Workspaces</h2>
        </div>
        <p class="section-note">Every existing repository workspace was audited without overwriting sibling session files.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Audit ID</th>
              <th scope="col">Repository File / Scope</th>
              <th scope="col">Inspected Content</th>
              <th scope="col">Line-by-Line Verification Finding</th>
              <th scope="col">Audit Status</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {aud_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">02 · Primary Evidence Register</div>
          <h2>Verified Official Trusted Sources Registry (Inspected 2026-11-12 UTC)</h2>
        </div>
        <p class="section-note">Zero third-party blogs, rumor aggregators, or unverified scrapers are used in this hub.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Source ID</th>
              <th scope="col">Official Publisher</th>
              <th scope="col">Document / Feed Title</th>
              <th scope="col">What Was Verified</th>
              <th scope="col">Documented Limitation</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {src_rows}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "repo-audit.html",
        "Repo Audit & Sources",
        "07 · Repository Verification & Official Source Register",
        "Line-by-Line Repository Review & Verified Official Sources",
        "Complete audit log of NFL3 from initial commit 83b6ce2 through concurrent multi-session workspaces, paired with all 17 primary official sources verified during this session.",
        body,
    )


def build_flagged(flg_data: dict) -> str:
    irr_rows = ""
    for f in flg_data["irregularities"]:
        irr_rows += (
            f'<tr data-tag="irregularity">'
            f'{td_cell(f["flag_id"])}'
            f'{td_cell(f["origin"])}'
            f'{td_cell(f["item"])}'
            f'{td_cell(f["verified_observation"])}'
            f'{td_cell(f["handling"])}'
            f'{source_td(f["source_label"], f["source_url"])}'
            f"</tr>"
        )

    blk_rows = ""
    for b in flg_data["unverified_blanks"]:
        blk_rows += (
            f'<tr data-tag="blank">'
            f'{td_cell(b["blank_id"])}'
            f'{td_cell(b["table_location"])}'
            f'{td_cell(b["field_name"])}'
            f'{td_cell(b["verified_value"], is_blank_allowed=True)}'
            f'{td_cell(b["reason_unverified"])}'
            f'{source_td(b["source_label"], b["source_url"])}'
            f"</tr>"
        )

    body = f"""
    <div class="alert-banner">
      <strong>Non-Blocking Transparent Review Queue:</strong> Per project verification governance, every source contradiction, cross-workspace irregularity, and unconfirmed blank value is published below with direct links to official primary pages for human inspection. Nothing is hidden or filled by guesswork.
    </div>

    <div class="filter-bar">
      <button class="filter-btn active" type="button" data-filter="all">All Review Items (18)</button>
      <button class="filter-btn" type="button" data-filter="irregularity">Source &amp; Repo Irregularities (12)</button>
      <button class="filter-btn" type="button" data-filter="blank">Intentionally Blank Unverified Fields (6)</button>
    </div>

    <section class="section-block" style="margin-top:14px;">
      <div class="section-header">
        <div>
          <div class="eyebrow">01 · Irregularities Register</div>
          <h2>Flagged Official-Source Contradictions &amp; Repository Irregularities</h2>
        </div>
        <p class="section-note">Includes internal contradictions found inside official NFL pages as well as citation bugs in sibling workspaces.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Flag ID</th>
              <th scope="col">Origin</th>
              <th scope="col">Flagged Irregularity</th>
              <th scope="col">Exact Line-by-Line Observation</th>
              <th scope="col">Resolution / Handling</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {irr_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-block">
      <div class="section-header">
        <div>
          <div class="eyebrow">02 · Unverified Blank Values Register</div>
          <h2>Fields Left Blank Because No Official Source Confirms a Value</h2>
        </div>
        <p class="section-note">Verified Value column is strictly empty ('') across all unestablished metrics.</p>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Blank ID</th>
              <th scope="col">Site Location</th>
              <th scope="col">Unverified Field(s)</th>
              <th scope="col">Verified Value</th>
              <th scope="col">Why Unverified &amp; Required Unlock</th>
              <th scope="col">Official Source</th>
            </tr>
          </thead>
          <tbody>
            {blk_rows}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_shell(
        "flagged.html",
        "Flagged for Review",
        "08 · Flagged for Review",
        "Flagged for Review: Irregularities & Unverified Blank Items",
        "Centralized audit queue of all official-source contradictions, repository citation irregularities, and unconfirmed values intentionally left blank for manual review.",
        body,
    )


def main() -> None:
    req_data = load_json("requirements_summary.json")
    sug_data = load_json("suggestions.json")
    q_data = load_json("questions_discovery.json")
    orig_data = load_json("origination_leaderboard.json")
    inj_data = load_json("injuries_depth.json")
    audit_data = load_json("repo_audit_sources.json")
    flg_data = load_json("flagged_review.json")

    pages = {
        "index.html": build_index(req_data),
        "executive-summary.html": build_exec_summary(req_data),
        "suggestions.html": build_suggestions(sug_data),
        "questions.html": build_questions(q_data),
        "origination.html": build_origination(orig_data),
        "depth-injuries.html": build_depth_injuries(inj_data),
        "repo-audit.html": build_repo_audit(audit_data),
        "flagged.html": build_flagged(flg_data),
    }

    for name, html in pages.items():
        (HUB_ROOT / name).write_text(html, encoding="utf-8")

    print(f"Successfully generated {len(pages)} HTML pages in {HUB_ROOT}.")


if __name__ == "__main__":
    main()
