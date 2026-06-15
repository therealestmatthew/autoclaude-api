"""Tests for the HackerNews extractor.

Uses httpx.MockTransport to inject Algolia-shaped responses; no network IO.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from scout.agent.types import HackerNewsSource, MatchSpec, SourceState
from scout.extractors.hackernews import HackerNewsExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HN_RESULTS = json.loads((FIXTURES / "hn-search-results.json").read_text())


def _source(
    *,
    any_of: list[str] | None = None,
    min_points: int | None = 10,
) -> HackerNewsSource:
    return HackerNewsSource(
        name="hackernews",
        type="hackernews",
        match=MatchSpec(any_of=any_of or ["claude"], min_points=min_points),
    )


def _client(
    payload: dict,
    *,
    captured: list[httpx.Request] | None = None,
) -> httpx.Client:
    """Mock client that returns `payload` JSON for every GET."""

    def handler(req: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(req)
        return httpx.Response(200, json=payload)

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Happy path & classification
# ---------------------------------------------------------------------------

def test_emits_repo_and_article_candidates():
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))

    by_kind = {c.kind for c in cands}
    assert "repo" in by_kind
    assert "article" in by_kind

    repo = next(c for c in cands if c.source_url == "https://github.com/alice/foo")
    assert repo.kind == "repo"
    assert repo.source_type == "github"
    assert repo.source_authors == ["alice"]
    assert repo.score == 42
    assert repo.raw_url == "https://news.ycombinator.com/item?id=39000001"

    article = next(c for c in cands if c.source_url == "https://example.com/post")
    assert article.kind == "article"
    assert article.source_type == "article"


def test_min_points_filter_rejects_low_score():
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    cands = list(extractor.fetch(_source(min_points=10), state, run_id="run-1"))
    # The "tiny utility" hit at 2 points should not pass.
    assert all(c.source_url != "https://example.com/tiny" for c in cands)


def test_ask_hn_with_no_url_is_skipped():
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    # Ask-HN has objectID 39000002 and no URL — should not appear.
    assert all("39000002" not in (c.raw_url or "") for c in cands)


# ---------------------------------------------------------------------------
# Dedup & cursor
# ---------------------------------------------------------------------------

def test_dedup_by_object_id_within_run():
    # Two query terms returning the same fixture → still emits each hit once.
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    cands = list(
        extractor.fetch(
            _source(any_of=["claude", "anthropic"], min_points=10),
            state,
            run_id="run-1",
        )
    )
    urls = [c.source_url for c in cands]
    assert len(urls) == len(set(urls))


def test_cursor_advances_to_max_created_at_i():
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    list(extractor.fetch(_source(min_points=10), state, run_id="run-1"))
    # The max created_at_i across all hits in the fixture (including those
    # filtered by score) is 1717000400.
    assert state.cursor["last_seen_created_at_i"] == 1717000400


def test_second_run_passes_numeric_filter_param():
    captured: list[httpx.Request] = []
    extractor = HackerNewsExtractor(
        client=_client(HN_RESULTS, captured=captured)
    )
    state = SourceState(source="hackernews")
    state.cursor["last_seen_created_at_i"] = 1717000000
    list(extractor.fetch(_source(min_points=10), state, run_id="run-2"))
    assert captured, "expected at least one request"
    assert any(
        req.url.params.get("numericFilters") == "created_at_i>1717000000"
        for req in captured
    )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def test_bidi_override_in_title_is_sanitized():
    extractor = HackerNewsExtractor(client=_client(HN_RESULTS))
    state = SourceState(source="hackernews")
    cands = list(extractor.fetch(_source(min_points=10), state, run_id="run-1"))
    evil = next(
        (c for c in cands if c.source_url == "https://github.com/mallory/evil"),
        None,
    )
    assert evil is not None
    assert "‮" not in evil.title
    assert "evil" in evil.title
