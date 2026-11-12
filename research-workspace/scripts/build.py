#!/usr/bin/env python3
"""Build a dependency-free, evidence-labeled static research dashboard."""
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NFL = 'https://www.nfl.com/injuries/league/2026/REG9'
DEPTH = 'https://static.clubs.nfl.com/image/upload/buccaneers/ohiml2zpdqt07wdkhc7s'
ODDS = 'https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL'
INTEGRITY = 'https://www.nfl.com/news/nfl-draftkings-fanduel-fanatics-sports-betting-partners'
NIST = 'https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=933682'
PAGES = 'https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages'

nav = [('overview','Overview','01'),('availability','Availability','02'),('strategies','Strategy lab','03'),('leaderboard','Leaderboard','04'),('decisions','Decision room','05'),('flagged','Flagged for review','06')]

def table(headers, rows):
    # The final column always identifies the official source of context or evidence.
    out = '<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">'+escape(x)+'</th>' for x in headers) + '<th scope="col">Source</th></tr></thead><tbody>'
    for cells, link, label in rows:
        assert len(cells) == len(headers)
        out += '<tr>' + ''.join('<td>'+escape(str(x))+'</td>' for x in cells) + '<td><a class="source" href="'+escape(link, quote=True)+'" target="_blank" rel="noopener noreferrer">'+escape(label)+' ↗</a></td></tr>'
    return out + '</tbody></table></div>'

def section(kicker, title, intro, body):
    return f'<section class="section"><div class="section-heading"><div><span class="eyebrow">{kicker}</span><h2>{title}</h2></div><p>{intro}</p></div>{body}</section>'

snapshot = [
    (['Baltimore','Lamar Jackson','QB','Thumb','Did Not Participate In Practice','Out'], NFL, 'NFL report'),
    (['Baltimore','Tyler Huntley','QB','Toe','Did Not Participate In Practice','Out'], NFL, 'NFL report'),
    (['Baltimore','Jaylinn Hawkins','S','Knee','Did Not Participate In Practice','Out'], NFL, 'NFL report'),
    (['Jacksonville','Bhayshul Tuten','RB','Ankle, Foot','Did Not Participate In Practice','Questionable'], NFL, 'NFL report'),
]
flags = [
    (['F01','Week label conflict','NFL report title says Week 10; page body says WEEK 9. Date and URL are retained; do not resolve by inference.','Open'], NFL, 'NFL report'),
    (['F02','No automated feed','No ingestion, freshness monitoring, historical archive or lineup reconciliation is installed. The example is a static snapshot.','Open'], NFL, 'NFL report'),
    (['F03','Replacement order unknown','Injury statuses alone do not establish a replacement, depth rank, active status, or defensive weakness.','Open'], DEPTH, 'Club depth chart'),
    (['F04','Odds and settlement missing','No timestamped prices, operator rules, results or licensed feed are present. No lines or returns are verified.','Open'], ODDS, 'NFL odds FAQ'),
    (['F05','Skill and correlations unmeasured','No historical dataset or held-out test exists; correlation, ranking, rewards and validation results remain unverified.','Open'], NIST, 'NIST research'),
    (['F06','Legal and data rights','Jurisdiction, permissions and licensing for collection, redistribution and any competition rewards are not established.','Open'], INTEGRITY, 'NFL integrity'),
]

