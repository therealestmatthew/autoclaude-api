"""Pins the idempotency invariant called out in the milestone plan.

Running `sync` twice in a row on an unchanged repo writes zero data rows
on the second invocation. This is the property that makes the polling
reconciler safe to fire every 60 seconds without wear on the storage.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.db import sync
from web.apps.api.db.models import Base
from web.apps.api.db.session import make_engine, make_session_factory
from web.apps.api.indexer import Indexer

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "web" / "sample_repo"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    dsn = f"sqlite:///{(tmp_path / 'index.sqlite').as_posix()}"
    eng = make_engine(dsn)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


def test_idempotent_sync(repo: Path, factory: sessionmaker[Session]) -> None:
    first = sync(Indexer(repo), factory)
    second = sync(Indexer(repo), factory)

    assert first.rows_written > 0
    assert second.rows_written == 0
    assert second.rows_deleted == 0
    assert second.rows_skipped == first.records


def test_idempotent_after_touch(repo: Path, factory: sessionmaker[Session]) -> None:
    """`touch`-only updates change mtime but not content. The sync engine must
    NOT write rows in that case."""
    sync(Indexer(repo), factory)
    (repo / "catalog" / "alpha-tool.md").touch()
    result = sync(Indexer(repo), factory)
    assert result.rows_written == 0
