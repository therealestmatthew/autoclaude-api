"""Fixtures for web integration tests.

The fastapi test client speaks the same wire format as a real client; tests
here build the app pointed at the bundled sample repo and exercise routers
end-to-end. 8.2: the app's index is DB-backed, so each test gets a fresh
per-test SQLite under `tmp_path`, the schema is created from the ORM
metadata (Alembic correctness has its own test), and an initial sync is
driven before the TestClient is handed back.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from web.apps.api.cache import CachedIndex, reset_cached_index
from web.apps.api.db.models import Base
from web.apps.api.db.session import make_engine, make_session_factory
from web.apps.api.main import create_app
from web.apps.api.routers.deps import get_index
from web.apps.api.settings import Settings, reset_settings

FIXTURE_REPO_SRC = (
    Path(__file__).resolve().parents[2] / "fixtures" / "web" / "sample_repo"
)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """A writable copy of the fixture repo per test, so mtime-based cache
    invalidation tests can mutate without affecting siblings."""
    dest = tmp_path / "sample_repo"
    shutil.copytree(FIXTURE_REPO_SRC, dest)
    return dest


@pytest.fixture
def db_engine(tmp_path: Path) -> Engine:
    """Per-test SQLite with the schema applied via the ORM metadata."""
    dsn = f"sqlite:///{(tmp_path / 'index.sqlite').as_posix()}"
    engine = make_engine(dsn)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(fixture_repo: Path, db_engine: Engine) -> TestClient:
    reset_cached_index()
    reset_settings()
    # Skip auto-migrate (already done via create_all) and the reconciler loop
    # (tests drive sync explicitly via /sync or the cache fixture).
    settings = Settings(
        repo_root=fixture_repo,
        host="127.0.0.1",
        port=0,
        cors_origins=(),
        log_level="warning",
        index_dsn=None,
        reconcile_interval=0.0,
        auto_migrate=False,
    )
    app = create_app(repo_root=fixture_repo, settings=settings)

    # Replace the dependency with an index bound to the per-test engine.
    factory = make_session_factory(db_engine)
    cache = CachedIndex(fixture_repo, engine=db_engine, session_factory=factory)
    cache.force_rebuild()  # initial sync so routers have data to return.
    app.dependency_overrides[get_index] = lambda: cache

    with TestClient(app) as tc:
        yield tc


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    )
    return out.stdout


@pytest.fixture
def git_fixture_repo(fixture_repo: Path) -> Path:
    """A fixture_repo with `git init` + an initial commit so write-back
    tests have a clean tree to commit on top of."""
    _git(fixture_repo, "init", "-q", "-b", "main")
    _git(fixture_repo, "config", "user.email", "test@example.com")
    _git(fixture_repo, "config", "user.name", "Test")
    _git(fixture_repo, "config", "commit.gpgsign", "false")
    _git(fixture_repo, "add", "-A")
    _git(fixture_repo, "commit", "-q", "-m", "initial")
    return fixture_repo


@pytest.fixture
def git_client(git_fixture_repo: Path, db_engine: Engine) -> TestClient:
    """Same shape as `client`, but the underlying repo is a real git repo
    so write-back endpoints actually exercise the commit pipeline."""
    reset_cached_index()
    reset_settings()
    settings = Settings(
        repo_root=git_fixture_repo,
        host="127.0.0.1",
        port=0,
        cors_origins=(),
        log_level="warning",
        index_dsn=None,
        reconcile_interval=0.0,
        auto_migrate=False,
    )
    app = create_app(repo_root=git_fixture_repo, settings=settings)
    factory = make_session_factory(db_engine)
    cache = CachedIndex(
        git_fixture_repo, engine=db_engine, session_factory=factory
    )
    cache.force_rebuild()
    app.dependency_overrides[get_index] = lambda: cache
    with TestClient(app) as tc:
        yield tc
