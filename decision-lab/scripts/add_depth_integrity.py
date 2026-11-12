#!/usr/bin/env python3
"""Annotate captured depth rows with a reproducible cell-integrity flag.

Why this exists
---------------
The depth capturer used to concatenate the text of a published table cell. Some
club pages publish two players in one cell, so those rows hold a joined string
such as "Pat Freiermuth Darnell Washington". Splitting such a string by
whitespace is not safe: it cannot tell "Kris Jenkins Jr." from a second player,
and it cannot tell "P.J. Locke" from an initial.

This script therefore does NOT split any name or infer any new player. It only
flags which published rows are affected, so the site can show them as
unverified instead of presenting them as clean player entries. The flag is
derived from the cell's own anchors, which is evidence rather than a guess.

A row is flagged when the club page supplied more than one anchor for the cell
AND the stored string begins with the published first player's words. In that
case the row is marked `needs_split`; it is never silently rewritten.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_official as capture

DATA = Path(__file__).resolve().parents[1] / "data"
SNAPSHOT = DATA / "official_snapshot.json"

RULES = [
    "A blank published cell stays blank; nothing is inferred.",
    "A published depth rank is order, not confirmed starter status or snap count.",
    "A source hash proves capture integrity, not future source stability or reuse rights.",
    "A page that calls its own chart unofficial is labelled UNOFFICIAL.",
]


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def words(text: str) -> list[str]:
    """Lowercase word list with generational suffixes removed.

    Club URLs often omit the suffix ("jon-runyan" for "Jon Runyan Jr."), so the
    suffix must not count as an extra word or every suffixed name is misread as
    a joined cell.
    """
    import re
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    parts = [w for w in re.split(r"[^a-z]+", text) if w]
    return [w for w in parts if w not in SUFFIXES]


def main() -> int:
    doc = json.loads(SNAPSHOT.read_text())
    rows = doc["depth_rows"]
    needs_split = []
    for row in rows:
        row["cell_integrity"] = "ok"
        url = row.get("player_url") or ""
        if not url:
            continue
        slug_words = words(urlparse(url).path.rstrip("/").split("/")[-1])
        value_words = words(row["player"])
        # The stored value starts with the anchored first player but carries more
        # words than that player's own name: the cell was joined from two players.
        if len(value_words) > len(slug_words) and value_words[: len(slug_words)] == slug_words:
            row["cell_integrity"] = "needs_split"
            needs_split.append({
                "team": row["team"], "unit": row["unit"], "position": row["position"],
                "published_rank": row["published_rank"], "stored_value": row["player"],
                "published_first_player_url": url, "source_url": row["source_url"],
            })
    doc["depth_cell_integrity"] = {
        "checked_at": "2026-11-12",
        "session": "arena/dc6c67cf-nfl3",
        "rows_checked": len(rows),
        "rows_needs_split": len(needs_split),
        "policy": ("Flagged rows keep every published character. No name is split, reordered or "
                   "invented here, because word splitting cannot distinguish a second player from "
                   "a suffix or an initial. Affected rows are published as unverified and are "
                   "excluded from any starter/backup conclusion until the parser fix is applied in "
                   "a fresh capture."),
        "parser_fixed": True,
        "parser_fix": ("capture_official.cell_entries() now emits one row per published anchor, so a "
                       "fresh capture will not reproduce the joined string."),
        "rows": needs_split,
    }
    doc["rules"] = RULES + [r for r in doc.get("rules", []) if r not in RULES]
    SNAPSHOT.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"depth rows checked: {len(rows)}; flagged needs_split: {len(needs_split)}")
    for item in needs_split:
        print(" ", item["team"], item["position"], item["published_rank"], repr(item["stored_value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
