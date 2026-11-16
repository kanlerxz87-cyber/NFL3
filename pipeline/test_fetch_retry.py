#!/usr/bin/env python3
"""Offline regression tests for the transient-failure retry in fetch_official.py.

The scheduled data-refresh failed on 2026-11-16 (run 43900887096) when release-asset
downloads were dropped mid-TLS; the fetch had no retry and the whole step went red on
a failure a second attempt would have cleared. These tests pin the retry contract
without touching the network:

  - a transient TLS EOF is retried and the download then succeeds
  - a persistent transient failure raises after the fixed number of attempts
  - HTTP 404 is not retried (deterministic: the asset is gone)
  - a SHA-256 integrity mismatch is fatal and is never retried
  - a size mismatch is fatal and is never retried
  - the release-API lookup is retried on transient failures too
  - no half-written .part file survives a failed download
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_official  # noqa: E402

DATA = b"nfl3 verified asset bytes\n" * 128
DATA_SHA = "sha256:" + hashlib.sha256(DATA).hexdigest()
ASSET_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv"
API_URL = "https://api.github.com/repos/nflverse/nflverse-data/releases/tags/injuries"


class FakeResponse:
    """Minimal context-manager response: yields its chunks then EOF."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    def read(self, size: int = -1) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def tls_eof() -> urllib.error.URLError:
    # the exact failure observed in CI run 43900887096
    return urllib.error.URLError(OSError("TLS/SSL connection has been closed (EOF)"))


class ScriptedURLOpen:
    """Replaces urllib.request.urlopen with a scripted sequence.

    A list member means "this failure repeats forever from now on" (used for the
    persistent-failure case), so it never runs out of items.
    """

    def __init__(self, script):
        self.script = list(script)          # items: exception instance or FakeResponse
        self.repeat: BaseException | None = None
        self.calls: list[str] = []

    def __call__(self, req, timeout=None, **kwargs):
        url = req.full_url
        self.calls.append(url)
        if self.repeat is not None:
            raise self.repeat
        item = self.script.pop(0) if self.script else None
        if item is None:
            raise AssertionError(f"unexpected extra urlopen call: {url}")
        if isinstance(item, list):
            self.repeat = item[-1]
            raise self.repeat
        if isinstance(item, BaseException):
            raise item
        return item


