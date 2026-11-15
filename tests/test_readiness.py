"""Regression checks for the landing-page readiness table and count summary."""
import collections
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
    print("Readiness checks passed: 26 canonical requirement rows, correct status arithmetic, detailed-register link, and dated snapshot counts.")


if __name__ == "__main__":
    main()
