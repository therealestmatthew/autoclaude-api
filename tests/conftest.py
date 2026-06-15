"""Shared fixtures across the suite (unit + integration).

Per-scope fixtures live in tests/<scope>/conftest.py. Keep this file for things
both scopes use.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from scout.agent.types import Candidate, SourceState


@pytest.fixture
def sample_candidate() -> Candidate:
    """A minimal, valid Candidate. Override fields per test as needed."""
    return Candidate(
        name="example-tool",
        kind="repo",
        title="Example tool",
        source_type="github",
        source_url="https://github.com/alice/example-tool",
        discovered_via="awesome-claude-code",
        discovered_on="2026-06-14",
        run_id="scout-test-run",
    )


@pytest.fixture
def empty_source_state() -> SourceState:
    """A fresh, empty SourceState for the synthetic source name `test-source`."""
    return SourceState(source="test-source")


@pytest.fixture
def make_mock_httpx_client() -> Callable[..., httpx.Client]:
    """Factory: returns a function that builds an httpx.Client whose every
    request returns a fixed response.

    Usage:
        def test_x(make_mock_httpx_client):
            client = make_mock_httpx_client(text="hello", status=200)
            ...
    """
    def _factory(text: str = "", status: int = 200) -> httpx.Client:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(status, text=text)
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=httpx.Timeout(5.0),
            follow_redirects=True,
        )
    return _factory
