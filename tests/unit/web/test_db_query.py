"""Tests for ORM -> AssetRecord materialisation."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.db import load_snapshot, sync
from web.apps.api.indexer import Indexer


@pytest.fixture
def repo(fixture_repo: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(fixture_repo, dest)
    return dest


def test_load_snapshot_matches_indexer(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    snapshot_direct = Indexer(repo).scan()
    sync(Indexer(repo), db_factory)
    snapshot_from_db = load_snapshot(db_factory, repo.as_posix())

    assert len(snapshot_from_db.records) == len(snapshot_direct.records)

    direct_by_path = {r.path: r for r in snapshot_direct.records}
    for db_rec in snapshot_from_db.records:
        original = direct_by_path[db_rec.path]
        assert db_rec.bucket == original.bucket
        assert db_rec.slug == original.slug
        assert db_rec.kind == original.kind
        assert db_rec.title == original.title
        assert db_rec.status == original.status
        assert db_rec.body == original.body


def test_snapshot_carries_meta_ceiling(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    sync(Indexer(repo), db_factory)
    snapshot = load_snapshot(db_factory, repo.as_posix())
    assert snapshot.scan_mtime_ceiling > 0
    assert snapshot.repo_root == repo.as_posix()
