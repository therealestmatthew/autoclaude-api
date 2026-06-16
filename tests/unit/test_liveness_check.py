"""URL-liveness rules.

Pins the streak math the dedup engine's pass 4 relies on. If these flake,
catalog rot won't be detected (or, worse, healthy URLs will be archived).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from scout.liveness.check import check_urls_once

CATALOG_TEMPLATE = """---
name: {name}
kind: repo
title: "{name}"
status: reviewed
source:
  type: github
  url: {url}
  authors: []
  license: ""
discovered:
  via: manual
  on: 2026-06-01
created_at: 2026-06-01
updated_at: 2026-06-01
---
body
"""


def _seed_catalog(catalog_dir: Path, urls: dict[str, str]) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    for name, url in urls.items():
        (catalog_dir / f"{name}.md").write_text(
            CATALOG_TEMPLATE.format(name=name, url=url)
        )


def _client_for(status_for_url: Callable[[str], int]) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status_for_url(str(req.url)))
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


class TestStreakRules:
    def test_404_starts_streak(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        client = _client_for(lambda _: 404)
        today = date(2026, 6, 15)
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=client, today=today, max_urls=None,
        )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 1
        assert entry["first_404"] == "2026-06-15"
        assert entry["last_status"] == 404

    def test_consecutive_404s_increment(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        for day in (date(2026, 6, 13), date(2026, 6, 14), date(2026, 6, 15)):
            check_urls_once(
                tmp_path / "catalog", state_path,
                client=_client_for(lambda _: 404), today=day, max_urls=None,
            )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 3
        assert entry["first_404"] == "2026-06-13"  # didn't move
        assert entry["last_check"] == "2026-06-15"

    def test_200_resets_streak(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        for day in (date(2026, 6, 13), date(2026, 6, 14)):
            check_urls_once(
                tmp_path / "catalog", state_path,
                client=_client_for(lambda _: 404), today=day, max_urls=None,
            )
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 200),
            today=date(2026, 6, 15), max_urls=None,
        )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 0
        assert entry["first_404"] is None
        assert entry["last_status"] == 200

    def test_5xx_does_not_move_streak(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        # Start with 2 confirmed 404s.
        for day in (date(2026, 6, 13), date(2026, 6, 14)):
            check_urls_once(
                tmp_path / "catalog", state_path,
                client=_client_for(lambda _: 404), today=day, max_urls=None,
            )
        # Then a 503 — must not increment, must not reset.
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 503),
            today=date(2026, 6, 15), max_urls=None,
        )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 2
        assert entry["first_404"] == "2026-06-13"
        assert entry["last_status"] == 503

    def test_network_error_records_last_error_but_does_not_move_streak(
        self, tmp_path: Path,
    ) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 404),
            today=date(2026, 6, 13), max_urls=None,
        )

        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("dns fail")

        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(5.0),
        )
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=client, today=date(2026, 6, 15), max_urls=None,
        )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 1
        assert entry["first_404"] == "2026-06-13"
        assert "dns fail" in entry["last_error"]


class TestIdempotency:
    def test_second_run_same_day_same_status_does_not_move_streak(
        self, tmp_path: Path,
    ) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 404),
            today=date(2026, 6, 14), max_urls=None,
        )
        # Same status, same day — idempotency contract: counters MUST NOT move.
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 404),
            today=date(2026, 6, 14), max_urls=None,
        )
        entry = json.loads(state_path.read_text())["checks"]["https://example.com/a"]
        assert entry["404_count"] == 1
        assert entry["first_404"] == "2026-06-14"
        assert entry["last_check"] == "2026-06-14"

    def test_state_file_is_deterministic(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {
            "a": "https://example.com/a",
            "b": "https://example.com/b",
        })
        state_path_1 = tmp_path / "live1.json"
        state_path_2 = tmp_path / "live2.json"
        for sp in (state_path_1, state_path_2):
            check_urls_once(
                tmp_path / "catalog", sp,
                client=_client_for(lambda _: 200),
                today=date(2026, 6, 15), max_urls=None,
            )
        assert state_path_1.read_bytes() == state_path_2.read_bytes()


class TestThrottle:
    def test_since_skips_recent(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 200),
            today=date(2026, 6, 14), max_urls=None,
        )
        stats = check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 200),
            today=date(2026, 6, 15),
            since=date(2026, 6, 14),  # skip URLs last_checked >= 2026-06-14
            max_urls=None,
        )
        assert stats["skipped_throttle"] == 1
        assert stats["checked"] == 0

    def test_max_urls_caps_per_run(self, tmp_path: Path) -> None:
        urls = {f"u{i}": f"https://example.com/{i}" for i in range(10)}
        _seed_catalog(tmp_path / "catalog", urls)
        state_path = tmp_path / "url-liveness.json"
        stats = check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 200),
            today=date(2026, 6, 15), max_urls=3,
        )
        assert stats["checked"] == 3


class TestUnsafeURL:
    def test_loopback_url_recorded_as_unsafe_not_attempted(
        self, tmp_path: Path,
    ) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "http://127.0.0.1/x"})
        state_path = tmp_path / "url-liveness.json"

        def handler(req: httpx.Request) -> httpx.Response:
            pytest.fail("unsafe URL must not reach transport")
            raise AssertionError

        client = httpx.Client(transport=httpx.MockTransport(handler))
        stats = check_urls_once(
            tmp_path / "catalog", state_path,
            client=client, today=date(2026, 6, 15), max_urls=None,
        )
        assert stats["unsafe"] == 1
        entry = json.loads(state_path.read_text())["checks"]["http://127.0.0.1/x"]
        assert "unsafe-url" in entry["last_error"]


class TestCorruptState:
    def test_corrupt_state_backs_up_and_starts_fresh(self, tmp_path: Path) -> None:
        _seed_catalog(tmp_path / "catalog", {"a": "https://example.com/a"})
        state_path = tmp_path / "url-liveness.json"
        state_path.write_text("not json {")
        check_urls_once(
            tmp_path / "catalog", state_path,
            client=_client_for(lambda _: 200),
            today=date(2026, 6, 15), max_urls=None,
        )
        # Backup file is created next to the original.
        backups = list(tmp_path.glob("url-liveness.json.broken-*"))
        assert len(backups) == 1
        # New state file is valid JSON.
        json.loads(state_path.read_text())
