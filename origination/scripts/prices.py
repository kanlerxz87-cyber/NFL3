#!/usr/bin/env python3
"""Price-snapshot store: record opening and closing numbers for every market we originate.

The store has three layers.

1. **Immutable snapshots** — `origination/data/prices/snapshots/<observed_at>.json`. One file per
   observation of a price source. It is written once and never rewritten; a re-observation is a new
   file. Each file carries the source URL, the observation timestamp, the file's own SHA-256 and the
   digest of the upstream release asset it came from.

2. **The ledger** — `origination/data/prices/ledger.json`. Derived from the snapshots. For every
   event x market it records, with the number of observations that support it:
     opening      the earliest pre-kickoff observation we hold            (blank if we hold none)
     latest       the latest pre-kickoff observation we hold              (blank if we hold none)
     closing      the latest pre-kickoff observation before kickoff       (blank if we hold none)
     post_hoc     the first observation recorded after kickoff            (never used as an opening
                                                                           or a closing number)
   A market with no pre-kickoff observation gets a blank, not an estimate.

3. **The policy** — `origination/data/prices/POLICY.md`, committed before any evaluation was run.
   It decides, in advance, which price a backtest may use, what counts as the close, how vig is
   removed and which columns are excluded from every gate. The policy carries a content hash so a
   later change is visible as a diff rather than a silent edit.

Honest limitation recorded with the store: on 2026-11-15 we hold **one** community price observation.
Weeks 1-9 had already kicked off, so their prices are post-hoc and cannot seed an opening line or a
closing line. The 13 Week 10 games that had not kicked off at the observation time are the first
genuine pre-kickoff observations this repository holds. That is the day-one baseline.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import common as C
import inputs

SNAP_DIR = C.DATA / "prices" / "snapshots"
POLICY = C.DATA / "prices" / "POLICY.md"

MARKETS = ("spread", "total", "moneyline")


def kickoff_utc(game: dict) -> dt.datetime | None:
    """Kickoff as an aware UTC datetime, from the schedule's published date and time."""
    if not game["gameday"]:
        return None
    hhmm = game["gametime"] or "00:00"
    try:
        date = dt.date.fromisoformat(game["gameday"])
        hour, minute = (int(x) for x in hhmm.split(":")[:2])
    except (ValueError, TypeError):
        return None
    # nflverse publishes kickoff in US Eastern. During the NFL season Eastern is UTC-4 (EDT) for
    # Weeks 1-8 and UTC-5 (EST) from the first Sunday in November. The schedule file does not carry a
    # zone, so this is a documented approximation and is flagged as such on the price page.
    return dt.datetime(date.year, date.month, date.day, hour, minute,
                       tzinfo=dt.timezone(dt.timedelta(hours=-4))).astimezone(dt.timezone.utc)


def eastern_offset_note() -> str:
    return ("Kickoff times are published in US Eastern by the schedule release and are converted with a "
            "fixed UTC-4 offset. Weeks 9-18 observe Eastern Standard Time (UTC-5), so kickoff instants "
            "in those weeks are up to 60 minutes later than recorded here. The error only affects the "
            "pre/post-kickoff boundary for a snapshot taken within an hour of kickoff; it is flagged, "
            "not silently corrected.")


def snapshot_from_schedule(games: list[dict], observed_at: str, manifest_entry: dict) -> dict:
    """Turn one observed schedule/price release into an immutable snapshot of every market row."""
    rows = []
    for game in games:
        ko = kickoff_utc(game)
        rows.append({
            "event_id": game["game_id"], "week": game["week"], "gameday": game["gameday"],
            "gametime_et": game["gametime"], "kickoff_utc_approx": ko.isoformat() if ko else None,
            "away": game["away"], "home": game["home"],
            "markets": {
                "spread": {"home_line": game["spread_line"],
                           "home_price": game["home_spread_odds"],
                           "away_price": game["away_spread_odds"]},
                "total": {"line": game["total_line"], "over_price": game["over_odds"],
                          "under_price": game["under_odds"]},
                "moneyline": {"home": game["home_moneyline"], "away": game["away_moneyline"]},
            },
        })
    payload = {
        "schema_version": 1,
        "kind": "price_snapshot",
        "observed_at": observed_at,
        "source_class": "COMMUNITY",
        "source_url": C.G["schedules"],
        "release_tag": manifest_entry.get("release_tag", "schedules"),
        "release_asset_updated_utc": manifest_entry.get("release_asset_updated_utc"),
        "upstream_sha256": manifest_entry.get("sha256"),
        "upstream_bytes": manifest_entry.get("bytes"),
        "local_manifest_path": "data/raw/manifest.json",
        "note": ("Recorded from the digest-verified community schedule release. These are the numbers "
                 "that release publishes in its away_moneyline/home_moneyline/spread_line/total_line "
                 "columns; they are not an official NFL price and the release does not state whether "
                 "they are an open or a close."),
        "rows": rows,
    }
    return payload


def write_snapshots() -> list[Path]:
    """Append a snapshot for the current manifest state, keeping every earlier capture.

    A second observation of the same release is a genuinely new observation: the release is refreshed
    hourly during the season, so its prices can move between reads. Each distinct capture is written to
    its own immutable file and named by its observation time, and the earlier files are never touched.
    Two captures of a byte-identical release are not duplicated: the payload hash decides.
    """
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    entry = inputs_manifest_entry("games")
    observed_at = (entry.get("release_asset_updated_utc") or "2026-11-15T12:36:23Z")
    observed_at = observed_at.replace("+00:00", "Z")
    if not observed_at.endswith("Z"):
        observed_at += "Z"
    payload = snapshot_from_schedule(inputs.games(), observed_at, entry)
    encoded = (C.json.dumps(payload, indent=1) + "\n").encode()
    payload_sha = C.sha256_bytes(encoded)
    for existing_path in sorted(SNAP_DIR.glob("*.json")):
        existing = C.read_json(existing_path)
        if existing.get("snapshot_sha256") == payload_sha:
            return [existing_path]
    payload["snapshot_sha256"] = payload_sha
    name = observed_at.replace(":", "").replace("-", "")
    base = SNAP_DIR / f"{name}.json"
    path, n = base, 1
    while path.exists():
        path = SNAP_DIR / f"{base.stem}-{n}.json"
        n += 1
    path.write_bytes((C.json.dumps(payload, indent=1) + "\n").encode())
    return [path]


def inputs_manifest_entry(key: str) -> dict:
    return C.manifest()["files"].get(key, {})


def load_snapshots() -> list[dict]:
    return [C.read_json(p) for p in sorted(SNAP_DIR.glob("*.json"))]


def opening_values_differ(opening: dict | None, latest: dict | None) -> bool:
    """Did any published component of this market move between the opening and the latest observation?"""
    if not opening or not latest:
        return False
    for key in set(opening) | set(latest):
        a, b = opening.get(key), latest.get(key)
        if a is None or b is None:
            if a != b:
                return True
            continue
        if abs(float(a) - float(b)) > 1e-9:
            return True
    return False


