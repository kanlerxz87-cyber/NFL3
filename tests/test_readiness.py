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
    # arena/16183225-nfl3, 2026-11-15). The landing matrix keeps its dated catalog labels and is
    # deliberately not asserted against these.
    register = (ROOT / "readiness" / "data" / "readiness.csv").read_text(encoding="utf-8")
    rows = {r["id"]: r for r in csv.DictReader(register.splitlines())}
    assert len(rows) == 64, f"detailed register should hold 64 rows, found {len(rows)}"
    assert rows["R1"]["status"] == "Done" and "136/136" in rows["R1"]["current"], "R1 must record the 136/136 official verification"
    assert rows["R2"]["status"] == "Partial" and "87f83f5ee231" in rows["R2"]["current"], "R2 must record the corpus freeze commit"
    assert "a1633c20" in rows["R2"]["current"], "R2 must record the frozen corpus hash"
    assert rows["A3"]["status"] == "Partial" and "139 game-status changes" in rows["A3"]["current"], "A3 must record the published per-player deltas"
    assert rows["A4"]["current"].count("20") >= 4 and "2026-11-15" in rows["A4"]["current"], "A4 must record four dated reads"
    status_counts2 = collections.Counter(r["status"] for r in rows.values())
    assert status_counts2["Done"] == 3 and status_counts2["Partial"] == 18 and status_counts2["Blocked"] == 14 \
        and status_counts2["Not started"] == 28 and status_counts2["Decision recorded"] == 1, \
        f"detailed register status arithmetic drifted: {status_counts2}"
    for rid in ("R1", "R2", "A3", "A4"):
        assert rows[rid]["official"].startswith("http"), f"{rid} must keep an official source link"
    print("Readiness checks passed: 26 canonical requirement rows, correct status arithmetic, detailed-register link, dated snapshot counts, verified-results/corpus-freeze/injury-delta rows.")


if __name__ == "__main__":
    main()
