"""Tests for the in-memory mtime-invalidating cache."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from web.apps.api.cache import CachedIndex


@pytest.fixture
def writable_repo(fixture_repo: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(fixture_repo, dest)
    return dest


def test_cold_start_builds_snapshot(writable_repo: Path) -> None:
    cache = CachedIndex(writable_repo)
    snap1 = cache.get()
    assert len(snap1.records) > 0


def test_hit_returns_same_object(writable_repo: Path) -> None:
    cache = CachedIndex(writable_repo)
    snap1 = cache.get()
    snap2 = cache.get()
    assert snap1 is snap2  # cached object identity proves no rebuild


def test_mtime_invalidates(writable_repo: Path) -> None:
    cache = CachedIndex(writable_repo)
    snap1 = cache.get()
    initial_count = len(snap1.records)
    # Bump catalog dir mtime by adding a new file.
    time.sleep(0.01)
    new_file = writable_repo / "catalog" / "gamma-new.md"
    new_file.write_text(
        "---\nname: gamma-new\nkind: article\ntitle: New\nstatus: reviewed\n"
        "source:\n  url: x\ndiscovered:\n  via: manual\n  on: 2026-06-16\n"
        "created_at: 2026-06-16\nupdated_at: 2026-06-16\n---\n",
        encoding="utf-8",
    )
    # Force the directory's mtime to update on filesystems that batch updates.
    os.utime(writable_repo / "catalog", None)
    snap2 = cache.get()
    assert snap2 is not snap1
    assert len(snap2.records) == initial_count + 1


def test_force_rebuild(writable_repo: Path) -> None:
    cache = CachedIndex(writable_repo)
    snap1 = cache.get()
    snap2 = cache.force_rebuild()
    assert snap2 is not snap1
    assert len(snap2.records) == len(snap1.records)
