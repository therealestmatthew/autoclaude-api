"""Shared fixtures for web app unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.db.models import Base
from web.apps.api.db.session import make_engine, make_session_factory

FIXTURE_REPO = Path(__file__).resolve().parents[2] / "fixtures" / "web" / "sample_repo"


@pytest.fixture
def fixture_repo() -> Path:
    """Path to the in-tree sample repo used by web indexer + API tests."""
    return FIXTURE_REPO


@pytest.fixture
def db_engine(tmp_path: Path) -> Engine:
    """Per-test SQLite engine with the schema in place.

    Uses `Base.metadata.create_all` rather than running Alembic, because:
    - It's faster.
    - Alembic correctness has its own dedicated integration test.
    - Unit tests should isolate their concern (the sync engine, the query
      layer, the CLI) from the migration runner.
    """
    dsn = f"sqlite:///{(tmp_path / 'index.sqlite').as_posix()}"
    engine = make_engine(dsn)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_factory(db_engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(db_engine)
