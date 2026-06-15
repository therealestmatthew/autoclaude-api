"""Tests for the awesome-list extractor.

Uses httpx.MockTransport to inject a fake server response, so no network IO.
"""

from __future__ import annotations

import httpx

from scout.agent.types import (
    AwesomeListEntry,
    AwesomeListSource,
    SourceState,
)
from scout.extractors.awesome_list import AwesomeListExtractor

SAMPLE_LIST = """\
# Awesome Claude Code

A curated list of awesome things.

## Tools
- [foo-tool](https://github.com/alice/foo-tool) — a tool that foos.
- [bar-skill](https://github.com/bob/bar-skill/tree/main/skills/bar) — a sub-tree link.
- [Image badge](https://img.shields.io/badge/x-y-z) — should be skipped.
- [Anchor](#section) — relative anchor, should be skipped.
- [Gitlab thing](https://gitlab.com/example/repo) — not github, skipped.

## Discussions
- [Sponsors page](https://github.com/sponsors/anthropic) — not-useful prefix.
- [Topic page](https://github.com/topics/claude-code) — not-useful prefix.

## See also
- [baz](https://github.com/carol/baz) — described.
"""


def _mock_extractor(payload: str = SAMPLE_LIST) -> AwesomeListExtractor:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )
    return AwesomeListExtractor(client=client)


def _source() -> AwesomeListSource:
    return AwesomeListSource(
        name="awesome-lists",
        type="awesome-list",
        lists=[
            AwesomeListEntry(
                name="awesome-claude-code",
                url="https://example.invalid/awesome-claude-code/README.md",
            )
        ],
    )


def test_emits_github_repo_candidates_only():
    extractor = _mock_extractor()
    state = SourceState(source="awesome-lists")
    cands = list(extractor.fetch(_source(), state, run_id="test-run"))
    urls = [c.source_url for c in cands]
    assert "https://github.com/alice/foo-tool" in urls
    assert "https://github.com/bob/bar-skill/tree/main/skills/bar" in urls
    assert "https://github.com/carol/baz" in urls
    # Skipped:
    assert all("img.shields.io" not in u for u in urls)
    assert all("gitlab.com" not in u for u in urls)
    assert all("/sponsors/" not in u for u in urls)
    assert all("/topics/" not in u for u in urls)
    assert all(not u.startswith("#") for u in urls)
    # No accidental anchor-only entries
    assert len(cands) == 3


def test_dedups_against_seen_urls():
    extractor = _mock_extractor()
    state = SourceState(source="awesome-lists")
    # Pre-seed seen_urls with one of the URLs
    state.seen_urls["https://github.com/alice/foo-tool"] = "2026-06-13"
    cands = list(extractor.fetch(_source(), state, run_id="test-run"))
    urls = [c.source_url for c in cands]
    assert "https://github.com/alice/foo-tool" not in urls
    assert len(cands) == 2


def test_records_seen_urls_for_emitted_candidates():
    extractor = _mock_extractor()
    state = SourceState(source="awesome-lists")
    list(extractor.fetch(_source(), state, run_id="test-run"))
    # All 3 emitted URLs should now be in seen_urls
    assert len(state.seen_urls) == 3
    assert "https://github.com/alice/foo-tool" in state.seen_urls


def test_candidate_shape():
    extractor = _mock_extractor()
    state = SourceState(source="awesome-lists")
    cand = next(iter(extractor.fetch(_source(), state, run_id="test-run-42")))
    assert cand.kind == "repo"
    assert cand.source_type == "github"
    assert cand.discovered_via == "awesome-claude-code"
    assert cand.run_id == "test-run-42"
    assert cand.name  # not empty
    assert cand.title == "foo-tool"
    assert cand.raw_url == "https://example.invalid/awesome-claude-code/README.md"


def test_http_error_recorded_in_state_stats_not_raised():
    def boom(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(boom), timeout=httpx.Timeout(5.0))
    extractor = AwesomeListExtractor(client=client)
    state = SourceState(source="awesome-lists")
    cands = list(extractor.fetch(_source(), state, run_id="test-run"))
    assert cands == []
    assert "list_errors" in state.stats
    assert len(state.stats["list_errors"]) == 1


def test_no_links_yields_nothing():
    extractor = _mock_extractor(payload="# Empty list\n\nNo links here.")
    state = SourceState(source="awesome-lists")
    assert list(extractor.fetch(_source(), state, run_id="test-run")) == []


def test_title_with_bidi_override_is_sanitized():
    # U+202E RIGHT-TO-LEFT OVERRIDE hidden inside a link title — the kind of
    # payload a malicious awesome-list entry could carry to mask one URL as
    # another in agent or human reviewer context.
    poisoned = (
        "## Tools\n"
        "- [evil‮title](https://github.com/mallory/evil) — payload.\n"
    )
    extractor = _mock_extractor(payload=poisoned)
    state = SourceState(source="awesome-lists")
    cand = next(iter(extractor.fetch(_source(), state, run_id="test-run")))
    assert "‮" not in cand.title
    assert "‮" not in cand.raw_title
    # Sanity: the visible characters survive.
    assert "evil" in cand.title
