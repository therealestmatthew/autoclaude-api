"""End-to-end check: `scout run` writes liveness state, dedup pass 4 fires.

The runner's tail step HEADs catalog URLs and persists the streak counts.
On the same tick, the dedup engine's pass 4 reads that state and archives
anything whose 404 streak qualifies (≥3 consecutive 404s, first ≥30 days
old). This pins the contract that "liveness runs BEFORE dedup" so the two
share data within one tick.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import httpx
import pytest

from scout.agent import runner
from scout.liveness import check as liveness_check

FIXTURE_404 = Path(__file__).parent.parent / "fixtures" / "dedup" / "404-streak"
TODAY = date(2026, 6, 15)


def _seed_404_catalog(scout_world) -> None:
    shutil.copy(
        FIXTURE_404 / "catalog-dead.md",
        scout_world["catalog"] / "dead-link-asset.md",
    )
    # Seed liveness state with 2 prior 404s, first 31 days before today.
    state = {
        "checks": {
            "https://example.com/dead-link": {
                "404_count": 2,
                "first_404": "2026-05-14",
                "last_check": "2026-06-13",
                "last_status": 404,
                "last_error": None,
            }
        }
    }
    (scout_world["state"] / "url-liveness.json").write_text(json.dumps(state))


def test_run_once_with_liveness_populates_state_and_archives(
    scout_world, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_404_catalog(scout_world)
    monkeypatch.setattr(runner, "EXTRACTOR_REGISTRY", {}, raising=True)
    monkeypatch.setattr(
        "scout.dedup.engine.date",
        type("_D", (), {"today": staticmethod(lambda: TODAY)}),
    )

    # Stub the liveness HTTP client so the runner does no real network.
    def fake_check_urls_once(catalog_dir, state_path, **kwargs):
        return liveness_check.check_urls_once(
            catalog_dir, state_path,
            client=_404_client(),
            today=TODAY,
            **{k: v for k, v in kwargs.items() if k not in ("client", "today")},
        )

    monkeypatch.setattr(runner, "check_urls_once", fake_check_urls_once)

    stats = runner.run_once()

    # Liveness ran and bumped the streak to 3.
    state = json.loads((scout_world["state"] / "url-liveness.json").read_text())
    entry = state["checks"]["https://example.com/dead-link"]
    assert entry["404_count"] == 3
    assert entry["last_check"] == TODAY.isoformat()

    # Dedup pass 4 saw the streak and archived the asset.
    assert stats["dedup"]["pass4_auto_archived"] == 1
    archived = (scout_world["catalog"] / "dead-link-asset.md").read_text()
    assert "status: archived" in archived
    assert "archived_reason" in archived


def test_no_check_urls_skips_liveness(
    scout_world, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `run_liveness=False`, the runner does not touch the state file
    (idempotency contract for `scout run --no-check-urls`)."""
    _seed_404_catalog(scout_world)
    before = (scout_world["state"] / "url-liveness.json").read_bytes()
    monkeypatch.setattr(runner, "EXTRACTOR_REGISTRY", {}, raising=True)

    runner.run_once(run_liveness=False, run_dedup=False)

    after = (scout_world["state"] / "url-liveness.json").read_bytes()
    assert before == after


def _404_client() -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404)
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )
