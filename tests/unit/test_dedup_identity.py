"""Unit tests for pass 1 (identity) and pass 2 (canonical-URL) collapse.

These cover the core dedup contract: exact-URL duplicates, exact-fingerprint
duplicates, github subpath collapse, catalog-survivor preference, cross-kind
collapse (article + repo at same URL → repo wins).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from scout.dedup import run_passes

TODAY = date(2026, 6, 15)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_md(
    path: Path,
    *,
    slug: str,
    url: str,
    kind: str = "article",
    title: str | None = None,
    authors: list[str] | None = None,
    fingerprint: str | None = None,
    discovered_on: str = "2026-06-15",
    parent: str | None = None,
    status: str = "draft",
    is_catalog: bool = False,
    body: str = "# Body\n",
) -> Path:
    fm: dict = {
        "name": slug,
        "kind": kind,
        "title": title or slug.replace("-", " ").title(),
        "status": "reviewed" if is_catalog else status,
        "source": {
            "type": "github" if "github.com" in url else "article",
            "url": url,
            "authors": authors or [],
            "license": "",
        },
        "discovered": {"via": "test", "on": discovered_on, "run_id": "test-run"},
        "created_at": discovered_on,
        "updated_at": discovered_on,
    }
    if parent:
        fm["relations"] = {"parent": parent}
    if fingerprint:
        fm["fingerprint"] = fingerprint
    text = "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body
    path.write_text(text)
    return path


def _world(tmp_path: Path) -> tuple[Path, Path, Path]:
    queue = tmp_path / "queue"
    catalog = tmp_path / "catalog"
    state = tmp_path / "state"
    for p in (queue, catalog, state):
        p.mkdir()
    return queue, catalog, state


# ---------------------------------------------------------------------------
# Pass 1 — exact identity
# ---------------------------------------------------------------------------


class TestPass1ExactURL:
    def test_two_queue_files_same_url_collapse_to_earliest(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        a = _make_md(
            queue / "a.md",
            slug="a", url="https://example.com/x",
            discovered_on="2026-06-10",
        )
        b = _make_md(
            queue / "b.md",
            slug="b", url="https://example.com/x",
            discovered_on="2026-06-14",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass1_identity_collapse == 1
        assert a.exists(), "earliest discovered_on should survive"
        assert not b.exists(), "later candidate should be discarded"

    def test_three_queue_files_collapse_to_one(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        for i, day in enumerate(("2026-06-15", "2026-06-14", "2026-06-13")):
            _make_md(
                queue / f"q{i}.md",
                slug=f"q{i}", url="https://example.com/same",
                discovered_on=day,
            )
        report = run_passes(queue, catalog, state, today=TODAY)
        # One group → one collapse event (two losers deleted).
        assert report.pass1_identity_collapse == 1
        survivors = list(queue.glob("*.md"))
        assert len(survivors) == 1
        # q2 has the earliest discovered_on.
        assert survivors[0].name == "q2.md"

    def test_catalog_wins_over_queue(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            catalog / "cat.md",
            slug="cat", url="https://example.com/x", is_catalog=True,
        )
        q = _make_md(
            queue / "q.md",
            slug="q", url="https://example.com/x",
            discovered_on="2026-06-10",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass1_identity_collapse == 1
        assert not q.exists(), "queue duplicate should be discarded"
        # Catalog body untouched.
        assert "# Body" in (catalog / "cat.md").read_text()

    def test_disjoint_urls_do_nothing(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(queue / "a.md", slug="a", url="https://example.com/a")
        _make_md(queue / "b.md", slug="b", url="https://example.com/b")
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass1_identity_collapse == 0
        assert (queue / "a.md").exists()
        assert (queue / "b.md").exists()


class TestPass1Fingerprint:
    def test_same_fingerprint_different_url_collapses(self, tmp_path: Path) -> None:
        # Two repo children with identical file bytes (same fingerprint),
        # discovered via different paths.
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "a.md",
            slug="a", url="https://github.com/foo/bar/blob/x/agents/y.md",
            kind="agent", fingerprint="sha256:abc",
            discovered_on="2026-06-10",
        )
        _make_md(
            queue / "b.md",
            slug="b", url="https://github.com/foo/bar/blob/x/agents/z.md",
            kind="agent", fingerprint="sha256:abc",
            discovered_on="2026-06-14",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass1_identity_collapse == 1
        assert (queue / "a.md").exists()
        assert not (queue / "b.md").exists()


class TestCrossKindCollapse:
    def test_article_collapses_into_repo(self, tmp_path: Path) -> None:
        """Open question 4: dedup across `kind` on URL. Recommended: collapse
        to the `repo` member because it carries Phase 4 extraction potential."""
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "article.md",
            slug="x-article", url="https://github.com/foo/bar",
            kind="article", discovered_on="2026-06-10",
        )
        _make_md(
            queue / "repo.md",
            slug="x-repo", url="https://github.com/foo/bar",
            kind="repo", discovered_on="2026-06-12",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass1_identity_collapse == 1
        # repo survives even though it was discovered later.
        assert (queue / "repo.md").exists()
        assert not (queue / "article.md").exists()


# ---------------------------------------------------------------------------
# Pass 2 — canonical URL collapse
# ---------------------------------------------------------------------------


class TestPass2URLCanonical:
    def test_subpath_collapses_into_repo_url(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            queue / "subpath.md",
            slug="sub", url="https://github.com/foo/bar/blob/main/README.md",
            kind="article", discovered_on="2026-06-14",
        )
        _make_md(
            queue / "root.md",
            slug="root", url="https://github.com/foo/bar",
            kind="repo", discovered_on="2026-06-10",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        # Pass 1 finds no exact match (URLs differ). Pass 2 collapses on
        # canonical_github_url.
        assert report.pass1_identity_collapse == 0
        assert report.pass2_url_canonicalize == 1
        assert (queue / "root.md").exists()
        assert not (queue / "subpath.md").exists()

    def test_catalog_repo_absorbs_queue_subpath(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        _make_md(
            catalog / "repo.md",
            slug="repo", url="https://github.com/foo/bar",
            kind="repo", is_catalog=True,
        )
        q = _make_md(
            queue / "sub.md",
            slug="sub",
            url="https://github.com/foo/bar/blob/main/agents/x.md",
            kind="agent",
        )
        report = run_passes(queue, catalog, state, today=TODAY)
        assert report.pass2_url_canonicalize == 1
        assert not q.exists()
        # Catalog `updated_at` is bumped to today (allowlisted change).
        import yaml as _yaml
        fm_after = _yaml.safe_load((catalog / "repo.md").read_text().split("---")[1])
        assert str(fm_after["updated_at"]) == "2026-06-15"


# ---------------------------------------------------------------------------
# Catalog allowlist enforcement
# ---------------------------------------------------------------------------


class TestCatalogAllowlist:
    def test_collapse_does_not_modify_catalog_body(self, tmp_path: Path) -> None:
        queue, catalog, state = _world(tmp_path)
        cat = _make_md(
            catalog / "cat.md",
            slug="cat", url="https://example.com/x",
            is_catalog=True, body="# Reviewer notes\n\nimportant stuff\n",
        )
        _make_md(
            queue / "q.md",
            slug="q", url="https://example.com/x",
        )
        run_passes(queue, catalog, state, today=TODAY)
        text = cat.read_text()
        assert "important stuff" in text
        # Engine MUST NOT write a body section to /catalog/.
        assert "scout-dedup-collapse" not in text
