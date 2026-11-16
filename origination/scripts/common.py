"""Shared helpers for the origination workspace.

Everything here is dependency-free (Python standard library only) so the published numbers can be
audited without installing anything.

Source classes used on every page
---------------------------------
OFFICIAL  a value read from nfl.com / an official club page, linked on the same row.
COMMUNITY a value taken from the repository's digest-verified nflverse snapshot. The row links to the
          release asset and the local manifest entry that records its SHA-256. It is *never* counted
          as official and is excluded from every official-only gate.
DERIVED   a number this workspace computes from the two classes above. The inputs are named on the
          row. A derived number is not a fact about the NFL.
BLANK     the value cannot be confirmed. It stays empty and is published on Flagged for Review.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import html
import io
import json
import math
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "origination"
DATA = OUT / "data"
RAW = ROOT / "data" / "raw"
LAB = ROOT / "decision-lab" / "data"

SEASON = 2026
SEASON_TYPE = "REG"

# ----------------------------------------------------------------------------- official sources
S = {
    "standings": "https://www.nfl.com/standings/",
    "standings_div": "https://www.nfl.com/standings/division/2026/REG",
    "injuries": "https://www.nfl.com/injuries/",
    "injuries_w10": "https://www.nfl.com/injuries/league/2026/REG10",
    "schedule": "https://www.nfl.com/schedules/2026/by-week/week-10",
    "scores_w1": "https://www.nfl.com/scores/2026/week-1/",
    "scores_w10": "https://www.nfl.com/scores/2026/week-10/",
    "game_w10_was_nyg": "https://www.nfl.com/games/commanders-at-giants-2026-reg-10",
    "teams": "https://www.nfl.com/teams/",
    "stats": "https://www.nfl.com/stats/",
    "rulebook": "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook/",
    "odds_faq": "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL",
    "injury_policy": "https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693",
}

# Community release links (GitHub-hosted, digest-verified in data/raw/manifest.json).
G = {
    "repo": "https://github.com/nflverse/nflverse-data",
    "schedules": "https://github.com/nflverse/nflverse-data/releases/tag/schedules",
    "depth": "https://github.com/nflverse/nflverse-data/releases/tag/depth_charts",
    "injuries": "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
    "snaps": "https://github.com/nflverse/nflverse-data/releases/tag/snap_counts",
    "rosters": "https://github.com/nflverse/nflverse-data/releases/tag/rosters",
}

# Canonical team codes. nflverse uses ARI/LA; nfl.com uses AZ/LAR. Both are kept so a reader can
# match a row to either page without guessing.
OFFICIAL_CODE = {"ARI": "AZ", "LA": "LAR"}
FULL_NAME = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}
CLUB_SLUG = {code: name.lower().replace(" ", "-") for code, name in FULL_NAME.items()}


def team_page(code: str) -> str:
    return f"https://www.nfl.com/teams/{CLUB_SLUG[code]}/"


def club_name_to_code() -> dict[str, str]:
    """Map the club names used in the decision-lab capture to canonical codes."""
    out = {}
    for code, name in FULL_NAME.items():
        out[name.lower()] = code
        out[name.split()[-1].lower()] = code
    out.update({"cardinals": "ARI", "rams": "LA", "chargers": "LAC", "49ers": "SF",
                "commanders": "WAS", "eagles": "PHI", "bears": "CHI", "bengals": "CIN",
                "broncos": "DEN", "browns": "CLE", "buccaneers": "TB", "chiefs": "KC",
                "colts": "IND", "cowboys": "DAL", "dolphins": "MIA", "falcons": "ATL",
                "giants": "NYG", "jaguars": "JAX", "jets": "NYJ", "lions": "DET",
                "packers": "GB", "panthers": "CAR", "patriots": "NE", "raiders": "LV",
                "ravens": "BAL", "saints": "NO", "seahawks": "SEA", "steelers": "PIT",
                "titans": "TEN", "vikings": "MIN", "texans": "HOU", "bills": "BUF"})
    return out


# ----------------------------------------------------------------------------- IO
def read_csv(path: Path | str) -> list[dict]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json_default(value):
    """Only two things in this workspace are not JSON-native; both are paths."""
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT))
        except ValueError:
            return str(value)
    raise TypeError(f"not serialisable: {type(value).__name__}")


CANON_DECIMALS = 9


def _canonical(obj):
    """Round floats to CANON_DECIMALS before writing.

    Floating-point sums and powers can differ in the last one or two bits between platforms (a CI
    runner and a developer machine produced 1.7178225370738218 and 1.7178225370738216 for the same
    quantity). Written raw, that makes the committed artifact drift on a rebuild elsewhere. Rounding
    only the written form to 9 decimals removes the platform noise and leaves every published value
    at a precision far finer than any reported figure. In-memory arithmetic is not changed.
    """
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return obj
        return round(obj, CANON_DECIMALS)
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj


def write_json(name: str, payload) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_canonical(payload), indent=1, sort_keys=False, default=_json_default) + "\n",
                    encoding="utf-8")
    return path


def read_json(path: Path | str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest() -> dict:
    return read_json(RAW / "manifest.json")


# ----------------------------------------------------------------------------- small maths
def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return statistics.stdev(xs) if len(xs) > 1 else None


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return xs[int(pos)]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def r(x, nd=3):
    """Round for display, keeping None as an explicit blank."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return round(x, nd)


# ----------------------------------------------------------------------------- probability
def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def american_to_prob(price: float) -> float:
    """Implied probability of an American price, vig included."""
    if price is None:
        return None
    return (-price) / (-price + 100.0) if price < 0 else 100.0 / (price + 100.0)