content = {}
content['overview'] = (
    'Research dashboard', 'Make the next call<br><em>with better evidence.</em>',
    'A clear starting point for originating NFL lines, evaluating strategy ideas, and finding the information that is still missing.',
    '''<div class="notice"><span class="notice-dot"></span><div><strong>Research stage · not live</strong><p>No model, live feed, verified edge or betting recommendations are available. This dashboard is a sourced research and planning foundation.</p></div><a href="pages/flagged.html">Review limitations →</a></div>
    <div class="metrics"><div class="metric"><span>Evidence base</span><strong>Official</strong><small>NFL, club, NIST &amp; GitHub</small></div><div class="metric"><span>Candidate strategies</span><strong>03</strong><small>Proposals, not validated</small></div><div class="metric"><span>Live signals</span><strong>—</strong><small>Feed not connected</small></div><div class="metric"><span>Validation status</span><strong>Pending</strong><small>No historical backtest</small></div></div>''' +
    section('01 / EXECUTIVE SUMMARY','The state of play','What is known, what is not, and the most useful next step.', table(['Area','Finding','Next step'], [
        (['Evidence','The repository began with only a README; no sports data or models were present.','Establish approved, timestamped data sources before modeling.'], PAGES, 'GitHub Pages docs'),
        (['Availability','NFL publishes injury and practice statuses; they do not by themselves establish replacement order.','Reconcile club depth charts, inactives and actual participation.'], NFL, 'NFL report'),
        (['Pricing','NFL says its odds widgets use bookmaker-provided prices.','Secure a permitted, timestamped odds and settlement source.'], ODDS, 'NFL odds FAQ'),
        (['Decision','Three strategy concepts are documented, but none has passed a gate.','Freeze a protocol, then run chronological out-of-sample tests.'], NIST, 'NIST research'),
    ])) + '''<div class="next-grid"><a class="next-card" href="pages/decisions.html"><span>START HERE ↗</span><h3>Open the decision room</h3><p>Review the open questions and compare proposed paths before implementation.</p></a><a class="next-card pale" href="pages/strategies.html"><span>RESEARCH ↗</span><h3>Explore the strategy lab</h3><p>See the proposed signals, validation gates and correlation approach.</p></a></div>''')

content['availability'] = ('Player availability','Availability is<br><em>more than an injury.</em>', 'Separate what the league reports from what must still be established about lineups, replacements and on-field impact.',
    '''<div class="notice"><span class="notice-dot"></span><div><strong>Static historical examples · not a current injury tracker</strong><p>Observed on 12 Nov 2026 from the linked NFL report for the 5 Nov 2026 game. Statuses can change; do not use as current game-day information.</p></div></div>''' +
    section('01 / SOURCE EXCERPT','Reported availability','The following values are reproduced from the report; blanks elsewhere are not filled by inference.',table(['Team','Player','Pos.','Injury','Practice status','Game status'],snapshot)) +
    section('02 / PROPOSED PIPELINE','From status to impact','Design only. No collection or classification is running.',table(['Step','Required evidence','Decision rule'],[
        (['1 · Capture','NFL injury report, source URL and retrieval timestamp.','Preserve practice and game status separately; retain revisions.'],NFL,'NFL report'),
        (['2 · Map depth','Team-published depth charts and dated roster transactions.','Store rank and effective time; label team depth charts unofficial where stated.'],DEPTH,'Club example'),
        (['3 · Confirm','Team announcements, official inactives and game participation.','Do not assert a replacement until evidence supports it; retain unknowns.'],DEPTH,'Club example'),
        (['4 · Estimate','Historical position-level participation, performance, opponent and game context.','Compare like-for-like roles out of sample; uncertainty and missingness remain visible.'],NIST,'NIST research'),
    ])))

content['strategies'] = ('Strategy lab','Ideas are not<br><em>edges. Test them.</em>', 'Three candidate approaches for singles, parlays and player props. Each starts as a hypothesis, not a pick or a promise.',
    section('01 / CANDIDATES','Signal hypotheses','All candidates are unvalidated; source links support the inputs or methodology, not claims of profitability.',table(['Candidate','Hypothesis &amp; inputs'.replace('&amp;','&'),'Market','Status'],[
        (['S01 · Team strength','Model score margin and total from historical scores, schedule and time-stamped availability; produce a probability distribution.','Single spread / total','Proposed'],NFL,'NFL report'),
        (['S02 · Joint game outcomes','Simulate common game states and compute joint event probabilities; compare with actual combined prices.','Parlay','Proposed'],NIST,'NIST research'),
        (['S03 · Player opportunity','Model usage and performance conditional on confirmed availability, role and opponent; jointly simulate related player outcomes.','Player prop combinations','Proposed'],DEPTH,'Club example'),
    ])) +
    section('02 / VALIDATION','Gates before a leaderboard','Proposed protocol; thresholds and reward rules must be frozen before testing, not selected after seeing results.',table(['Gate','Pass condition / evidence'],[
        (['01 · Provenance','Permitted official sources, archived timestamps, known coverage and reproducible settlement; no future information in features.'],NFL,'NFL report'),
        (['02 · Freeze','Pre-register market, rules, baseline, minimum sample size, error metric, confidence level, costs and selection-adjustment method.'],NIST,'NIST research'),
        (['03 · Walk forward','Train only on earlier games; evaluate on later untouched games; retain a final holdout and compare a simple baseline.'],NIST,'NIST research'),
        (['04 · Calibrate','Report log loss / Brier score, calibration, sample size and uncertainty by market and season; include rejected trials.'],NIST,'NIST research'),
        (['05 · Economic test','Use available timestamped executable prices and actual settlement including pushes, voids, limits and costs; test net results with game-clustered uncertainty.'],ODDS,'NFL odds FAQ'),
        (['06 · Monitoring','Shadow run first; stop on stale data, drift or failed controls. Never claim luck has been eliminated.'],INTEGRITY,'NFL integrity'),
    ])) +
    '''<div class="callout"><span class="eyebrow">MODEL NOTES / PROPOSED</span><h3>Price the joint outcome, not the story.</h3><p>For a single event with estimated probability p, a fair decimal price is 1/p (excluding pushes and costs). For a parlay, use the estimated joint probability, not the product of marginal probabilities unless independence is justified. Operator settlement rules and available prices must be checked first.</p><p>For pairs of binary outcomes, estimate Pearson/phi correlation from aligned observations, report sample size and game-clustered confidence intervals, and check out of sample. Correlation depends on market definitions and context; it is not a joint probability. No numeric correlations can be verified yet.</p><a href="'''+NIST+'''" target="_blank" rel="noopener noreferrer">Methodological context: NIST research ↗</a></div>''')