def build_ledger() -> dict:
    """Derive opening / latest / closing / post-hoc per event x market from the immutable snapshots."""
    games = {g["game_id"]: g for g in inputs.games()}
    snaps = load_snapshots()
    if not snaps:
        raise SystemExit("price ledger: no snapshots present")
    events = {}
    for snap in snaps:
        observed = dt.datetime.fromisoformat(snap["observed_at"].replace("Z", "+00:00"))
        for row in snap["rows"]:
            ko = kickoff_utc(games[row["event_id"]]) if row["event_id"] in games else None
            pre = bool(ko and observed < ko)
            entry = events.setdefault(row["event_id"], {
                "event_id": row["event_id"], "week": row["week"], "gameday": row["gameday"],
                "gametime_et": row["gametime_et"], "away": row["away"], "home": row["home"],
                "kickoff_utc_approx": row["kickoff_utc_approx"],
                "observations": [], "markets": {m: {} for m in MARKETS},
            })
            entry["observations"].append({"observed_at": snap["observed_at"],
                                          "snapshot": snap.get("snapshot_sha256"),
                                          "pre_kickoff": pre})
            for market in MARKETS:
                cell = entry["markets"][market]
                payload = row["markets"][market]
                has_value = any(v is not None for v in payload.values())
                if not has_value:
                    continue
                if pre:
                    cell.setdefault("pre", []).append({"observed_at": snap["observed_at"],
                                                       "values": payload,
                                                       "snapshot": snap.get("snapshot_sha256")})
                else:
                    cell.setdefault("post", []).append({"observed_at": snap["observed_at"],
                                                        "values": payload,
                                                        "snapshot": snap.get("snapshot_sha256")})
    for entry in events.values():
        entry["observations"].sort(key=lambda x: x["observed_at"])
        for market, cell in entry["markets"].items():
            pre = sorted(cell.get("pre", []), key=lambda x: x["observed_at"])
            post = sorted(cell.get("post", []), key=lambda x: x["observed_at"])
            cell.clear()
            cell["n_pre_kickoff"] = len(pre)
            cell["n_post_kickoff"] = len(post)
            cell["opening"] = pre[0]["values"] if pre else None
            cell["opening_observed_at"] = pre[0]["observed_at"] if pre else None
            cell["latest"] = pre[-1]["values"] if pre else None
            cell["latest_observed_at"] = pre[-1]["observed_at"] if pre else None
            cell["closing"] = pre[-1]["values"] if pre else None
            cell["closing_observed_at"] = pre[-1]["observed_at"] if pre else None
            cell["closing_definition"] = ("single pre-kickoff observation: opening and closing are the "
                                          "same number until a second pre-kickoff capture exists")
            if len(pre) >= 2:
                cell["closing_definition"] = ("latest pre-kickoff observation; with two or more captures "
                                              "the opening and the closing are distinct numbers")
                cell["moved_since_opening"] = opening_values_differ(pre[0]["values"], pre[-1]["values"])
            cell["post_hoc"] = post[0]["values"] if post else None
            cell["post_hoc_observed_at"] = post[0]["observed_at"] if post else None
            cell["post_hoc_usable_for"] = ("reference only: recorded after kickoff, so it may not be used "
                                           "as an opening line, a closing line or CLV evidence")
    ledger = {
        "schema_version": 1,
        "built_at": C.GENERATED_AT,
        "policy": str(POLICY.relative_to(C.ROOT)),
        "policy_sha256": C.sha256_file(POLICY) if POLICY.exists() else None,
        "snapshot_files": [{"path": str(p.relative_to(C.ROOT)),
                            "sha256": C.sha256_file(p),
                            "observed_at": C.read_json(p)["observed_at"]} for p in sorted(SNAP_DIR.glob("*.json"))],
        "counts": {},
        "events": [events[k] for k in sorted(events, key=lambda g: (events[g]["week"], g))],
        "kickoff_conversion_note": eastern_offset_note(),
    }
    pre_open = sum(1 for e in ledger["events"] for m in MARKETS if e["markets"][m]["opening"])
    post_only = sum(1 for e in ledger["events"] for m in MARKETS
                    if not e["markets"][m]["opening"] and e["markets"][m]["post_hoc"])
    blank = sum(1 for e in ledger["events"] for m in MARKETS
                if not e["markets"][m]["opening"] and not e["markets"][m]["post_hoc"])
    ledger["counts"] = {
        "events": len(ledger["events"]),
        "snapshots": len(ledger["snapshot_files"]),
        "market_cells": len(ledger["events"]) * len(MARKETS),
        "with_pre_kickoff_opening": pre_open,
        "post_hoc_only": post_only,
        "no_observation_at_all": blank,
        "events_played_at_last_observation": sum(
            1 for e in ledger["events"] if inputs.played(games[e["event_id"]])),
    }
    C.write_json("prices/ledger.json", ledger)
    return ledger


