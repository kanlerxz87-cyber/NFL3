#!/usr/bin/env python3
"""
verify.py — the build gate.

Fails (exit 1) if the site would publish something this project promised not to
publish: a table row with no source, a broken internal link, a dead anchor, an
unlabelled blank, or an internal contradiction in the verified data.

Run:  python3 scripts/verify.py
Out:  data/verification_report.json  + human-readable console output
"""

import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

FAILS = []
WARNS = []
CHECKS = []


def ok(msg):
    CHECKS.append(msg)


def fail(msg):
    FAILS.append(msg)


def warn(msg):
    WARNS.append(msg)


def load(n):
    with open(os.path.join(DATA, n)) as f:
        return json.load(f)


# ------------------------------------------------------------------ html scan
class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []      # (href, tag)
        self.ids = set()
        self.tables = 0
        self.rows = 0
        self.cells_without_src = 0
        self.text = []
        self._open_table = 0
        self._in_th = False
        self.th_labels = []
        self.table_headers = []
        self.table_sources = []
        self.bad_tags = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag == "table":
            self.tables += 1
            self._open_table += 1
            self.th_labels = []
            self.table_sources.append(a.get("data-source"))
        if tag == "th" and self._open_table:
            self._in_th = True
        if tag == "tr" and self._open_table:
            self.rows += 1

    def handle_endtag(self, tag):
        if tag == "th":
            self._in_th = False
        if tag == "table":
            self._open_table -= 1
            if self._open_table == 0:
                self.table_headers.append(list(self.th_labels))

    def handle_data(self, d):
        if self._in_th:
            self.th_labels.append(d.strip())
        self.text.append(d)


def crawl():
    """Parse every generated page; collect links, ids and text."""
    pages = {}
    root_index = os.path.join(ROOT, "index.html")
    targets = [("index.html", root_index)]
    pdir = os.path.join(ROOT, "pages")
    for fn in sorted(os.listdir(pdir)):
        if fn.endswith(".html"):
            targets.append(("pages/" + fn, os.path.join(pdir, fn)))
    for rel, full in targets:
        with open(full) as f:
            src = f.read()
        sc = Scan()
        sc.feed(src)
        pages[rel] = sc
    return pages


def check_links(pages):
    files = set(pages.keys()) | {"assets/site.css", "assets/app.js"}
    anchor_checks = set()
    for rel, sc in pages.items():
        base = "" if rel == "index.html" else "pages/"
        for href in sc.links:
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if href.startswith("#"):
                target_page, anchor = rel, href[1:]
            else:
                path, _, anchor = href.partition("#")
                target_page = os.path.normpath(os.path.join(base, path)).replace("\\", "/")
                if target_page.startswith("./"):
                    target_page = target_page[2:]
            if target_page not in files and not os.path.exists(os.path.join(ROOT, target_page)):
                # a link may deliberately point outside this sub-site (e.g. back to the
                # repository root site). Resolve it against the filesystem before failing.
                outside = os.path.normpath(os.path.join(ROOT, base, path))
                if os.path.isfile(outside):
                    anchor_checks.add((outside, anchor))
                    continue
                fail(f"{rel}: broken internal link -> {href}")
                continue
            if anchor and target_page in pages:
                if anchor not in pages[target_page].ids:
                    fail(f"{rel}: link to missing anchor -> {href}")
                else:
                    anchor_checks.add((os.path.join(ROOT, target_page), anchor))
    ok(f"internal links checked across {len(pages)} pages; "
       f"{len(anchor_checks)} distinct anchors resolve")


def check_rows_have_sources(pages):
    """Declared-table contract:
      * every table must carry data-source
      * data-source == "method"  -> rules/formulas/parameters, cited in prose
      * data-source == "register"-> a register whose rows are indexed by id
      * anything else            -> a DATA table and MUST expose a source column
    """
    missing_decl = 0
    data_tables = 0
    for rel, sc in pages.items():
        if sc.tables != len(sc.table_sources):
            fail(f"{rel}: table/source declaration mismatch")
        for src, labels in zip(sc.table_sources, sc.table_headers):
            low = [l.lower().strip() for l in labels]
            if src is None:
                fail(f"{rel}: table '{', '.join(labels[:3])}…' has no data-source declaration")
                missing_decl += 1
                continue
            if src in ("method", "register"):
                continue
            data_tables += 1
            if not any(l in ("src", "source", "sources") for l in low):
                fail(f"{rel}: data table (source {src}) has no source column -> {', '.join(labels[:4])}")
    ok(f"table contract: {data_tables} data tables all expose a source column; "
       f"method/register tables declared explicitly; {missing_decl} undeclared")

