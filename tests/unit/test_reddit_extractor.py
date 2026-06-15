"""Tests for the Reddit extractor.

Uses httpx.MockTransport to inject /new.json-shaped responses; no network IO.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from scout.agent.types import MatchSpec, RedditSource, SourceState
from scout.extractors.reddit import RedditExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
REDDIT_NEW = json.loads((FIXTURES / "reddit-new.json").read_text())


def _source(*, subs: list[str] | None = None) -> RedditSource:
    return RedditSource(
        name="reddit",
        type="reddit",
        subreddits=subs or ["ClaudeCode"],
        match=MatchSpec(any_of=["claude", "anthropic"]),
    )


def _client(payload: dict) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


def _redirect_client(target: str) -> httpx.Client:
    """First request gets a 301 to `target`; subsequent requests would 200 but
    shouldn't be reached if safe_get_bytes does its job."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "www.reddit.com":
            return httpx.Response(301, headers={"location": target})
        return httpx.Response(200, json={"data": {"children": []}})

    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Happy path & filtering
# ---------------------------------------------------------------------------

def test_emits_repo_and_article_skips_self_and_redd_it():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))

    urls = {c.source_url for c in cands}
    assert "https://github.com/alice/claude-refactor-skill" in urls
    assert "https://www.anthropic.com/research/agents" in urls
    # is_self → skipped
    assert all("/r/ClaudeCode/comments/abc002" not in u for u in urls)
    # i.redd.it → skipped
    assert all("i.redd.it" not in u for u in urls)


def test_discovered_via_includes_sub_lowercased():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    cands = list(
        extractor.fetch(_source(subs=["ClaudeCode"]), state, run_id="run-1")
    )
    assert cands
    assert all(c.discovered_via == "reddit-claudecode" for c in cands)


def test_classifies_kind_correctly():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    by_url = {c.source_url: c for c in cands}
    assert by_url["https://github.com/alice/claude-refactor-skill"].kind == "repo"
    assert by_url["https://www.anthropic.com/research/agents"].kind == "article"


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------

def test_per_sub_cursor_advances():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    list(extractor.fetch(_source(subs=["ClaudeCode"]), state, run_id="run-1"))
    per_sub = state.cursor["per_sub"]
    assert per_sub["ClaudeCode"] == 1717000400.0


def test_per_sub_cursor_blocks_already_seen_on_second_run():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    list(extractor.fetch(_source(subs=["ClaudeCode"]), state, run_id="run-1"))
    # Wipe seen_urls so the cursor is the only thing blocking.
    state.seen_urls.clear()
    cands = list(
        extractor.fetch(_source(subs=["ClaudeCode"]), state, run_id="run-2")
    )
    assert cands == []


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def test_zwsp_in_title_is_sanitized():
    extractor = RedditExtractor(client=_client(REDDIT_NEW))
    state = SourceState(source="reddit")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    zw = next(
        (c for c in cands if c.source_url == "https://github.com/mallory/zw-claude"),
        None,
    )
    assert zw is not None
    assert "​" not in zw.title


def test_redirect_to_private_ip_is_recorded_not_raised():
    extractor = RedditExtractor(
        client=_redirect_client("http://10.0.0.1/leak")
    )
    state = SourceState(source="reddit")
    cands = list(extractor.fetch(_source(), state, run_id="run-1"))
    assert cands == []
    errors = state.stats.get("sub_errors") or []
    assert errors, "expected the SSRF rejection to be recorded"
    assert any("10.0.0.1" in (e.get("error") or "") for e in errors)
