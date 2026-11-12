#!/usr/bin/env python3
"""Fail-closed validation gates for NFL strategy research.

This module does not train a model or place bets. It assesses whether a frozen
forecast ledger is eligible for a decision/leaderboard under explicit evidence
rules. Synthetic unit-test records are never published as performance evidence.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from datetime import datetime
from statistics import NormalDist
from urllib.parse import urlparse

OFFICIAL_HOSTS = {
    "nfl.com", "www.nfl.com", "operations.nfl.com", "support.nfl.com", "nextgenstats.nfl.com",
    "media.nfl.com", "static.www.nfl.com", "www.commanders.com", "www.giants.com", "www.colts.com",
    "www.baltimoreravens.com", "www.patriots.com", "www.detroitlions.com", "www.denverbroncos.com",
    "www.seahawks.com", "www.itl.nist.gov", "itl.nist.gov", "scikit-learn.org", "docs.github.com",
    # Club depth-chart publishers added in the 2026-11-12 verification pass. They are
    # first-party club sites listed by the official NFL team directory.
    "www.houstontexans.com", "www.packers.com", "www.49ers.com", "www.buffalobills.com",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = (
    "strategy_id", "game_id", "season", "fold", "division", "market", "forecast_at", "logged_at",
    "available_at", "quote_at", "kickoff", "probability", "baseline_probability", "outcome",
    "american_odds", "settlement", "source_url", "source_sha256", "config_hash",
)
DEFAULT_POLICY = {
    "min_games": 256,
    "min_seasons": 2,
    "min_folds": 3,
    "min_shadow_games": 128,
    "bootstrap_replicates": 2000,
    "alpha": 0.05,
    "max_calibration_gap": 0.10,
    "min_calibration_bin": 20,
    "seed": 20261112,
}


def official_source(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "") in OFFICIAL_HOSTS


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt


def american_to_decimal(odds: float) -> float:
    if odds >= 100:
        return 1.0 + odds / 100.0
    if odds <= -100:
        return 1.0 + 100.0 / abs(odds)
    raise ValueError("invalid American odds")


def implied_probability(odds: float) -> float:
    return 1.0 / american_to_decimal(odds)


def remove_vig(probabilities: list[float]) -> list[float]:
    total = sum(probabilities)
    if total <= 0:
        raise ValueError("positive implied probabilities required")
    return [p / total for p in probabilities]


def brier(probability: float, outcome: int) -> float:
    return (probability - outcome) ** 2


def log_loss(probability: float, outcome: int) -> float:
    p = min(max(probability, 1e-15), 1 - 1e-15)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def bonferroni_z(trial_count: int, alpha: float = 0.05) -> float:
    if trial_count < 1 or not 0 < alpha < 1:
        raise ValueError("invalid multiplicity policy")
    return NormalDist().inv_cdf(1.0 - alpha / (2.0 * trial_count))


def cluster_lower_bound(game_values: dict[str, list[float]], replicates: int, alpha: float, seed: int) -> float | None:
    """One-sided percentile bootstrap lower bound, resampling whole games."""
    games = list(game_values)
    if not games or replicates < 200:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(replicates):
        sample = [value for _ in range(len(games)) for value in game_values[rng.choice(games)]]
        means.append(sum(sample) / len(sample))
    means.sort()
    index = max(0, min(len(means) - 1, math.floor(alpha * len(means))))
    return means[index]


def calibration_gap(records: list[dict], min_bin: int) -> float | None:
    bins: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("outcome") in (0, 1):
            bins[min(9, int(float(record["probability"]) * 10))].append(record)
    gaps = []
    for rows in bins.values():
        if len(rows) >= min_bin:
            mean_p = sum(float(r["probability"]) for r in rows) / len(rows)
            rate = sum(int(r["outcome"]) for r in rows) / len(rows)
            gaps.append(abs(mean_p - rate))
    return max(gaps) if gaps else None


def is_multi_leg(division: str) -> bool:
    text = division.lower()
    return "parlay" in text or "combo" in text or "combination" in text


def assess(records: list[dict], policy: dict) -> dict:
    cfg = {**DEFAULT_POLICY, **policy}
    gates: dict[str, dict] = {}
    scored = [r for r in records if r.get("outcome") in (0, 1) and r.get("settlement") in {"win", "loss"}]

    def gate(gid: str, passed: bool, evidence: str) -> None:
        gates[gid] = {"pass": bool(passed), "evidence": evidence}

    ok = bool(records)
    ok = ok and all(all(k in r and r[k] != "" for k in REQUIRED) for r in records)
    ok = ok and all(official_source(r["source_url"]) and r.get("source_verified") is True
                    and SHA256.match(str(r["source_sha256"])) and r.get("official_outcome_verified") is True
                    for r in records)
    gate("G01", ok, "Official HTTPS provenance, raw hash and official outcome confirmation required; community data excluded.")

    timing = True
    for r in records:
        try:
            available, forecast, logged, quote, kickoff = (parse_time(r[k]) for k in ("available_at", "forecast_at", "logged_at", "quote_at", "kickoff"))
            timing = timing and available <= forecast <= logged < kickoff and quote <= forecast
        except Exception:
            timing = False
    gate("G02", bool(records) and timing, "Features/quotes as-of forecast; forecast logged before kickoff; timezone-aware timestamps.")

    keys = [(r.get("strategy_id"), r.get("game_id"), r.get("market"), r.get("side", "")) for r in records]
    complete = bool(records) and len(keys) == len(set(keys))
    complete = complete and all(0 < float(r["probability"]) < 1 and 0 < float(r["baseline_probability"]) < 1 for r in records)
    complete = complete and all(r["outcome"] in (0, 1, "", None) for r in records)
    gate("G03", complete, "Unique event keys, bounded probabilities and no silent imputation; push/void rows excluded from scoring.")

    market = bool(records)
    for r in records:
        try:
            american_to_decimal(float(r["american_odds"]))
            market = market and r.get("settlement_verified") is True and r.get("settlement") in {"win", "loss", "push", "void"}
            if r.get("settlement") in {"win", "loss"}:
                market = market and int(r["outcome"]) == (1 if r["settlement"] == "win" else 0)
        except Exception:
            market = False
    gate("G04", market, "Valid price, documented settlement and verified grading required.")

    prereg = bool(records) and bool(cfg.get("config_hash")) and cfg.get("preregistered_at")
    if prereg:
        try:
            pre = parse_time(cfg["preregistered_at"])
            prereg = all(r.get("config_hash") == cfg["config_hash"] and pre < parse_time(r["logged_at"]) for r in records)
            prereg = prereg and isinstance(cfg.get("trial_count"), int) and cfg["trial_count"] >= 1
        except Exception:
            prereg = False
    gate("G05", prereg, "Frozen config hash and complete trial family declared before forecasts.")

    games = {r["game_id"] for r in scored}
    seasons = {r["season"] for r in scored}
    folds = {r["fold"] for r in scored}
    diffs: dict[str, list[float]] = defaultdict(list)
    for r in scored:
        diffs[r["game_id"]].append(brier(float(r["baseline_probability"]), int(r["outcome"])) - brier(float(r["probability"]), int(r["outcome"])))
    point_skill = sum(v for values in diffs.values() for v in values) / len(scored) if scored else None
    lower = cluster_lower_bound(diffs, int(cfg["bootstrap_replicates"]), float(cfg["alpha"]) / max(1, int(cfg.get("trial_count", 1))), int(cfg["seed"])) if diffs else None
    gap = calibration_gap(scored, int(cfg["min_calibration_bin"]))
    evaluation = (len(games) >= int(cfg["min_games"]) and len(seasons) >= int(cfg["min_seasons"])
                  and len(folds) >= int(cfg["min_folds"]) and lower is not None and lower > 0
                  and gap is not None and gap <= float(cfg["max_calibration_gap"]))
    gate("G06", evaluation, f"games={len(games)}, seasons={len(seasons)}, folds={len(folds)}, Brier skill={point_skill}, cluster lower={lower}, calibration gap={gap}.")

    division = records[0].get("division", "") if records else ""
    if is_multi_leg(division):
        joint_diffs: dict[str, list[float]] = defaultdict(list)
        joint_ok = bool(scored)
        for r in scored:
            try:
                jp, ip = float(r["joint_probability"]), float(r["independence_probability"])
                joint_ok = joint_ok and 0 < jp < 1 and 0 < ip < 1 and "joint_outcome" in r and r["joint_outcome"] in (0, 1)
                joint_diffs[r["game_id"]].append(brier(ip, int(r["joint_outcome"])) - brier(jp, int(r["joint_outcome"])))
            except Exception:
                joint_ok = False
        joint_lower = cluster_lower_bound(joint_diffs, int(cfg["bootstrap_replicates"]), float(cfg["alpha"]) / max(1, int(cfg.get("trial_count", 1))), int(cfg["seed"]) + 1) if joint_diffs else None
        dependence = joint_ok and joint_lower is not None and joint_lower > 0
        gate("G07", dependence, f"Direct joint calibration versus independence required; lower={joint_lower}.")
    else:
        gate("G07", True, "Not applicable to single-leg division; multi-leg expansion requires a separate joint gate.")

    personnel_rows = [r for r in records if r.get("uses_personnel")]
    personnel = True
    for r in personnel_rows:
        personnel = personnel and r.get("personnel_evidence_verified") is True and official_source(r.get("personnel_source_url", ""))
        try:
            personnel = personnel and parse_time(r["personnel_observed_at"]) <= parse_time(r["available_at"])
        except Exception:
            personnel = False
    gate("G08", personnel, "Personnel features require dated official/club evidence; conflicts/staleness abstain.")

    shadow = (cfg.get("shadow_verified") is True and cfg.get("shadow_version_hash") == cfg.get("config_hash")
              and int(cfg.get("shadow_game_count", 0)) >= int(cfg["min_shadow_games"])
              and all(r.get("prospective") is True for r in records))
    gate("G09", shadow, "Independent prospective shadow ledger with frozen version required.")

    prior = all(g["pass"] for gid, g in gates.items() if gid != "G10")
    rewards = prior and cfg.get("reward_policy_approved") is True and cfg.get("funding_verified") is True
    gate("G10", rewards, "Recognition/rewards only after G01-G09 plus approved policy and verified funding.")

    return {
        "eligible": all(g["pass"] for g in gates.values()),
        "gates": gates,
        "metrics": {
            "scored_rows": len(scored), "games": len(games), "brier_skill": point_skill,
            "brier_skill_lower": lower, "calibration_gap": gap,
            "correlation": None, "roi": None, "reward": None,
        },
        "note": "Blank correlation/ROI/reward means not verified or not computed by this release gate. Synthetic tests are not leaderboard entries.",
    }


def config_hash(document: dict) -> str:
    return hashlib.sha256(__import__("json").dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