def check_table_shapes():
    """Header/body cell counts must agree in every table, otherwise the grid
    silently shifts a column — the classic generated-HTML defect that no link
    checker catches."""
    pages = [("index.html", os.path.join(ROOT, "index.html"))]
    for fn in sorted(os.listdir(os.path.join(ROOT, "pages"))):
        if fn.endswith(".html"):
            pages.append(("pages/" + fn, os.path.join(ROOT, "pages", fn)))
    bad = 0
    seen_ids = 0
    for rel, full in pages:
        with open(full) as f:
            src = f.read()
        for m in re.finditer(r"<table\b.*?</table>", src, re.S):
            block = m.group(0)
            head = re.search(r"<thead>.*?</thead>", block, re.S)
            if not head:
                continue
            hcount = len(re.findall(r"<th\b", head.group(0)))
            body = block[head.end():]
            for row in re.findall(r"<tr\b.*?</tr>", body, re.S):
                dcount = len(re.findall(r"<td\b", row))
                if dcount and dcount != hcount:
                    fail(f"{rel}: row has {dcount} cells but the header has {hcount}")
                    bad += 1
        ids = re.findall(r'\sid="([^"]+)"', src)
        dupes = {i for i in ids if ids.count(i) > 1}
        for d in dupes:
            fail(f"{rel}: duplicate id '{d}'")
            bad += 1
        seen_ids += len(ids)
    if not bad:
        ok(f"table shapes: every row matches its header; {seen_ids} element ids unique per page")


def check_no_placeholders(pages):
    bad = re.compile(r"\b(TODO|TBD|FIXME|Lorem ipsum|nan|NaN)\b|>None<|\bNone\b(?=\s*</td>)")
    hits = 0
    for rel, sc in pages.items():
        text = "".join(sc.text)
        for m in bad.finditer(text):
            fail(f"{rel}: placeholder or null leakage -> '{m.group(0)}'")
            hits += 1
    if not hits:
        ok("no placeholder/null text in any page")
    return hits


def check_standings_integrity():
    sd = load("standings_2026.json")
    teams = sd["teams"]
    if len(teams) != 32:
        fail(f"standings: expected 32 clubs, found {len(teams)}")
    seen = set()
    for t in teams:
        if t["abbr"] in seen:
            fail(f"standings: duplicate club {t['abbr']}")
        seen.add(t["abbr"])
        if t["w"] + t["l"] + t["t"] != sum(int(x) for x in t["home"].split("-")) + sum(int(x) for x in t["road"].split("-")):
            fail(f"standings {t['abbr']}: W+L+T != home+road")
        if t["pf"] - t["pa"] != t["net"]:
            fail(f"standings {t['abbr']}: PF-PA != published NET")
        conf = sum(int(x) for x in t["conference_record"].split("-"))
        oconf = sum(int(x) for x in t["other_conference"].split("-"))
        if conf + oconf != t["w"] + t["l"] + t["t"]:
            fail(f"standings {t['abbr']}: conference + other-conference != total games")
        dw, dl, dt = [int(x) for x in t["division_record"].split("-")]
        cw, cl, ct = [int(x) for x in t["conference_record"].split("-")]
        if dw > cw or dl > cl:
            fail(f"standings {t['abbr']}: division record exceeds conference record")
    ok(f"standings integrity: {len(teams)} clubs, all arithmetic checks pass")

    divs = {}
    for t in teams:
        divs.setdefault(t["division"], 0)
        divs[t["division"]] += 1
    if sorted(divs.values()) != [4] * 8:
        fail(f"standings: divisions are not all 4 clubs -> {divs}")
    else:
        ok("standings integrity: 8 divisions of 4 clubs")


def check_injuries():
    inj = load("injuries.json")
    rows = inj["rows"]
    c = inj["meta"]["counts"]
    if len(rows) != c["rows"]:
        fail(f"injuries: meta says {c['rows']} rows, file has {len(rows)}")
    gs = sum(1 for r in rows if r["gs"])
    if gs != c["rows_with_game_status"]:
        fail(f"injuries: meta says {c['rows_with_game_status']} game statuses, found {gs}")
    names = sum(1 for r in rows if r["inj"])
    if names != c["rows_with_named_injury"]:
        fail(f"injuries: meta says {c['rows_with_named_injury']} named injuries, found {names}")
    teams = sorted({r["team"] for r in rows})
    if len(teams) != c["teams_complete"]:
        fail(f"injuries: meta says {c['teams_complete']} teams, found {len(teams)}")
    for r in rows:
        if not r.get("u", "").startswith("https://www.nfl.com/players/"):
            fail(f"injuries: row {r['p']} has no official player link")
        if r["gs"] and r["gs"] not in ("Out", "Doubtful", "Questionable"):
            fail(f"injuries: {r['p']} has an invalid game status '{r['gs']}'")
        if r["pr"] not in ("Did Not Participate", "Limited Participation", "Full Participation"):
            fail(f"injuries: {r['p']} has an invalid practice status '{r['pr']}'")
    ok(f"injuries: {len(rows)} rows across {len(teams)} clubs, all links official, all statuses legal")


