"""Regression checks for the landing-page readiness table and count summary."""
import collections
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requirement_ids(text: str) -> list[str]:
    return re.findall(r"<tr><td>(R\d{2})</td>", text)


def main() -> None:
    landing = (ROOT / "index.html").read_text(encoding="utf-8")
    canonical = (ROOT / "decision-lab/requirements.html").read_text(encoding="utf-8")
    expected = requirement_ids(canonical)
    assert len(expected) == 26 and len(expected) == len(set(expected)), "canonical register should contain 26 unique requirement IDs"
    assert requirement_ids(landing) == expected, "landing page must contain one row per canonical requirement in register order"
    assert 'href="readiness.html"' in landing, "landing matrix must link to the full-scope gate register"
    status_counts = collections.Counter(
        re.search(r'<span class="pill [^"]+">([^<]+)</span>', body).group(1)
        for _rid, body in re.findall(r'<tr><td>(R\d{2})</td>(.*?)</tr>', landing)
    )
    assert status_counts == {"implemented": 14, "partial": 10, "blocked": 2}, f"landing summary must match the 26 status cells: {status_counts}"
    assert "14 of 26 requirements implemented, 10 partial, 2 blocked" in landing, "summary totals must agree with the matrix"
    for snapshot_count in ("279", "195", "10"):
        assert f"><strong>{snapshot_count}</strong><" in landing, f"dated snapshot count {snapshot_count} is missing from the landing page"

    # Detailed 64-row register (rebuilt by readiness/build_readiness.py): regression checks for the
    # verified results feed, the corpus freeze and the published injury-hub delta (session
    # arena/16183225-nfl3, 2026-11-15), reconciled with the pricing/corpus work (session
    # arena/ba6c5155-nfl3, 2026-11-15). The landing matrix keeps its dated catalog labels and is
    # deliberately not asserted against these.
    register = (ROOT / "readiness" / "data" / "readiness.csv").read_text(encoding="utf-8")
    rows = {r["id"]: r for r in csv.DictReader(register.splitlines())}
    assert len(rows) == 64, f"detailed register should hold 64 rows, found {len(rows)}"
    assert rows["R1"]["status"] == "Done" and "136/136" in rows["R1"]["current"], "R1 must record the 136/136 official verification"
    assert rows["R2"]["status"] == "Done" and "76f4c7d775b8" in rows["R2"]["current"], "R2 must record the corpus freeze commit (its clears rule: frozen before any evaluation)"
    assert "a1633c20" in rows["R2"]["current"], "R2 must record the frozen corpus hash"
    assert rows["A3"]["status"] == "Partial" and "139 game-status changes" in rows["A3"]["current"], "A3 must record the published per-player deltas"
    assert rows["A4"]["current"].count("20") >= 4 and "2026-11-15" in rows["A4"]["current"], "A4 must record four dated reads"
    status_counts2 = collections.Counter(r["status"] for r in rows.values())
    # 8 Done / 20 Partial / 13 Blocked / 22 Not started / 1 Decision recorded after the
    # pricing-corpus pass; the skill lab and the availability ledger moved 11 further rows
    # (P3, P10, P11, A5, A13, A16, A19, L2, L3, L4, L5, L6, L7, L8).
    # Session arena/46fe1baa-nfl3 (2026-11-16): A17 Blocked -> Done (three Lions cells filled from the
    # official article); F-2 and F-3 Not started -> Partial (Week 11 venues and announcement recorded).
    assert status_counts2["Done"] == 8 and status_counts2["Partial"] == 33 and status_counts2["Blocked"] == 11 \
        and status_counts2["Not started"] == 11 and status_counts2["Decision recorded"] == 1, \
        f"detailed register status arithmetic drifted: {status_counts2}"
    assert rows["A17"]["status"] == "Done" and "Joseph" in rows["A17"]["current"], "A17 must be Done with the Joseph cell evidence"
    assert rows["A17"]["official"].startswith("https://www.nfl.com/news/"), "A17 must link the official Week 10 article"
    assert rows["F-2"]["status"] == "Partial" and "13 of 272" in rows["F-2"]["current"], "F-2 must record 13 of 272 venues, not 272"
    assert rows["F-3"]["status"] == "Partial" and "May 14, 2026" in rows["F-3"]["current"], "F-3 must record the dated announcement"
    assert rows["F-3"]["official"].startswith("https://media.nfl.com/"), "F-3 must link the official announcement"
    assert "162 of 272" in rows["P1"]["current"], "P1 must show the flagged 162 count (was 163 before the games refresh)"
    for rid in ("P3", "P10", "P11", "A13", "A16", "A19", "L2", "L3", "L4", "L5", "L6", "L7", "L8"):
        assert rows[rid]["status"] in ("Partial", "Done"), f"{rid} must record the skill-lab or ledger outcome"
    assert rows["L6"]["status"] == "Done", "L6 is complete: both control baselines run in every leaderboard run"
    assert "reserve" in rows["A19"]["current"], "A19 must record the captured reserve list"
    for rid in ("R1", "R2", "A3", "A4"):
        assert rows[rid]["official"].startswith("http"), f"{rid} must keep an official source link"
    print("Readiness checks passed: 26 canonical requirement rows, correct status arithmetic, detailed-register link, dated snapshot counts, verified-results/corpus-freeze/injury-delta rows.")


if __name__ == "__main__":
    main()
