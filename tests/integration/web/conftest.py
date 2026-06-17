"""Fixtures for web integration tests.

The fastapi test client speaks the same wire format as a real client; tests
here build the app pointed at the bundled sample repo and exercise routers
end-to-end.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.apps.api.cache import reset_cached_index
from web.apps.api.main import create_app

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
def client(fixture_repo: Path) -> TestClient:
    reset_cached_index()
    app = create_app(repo_root=fixture_repo)
    return TestClient(app)