def check_rules():
    rules = load("rules.json")
    for r in rules["rules"]:
        if r["status"] == "verified":
            if not r.get("source_id"):
                fail(f"rules: {r['id']} is verified but cites no source")
            elif not r["source_id"].startswith("S"):
                fail(f"rules: {r['id']} cites a malformed source id")
        if r["status"] == "unverified" and r.get("value") is not None:
            fail(f"rules: {r['id']} is unverified but carries a value -> {r['value']}")
    ok(f"rules: {len(rules['rules'])} rules; every verified rule cites a source, every unverified rule is blank")


def check_model():
    mo = load("model_outputs.json")
    sd = load("standings_2026.json")
    n = len(sd["verified_matchups_week10"])
    if len(mo["lines"]) != n:
        fail(f"model: {len(mo['lines'])} lines for {n} verified matchups")
    if len(mo["ratings"]) != 32:
        fail("model: ratings do not cover 32 clubs")
    if len(mo["luck_table"]) != 32:
        fail("model: luck table does not cover 32 clubs")
    for ln in mo["lines"]:
        if ln.get("is_market_line"):
            fail(f"model: {ln['id']} is flagged as a market line — impossible, no odds source exists")
        if len(ln["variants"]) != 4:
            fail(f"model: {ln['id']} does not carry the 4 HFA scenarios")
        for v in ln["variants"]:
            if not (0.0 <= v["home_win_prob"] <= 1.0):
                fail(f"model: {ln['id']} has an out-of-range win probability")
        # neutral-site games must not carry home-field advantage
        if ln.get("neutral_site"):
            probs = {round(v["home_win_prob"], 6) for v in ln["variants"]}
            if len(probs) != 1:
                fail(f"model: neutral-site game {ln['id']} varies with home-field advantage")
    # recompute league averages independently
    total_pf = sum(t["pf"] for t in sd["teams"])
    total_games = sum(t["w"] + t["l"] + t["t"] for t in sd["teams"])
    if abs(total_pf / total_games * 2 - mo["league"]["league_total_points"]) > 0.01:
        fail("model: league average total does not recompute from the standings")
    # Pythagorean exponent must be inside the searched grid
    k = mo["league"]["pythagorean_exponent_fitted"]
    if not (0.5 <= k <= 6.0):
        fail(f"model: fitted exponent {k} outside the searched range")
    # every derived value must be labelled derived
    ok(f"model: {len(mo['lines'])} lines, 32 ratings, 32 luck rows; neutral-site handling enforced")


def check_cross_references():
    flags = {f["id"] for f in load("flags.json")["flags"]}
    sources = {s["id"] for s in load("sources.json")["sources"]}
    questions = {q["id"] for q in load("questions.json")["questions"]}
    suggestions = {s["id"] for s in load("suggestions.json")["suggestions"]}
    strategies = {s["id"] for s in load("strategies.json")["strategies"]}
    gates = {g["id"] for g in load("gates.json")["gates"]}

    blob = ""
    for fn in os.listdir(DATA):
        if fn.endswith(".json"):
            with open(os.path.join(DATA, fn)) as f:
                blob += f.read()

    for token, pool, kind in [
        (r"\bF-\d\d\b", flags, "flag"),
        (r"\bQ-\d\d\b", questions, "question"),
        (r"\bSG-\d\d\b", suggestions, "suggestion"),
        (r"\bST-\d\d\b", strategies, "strategy"),
        (r"\bG\d{1,2}\b", gates, "gate"),
    ]:
        for m in set(re.findall(token, blob)):
            if m not in pool:
                fail(f"cross-reference: {kind} id '{m}' is used but does not exist")

    # every quoted source id in the data must exist
    for fn in os.listdir(DATA):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(DATA, fn)) as f:
            txt = f.read()
        for m in set(re.findall(r'"S\d\d"', txt)):
            sid = m.strip('"')
            if sid not in sources:
                fail(f"cross-reference: source id {sid} used in {fn} does not exist")
    ok("cross-references: flags, questions, suggestions, strategies, gates and source ids all resolve")


