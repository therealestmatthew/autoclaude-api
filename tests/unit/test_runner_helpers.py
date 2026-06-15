"""Tests for the runner's pure helpers: queue filename, candidate→markdown."""

from __future__ import annotations

from scout.agent.runner import _candidate_to_markdown, _queue_filename
from scout.agent.types import Candidate


def _sample_candidate(**overrides) -> Candidate:
    base = dict(
        name="example-tool",
        kind="repo",
        title="Example tool",
        source_type="github",
        source_url="https://github.com/alice/example",
        discovered_via="awesome-claude-code",
        discovered_on="2026-06-14",
        run_id="scout-2026-06-14-120000",
        raw_title="Example tool",
        raw_url="https://example.invalid/awesome.md",
    )
    base.update(overrides)
    return Candidate(**base)


def test_queue_filename_shape():
    c = _sample_candidate()
    fname = _queue_filename(c)
    # Format: <date>-<slug>-<hash>.md
    assert fname.startswith("2026-06-14-example-tool-")
    assert fname.endswith(".md")
    # 8-char hex hash
    suffix = fname.removeprefix("2026-06-14-example-tool-").removesuffix(".md")
    assert len(suffix) == 8
    assert all(ch in "0123456789abcdef" for ch in suffix)


def test_queue_filename_is_deterministic_for_same_url():
    a = _sample_candidate()
    b = _sample_candidate()
    assert _queue_filename(a) == _queue_filename(b)


def test_queue_filename_differs_by_url():
    a = _sample_candidate(source_url="https://github.com/alice/a")
    b = _sample_candidate(source_url="https://github.com/alice/b")
    assert _queue_filename(a) != _queue_filename(b)


def test_candidate_to_markdown_emits_frontmatter_and_body():
    c = _sample_candidate()
    md = _candidate_to_markdown(c)
    assert md.startswith("---\n")
    assert "\n---\n" in md
    assert "name: example-tool" in md
    assert "kind: repo" in md
    assert "status: draft" in md
    assert "via: awesome-claude-code" in md
    assert "Reviewer notes" in md


def test_candidate_to_markdown_omits_null_scout_fields():
    c = _sample_candidate()  # score and excerpt default to None
    md = _candidate_to_markdown(c)
    assert "score:" not in md
    assert "excerpt:" not in md


def test_candidate_to_markdown_includes_score_when_set():
    c = _sample_candidate(score=42)
    md = _candidate_to_markdown(c)
    assert "score: 42" in md
