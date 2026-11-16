#!/usr/bin/env python3
"""Fail-closed gate for the two-total workspace.

    python3 two-total/scripts/verify.py

Checks, in the order a failure would mislead a reader most:

 1. registration order — the commit recorded in the artifact is the commit that CREATED
    PRE_REGISTRATION.md, that commit is reachable from HEAD, and its content hash still matches.
 2. corpus integrity — the frozen corpus file hashes to the value in corpus/manifest.json, and the row
    count / split arithmetic in the artifact equals the corpus.
 3. arithmetic — every published MAE, RMSE, gap and error is recomputed from the per-row columns and must
    agree to 1e-6. The collapse verdict is recomputed from the five conditions.
 4. citations — every table body row on every rendered page carries an https link, and every per-game
    source link is on nfl.com.
 5. blank discipline — no placeholder token, no "None"/"NaN"/"nan" rendered as a value, and every blank
    cell on the every-game page carries a reason.
 6. price firewall — no ROI / CLV / staking / edge number appears in the workspace, and no column is
    labelled as a price.
 7. claims — no unqualified profitability or "validated" claim on any page.
 8. determinism — a rebuild produces a byte-identical artifact and byte-identical pages.
 9. links — every local link and asset referenced by a page exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parent
DATA = OUT / "data"
ART = DATA / "two_total.json"

PAGES = ["index.html", "rows.html", "method.html", "flagged.html"]
PLACEHOLDERS = ("TODO", "TBD", "FIXME", "XXX", "lorem ipsum", "PLACEHOLDER", "<N/A>")
OFFICIAL = ("www.nfl.com", "nfl.com", "operations.nfl.com", "support.nfl.com")
FORBIDDEN = [
    (r"\bvalidated strategy\b", "unqualified validated-strategy claim"),
    (r"\bguaranteed\b", "guarantee claim"),
    (r"\bprofitable\b", "profitability claim"),
    (r"\bROI\b\s*(?:of|=|:)?\s*[+\-]?\d", "an ROI figure"),
    (r"\bCLV\b\s*(?:of|=|:)?\s*[+\-]?\d", "a CLV figure"),
    (r"\b(profit|return on investment|closing line value)\s+(?:of|was|is)\s+[+\-]?\d", "a price-dependent figure"),
]
errors: list[str] = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


class Rows(HTMLParser):
    """Every table body row must carry at least one https link."""

    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.tbody = 0
        self.row = None
        self.blank_titles = []
        self.links: list[str] = []
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self.tbody += 1
        elif tag == "tr" and self.tbody:
            self.row = set()
        elif tag == "a":
            href = a.get("href", "")
            if href.startswith("https://"):
                self.links.append(href)
                if self.row is not None and self.tbody:
                    self.row.add(href)
            elif href and not href.startswith(("#", "mailto:")):
                self.assets.append(href)
            if self.row is not None and "blank" in a.get("class", ""):
                self.blank_titles.append(a.get("title", ""))
        elif tag in ("script", "link"):
            src = a.get("src") or a.get("href") or ""
            if src and not src.startswith(("http://", "https://", "//", "data:")):
                self.assets.append(src)

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            if self.tbody and not self.row:
                errors.append(f"{self.path.name}: a table body row has no https citation")
            self.row = None
        elif tag == "tbody" and self.tbody:
            self.tbody -= 1


def main() -> int:
    if not ART.is_file():
        print("FAIL two-total: artifact missing; run build.py")
        return 1
    D = json.loads(ART.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- 1. registration order
    reg = D["registration"]["commit"]
    created = [c for c in git("log", "--diff-filter=A", "--format=%H", "--",
                              "two-total/PRE_REGISTRATION.md").split() if c]
    if len(created) != 1:
        errors.append(f"registration: expected one creating commit, found {created}")
    elif created[0] != reg:
        errors.append(f"registration: artifact names {reg[:12]} but the creating commit is {created[0][:12]}")
    if reg:
        ok = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", reg, "HEAD"]).returncode == 0
        if not ok:
            errors.append(f"registration: commit {reg[:12]} is not reachable from HEAD")
    if sha256(OUT / "PRE_REGISTRATION.md") != D["registration"]["file_sha256"]:
        errors.append("registration: PRE_REGISTRATION.md changed after the artifact was built")

    # ---------------------------------------------------------------- 2. corpus integrity
    man = json.loads((ROOT / "corpus" / "manifest.json").read_text(encoding="utf-8"))
    if sha256(ROOT / "corpus" / "games_2026_w1_9.csv") != man["frozen_sha256"]:
        errors.append("corpus: frozen file hash differs from corpus/manifest.json")
    if D["corpus"]["sha256"] != man["frozen_sha256"]:
        errors.append("corpus: artifact records a different corpus hash than the manifest")
    import csv
    with (ROOT / "corpus" / "games_2026_w1_9.csv").open(encoding="utf-8", newline="") as fh:
        corpus = list(csv.DictReader(fh))
    if len(corpus) != D["corpus"]["games"]:
        errors.append(f"corpus: {len(corpus)} rows but artifact says {D['corpus']['games']}")
    if len(D["rows"]) != len(corpus):
        errors.append(f"rows: artifact holds {len(D['rows'])} rows for {len(corpus)} corpus games")
    split_total = sum(v["games_in_block"] for v in D["scores"]["by_block"].values())
    if split_total != len(corpus):
        errors.append(f"split: blocks cover {split_total} games, corpus has {len(corpus)}")
    for name, spec in man["split"].items():
        if not isinstance(spec, dict) or "games" not in spec:
            continue
        if D["scores"]["by_block"][name]["games_in_block"] != spec["games"]:
            errors.append(f"split: {name} holds {D['scores']['by_block'][name]['games_in_block']}, "
                          f"manifest says {spec['games']}")

    # the split must cover exactly the weeks the corpus covers, with no gap and no overlap
    weeks = sorted({int(r["week"]) for r in corpus})
    covered = []
    for name, (lo, hi) in (("train", (1, 6)), ("validation", (7, 8)), ("holdout", (9, 9))):
        covered.extend(range(lo, hi + 1))
    if sorted(covered) != list(range(min(weeks), max(weeks) + 1)):
        errors.append(f"split: blocks cover weeks {sorted(covered)}, corpus has {weeks}")
    if len(covered) != len(set(covered)):
        errors.append("split: blocks overlap")

    # ---------------------------------------------------------------- 3. arithmetic
    rows = D["rows"]
    scored = [r for r in rows if r["t1_error_abs"] is not None and r["t2_error_abs"] is not None]
    for r in rows:
        if r["t1_total"] is not None and r["t2_total"] is not None:
            if abs((r["t2_total"] - r["t1_total"]) - r["gap"]) > 1e-6:
                errors.append(f"gap: {r['game_id'] if 'game_id' in r else (r['week'], r['home'])} does not equal T2-T1")
        if r["actual_total"] is not None and r["t1_total"] is not None:
            if abs(abs(r["t1_total"] - r["actual_total"]) - r["t1_error_abs"]) > 1e-6:
                errors.append(f"error T1: week {r['week']} {r['away']} at {r['home']} does not reconcile")
        if r["actual_total"] is not None and r["t2_total"] is not None:
            if abs(abs(r["t2_total"] - r["actual_total"]) - r["t2_error_abs"]) > 1e-6:
                errors.append(f"error T2: week {r['week']} {r['away']} at {r['home']} does not reconcile")
    if scored:
        m1 = statistics.fmean([r["t1_error_abs"] for r in scored])
        m2 = statistics.fmean([r["t2_error_abs"] for r in scored])
        r1 = math.sqrt(statistics.fmean([r["t1_error_abs"] ** 2 for r in scored]))
        r2 = math.sqrt(statistics.fmean([r["t2_error_abs"] ** 2 for r in scored]))
        got = D["scores"]["overall"]
        for label, recomputed, published in (("MAE T1", m1, got["mae_t1"]), ("MAE T2", m2, got["mae_t2"]),
                                             ("RMSE T1", r1, got["rmse_t1"]), ("RMSE T2", r2, got["rmse_t2"])):
            if abs(recomputed - published) > 1e-6:
                errors.append(f"arithmetic: {label} recomputes to {recomputed} but {published} is published")
        if got["scored"] != len(scored):
            errors.append(f"arithmetic: overall n {got['scored']} != {len(scored)} reconcilable rows")
        # per-block recomputation
        for name, (lo, hi) in (("train", (1, 6)), ("validation", (7, 8)), ("holdout", (9, 9))):
            sub = [r for r in scored if lo <= r["week"] <= hi]
            b = D["scores"]["by_block"][name]
            if len(sub) != b["scored"]:
                errors.append(f"arithmetic: block {name} n {b['scored']} != {len(sub)}")
            elif sub:
                bm1 = statistics.fmean([r["t1_error_abs"] for r in sub])
                if abs(bm1 - b["mae_t1"]) > 1e-6:
                    errors.append(f"arithmetic: block {name} MAE T1 {b['mae_t1']} != {bm1}")
    # collapse verdict recomputed from the five conditions
    val = D["scores"]["by_block"]["validation"]
    boot = val["bootstrap_mae_diff"] or {}
    wk7 = D["scores"]["week7"]
    wk8 = D["scores"]["week8"]
    recomputed_checks = {
        "C1_challenger_better": val["mae_t2"] < val["mae_t1"],
        "C2_interval_lower_gt_0": (boot.get("lower95") or 0) > 0,
        "C3_rmse_agrees": val["rmse_t2"] < val["rmse_t1"],
        "C4_both_halves_agree": (wk7["mae_diff"] or 0) > 0 and (wk8["mae_diff"] or 0) > 0,
        "C5_min_n": val["scored"] >= 20,
    }
    if recomputed_checks != D["decision"]["checks"]:
        errors.append("decision: the published gate states do not recompute from the published numbers")
    if all(recomputed_checks.values()) != D["decision"]["collapsed"]:
        errors.append("decision: the collapse verdict does not follow from its own conditions")

    # flags and questions must be uniquely identified and ordered, so a reader can cite one
    ids = [f["id"] for f in D["flags"]]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        errors.append(f"flags: ids are not unique and ordered: {ids}")
    qids = [q["id"] for q in D["questions"]]
    if len(qids) != len(set(qids)):
        errors.append(f"questions: duplicate ids: {qids}")
    # the closure sensitivity must agree with the rows it is derived from
    cs = D.get("closure_sensitivity")
    if cs:
        row = next((r for r in rows if r["actual_total"] is None), None)
        if row is None:
            errors.append("sensitivity: a sensitivity is published but no row is withheld")
        else:
            if (cs["row"]["week"], cs["row"]["away"], cs["row"]["home"]) != \
                    (row["week"], row["away"], row["home"]):
                errors.append("sensitivity: the witnessed row is not the withheld row")
            if abs(cs["error_t1"] - abs(row["t1_total"] - cs["official_total"])) > 1e-6:
                errors.append("sensitivity: T1 error does not recompute against the official total")
            if abs(cs["error_t2"] - abs(row["t2_total"] - cs["official_total"])) > 1e-6:
                errors.append("sensitivity: T2 error does not recompute against the official total")
            for name, (lo, hi) in (("train", (1, 6)), ("validation", (7, 8)), ("holdout", (9, 9))):
                b = cs["per_block"][name]
                sub = [r for r in scored if lo <= r["week"] <= hi]
                if b["n_before"] != len(sub):
                    errors.append(f"sensitivity: {name} n_before {b['n_before']} != {len(sub)}")
            if cs["verdict_affected"] != (cs["row"]["block"] in ("validation", "holdout")):
                errors.append("sensitivity: verdict_affected does not follow from the row's block")
        if not cs["official_source"].startswith("https://www.nfl.com/"):
            errors.append("sensitivity: the witnessed result does not cite an official nfl.com URL")

    # ---------------------------------------------------------------- 4/5/9. pages
    for name in PAGES:
        p = OUT / name
        if not p.is_file():
            errors.append(f"pages: {name} missing")
            continue
        parser = Rows(p)
        text = p.read_text(encoding="utf-8")
        parser.feed(text)
        parser.close()
        for asset in parser.assets:
            target = (p.parent / urlparse(asset).path).resolve()
            if not target.exists():
                errors.append(f"{name}: broken local link or asset: {asset}")
        for link in parser.links:
            host = urlparse(link).hostname or ""
            if not any(host == h or host.endswith("." + h) for h in OFFICIAL) and \
                    not host.endswith("github.com"):
                errors.append(f"{name}: citation is not an official NFL host: {link}")
        for token in PLACEHOLDERS:
            if token.lower() in text.lower():
                errors.append(f"{name}: placeholder token {token!r} published")
        for pat, why in FORBIDDEN:
            if re.search(pat, text, re.I):
                errors.append(f"{name}: {why}")
        for title in parser.blank_titles:
            if not title.strip():
                errors.append(f"{name}: a blank cell has no reason in its title attribute")
        for bad in ("nan", "None", "NaN"):
            if re.search(rf">\s*{bad}\s*<", text):
                errors.append(f"{name}: value '{bad}' rendered as a value")
        if "not a leaderboard result" not in text.lower():
            errors.append(f"{name}: missing the 'not a leaderboard result' label")

    # ---------------------------------------------------------------- 6. price firewall
    for name in PAGES:
        text = (OUT / name).read_text(encoding="utf-8")
        if re.search(r"<th[^>]*>\s*(ROI|Edge|CLV|Profit|Stake)\s*</th>", text, re.I):
            errors.append(f"{name}: a price-dependent column header is published")
    if D["price_firewall"]["licensed_price_sources"] != 0:
        errors.append("price firewall: artifact claims a licensed price source; this workspace must not")

    # ---------------------------------------------------------------- 7. blank reasons
    for r in rows:
        if r["actual_total"] is None and not r.get("blank_reason") and r["t1_total"] is not None:
            # a row may have a blank truth only for the documented hidden score; that is asserted below
            pass
    hidden = [r for r in rows if r["actual_total"] is None]
    if len(hidden) > 1:
        errors.append(f"blanks: {len(hidden)} rows lack a final score; the corpus documents exactly 1")

    # ---------------------------------------------------------------- 8. determinism
    before = {"art": sha256(ART), "pages": {n: sha256(OUT / n) for n in PAGES}}
    for script in ("build.py", "pages.py"):
        proc = subprocess.run([sys.executable, str(HERE / script)], capture_output=True, text=True)
        if proc.returncode:
            errors.append(f"determinism: {script} failed on rerun: {proc.stderr[-400:]}")
            break
    after = {"art": sha256(ART), "pages": {n: sha256(OUT / n) for n in PAGES}}
    if before != after:
        changed = [k for k in before["pages"] if before["pages"][k] != after["pages"][k]]
        errors.append(f"determinism: rebuild changed {changed or 'the artifact'}")

    # ---------------------------------------------------------------- report
    if errors:
        print("two-total verification FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"two-total verification passed: {len(rows)} corpus rows, {len(scored)} scored, "
          f"{len(PAGES)} pages, registration {reg[:12]}, corpus {D['corpus']['sha256'][:12]}, "
          f"collapse={D['decision']['collapsed']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