POLICY_TEXT = """# Price-data policy — pre-registered before any backtest was published

Registered: 2026-11-15 (UTC). Content hash is written into `data/prices/ledger.json`, so any later edit
shows up as a changed hash in the diff of this commit. This file is a decision, not a finding.

## The source boundary (why we hold what we hold)

* The NFL publishes no odds feed this project may use, and the NFL's own betting FAQ states that odds
  shown on NFL properties are a widget supplied by a partner. Those numbers are not a licensed archive.
  Legitimate historical price archives are licensed commercial products. This project holds none.
* The only price series in this repository is the community `schedules` release (nflverse-data). Its
  digest is verified against the published SHA-256 in `data/raw/manifest.json`. That proves byte
  integrity, **not** official authority, and it does not prove the number is an open or a close.
* Therefore every price on this site is labelled **COMMUNITY**. No price is ever labelled official.

## P01 — Opening and closing are different objects

Opening = the earliest pre-kickoff observation this repository holds for that event x market.
Closing = the latest pre-kickoff observation held before that event's kickoff.
Neither is ever inferred. If we hold no pre-kickoff observation, both stay blank.

## P02 — An after-the-fact number is not an opening, a close, or CLV evidence

An observation recorded after an event's kickoff is stored as `post_hoc`. It may be used as a reference
only. It may never enter an opening-line study, a closing-line-value study or any "we beat the close"
claim. The ledger counts those cells explicitly (`counts.post_hoc_only`).

## P03 — Day-one status, stated plainly

At the first observation (2026-11-15, Weeks 1-9 already played) this repository holds **one** price
observation. Consequences, published rather than hidden:

* the 136-game corpus (Weeks 1-10 including the played Week 10 game) keeps its numbers in `post_hoc`,
  so no backtest may claim an opening-line or CLV edge on it;
* the Week 10 games that had not kicked off at the observation time are the first genuine pre-kickoff
  numbers this repository owns; for them opening = closing until a second capture exists, and the
  ledger says so cell by cell.

## P04 — The capture schedule (the automation that must run)

A scheduled job captures the price source at least: daily during the week, and at T-60 minutes before
each kickoff. Each capture is a new immutable snapshot file. A missed capture is recorded as a gap, not
back-filled. No backtest may be published for a market whose capture coverage is below the pre-registered
gate (see `strategies.html`, gate G05).

## P05 — Vig removal

Two-way markets are de-vigged multiplicatively: `p_fair = p_raw / (p_raw + p_other)`. This is stated so
the residual and correlation work is reproducible. It is an assumption, not a measurement, and it is
applied identically to every price so it cannot favour a strategy.

## P06 — Push and void

Spread and total lines published on the half-point are push-free. Whole-number lines can push. Where a
result lands exactly on the number, the leg is graded as a push and excluded from win/loss scoring; it
still counts toward `n`. Moneyline has no push. This rule is applied mechanically by the grader and is
unit-tested.

## P07 — Settlement source

A bet settles against the official final score. In this workspace the official final score is the
reconciled result feed (`results.html`), which reproduces nfl.com's standing totals exactly for all 32
clubs. The community game log is a cross-check, never the settlement authority.

## P08 — One book, no line shopping, no best-of-multi-book

The price series carries no bookmaker identity, so a backtest may not assume a better number existed.
The grader uses exactly the stored number. If a licensed multi-book feed is later purchased, this policy
is superseded by a new dated policy file, not edited in place.

## P09 — Time zones

Kickoff times come from the schedule release in US Eastern and are converted at a fixed UTC-4 offset.
The boundary error (up to 60 minutes in EST weeks) is published, not corrected silently. It can only
mislabel an observation as pre-kickoff when that observation is within an hour of kickoff.

## P10 — What may never appear on the leaderboard

A backtest number produced under a superseded policy, or from a market without opening/closing
coverage, or from a source other than the settlement authority in P07. Those rows stay blank and are
published on Flagged for Review.
"""


def write_policy() -> Path:
    POLICY.parent.mkdir(parents=True, exist_ok=True)
    if not POLICY.exists():
        POLICY.write_text(POLICY_TEXT, encoding="utf-8")
    return POLICY


def main() -> int:
    write_policy()
    snaps = write_snapshots()
    ledger = build_ledger()
    print(f"Price store: {len(snaps)} snapshot file(s) matched or written for this input; "
          f"{ledger['counts']['snapshots']} total retained. "
          f"{ledger['counts']['events']} events, {ledger['counts']['market_cells']} event x market cells.")
    print(f"  pre-kickoff opening: {ledger['counts']['with_pre_kickoff_opening']} | "
          f"post-hoc only: {ledger['counts']['post_hoc_only']} | "
          f"no observation: {ledger['counts']['no_observation_at_all']}")
    print(f"  policy sha256: {ledger['policy_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
