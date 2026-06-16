"""End-to-end check that the dedup pass is wired into `runner.run_once`.

The test seeds an isolated world with the fixture queue/catalog files from
`tests/fixtures/dedup/`, then runs the full tick. The dedup pass should:

  - collapse the exact-duplicate-pair (pass 1)
  - emit a merge proposal for the near-duplicate-pair (pass 3)
  - auto-archive the superseded-chain catalog asset (pass 4)
  - auto-archive the 404-streak catalog asset when sidecar liveness state
    is dropped in (pass 4)
  - leave the queue + state stable on a back-to-back second run
    (idempotency)

It also pins the thread-log shape: a `scout-dedup`-agent record lands in
today's JSONL with the pass counts.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from scout.agent import runner
from scout.dedup import run_passes

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "dedup"
TODAY = date(2026, 6, 15)


def _seed_world(world, *fixture_subdirs: str) -> None:
    """Copy fixture queue/catalog files into the isolated world.

    Filenames are namespaced by their source subdir so multiple fixture sets
    can coexist in the same world without clashing on `queue-a.md`."""
    for sub in fixture_subdirs:
        src_dir = FIXTURE_ROOT / sub
        for src in src_dir.iterdir():
            if src.name == "README.md":
                continue
            if src.name.startswith("queue-"):
                shutil.copy(src, world["queue"] / f"{sub}--{src.name}")
            elif src.name.startswith("catalog-"):
                shutil.copy(src, world["catalog"] / f"{sub}--{src.name}")
            elif src.name == "state-url-liveness.json":
                shutil.copy(src, world["state"] / "url-liveness.json")


def test_runner_invokes_dedup_at_tail(scout_world, monkeypatch: pytest.MonkeyPatch) -> None:
    """`runner.run_once` with no extractors and no sources still runs the
    dedup pass at the end; the per-tick stats record the pass counts."""
    _seed_world(scout_world, "exact-duplicate-pair")
    monkeypatch.setattr(
        "scout.dedup.engine.date",
        type("_D", (), {"today": staticmethod(lambda: TODAY)}),
    )
    monkeypatch.setattr(runner, "EXTRACTOR_REGISTRY", {}, raising=True)

    stats = runner.run_once()

    assert "dedup" in stats
    assert stats["dedup"]["pass1_identity_collapse"] == 1
    # One queue file survives — the earlier-discovered one.
    survivors = sorted(p.name for p in scout_world["queue"].glob("*.md"))
    assert survivors == ["exact-duplicate-pair--queue-a.md"]


def test_full_fixture_set_collapses_archives_and_proposes(
    scout_world, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All four fixture scenarios at once: pass 1 collapses, pass 3 proposes,
    pass 4 archives. Then re-run and verify the state is unchanged."""
    _seed_world(
        scout_world,
        "exact-duplicate-pair",
        "near-duplicate-pair",
        "superseded-chain",
        "404-streak",
    )

    report = run_passes(
        scout_world["queue"],
        scout_world["catalog"],
        scout_world["state"],
        today=TODAY,
    )

    assert report.pass1_identity_collapse == 1
    assert report.pass3_merge_proposals == 1
    assert report.pass4_auto_archived == 2  # superseded + 404 streak

    # Catalog archives recorded.
    superseded = (scout_world["catalog"] / "superseded-chain--catalog-old.md").read_text()
    assert "status: archived" in superseded
    assert "archived_reason: superseded" in superseded

    dead = (scout_world["catalog"] / "404-streak--catalog-dead.md").read_text()
    assert "status: archived" in dead
    assert "archived_reason: source-url-404" in dead

    # Near-duplicate pair carries a merge proposal section + mergeset_id.
    a = (scout_world["queue"] / "near-duplicate-pair--queue-a.md").read_text()
    assert "scout-dedup-proposal-start" in a
    assert "mergeset_id: ms-" in a

    # Idempotency: re-run and compare every byte.
    snap1 = _snapshot(scout_world)
    report2 = run_passes(
        scout_world["queue"],
        scout_world["catalog"],
        scout_world["state"],
        today=TODAY,
    )
    snap2 = _snapshot(scout_world)

    # The idempotency contract is about disk state, not counter values.
    # Active proposals stay reported (they're still active); identity-collapse
    # and archive counters drop to 0 because nothing new fires.
    assert report2.pass1_identity_collapse == 0
    assert report2.pass4_auto_archived == 0
    assert snap1 == snap2, "second run must be a disk-state no-op"


def test_dedup_thread_log_record_shape(
    scout_world, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_world(scout_world, "exact-duplicate-pair")

    record = runner.dedup_once()

    log_files = list(scout_world["threads"].glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().splitlines()
    parsed = [json.loads(line) for line in lines]
    dedup_entries = [r for r in parsed if r["agent"] == "scout-dedup"]
    assert len(dedup_entries) == 1
    entry = dedup_entries[0]
    assert entry["outcome"] == "ok"
    assert entry["thread_id"] == record["thread_id"]
    assert entry["stats"]["pass1_identity_collapse"] == 1
    assert "summary" in entry


def _snapshot(world) -> dict[str, str]:
    out: dict[str, str] = {}
    for dirname in ("queue", "catalog", "state"):
        d = world[dirname]
        for p in sorted(d.glob("*")):
            if p.is_file():
                out[f"{dirname}/{p.name}"] = p.read_text()
    return out
