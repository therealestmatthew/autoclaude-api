"""Fixtures and configuration for integration tests.

What makes a test "integration" here:
  - It exercises multiple modules together (typically the runner + an extractor).
  - It hits the real filesystem (under tmp_path).
  - It does NOT hit the network — we still mock HTTP.

The `integration` pytest marker is auto-applied to every test collected from
this directory (so `pytest -m "not integration"` can skip them, and the marker
is searchable in `--collect-only -q`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest

from scout.agent import runner


class ScoutWorld(TypedDict):
    catalog: Path
    queue: Path
    state: Path
    threads: Path
    sources: Path


@pytest.fixture
def scout_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScoutWorld:
    """Isolated on-disk world for the runner.

    Creates fresh catalog/queue/state/threads/sources dirs under tmp_path and
    monkeypatches the runner module constants to point at them. Tests can
    populate the dirs (e.g. write a source YAML, a catalog asset) and then call
    `runner.run_once()` knowing nothing touches the real repo.
    """
    world: ScoutWorld = {
        "catalog": tmp_path / "catalog",
        "queue": tmp_path / "queue",
        "state": tmp_path / "state",
        "threads": tmp_path / "threads",
        "sources": tmp_path / "sources",
    }
    for p in world.values():
        p.mkdir()

    monkeypatch.setattr(runner, "CATALOG_DIR", world["catalog"])
    monkeypatch.setattr(runner, "QUEUE_DIR", world["queue"])
    monkeypatch.setattr(runner, "STATE_DIR", world["state"])
    monkeypatch.setattr(runner, "THREADS_DIR", world["threads"])
    monkeypatch.setattr(runner, "SOURCES_DIR", world["sources"])

    return world


_INTEGRATION_DIR = Path(__file__).parent


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-apply the `integration` marker to anything collected from this dir."""
    marker = pytest.mark.integration
    for item in items:
        item_path = Path(str(item.fspath))
        if _INTEGRATION_DIR in item_path.parents:
            item.add_marker(marker)