content['leaderboard'] = ('Leaderboard','Earn a place<br><em>on evidence.</em>', 'A competition design that rewards repeatable forecasting skill, not a lucky run. There are no verified results to rank yet.',
    '''<div class="notice"><span class="notice-dot"></span><div><strong>No ranked entries</strong><p>All three concepts are proposals. There are no measured scores, returns, correlations or rewards.</p></div><a href="strategies.html">See validation gates →</a></div>''' +
    section('01 / CANDIDATE BOARD','Awaiting validation','Performance cells are intentionally blank until data and tests are verified.',table(['Strategy','Gate status','Sample','Out-of-sample score','Correlation','Rank'],[
        (['S01 · Team strength','Not tested','','','',''],NIST,'NIST research'),
        (['S02 · Joint game outcomes','Not tested','','','',''],NIST,'NIST research'),
        (['S03 · Player opportunity','Not tested','','','',''],NIST,'NIST research'),
    ])) +
    section('02 / COMPETITION DESIGN','A fairer contest','These are proposed rules, not an operating competition.',table(['Component','Recommendation'],[
        (['Eligibility','Require all gates to pass; log every registered strategy, version, trial and failed submission.'],NIST,'NIST research'),
        (['Ranking','Rank within comparable market cohorts by predeclared out-of-sample proper scoring improvement versus baseline; publish uncertainty and sample size.'],NIST,'NIST research'),
        (['Ties &amp; uncertainty'.replace('&amp;','&'),'Treat overlapping uncertainty as inconclusive; do not rank underpowered entries as winners.'],NIST,'NIST research'),
        (['Rewards','Propose non-cash recognition only after independent holdout verification; eligibility, timing and legal approval remain undecided.'],INTEGRITY,'NFL integrity'),
        (['Risk','No staking or guaranteed returns; gambling laws and platform policies vary.'],INTEGRITY,'NFL integrity'),
    ])))

content['decisions'] = ('Decision room','Choose the path<br><em>before building it.</em>', 'A reviewable backlog of questions, missing information and suggested next moves. Recommendations are proposals, not established facts.',
    section('01 / OPEN QUESTIONS','What must be answered?','Each source is context for discovery; it does not answer project-specific unknowns.',table(['Question','Known / missing','Discovery action'],[
        (['Which markets and jurisdictions?','Singles, parlays and player props requested; jurisdiction and permitted market rules unknown.','Review applicable law and operator terms before any launch.'],INTEGRITY,'NFL integrity'),
        (['Can data be collected and redistributed?','NFL publishes reports; permitted access, historical coverage, terms and rights are unknown.','Obtain written permissions or a licensed feed; inventory fields and retention.'],NFL,'NFL report'),
        (['What is an actionable price?','Bookmaker prices exist; historical quotes, timestamps, limits and settlement rules are missing.','Evaluate licensed quote and settlement vendors, including corrections.'],ODDS,'NFL odds FAQ'),
        (['Who actually replaces an absent player?','A report provides status, not a confirmed replacement or depth impact.','Compare dated team charts, inactives and participation; preserve uncertainty.'],DEPTH,'Club example'),
        (['What proves skill?','No holdout, sample requirement, baseline or performance metrics exist.','Pre-register tests and thresholds; retain an untouched future holdout.'],NIST,'NIST research'),
        (['What are rewards and controls?','No prize, budget, eligibility or competition rules are established.','Choose recognition or a legally reviewed reward framework before inviting entries.'],INTEGRITY,'NFL integrity'),
    ])) +
    section('02 / SUGGESTIONS','Options to review','Ordered by dependency, not by a claim of measured impact.',table(['Priority','Suggestion','Trade-off / acceptance'],[
        (['01 · Data','License or obtain permitted official injury, lineup, game and odds history.','Cost and access unknown; require coverage, revision history and timestamps.'],NFL,'NFL report'),
        (['02 · Quality','Build automated capture with source links, deduplication and freshness alerts.','Requires operating infrastructure; stop outputs on stale or missing data.'],DEPTH,'Club example'),
        (['03 · Baseline','Start with a simple, reproducible single-market baseline.','Less complex than joint simulation; compare on a frozen forward test.'],NIST,'NIST research'),
        (['04 · Expansion','Add joint game and prop models only after single-event calibration.','Requires matched joint observations and valid operator settlement rules.'],ODDS,'NFL odds FAQ'),
        (['05 · Governance','Publish methodology, failures, uncertainty and independent review before rewards.','Slower release; reduces selection bias and unsubstantiated claims.'],INTEGRITY,'NFL integrity'),
    ])))

content['flagged'] = ('Review queue','Known gaps.<br><em>No guesswork.</em>', 'Irregularities and unverified items remain visible here so they can be investigated without being mistaken for facts.',
    section('01 / REVIEW REGISTER','Flagged for review','Open items do not become verified simply because a source is linked.',table(['ID','Issue','Evidence / follow-up','Status'], flags)) +
    '''<div class="callout"><span class="eyebrow">READ THIS FIRST</span><h3>Understanding the sources</h3><p>Official sources verify only the specific statements attributed to them. Club depth charts can be explicitly unofficial and may change. Methodology and recommendations are the project’s proposals, not endorsements by the linked organizations.</p><a href="'''+DEPTH+'''" target="_blank" rel="noopener noreferrer">Review the club's depth-chart caveat ↗</a></div>''')

for slug, (label, title, subtitle, body) in content.items():
    root = slug == 'overview'
    prefix = '' if root else '../'
    links = ''.join(f'<a class="nav-link {"active" if slug==key else ""}" {"aria-current=page" if slug==key else ""} href="{prefix + ("index.html" if key=="overview" else "pages/"+key+".html")}"><span>{num}</span>{name}</a>' for key,name,num in nav)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="NFL decision research dashboard"><title>{escape(label)} | NFL3</title><link rel="stylesheet" href="{prefix}assets/style.css"><script src="{prefix}assets/app.js" defer></script></head>
<body><a class="skip" href="#main">Skip to content</a><div class="app"><aside class="sidebar"><a class="brand" href="{prefix}index.html"><span class="brand-mark">N<span>3</span></span><span>NFL<span class="brand-thin"> / </span>LAB<small>DECISION INTELLIGENCE</small></span></a><div class="side-label">WORKSPACE</div><nav aria-label="Main navigation">{links}</nav><div class="side-bottom"><span class="status-dot"></span><div><strong>Research mode</strong><small>Evidence before action</small></div></div></aside><main id="main"><header class="topbar"><span>NFL3 <b>/</b> {escape(label)}</span><span class="top-status"><i></i> RESEARCH WORKSPACE</span></header><div class="content"><div class="hero"><div><span class="eyebrow"><span class="green-dot"></span> NFL3 / {escape(label.upper())}</span><h1>{title}</h1><p>{escape(subtitle)}</p></div><div class="hero-note"><span>THE PRINCIPLE</span><strong>Better inputs.<br>Better decisions.</strong><small>Independent research<br>Not betting advice</small></div></div>{body}<footer><span> NFL3 <b> / </b> RESEARCH WORKSPACE</span><span>Built for clarity, not certainty.</span><a href="{prefix}pages/flagged.html">Limitations &amp; review ↗</a></footer></div></main></div></body></html>'''
    output = ROOT / ('index.html' if root else 'pages/'+slug+'.html')
    output.write_text(html, encoding='utf-8')
print(f'Built {len(content)} pages.')
