"""Tests for the DB-backed CachedIndex (8.2)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.cache import CachedIndex


@pytest.fixture
def writable_repo(fixture_repo: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(fixture_repo, dest)
    return dest


@pytest.fixture
def cache(
    writable_repo: Path,
    db_engine: Engine,
    db_factory: sessionmaker[Session],
) -> CachedIndex:
    return CachedIndex(writable_repo, engine=db_engine, session_factory=db_factory)


def test_get_empty_before_sync(cache: CachedIndex) -> None:
    """A fresh DB returns an empty snapshot. Routers can serve `[]` without
    a sync ever having run; tests then rely on `force_rebuild` to populate."""
    snap = cache.get()
    assert snap.records == []


def test_force_rebuild_populates(cache: CachedIndex) -> None:
    snap = cache.force_rebuild()
    assert len(snap.records) > 0
    again = cache.get()
    assert len(again.records) == len(snap.records)


def test_sync_picks_up_new_file(cache: CachedIndex, writable_repo: Path) -> None:
    cache.force_rebuild()
    baseline = len(cache.get().records)
    new_file = writable_repo / "catalog" / "gamma-new.md"
    new_file.write_text(
        "---\nname: gamma-new\nkind: article\ntitle: New\nstatus: reviewed\n"
        "source:\n  url: x\ndiscovered:\n  via: manual\n  on_: 2026-06-16\n"
        "created_at: 2026-06-16\nupdated_at: 2026-06-16\n---\n",
        encoding="utf-8",
    )
    result = cache.sync()
    assert result.rows_written == 1
    assert result.rows_skipped == baseline
    assert len(cache.get().records) == baseline + 1


def test_sync_drops_deleted_file(cache: CachedIndex, writable_repo: Path) -> None:
    cache.force_rebuild()
    baseline = len(cache.get().records)
    (writable_repo / "catalog" / "alpha-tool.md").unlink()
    result = cache.sync()
    assert result.rows_deleted == 1
    assert len(cache.get().records) == baseline - 1


def test_repeated_sync_is_idempotent(cache: CachedIndex) -> None:
    first = cache.sync()
    assert first.rows_written > 0
    second = cache.sync()
    assert second.rows_written == 0
    assert second.rows_deleted == 0
    assert second.rows_skipped == first.records