def run_case(name: str, fn, results: list) -> None:
    try:
        fn()
        print(f"OK  {name}")
    except AssertionError as exc:
        results.append(name)
        print(f"FAIL {name}: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported as a test failure, not a crash
        results.append(name)
        print(f"FAIL {name}: unexpected {type(exc).__name__}: {exc}")


def main() -> int:
    results: list[str] = []
    saved_backoff, saved_urlopen = fetch_official.RETRY_BACKOFF_SECONDS, urllib.request.urlopen
    fetch_official.RETRY_BACKOFF_SECONDS = (0, 0, 0)

    def with_urlopen(script):
        fake = ScriptedURLOpen(script)
        urllib.request.urlopen = fake
        return fake

    try:
        def case_transient_then_success():
            with tempfile.TemporaryDirectory() as tmpdir:
                fake = with_urlopen([tls_eof(), tls_eof(), FakeResponse([DATA])])
                dest = str(Path(tmpdir) / "injuries_2026.csv")
                rec = fetch_official.download(dest=dest, url=ASSET_URL, expected_sha=DATA_SHA,
                                              expected_size=len(DATA))
                assert rec["verified"] is True and rec["bytes"] == len(DATA), rec
                assert Path(dest).read_bytes() == DATA, "stored bytes differ from the payload"
                assert len(fake.calls) == 3, f"expected 3 attempts (2 retries), saw {len(fake.calls)}"
                assert not Path(dest + ".part").exists(), "a .part file survived a successful download"

        def case_persistent_transient_gives_up():
            with tempfile.TemporaryDirectory() as tmpdir:
                fake = with_urlopen([[tls_eof()]])
                dest = str(Path(tmpdir) / "injuries_2026.csv")
                try:
                    fetch_official.download(dest=dest, url=ASSET_URL, expected_sha=DATA_SHA,
                                            expected_size=len(DATA))
                    raise AssertionError("persistent TLS EOF must raise, not return")
                except urllib.error.URLError:
                    pass
                assert len(fake.calls) == fetch_official.RETRY_ATTEMPTS, \
                    f"expected {fetch_official.RETRY_ATTEMPTS} attempts, saw {len(fake.calls)}"
                assert not Path(dest + ".part").exists(), "a .part file survived a failed download"

        def case_404_not_retried():
            with tempfile.TemporaryDirectory() as tmpdir:
                not_found = urllib.error.HTTPError(ASSET_URL, 404, "Not Found", None, None)
                fake = with_urlopen([not_found])
                try:
                    fetch_official.download(dest=str(Path(tmpdir) / "x.csv"), url=ASSET_URL,
                                            expected_sha=DATA_SHA, expected_size=len(DATA))
                    raise AssertionError("404 must raise, not return")
                except urllib.error.HTTPError as exc:
                    assert exc.code == 404
                assert len(fake.calls) == 1, f"404 must not be retried, saw {len(fake.calls)} calls"

        def case_integrity_never_retried():
            with tempfile.TemporaryDirectory() as tmpdir:
                fake = with_urlopen([FakeResponse([DATA])])
                wrong = "sha256:" + "0" * 64
                try:
                    fetch_official.download(dest=str(Path(tmpdir) / "x.csv"), url=ASSET_URL,
                                            expected_sha=wrong, expected_size=len(DATA))
                    raise AssertionError("digest mismatch must raise SystemExit")
                except SystemExit:
                    pass
                assert len(fake.calls) == 1, "an integrity failure must never be retried"

        def case_size_never_retried():
            with tempfile.TemporaryDirectory() as tmpdir:
                fake = with_urlopen([FakeResponse([DATA])])
                try:
                    fetch_official.download(dest=str(Path(tmpdir) / "x.csv"), url=ASSET_URL,
                                            expected_sha=DATA_SHA, expected_size=len(DATA) + 1)
                    raise AssertionError("size mismatch must raise SystemExit")
                except SystemExit:
                    pass
                assert len(fake.calls) == 1, "a size failure must never be retried"

        def case_api_lookup_retried():
            payload = json.dumps({"tag_name": "injuries", "assets": [{"name": "injuries_2026.csv"}]}).encode()
            fake = with_urlopen([tls_eof(), FakeResponse([payload])])
            data = fetch_official.api_json(API_URL)
            assert data["tag_name"] == "injuries", data
            assert len(fake.calls) == 2, f"expected 1 retry on the API lookup, saw {len(fake.calls)}"

        def case_release_assets_mapping():
            payload = json.dumps({"assets": [{"name": "a.csv"}, {"name": "b.csv"}]}).encode()
            with_urlopen([FakeResponse([payload])])
            assets = fetch_official.release_assets("injuries")
            assert set(assets) == {"a.csv", "b.csv"}, assets

        def case_classification():
            assert fetch_official._is_retryable(tls_eof()) is True
            assert fetch_official._is_retryable(urllib.error.HTTPError(ASSET_URL, 404, "Not Found", None, None)) is False
            assert fetch_official._is_retryable(urllib.error.HTTPError(ASSET_URL, 429, "Too Many Requests", None, None)) is True
            assert fetch_official._is_retryable(urllib.error.HTTPError(ASSET_URL, 503, "Service Unavailable", None, None)) is True
            assert fetch_official._is_retryable(TimeoutError("timed out")) is True
            assert fetch_official._is_retryable(ValueError("nope")) is False

        for name, fn in [
            ("transient TLS EOF retried then download succeeds", case_transient_then_success),
            ("persistent transient failure gives up after RETRY_ATTEMPTS", case_persistent_transient_gives_up),
            ("HTTP 404 raises through without retry", case_404_not_retried),
            ("digest mismatch is fatal and never retried", case_integrity_never_retried),
            ("size mismatch is fatal and never retried", case_size_never_retried),
            ("release-API lookup retried on transient failure", case_api_lookup_retried),
            ("release_assets maps assets by name", case_release_assets_mapping),
            ("retryable classification is exact", case_classification),
        ]:
            run_case(name, fn, results)
    finally:
        fetch_official.RETRY_BACKOFF_SECONDS = saved_backoff
        urllib.request.urlopen = saved_urlopen

    if results:
        print(f"RESULT: FAILED - {len(results)} case(s): {', '.join(results)}")
        return 1
    print("RESULT: OK - fetch retry contract holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