def american_payout(price: float) -> float:
    """Profit per 1 unit staked at an American price."""
    return (100.0 / -price) if price < 0 else (price / 100.0)


def american_from_prob(p: float) -> int:
    """Fair American price for a probability (no vig)."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    return round(-100.0 * p / (1 - p)) if p > 0.5 else round(100.0 * (1 - p) / p)


def two_way_novig(p_a: float, p_b: float) -> tuple[float, float]:
    total = p_a + p_b
    return p_a / total, p_b / total


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ----------------------------------------------------------------------------- proper scores
def brier(p: float, y: int) -> float:
    return (p - y) ** 2


def log_loss(p: float, y: int, eps: float = 1e-12) -> float:
    p = min(max(p, eps), 1 - eps)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def brier_skill(score_model: float, score_bench: float) -> float:
    """Brier Skill Score = 1 - Brier_model / Brier_benchmark. Positive means better than benchmark."""
    if score_bench == 0:
        return None
    return 1.0 - score_model / score_bench


def cluster_bootstrap_ci(values_a, values_b, groups, n_boot=2000, seed=20261115, alpha=0.05):
    """Paired game-cluster bootstrap of mean(a - b).

    Resamples whole games (clusters), not individual legs, because legs inside a game are dependent.
    Returns a dict with the point estimate, a percentile interval and the seed so it is reproducible.
    """
    import random

    by_group: dict[object, list[tuple[float, float]]] = {}
    for a, b, g in zip(values_a, values_b, groups):
        by_group.setdefault(g, []).append((a - b, 0.0))
    keys = list(by_group)
    if not keys:
        return {"point": None, "lo": None, "hi": None, "n_clusters": 0, "n_boot": 0, "seed": seed}
    diffs = [a - b for a, b in zip(values_a, values_b)]
    point = mean(diffs)
    rng = random.Random(seed)
    samples = []
    for _ in range(n_boot):
        draw = []
        for _ in keys:
            k = keys[rng.randrange(len(keys))]
            draw.extend(d for d, _ in by_group[k])
        if draw:
            samples.append(mean(draw))
    samples.sort()
    lo = samples[int(alpha / 2 * (len(samples) - 1))]
    hi = samples[int((1 - alpha / 2) * (len(samples) - 1))]
    return {"point": point, "lo": lo, "hi": hi, "n_clusters": len(keys),
            "n_boot": len(samples), "seed": seed}


def one_sided_p(diffs, n_boot=4000, seed=20261115) -> float:
    """Bootstrap p-value for mean(diffs) > 0 (paired, sign-resampling of clusters ignored here)."""
    import random

    if not diffs:
        return 1.0
    rng = random.Random(seed)
    obs = mean(diffs)
    if obs is None:
        return 1.0
    centred = [d - obs for d in diffs]
    hits = 0
    for _ in range(n_boot):
        draw = [centred[rng.randrange(len(centred))] for _ in centred]
        if mean(draw) >= obs:
            hits += 1
    return (hits + 1) / (n_boot + 1)


# ----------------------------------------------------------------------------- HTML
def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def cell(value, source_key: str | None = None, source_url: str | None = None, nd=3,
         label: str = "", cls: str = "source") -> str:
    """Render a value cell. A confirmable value carries the link that confirms it.

    A blank must never look like a value: it renders as an explicit badge plus the flag text, so a
    reader cannot mistake "unknown" for zero.
    """
    url = source_url or (S.get(source_key) if source_key else None)
    if value is None or value == "":
        tail = f" <span class='blank'>unverified</span>"
        if label:
            tail += f"<span class='why'>{esc(label)}</span>"
        return tail
    shown = f"{value:.{nd}f}" if isinstance(value, float) else esc(value)
    if url:
        return (f"<a class='{cls}' href='{esc(url)}' target='_blank' rel='noopener noreferrer' "
                f"title='{esc(label)}'>{shown}</a>")
    return shown


def page(title: str, subtitle: str, body: str, nav_extra: list[tuple[str, str]] | None = None) -> str:
    pages = [
        ("index.html", "Overview"),
        ("requirements.html", "Requirements"),
        ("decisions.html", "Decisions & questions"),
        ("strategies.html", "Strategy registry"),
        ("leaderboard.html", "Leaderboard"),
        ("lines.html", "Originated lines"),
        ("prices.html", "Price store"),
        ("availability.html", "Availability & depth"),
        ("correlations.html", "Correlations"),
        ("luck.html", "Luck removal"),
        ("suggestions.html", "Suggestions"),
        ("flagged.html", "Flagged for review"),
        ("sources.html", "Sources"),
    ]
    here = "index.html"
    for url, _ in pages:
        pass
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | NFL3 origination workspace</title>
<link rel="stylesheet" href="assets/origination.css"></head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="index.html"><b>N</b> NFL3 <span>/ origination</span></a>
<nav aria-label="Origination navigation" data-current="{esc(HERE.get('page',''))}">
{''.join(f"<a href='{u}'>{esc(t)}</a>" for u, t in pages)}
</nav></div></header>
<main class="wrap">
<div class="hrow"><div><p class="eyebrow">{esc(subtitle)}</p><h1>{esc(title)}</h1></div>
<span class="badge warn">Research · not betting advice</span></div>
{body}
</main>
<footer class="wrap foot"><span><strong>NFL3 origination workspace</strong> · every row links to its source ·
a value that could not be confirmed stays blank.</span>
<span>Generated {esc(GENERATED_AT)}</span></footer>
</body></html>
"""


HERE: dict[str, str] = {"page": ""}
GENERATED_AT = "2026-11-15"
