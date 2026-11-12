#!/usr/bin/env python3
"""Deterministic topic grouping for the consolidated registers.

The four workspaces use different labels for the same subject. This maps an
item's area and text onto one shared theme using keyword rules, so the merged
register reads as a categorised list. Rules are explicit and reviewable; where
no rule matches, the original label is kept.
"""
from __future__ import annotations

THEMES: list[tuple[str, tuple[str, ...]]] = [
    ("Data rights & licensing", ("licens", "rights", "legal", "jurisdiction", "terms",
                                 "nflverse", "authority", "authoritative when", "disagree",
                                 "contradiction", "precedence", "security", "privacy", "accounts")),
    ("Market data & prices", ("odds", "price", "pricing", "lines", "sportsbook", "closing",
                              "clv", "market", "taxonomy", "props are offered", "cost of a bet")),
    ("Outcomes & grading", ("settle", "grading", "graded", "outcome", "results", "scores",
                            "push", "void", "historical game")),
    ("Injury & availability", ("injury", "injuries", "depth", "string", "backup", "inactive",
                               "practice squad", "questionable", "doubtful", "status", "starter")),
    ("Correlation & parlays", ("correlation", "parlay", "dependent", "joint", "leg")),
    ("Model & signals", ("model", "signal", "rating", "estimate", "weather", "feature",
                         "pythagorean", "baseline", "strength")),
    ("Validation & sample size", ("sample", "validation", "threshold", "evidence",
                                  "multiple testing", "false discovery", "brier", "walk-forward",
                                  "overfit", "out of sample")),
    ("Luck, variance & staking", ("luck", "skill", "sharpe", "variance", "bankroll", "staking",
                                  "drawdown", "kelly")),
    ("Rewards & competition", ("reward", "leaderboard", "competition", "prize", "funded", "winner")),
    ("Operations & automation", ("automation", "ingestion", "rebuil", "verification", "workflow",
                                 "human in the loop", "review", "publish", "site")),
    ("Scope & product", ("scope", "product", "recommendation", "audience", "monetis")),
    ("Rules of play", ("rule", "kickoff", "onside", "disqualification")),
]


def theme_for(*texts: str) -> str:
    blob = " ".join(t for t in texts if t).lower()
    best_name, best_hits = "", 0
    for name, keys in THEMES:
        hits = sum(1 for k in keys if k in blob)
        if hits > best_hits:
            best_name, best_hits = name, hits
    return best_name or "Other"
