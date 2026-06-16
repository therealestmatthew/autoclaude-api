"""Idempotency contract: running the dedup engine twice in a row over the
same disk state must produce identical state on the second run.

A non-idempotent dedup is worse than no dedup — it would oscillate, churn
through reviewers' diffs, and erode trust in the engine's recommendations.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from scout.dedup import run_passes

TODAY = date(2026, 6, 15)


def _make_md(
    path: Path,
    *,
    slug: str,
    url: str,
    kind: str = "article",
    title: str | None = None,
    authors: list[str] | None = None,
    is_catalog: bool = False,
    body: str = "# Body\n",
) -> None:
    fm: dict = {
        "name": slug,
        "kind": kind,
        "title": title or slug,
        "status": "reviewed" if is_catalog else "draft",
        "source": {
            "type": "article", "url": url,
            "authors": authors or [], "license": "",
        },
        "discovered": {"via": "test", "on": "2026-06-15", "run_id": "t"},
        "created_at": "2026-06-15",
        "updated_at": "2026-06-15",
    }
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body)


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    queue = tmp_path / "queue"
    catalog = tmp_path / "catalog"
    state = tmp_path / "state"
    for p in (queue, catalog, state):
        p.mkdir()
    return queue, catalog, state


def _snapshot(*dirs: Path) -> dict[str, str]:
    """Capture every file's contents under each dir, keyed by name."""
    out: dict[str, str] = {}
    for d in dirs:
        for p in sorted(d.glob("*")):
            if p.is_file():
                out[f"{d.name}/{p.name}"] = p.read_text()
    return out


class TestIdempotency:
    def test_empty_inputs_are_stable(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        r1 = run_passes(queue, catalog, state, today=TODAY)
        r2 = run_passes(queue, catalog, state, today=TODAY)
        assert r1.summary() == r2.summary()
        # No ledger file is created when nothing happened.
        assert not (state / "merge-decisions.json").exists()

    def test_identity_collapse_settles_after_first_run(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(queue / "a.md", slug="a", url="https://example.com/x")
        _make_md(queue / "b.md", slug="b", url="https://example.com/x")
        run_passes(queue, catalog, state, today=TODAY)
        snap1 = _snapshot(queue, catalog, state)
        r2 = run_passes(queue, catalog, state, today=TODAY)
        snap2 = _snapshot(queue, catalog, state)
        # The second run does nothing.
        assert r2.pass1_identity_collapse == 0
        assert snap1 == snap2

    def test_proposal_section_is_stable(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md", slug="a", url="https://example.com/a",
            title="Claude Code Best Practices Guide",
            authors=["anthropic"],
        )
        _make_md(
            queue / "b.md", slug="b", url="https://example.com/b",
            title="Best Practices Guide for Claude Code",
            authors=["anthropic"],
        )
        run_passes(queue, catalog, state, today=TODAY)
        snap1 = _snapshot(queue, catalog, state)
        run_passes(queue, catalog, state, today=TODAY)
        snap2 = _snapshot(queue, catalog, state)
        assert snap1 == snap2

    def test_catalog_archive_settles(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        # Catalog asset with supersedes, old updated_at → should archive.
        path = catalog / "old.md"
        fm = {
            "name": "old",
            "kind": "article",
            "title": "Old asset",
            "status": "reviewed",
            "source": {
                "type": "article", "url": "https://example.com/old",
                "authors": [], "license": "",
            },
            "discovered": {"via": "manual", "on": "2026-04-01"},
            "relations": {"supersedes": ["older-thing"]},
            "created_at": "2026-04-01",
            "updated_at": "2026-04-01",
        }
        path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n")

        r1 = run_passes(queue, catalog, state, today=TODAY)
        assert r1.pass4_auto_archived == 1
        # status, archived_at, archived_reason set.
        fm_after = yaml.safe_load(path.read_text().split("---")[1])
        assert fm_after["status"] == "archived"
        assert fm_after["archived_reason"] == "superseded"
        assert str(fm_after["archived_at"]) == "2026-06-15"

        snap1 = _snapshot(queue, catalog, state)
        r2 = run_passes(queue, catalog, state, today=TODAY)
        snap2 = _snapshot(queue, catalog, state)
        assert r2.pass4_auto_archived == 0, "already archived — must not re-fire"
        assert snap1 == snap2

    def test_ledger_does_not_accumulate_dup_collapse_entries(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(queue / "a.md", slug="a", url="https://example.com/x")
        _make_md(queue / "b.md", slug="b", url="https://example.com/x")
        run_passes(queue, catalog, state, today=TODAY)
        ledger1 = json.loads((state / "merge-decisions.json").read_text())
        # Second run: no collapses (b is gone), ledger unchanged.
        run_passes(queue, catalog, state, today=TODAY)
        ledger2 = json.loads((state / "merge-decisions.json").read_text())
        assert ledger1 == ledger2
        assert len(ledger1["applied_collapses"]) == 1
