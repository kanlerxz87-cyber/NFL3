"""Regression checks for the landing matrix and canonical gate-detail page."""
import json
import re
import collections
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "decision-lab/data/readiness.json").read_text(encoding="utf-8"))


def requirement_ids(text: str) -> list[str]:
    return re.findall(r"<tr><td>(R\d{2})</td>", text)


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/build_readiness.py")], cwd=ROOT, check=True)
    expected = [item["id"] for item in DATA["requirements"]]
    assert len(expected) == len(set(expected)), "duplicate readiness IDs"
    landing = (ROOT / "index.html").read_text(encoding="utf-8")
    assert requirement_ids(landing) == expected, "landing page must have one row per requirement in register order"
    assert 'href="decision-lab/readiness.html"' in landing, "landing matrix must link to the detailed gate page"
    status_counts = collections.Counter(
        re.search(r'<span class="pill [^"]+">([^<]+)</span>', body).group(1)
        for _rid, body in re.findall(r'<tr><td>(R\d{2})</td>(.*?)</tr>', landing)
    )
    assert status_counts == {"implemented": 14, "partial": 10, "blocked": 2}, f"landing readiness summary must match its rows: {status_counts}"
    assert "14 of 26 requirements implemented, 10 partial, 2 blocked" in landing, "summary totals must agree with the matrix"
    detail = (ROOT / "decision-lab/readiness.html").read_text(encoding="utf-8")
    assert requirement_ids(detail) == expected, "detail page and landing matrix disagree"
    for item in DATA["requirements"]:
        assert item.get("gate") and item.get("blocker") and item.get("clearance"), f"{item['id']} is incomplete"
        if item.get("number") is None:
            assert item.get("number_status", "").startswith("Unverified"), f"{item['id']} blank number is not flagged"
            match = re.search(rf'<tr><td>{item["id"]}</td>.*?</tr>', detail)
            assert match and 'class="blank"' in match.group(0) and "Unverified" in match.group(0), f"{item['id']} blank threshold must render blank and flagged"
    print(f"Readiness checks passed: {len(expected)} requirements, exact register match, gate/blocker/clearance present, unknown numeric thresholds blank and flagged.")


if __name__ == "__main__":
    main()
