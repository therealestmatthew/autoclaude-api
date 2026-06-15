"""Tests for the Lobsters extractor.

Uses httpx.MockTransport with the RSS fixture; no network IO.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from scout.agent.types import LobstersSource, MatchSpec, SourceState
from scout.extractors.lobsters import LobstersExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
LOBSTERS_RSS = (FIXTURES / "lobsters-rss.xml").read_text()


def _source() -> LobstersSource:
    return LobstersSource(
        name="lobsters",
        type="lobsters",
        feeds=["https://lobste.rs/t/ai.rss"],
        match=MatchSpec(any_of=["claude", "anthropic"]),
    )


def _client(payload: str | bytes, *, status: int = 200) -> httpx.Client:
    body_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body_bytes)

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


def test_emits_only_keyword_matches():
    extractor = LobstersExtractor(client=_client(LOBSTERS_RSS))
    state = SourceState(source="lobsters")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))

    urls = {c.source_url for c in cands}
    assert "https://github.com/alice/claude-skill-manager" in urls
    assert "https://example.com/anthropic-paper" in urls
    # No-match item is filtered out.
    assert "https://example.com/programming-post" not in urls


def test_classifies_repo_and_article():
    extractor = LobstersExtractor(client=_client(LOBSTERS_RSS))
    state = SourceState(source="lobsters")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))

    by_url = {c.source_url: c for c in cands}
    repo = by_url["https://github.com/alice/claude-skill-manager"]
    article = by_url["https://example.com/anthropic-paper"]
    assert repo.kind == "repo"
    assert repo.source_type == "github"
    assert article.kind == "article"
    assert article.source_type == "article"
    # Comments URL ends up in raw_url.
    assert repo.raw_url.startswith("https://lobste.rs/s/")


def test_cursor_advances_past_max_pubdate():
    extractor = LobstersExtractor(client=_client(LOBSTERS_RSS))
    state = SourceState(source="lobsters")
    list(extractor.fetch(_source(), state, run_id="run-1"))
    assert state.cursor.get("last_seen_pub_ts")
    cursor = state.cursor["last_seen_pub_ts"]
    # Latest matching item is 2025-06-04 13:00:00 UTC = 1749042000.
    assert cursor == 1749042000.0


def test_second_run_skips_items_at_or_before_cursor():
    # First run advances cursor; second run on the same payload yields nothing
    # new.
    extractor = LobstersExtractor(client=_client(LOBSTERS_RSS))
    state = SourceState(source="lobsters")
    list(extractor.fetch(_source(), state, run_id="run-1"))
    # Wipe seen_urls so the cursor (not URL-dedup) is what blocks the items.
    state.seen_urls.clear()
    cands = list(extractor.fetch(_source(), state, run_id="run-2"))
    assert cands == []


def test_malformed_xml_recorded_in_state_stats():
    extractor = LobstersExtractor(client=_client("<not-xml"))
    state = SourceState(source="lobsters")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    assert cands == []
    assert state.stats.get("feed_errors")


def test_zero_width_joiner_in_title_is_sanitized():
    extractor = LobstersExtractor(client=_client(LOBSTERS_RSS))
    state = SourceState(source="lobsters")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    zw = next(
        (c for c in cands if c.source_url == "https://github.com/mallory/zw-evil"),
        None,
    )
    assert zw is not None, "expected the ZWJ-laden entry to be emitted"
    # The U+200B ZERO WIDTH SPACE in the fixture title must be gone.
    assert "​" not in zw.title
    assert "claude" in zw.title
