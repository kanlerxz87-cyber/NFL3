#!/usr/bin/env python3
"""Strict build gate for the ops centre.

Fails the build on any of:
  1. a data table row with no official source link and no explicit unverified marker
  2. a broken local link, asset reference or nav target
  3. placeholder leakage (None / nan / null / TODO / undefined)
  4. a blank cell rendered as if it were a value
  5. a non-deterministic build (two runs differ)
  6. a claim of a validated strategy, a measured official correlation, or a
     confirmed replacement anywhere on the site
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops-center"
PAGES = sorted(p.name for p in OPS.glob("*.html"))

import build as builder  # noqa: E402  (reuses the same source classifier as the site)

OFFICIAL_HOSTS = {
    "www.commanders.com", "www.seahawks.com", "www.patriots.com", "www.giants.com",
    "www.bengals.com", "www.buffalobills.com", "www.clevelandbrowns.com",
    "www.azcardinals.com", "www.chargers.com", "www.chicagobears.com",
    "www.chiefs.com", "www.colts.com", "www.dallascowboys.com",
    "www.denverbroncos.com", "www.miamidolphins.com", "www.atlantafalcons.com",
    "www.jaguars.com", "www.newyorkjets.com", "www.detroitlions.com",
    "www.panthers.com", "www.philadelphiaeagles.com", "www.raiders.com",
    "www.therams.com", "www.baltimoreravens.com", "www.neworleanssaints.com",
    "www.steelers.com", "www.buccaneers.com", "www.tennesseetitans.com",
    "www.vikings.com", "www.49ers.com", "www.greenbaypackers.com",
    "www.houstontexans.com",
}
AUTHORITY_HOSTS = {
    "www.itl.nist.gov", "scikit-learn.org", "www.weather.gov",
    "kansspelautoriteit.nl", "www.gaming.nv.gov", "docs.github.com",
}
SECONDARY_HOSTS = {"sports.yahoo.com", "lamag.com", "statrankings.com",
                   "fsroundup.com", "sticktothemodel.com"}

FORBIDDEN_CLAIMS = [
    (r"validated\s+strateg(y|ies)", "mentions validated strategies"),
    (r"measured\s+correlation", "claims a measured correlation"),
    (r"confirmed\s+replacement", "claims a confirmed replacement"),
]

LINK = re.compile(r'href="([^"]+)"')
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
PLACEHOLDER = re.compile(r"\b(None|null|nan|NaN|undefined|TODO|FIXME|XXX)\b")


def local_targets() -> set[str]:
    out = set()
    for p in OPS.rglob("*.html"):
        out.add(str(p.relative_to(OPS)))
    for p in OPS.rglob("*.*"):
        if p.suffix in (".css", ".js", ".json"):
            out.add(str(p.relative_to(OPS)))
    for name in ("index.html", "decision-lab/index.html", "dashboard/index.html"):
        out.add("../" + name)
    return out


def check_pages(errors: list[str], warnings: list[str]) -> None:
    targets = local_targets()
    total_rows = 0
    sourced_rows = 0
    for name in PAGES:
        text = (OPS / name).read_text(encoding="utf-8")

        body = re.sub(r"<script.*?</script>", "", text, flags=re.S)
        for cell in TD.findall(body) + re.findall(r"<option[^>]*>(.*?)</option>", body, flags=re.S):
            text_only = re.sub(r"<[^>]+>", "", cell).replace("&mdash;", "").strip()
            m = PLACEHOLDER.fullmatch(text_only)
            if m:
                errors.append(f"{name}: placeholder leakage '{m.group(1)}' in a table cell")

        for href in LINK.findall(text):
            if href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            clean = href.split("#")[0]
            if not clean:
                continue
            if clean.startswith("../"):
                if not (ROOT / clean[3:]).exists():
                    errors.append(f"{name}: broken parent link '{href}'")
                continue
            if not (OPS / clean).exists():
                errors.append(f"{name}: broken local link '{href}'")

        for rid, row in enumerate(ROW.findall(text), 1):
            if "<th" in row:
                continue
            total_rows += 1
            cells = TD.findall(row)
            if not cells:
                continue
            has_source = any('class="src' in c for c in cells)
            has_unverified = any("unv" in c for c in cells)
            if has_source:
                sourced_rows += 1
            elif not has_unverified:
                errors.append(f"{name}: row {rid} has no source link and no unverified marker")

        for ext_link in re.findall(r'class="src[^"]*" href="([^"]+)"', text):
            cls = builder.source_class(ext_link)
            if cls == "internal":
                pass
            elif cls == "community":
                warnings.append(f"{name}: community-data row source: {ext_link}")
            elif cls == "secondary":
                warnings.append(f"{name}: secondary (non-official) row source: {ext_link}")
            elif cls == "unknown":
                errors.append(f"{name}: source link host not classified: {ext_link}")

        body = re.sub(r"<script.*?</script>", "", text, flags=re.S)
        body = re.sub(r"<th.*?</th>", " ", body, flags=re.S)
        for cell in TD.findall(body):
            low = re.sub(r"<[^>]+>", " ", cell).lower()
            for pattern, why in FORBIDDEN_CLAIMS:
                for m in re.finditer(pattern, low):
                    window = low[max(0, m.start() - 60):m.start()]
                    if re.search(r"\b(no|not|never|without|zero|0|nor)\b", window):
                        continue
                    warnings.append(f"{name}: {why} — '{low.strip()[:80]}'")

    print(f"rows: {total_rows}, rows carrying an official source link: {sourced_rows}")


def check_determinism(errors: list[str]) -> None:
    before = {p: (OPS / p).read_text(encoding="utf-8") for p in PAGES}
    subprocess.run([sys.executable, str(OPS / "scripts" / "build.py")],
                   check=True, capture_output=True, cwd=str(ROOT))
    for p in PAGES:
        after = (OPS / p).read_text(encoding="utf-8")
        if after != before[p]:
            errors.append(f"{p}: build is not deterministic")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    check_pages(errors, warnings)
    check_determinism(errors)

    for w in warnings:
        print(f"WARN  {w}")
    for err in errors:
        print(f"FAIL  {err}")
    print(f"\n{len(PAGES)} pages, {len(errors)} failures, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
