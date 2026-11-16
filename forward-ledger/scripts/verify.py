#!/usr/bin/env python3
"""Gates for the forward ledger. Every gate here is a check that a claim already made on a page is true.

The pages say "registered before results were seen", "no price", "no backtest number on the leaderboard" and
"every row is sourced". Each sentence is a promise the reader cannot audit from the page alone, so each one is a
test here, and the build refuses to claim what this script would fail.

    python3 forward-ledger/scripts/verify.py

Exit 0 = every gate passes. Exit 1 = a gate failed and the pages must be corrected before anything is published.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = HERE / "data"
PAGES = ["index.html", "results.html", "availability.html", "backtest.html", "prospects.html",
         "leaderboard.html", "review.html", "sources.html"]
MODEL_ARTIFACTS = ["scripts/model.py", "data/ratings_2026_w10.csv", "data/fit_diagnostics.json",
                   "data/prospects_2026_w11.csv", "data/prospect_records.jsonl", "data/leaderboard.json"]
PRICE_COLUMNS = ["market_line", "difference", "residual", "price_open", "price_close", "closing_line",
                 "stake", "roi", "hold", "pnl"]


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def first_commit(rel: str) -> str:
    out = run("git", "log", "--format=%H", "--reverse", "--", rel)
    return out.splitlines()[0] if out else ""


def commit_time(sha: str) -> int:
    if not sha:
        return 0
    return int(run("git", "show", "-s", "--format=%ct", sha) or 0)


def read_rows(name: str) -> list:
    with (DATA / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def page_text(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


checks, fails = [], []


def gate(ok: bool, label: str, detail: str = "") -> None:
    (checks if ok else fails).append(f"{label}: {detail}" if detail else label)


def main() -> int:
    pages = {}
    for name in PAGES:
        if not (HERE / name).is_file():
            fails.append(f"G0 pages: {name} has not been built")
            continue
        pages[name] = page_text(name)
    if len(pages) != len(PAGES):
        return report("G0 pages")

    # G1 registration precedes the artifacts it governs
    prereg = first_commit("forward-ledger/PREREGISTRATION.md")
    gate(bool(prereg), "G1 registration committed", f"{prereg[:9]}" if prereg else "not committed")
    if prereg:
        too_early = []
        for rel in MODEL_ARTIFACTS:
            sha = first_commit("forward-ledger/" + rel)
            if not sha:
                too_early.append(f"{rel} (uncommitted)")
            elif commit_time(sha) < commit_time(prereg):
                too_early.append(f"{rel} ({sha[:9]} precedes {prereg[:9]})")
        gate(not too_early, "G1 every model artifact first committed after the registration",
             "earlier: " + ", ".join(too_early) if too_early else f"{len(MODEL_ARTIFACTS)} artifacts, registration "
             f"{prereg[:9]} at {commit_time(prereg)}")

    # G2 prices and price-derived values are empty everywhere they appear
    prospects = read_rows("prospects_2026_w11.csv")
    filled = {c: sum(1 for r in prospects if str(r.get(c, "")).strip()) for c in PRICE_COLUMNS if c in prospects[0]}
    gate(not any(filled.values()), "G2 no price, residual or stake value in the forecast register",
         f"{len(prospects)} rows, columns scanned {', '.join(filled) or 'none present'}")
    ledger = read_rows("results_ledger.csv")
    leak = [c for c in PRICE_COLUMNS if ledger and c in ledger[0]]
    gate(not any(str(r.get(c, "")).strip() for r in ledger for c in leak),
         "G2 no price column in the results ledger", "columns present: " + (", ".join(leak) or "none"))
    for name in ("prospects.html", "leaderboard.html", "results.html"):
        body = re.sub(r"<[^>]+>", " ", pages[name])
        hits = re.findall(r"(?<!\bno )ROI\b|\bclosing line\b|\bvig\b|\bCLV\b", body)
        gate(not hits, f"G2 {name} prints no price-derived metric", ", ".join(sorted(set(hits))) or "clean")

    # G3 no backtest number may be echoed on the leaderboard
    diag = json.loads((DATA / "fit_diagnostics.json").read_text())
    hold = diag["chronological_holdout"]
    ins = diag["in_sample"]
    forbidden = {f"{v:.5f}" for v in (hold["brier_home_win_model"], hold["brier_home_win_base_rate"],
                                      hold["brier_skill_vs_base_rate"], hold["mean_abs_margin_error"],
                                      ins["margin_r2"], ins["total_r2"]) if isinstance(v, (int, float))}
    board = pages["leaderboard.html"]
    echoed = sorted(v for v in forbidden if v in board)
    gate(not echoed, "G3 the leaderboard carries no backtest statistic",
         "leaked: " + ", ".join(echoed) if echoed else f"{len(forbidden)} diagnostics withheld")
    gate("no performance numbers" in board or "none exists yet" in board,
         "G3 the leaderboard states why it is empty")
    gate(bool(re.search(r"rows eligible", board)) and 'class="pill blank"' in board or "0 rows eligible" in board,
         "G3 the leaderboard shows its own eligibility count")

    # G4 every rendered data row carries a link, and the pages link nothing but https sources
    row_pat = re.compile(r"<tr>(.*?)</tr>", re.S)
    bad_rows, n_rows = [], 0
    for name, text in pages.items():
        for block in re.finditer(r'<div class="tablewrap"([^>]*)>(.*?)</tbody></table></div>', text, re.S):
            if 'data-navigation="1"' in block.group(1):
                continue
            for row in row_pat.findall(block.group(2)):
                if "<td" not in row:
                    continue
                n_rows += 1
                if 'href="https://' not in row:
                    bad_rows.append(f"{name}:{re.sub('<[^>]+>', ' ', row)[:70]}")
                if 'data-official="1"' in block.group(1) and not re.search(
                        r'href="https://(www|static\.www|operations)\.nfl\.com', row):
                    bad_rows.append(f"{name}: league-fact row without an nfl.com link: "
                                    f"{re.sub('<[^>]+>', ' ', row)[:70]}")
    gate(not bad_rows, f"G4 every sourced row links its source ({n_rows} rows)",
         f"{len(bad_rows)} rows without a link, e.g. {bad_rows[0]}" if bad_rows else "0 unsourced rows")
    local = re.compile(r'href="(?!https?://|#|mailto:)([^"]+)"')
    broken = []
    for name, text in pages.items():
        for target in set(local.findall(text)):
            path = (HERE / target.split("#")[0]).resolve()
            if not path.exists():
                broken.append(f"{name} -> {target}")
    gate(not broken, "G4 no broken relative link in any page", ", ".join(broken[:4]) or f"{len(PAGES)} pages checked")
    tracked = set(run("git", "ls-files").splitlines())
    blob = re.compile(r'href="https://github\.com/kanlerxz87-cyber/NFL3/blob/main/([^"#]+)"')
    ghost = [f"{name} -> {m.group(1)}" for name, text in pages.items() for m in blob.finditer(text)
             if m.group(1) not in tracked]
    blob_links = sum(len(blob.findall(text)) for text in pages.values())
    gate(not ghost, "G4 every repository link points at a tracked file",
         "not in the tree: " + ", ".join(ghost[:4]) if ghost else f"{blob_links} blob links resolve")
    abs_site = [f"{name}: {m}" for name, text in pages.items() for m in re.findall(r'href="/[^"]*"', text)]
    gate(not abs_site, "G4 no site-absolute URL (GitHub Pages serves under /NFL3/)", ", ".join(abs_site[:3]))

    # G5 placeholders and unrendered template output
    placeholder = re.compile(r"\b(TBD|TODO|FIXME|lorem ipsum|None|nan)\b")
    hits = [f"{name}: {m.group(0)}" for name, text in pages.items()
            for m in placeholder.finditer(re.sub(r"<[^>]+>", " ", text)) if "None" != "nan"]
    gate(not hits, "G5 no placeholder or unrendered value reaches a page", "; ".join(hits[:4]))

    # G6 blanks are marked, not silently empty
    blank_cells = {name: text.count('class="blanked"') for name, text in pages.items()}
    gate(all(v > 0 for k, v in blank_cells.items() if k in ("prospects.html", "results.html", "availability.html")),
         "G6 a cell with no official value renders as an explicit blank",
         ", ".join(f"{k.split('.')[0]} {v}" for k, v in blank_cells.items() if v))
    ml_blank = sum(1 for r in prospects if not str(r["market_line"]).strip())
    gate(ml_blank == len(prospects), "G6 the market-line column is blank on every row",
         f"{ml_blank}/{len(prospects)} rows blank")

    # G7 point-in-time integrity of the prospective register
    late = [r["fixture"] for r in prospects if str(r["issued_at_utc"])[:10] > str(r["kickoff_et"])[:10]]
    gate(not late, "G7 every forecast was issued on or before its own kickoff",
         "late: " + ", ".join(late[:3]) if late else f"{len(prospects)} rows")
    same = {r["issued_at_utc"] for r in prospects}
    gate(len(same) == 1, "G7 one issue stamp for the whole slate", ", ".join(sorted(same)))
    stamps = json.loads((DATA / "ledger_manifest.json").read_text())
    window_played = [r["fixture"] for r in ledger if r["status"] == "final" and r["week"] == 11]
    gate(not window_played, "G7 no fixture in the prospective window is graded yet, so no ranking is possible",
         f"graded Week 11 rows: {len(window_played)}; ledger built {stamps.get('built_from_read_date')}")

    # G8 cross-checks stay at zero disagreement
    cross = json.loads((DATA / "standings_crosscheck_origination.json").read_text())
    gate(cross["clubs_disagreeing"] == 0 and cross["clubs_in_standings"] == 32 and cross["clubs_in_ledger"] == 32
         and cross["clubs_matching_on_all_five_fields"] == 32 and not cross["clubs_only_in_ledger"],
         "G8 ledger reproduces the independent standings read",
         f"{cross['field_checks']} field checks, {cross['clubs_disagreeing']} disagreements, "
         f"{cross['clubs_matching_on_all_five_fields']} of {cross['clubs_in_standings']} clubs match on all five "
         f"fields, {len(cross['clubs_only_in_ledger'])} ledger-only clubs")
    agree = stamps["frozen_corpus_agreement"]
    gate(agree["score_mismatches"] == 0, "G8 the frozen corpus is not contradicted",
         f"{agree['exact_score_matches']}/{agree['graded_ledger_rows_weeks_1_9']} identical, "
         f"{agree['blank_in_frozen_corpus']} blank in the corpus, {agree['score_mismatches']} mismatches")
    rows = read_rows("standings_crosscheck_origination.csv")
    gate(all(r["agreement"] == "match" for r in rows) and len(rows) == 32,
         "G8 every standings comparison row reads match", f"{len(rows)} rows")
    chip = stamps["standings_crosscheck"]
    gate(chip["mismatches"] == 0, "G8 club records match the chips printed on official pages",
         f"{chip['clubs_checked_against_official_chips']} of 32 clubs read, {chip['mismatches']} mismatches, "
         f"{len(chip['clubs_not_read_in_this_pass'])} deliberately not compared "
         f"({', '.join(chip['clubs_not_read_in_this_pass'])})")
    gate(stamps["graded"] == sum(1 for r in ledger if r["status"] == "final")
         and stamps["fixtures"] == len(ledger) == 150 and stamps["scheduled_unplayed"] == 1,
         "G8 the manifest counts describe the ledger they publish",
         f"{stamps['graded']} graded of {stamps['fixtures']} fixtures, {stamps['scheduled_unplayed']} unplayed")
    gate(stamps["frozen_corpus_agreement"]["graded_ledger_rows_weeks_1_9"] == 136
         and stamps["frozen_corpus_agreement"]["fixtures_absent_from_corpus"] == 0,
         "G8 Weeks 1-9 of the ledger cover the frozen corpus completely",
         f"{stamps['frozen_corpus_agreement']['corpus_rows']} corpus rows, "
         f"{stamps['frozen_corpus_agreement']['fixtures_absent_from_corpus']} absent from the ledger")
    avail = json.loads((DATA / "availability_w10.json").read_text())
    gate(avail["rows"] == sum(int(r["rows"]) for r in read_rows("availability_w10.csv")),
         "G8 the availability page's club rows sum to the capture it claims",
         f"{avail['rows']} rows across {avail['clubs_with_a_table']} clubs")

    # G9 findings register: every finding states an owner, an action and an official link
    findings = read_rows("review_findings.csv")
    incomplete = [f["id"] for f in findings
                  if not (f["evidence"].strip() and f["action"].strip() and f["owner"].strip()
                          and f["official_source_url"].startswith("https://"))]
    gate(not incomplete, f"G9 all {len(findings)} review findings carry evidence, action, owner and an https source",
         "incomplete: " + ", ".join(incomplete) if incomplete else "none")
    league = [f["id"] for f in findings if f["official_source_label"].lower().startswith(("nfl", "the official"))
              and ".nfl.com" not in f["official_source_url"]]
    gate(not league, "G9 every finding whose label claims an official page links an nfl.com URL",
         "wrong host: " + ", ".join(league) if league else
         f"{sum(1 for f in findings if '.nfl.com' in f['official_source_url'])} of {len(findings)} findings cite "
         "official NFL pages; the rest cite repository files and are labelled as such")
    anchors = set(re.findall(r'id="(FL-\d+)"', pages["review.html"]))
    gate({f["id"] for f in findings} == anchors, "G9 every finding is addressable by anchor on the review page",
         f"{len(anchors)} anchors")
    return report()


def report(stage: str = "") -> int:
    print(f"forward-ledger verification\n{'-' * 68}")
    for line in checks:
        print(f"PASS  {line}")
    for line in fails:
        print(f"FAIL  {line}")
    print("-" * 68)
    print(f"{len(checks)} gates passed, {len(fails)} failed" + (f" (stopped at {stage})" if stage else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
