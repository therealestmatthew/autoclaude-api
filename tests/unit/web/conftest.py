"""Shared fixtures for web app unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_REPO = Path(__file__).resolve().parents[2] / "fixtures" / "web" / "sample_repo"


@pytest.fixture
def fixture_repo() -> Path:
    """Path to the in-tree sample repo used by web indexer + API tests."""
    return FIXTURE_REPO
