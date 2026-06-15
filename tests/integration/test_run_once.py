"""Integration test: full `runner.run_once()` loop.

Patches the extractor registry to inject a deterministic fake, seeds an
isolated catalog + source config under `scout_world`, runs the orchestrator,
then asserts the visible side effects: queue files, state file, thread log.

This is the canonical example of an integration test in this repo. Use it as
the template when writing new ones (Phase 3 extractors, the Phase 4 repo
extractor, the reviewer agent, etc.).
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterator

import pytest

from scout.agent import runner
from scout.agent.types import (
    AwesomeListSource,
    Candidate,
    SourceState,
)


class FakeExtractor:
    """Yields a fixed list of candidates regardless of source content.

    Mirrors the real Extractor protocol shape so we exercise the real runner
    dispatch path. The runner's only contract with extractors is the
    `(source, state, run_id) -> Iterator[Candidate]` signature; this satisfies it.
    """

    type = "awesome-list"

    def __init__(self, candidates: list[Candidate]) -> None:
        self._candidates = candidates

    def fetch(
        self,
        source: AwesomeListSource,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        for c in self._candidates:
            state.seen_urls[c.source_url] = c.discovered_on
            yield c


def _candidate(**overrides: object) -> Candidate:
    base: dict[str, object] = dict(
        name="example",
        kind="repo",
        title="Example",
        source_type="github",
        source_url="https://github.com/alice/example",
        discovered_via="awesome-claude-code",
        discovered_on="2026-06-14",
        run_id="test-run",
    )
    base.update(overrides)
    return Candidate(**base)  # type: ignore[arg-type]


def test_full_loop_writes_queue_state_and_thread_log(
    scout_world, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — one source config, one pre-existing catalog asset that should
    # cause exactly one of the candidates to be deduped.
    (scout_world["sources"] / "awesome-lists.yaml").write_text(textwrap.dedent("""\
        name: awesome-lists
        type: awesome-list
        enabled: true
        poll_interval_minutes: 1440
        lists:
          - name: test-list
            url: https://example.invalid/list.md
    """))
    (scout_world["catalog"] / "alice-existing.md").write_text(textwrap.dedent("""\
        ---
        name: alice-existing
        kind: repo
        title: Existing
        status: reviewed
        source:
          type: github
          url: https://github.com/alice/existing
        discovered:
          via: manual
          on: 2026-06-13
        created_at: 2026-06-13
        updated_at: 2026-06-13
        ---
    """))

    fake = FakeExtractor([
        _candidate(name="alice-existing", source_url="https://github.com/alice/existing"),
        _candidate(name="alice-new-1", source_url="https://github.com/alice/new-1"),
        _candidate(name="alice-new-2", source_url="https://github.com/alice/new-2"),
    ])
    monkeypatch.setitem(runner.EXTRACTOR_REGISTRY, "awesome-list", fake)

    # Act
    stats = runner.run_once()

    # Assert — stats
    assert stats["candidates_queued"] == 2
    assert stats["candidates_skipped_catalog_dedup"] == 1
    assert stats["errors"] == []

    # Assert — queue
    queue_files = sorted(scout_world["queue"].glob("*.md"))
    assert len(queue_files) == 2
    queue_text = " ".join(p.read_text() for p in queue_files)
    assert "alice-new-1" in queue_text
    assert "alice-new-2" in queue_text
    assert "alice-existing" not in queue_text

    # Assert — state
    state_files = list(scout_world["state"].glob("*.json"))
    assert len(state_files) == 1
    assert state_files[0].name == "awesome-lists.json"
    state = json.loads(state_files[0].read_text())
    assert state["source"] == "awesome-lists"
    assert state["stats"]["runs"] == 1
    assert state["stats"]["candidates_queued_total"] == 2

    # Assert — thread log: one JSONL record naming the run
    thread_files = list(scout_world["threads"].glob("*.jsonl"))
    assert len(thread_files) == 1
    record = json.loads(thread_files[0].read_text().strip())
    assert record["thread_id"] == stats["run_id"]
    assert record["agent"] == "scout"
    assert record["outcome"] == "ok"


def test_canonical_url_dedup_catches_subtree_links(
    scout_world, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the catalog has a repo at its root URL, a candidate at a subtree of
    that repo must still dedup (covers the awesome-list-points-at-subdir case).
    """
    (scout_world["sources"] / "awesome-lists.yaml").write_text(textwrap.dedent("""\
        name: awesome-lists
        type: awesome-list
        enabled: true
        poll_interval_minutes: 1440
        lists:
          - name: test-list
            url: https://example.invalid/list.md
    """))
    (scout_world["catalog"] / "alice-existing.md").write_text(textwrap.dedent("""\
        ---
        name: alice-existing
        kind: repo
        title: Existing
        status: reviewed
        source:
          type: github
          url: https://github.com/alice/existing
        discovered:
          via: manual
          on: 2026-06-13
        created_at: 2026-06-13
        updated_at: 2026-06-13
        ---
    """))

    fake = FakeExtractor([
        _candidate(
            name="alice-existing-skill",
            source_url="https://github.com/alice/existing/tree/main/skills/foo",
        ),
    ])
    monkeypatch.setitem(runner.EXTRACTOR_REGISTRY, "awesome-list", fake)

    stats = runner.run_once()
    assert stats["candidates_queued"] == 0
    assert stats["candidates_skipped_catalog_dedup"] == 1
