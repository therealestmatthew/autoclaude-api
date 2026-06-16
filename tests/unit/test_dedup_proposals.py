"""Unit tests for pass 3 (soft-overlap merge proposals).

Covers: Jaccard threshold, primary-author bucketing, mergeset_id stability,
rejection ledger, cross-repo sibling-child exclusion.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from scout.dedup import run_passes
from scout.dedup.engine import PROPOSAL_REJECTED_HEADER

TODAY = date(2026, 6, 15)


def _make_md(
    path: Path,
    *,
    slug: str,
    url: str,
    kind: str = "article",
    title: str | None = None,
    authors: list[str] | None = None,
    parent: str | None = None,
    is_catalog: bool = False,
    body: str = "# Body\n",
) -> Path:
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
    if parent:
        fm["relations"] = {"parent": parent}
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body)
    return path


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    queue = tmp_path / "queue"
    catalog = tmp_path / "catalog"
    state = tmp_path / "state"
    for p in (queue, catalog, state):
        p.mkdir()
    return queue, catalog, state


class TestPass3OverlapDetection:
    def test_high_jaccard_same_author_emits_proposal(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md", slug="a",
            url="https://example.com/a",
            title="Claude Code Best Practices Guide",
            authors=["anthropic"],
        )
        _make_md(
            queue / "b.md", slug="b",
            url="https://example.com/b",
            title="Best Practices Guide for Claude Code",
            authors=["anthropic"],
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass3_merge_proposals == 1
        text = (queue / "a.md").read_text()
        assert "scout-dedup-proposal-start" in text
        assert "mergeset_id" in text
        assert "`b`" in text  # references the other slug
        # Same mergeset_id appears on both members.
        a_fm = yaml.safe_load((queue / "a.md").read_text().split("---")[1])
        b_fm = yaml.safe_load((queue / "b.md").read_text().split("---")[1])
        assert a_fm["mergeset_id"] == b_fm["mergeset_id"]
        assert a_fm["mergeset_id"].startswith("ms-")

    def test_different_author_does_not_overlap(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md", slug="a", url="https://example.com/a",
            title="Some Cool Tool For Agents", authors=["alice"],
        )
        _make_md(
            queue / "b.md", slug="b", url="https://example.com/b",
            title="Some Cool Tool For Agents", authors=["bob"],
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass3_merge_proposals == 0

    def test_low_jaccard_does_not_overlap(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md", slug="a", url="https://example.com/a",
            title="Claude Code Best Practices",
            authors=["anthropic"],
        )
        _make_md(
            queue / "b.md", slug="b", url="https://example.com/b",
            title="MCP Server Configuration Guide",
            authors=["anthropic"],
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass3_merge_proposals == 0

    def test_different_kind_does_not_overlap(self, tmp_path: Path) -> None:
        # Locked decision: pass 3 buckets by (kind, primary_author).
        # An agent and a skill with identical titles do NOT merge here —
        # pass 1 / pass 2 already handle URL-based same-artifact collapse.
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md", slug="a", url="https://example.com/a",
            title="Code Review Helper Tool", kind="agent",
            authors=["anthropic"],
        )
        _make_md(
            queue / "b.md", slug="b", url="https://example.com/b",
            title="Code Review Helper Tool", kind="skill",
            authors=["anthropic"],
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass3_merge_proposals == 0


class TestSiblingChildExclusion:
    def test_cross_repo_children_same_name_do_not_merge(self, tmp_path: Path) -> None:
        """Locked decision: <repo-a>--code-reviewer and <repo-b>--code-reviewer
        are NOT duplicates. The parent scoping already differentiates them."""
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md",
            slug="repo-a--code-reviewer",
            url="https://github.com/repo-a/blob/x/agents/code-reviewer.md",
            kind="agent", authors=["anthropic"], parent="repo-a",
            title="Code Reviewer Agent",
        )
        _make_md(
            queue / "b.md",
            slug="repo-b--code-reviewer",
            url="https://github.com/repo-b/blob/x/agents/code-reviewer.md",
            kind="agent", authors=["anthropic"], parent="repo-b",
            title="Code Reviewer Agent",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass3_merge_proposals == 0


class TestRejection:
    def test_rejected_header_records_in_ledger_and_carries(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        body_with_rejection = (
            "# Body\n\n"
            "<!-- scout-dedup-proposal-start -->\n"
            f"{PROPOSAL_REJECTED_HEADER}\n\n"
            "This was rejected by the reviewer.\n"
            "<!-- scout-dedup-proposal-end -->\n"
        )
        _make_md(
            queue / "a.md", slug="a", url="https://example.com/a",
            title="Claude Code Best Practices",
            authors=["anthropic"],
            body=body_with_rejection,
        )
        _make_md(
            queue / "b.md", slug="b", url="https://example.com/b",
            title="Best Practices for Claude Code",
            authors=["anthropic"],
        )
        # Run twice — second run must see the ledger and not re-propose.
        r1 = run_passes(queue, catalog, state, today=TODAY)
        assert r1.rejected_proposals_carried == 1
        assert r1.pass3_merge_proposals == 0

        ledger = json.loads((state / "merge-decisions.json").read_text())
        assert len(ledger["rejected_proposals"]) == 1
        assert ledger["rejected_proposals"][0]["reason"] == "human-override"

        r2 = run_passes(queue, catalog, state, today=TODAY)
        assert r2.pass3_merge_proposals == 0
        assert r2.rejected_proposals_carried == 1