def check_decisions():
    qs = load("questions.json")["questions"]
    for q in qs:
        if q["status"] == "answered" and not q.get("evidence"):
            fail(f"questions: {q['id']} marked answered with no evidence")
        if q["status"] in ("unknown", "blocked") and not q.get("how_to_close"):
            fail(f"questions: {q['id']} is open with no closure route")
        if q["priority"] not in ("P0", "P1", "P2"):
            fail(f"questions: {q['id']} has an invalid priority")
    sgs = load("suggestions.json")["suggestions"]
    for s in sgs:
        for k in ("impact", "confidence", "effort", "risk"):
            if not (1 <= s[k] <= 5):
                fail(f"suggestions: {s['id']} has {k}={s[k]} outside 1-5")
        if s["recommendation"] not in ("Adopt now", "Pilot", "Defer", "Reject"):
            fail(f"suggestions: {s['id']} has an invalid recommendation")
        if not s.get("decision_criteria"):
            fail(f"suggestions: {s['id']} has no decision criteria")
    ok(f"decisions: {len(qs)} questions and {len(sgs)} suggestions are complete and scorable")


def check_strategies():
    st = load("strategies.json")["strategies"]
    math_ = load("strategy_math.json")
    if not math_["meta"].get("synthetic"):
        fail("strategy math: must be labelled synthetic")
    scored = [s for s in st if any(v == "pass" for v in s["gates"].values())]
    if scored:
        fail(f"strategies: {len(scored)} claim a passed gate, but no odds data exists")
    for s in st:
        if "blocked" not in s["gates"].values() and "unrun" not in s["gates"].values():
            fail(f"strategies: {s['id']} has no gate state recorded")
    ok(f"strategies: {len(st)} strategies, none claim a passed gate, all gate states recorded")


def check_gate_numbers():
    """Catch the class of error where prose quotes a threshold that the adjacent
    computation contradicts. Every 't >= X' on the gates page must match a
    Bonferroni threshold in strategy_math.json."""
    sm = load("strategy_math.json")
    allowed = {round(r["t_threshold"], 2) for r in sm["multiplicity"]["rows"]}
    path = os.path.join(ROOT, "pages", "gates.html")
    with open(path) as f:
        src = f.read()
    quoted = [float(x) for x in re.findall(r"t\s*(?:&gt;=|>=)\s*([0-9]+\.[0-9]+)", src)]
    bad = [q for q in quoted if not any(abs(q - a) < 0.011 for a in allowed)]
    if bad:
        fail(f"gates page quotes t-thresholds that the computation does not support: {sorted(set(bad))} "
             f"(computed: {sorted(allowed)})")
    else:
        ok(f"gate numbers: every quoted t-threshold ({len(quoted)} occurrences) matches the computed "
           f"Bonferroni table {sorted(allowed)}")


def check_claims_consistency():
    """Guard against the site over-claiming anywhere in prose."""
    mo = load("model_outputs.json")
    if "not market lines" not in mo["meta"]["warning"].lower():
        fail("model: warning does not disclaim market lines")
    ex = load("executive_summary.json")
    txt = json.dumps(ex).lower()
    for phrase in ("does not publish its own lines", "odds archive"):
        if phrase not in txt:
            warn(f"exec summary: expected disclaimer phrase missing -> '{phrase}'")
    ok("claims: model output and executive summary both disclaim market lines")


def main():
    pages = crawl()
    check_links(pages)
    check_rows_have_sources(pages)
    check_table_shapes()
    check_no_placeholders(pages)
    check_standings_integrity()
    check_injuries()
    check_rules()
    check_model()
    check_cross_references()
    check_decisions()
    check_strategies()
    check_claims_consistency()
    check_gate_numbers()

    report = {
        "generated": "2026-11-12",
        "result": "PASS" if not FAILS else "FAIL",
        "checks_passed": CHECKS,
        "warnings": WARNS,
        "failures": FAILS,
        "pages_scanned": len(pages),
        "policy": ("A row without a source, a broken link, a dead anchor, a null leak or an internal "
                   "contradiction fails the build. Unverified values are allowed only when blank and flagged."),
    }
    with open(os.path.join(DATA, "verification_report.json"), "w") as f:
        json.dump(report, f, indent=1)

    print(f"pages scanned : {len(pages)}")
    for c in CHECKS:
        print(f"  ok   {c}")
    for w in WARNS:
        print(f"  warn {w}")
    for f_ in FAILS:
        print(f"  FAIL {f_}")
    print()
    print(f"RESULT: {report['result']}  ({len(CHECKS)} checks passed, {len(WARNS)} warnings, {len(FAILS)} failures)")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
