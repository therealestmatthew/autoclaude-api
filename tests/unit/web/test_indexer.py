"""Unit tests for the markdown indexer.

Covers: bucket classification, frontmatter parsing, slug fallback,
issues collection. Filesystem I/O against the in-tree fixture repo only.
"""

from __future__ import annotations

from pathlib import Path

from web.apps.api.indexer import (
    ALL_BUCKETS,
    Indexer,
    classify_bucket,
)


def test_scan_returns_records(fixture_repo: Path) -> None:
    snapshot = Indexer(fixture_repo).scan()
    assert len(snapshot.records) > 0
    assert snapshot.repo_root == fixture_repo.resolve().as_posix()


def test_bucket_classification(fixture_repo: Path) -> None:
    cases = [
        ("catalog/alpha-tool.md", "catalog"),
        ("catalog/beta-skill.md", "catalog"),
        ("catalog/README.md", "readme"),
        ("scout/queue/2026-06-15-fresh-candidate-abcd1234.md", "queue"),
        ("scout/queue/_template.md", "other"),
        ("scout/queue/README.md", "readme"),
        ("consulting/engagements/2026-acme/README.md", "engagement"),
        ("conventions/naming.md", "convention"),
        ("docs/plans/phase-1-fixture.md", "plan"),
        ("CLAUDE.md", "convention"),  # has kind: convention; path bucket is "other"
    ]
    for rel, expected in cases:
        path = fixture_repo / rel
        if rel == "CLAUDE.md":
            # CLAUDE.md doesn't live under a bucketed path — it's "other"
            # by classification regardless of frontmatter `kind`.
            assert classify_bucket(path, fixture_repo) == "other"
        else:
            assert classify_bucket(path, fixture_repo) == expected, rel


def test_catalog_record_shape(fixture_repo: Path) -> None:
    snapshot = Indexer(fixture_repo).scan()
    by_slug = snapshot.by_slug()
    alpha = by_slug["alpha-tool"]
    assert alpha.bucket == "catalog"
    assert alpha.kind == "repo"
    assert alpha.title == "Alpha tool"
    assert alpha.status == "adopted"
    assert alpha.quality == 4
    assert "fixture" in alpha.tags
    assert alpha.source is not None
    assert alpha.source["url"].startswith("https://github.com/example/")
    assert alpha.created_at == "2026-06-01"
    assert alpha.updated_at == "2026-06-02"
    assert alpha.body.strip().startswith("# alpha-tool")
    assert alpha.issues == ()


def test_queue_record_shape(fixture_repo: Path) -> None:
    snapshot = Indexer(fixture_repo).scan()
    by_slug = snapshot.by_slug()
    fresh = by_slug["fresh-candidate"]
    assert fresh.bucket == "queue"
    assert fresh.kind == "article"


def test_engagement_picked_up(fixture_repo: Path) -> None:
    snapshot = Indexer(fixture_repo).scan()
    by_slug = snapshot.by_slug()
    eng = by_slug["2026-acme"]
    assert eng.bucket == "engagement"
    assert eng.status == "active"


def test_stats(fixture_repo: Path) -> None:
    snapshot = Indexer(fixture_repo).scan()
    stats = snapshot.stats()
    assert stats.total == len(snapshot.records)
    assert stats.by_bucket["catalog"] == 4
    assert stats.by_bucket["queue"] == 2
    assert stats.by_bucket["engagement"] == 1
    # All listed buckets are in the enum.
    for b in stats.by_bucket:
        assert b in ALL_BUCKETS


def test_slug_collision_recorded(fixture_repo: Path, tmp_path: Path) -> None:
    """Two files with the same `name` field collide; the second gets an issue."""
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(fixture_repo, repo)
    # alpha-tool already exists in catalog; add another file claiming the same
    # slug under a different bucket.
    (repo / "scout" / "queue" / "alpha-tool.md").write_text(
        "---\nname: alpha-tool\nkind: repo\ntitle: dupe\nsource:\n  url: x\n"
        "discovered:\n  via: manual\n  on: 2026-06-15\n---\n\n",
        encoding="utf-8",
    )
    snapshot = Indexer(repo).scan()
    by_slug = snapshot.by_slug()
    # First wins on the bare slug key; collision goes under "<bucket>:<slug>"
    assert "alpha-tool" in by_slug
    collided_keys = [k for k in by_slug if k.startswith("queue:alpha-tool")]
    assert collided_keys
    assert any("slug-collision" in i for i in by_slug[collided_keys[0]].issues)


def test_missing_frontmatter_flagged(fixture_repo: Path, tmp_path: Path) -> None:
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(fixture_repo, repo)
    (repo / "catalog" / "no-fm.md").write_text("# no frontmatter\n", encoding="utf-8")
    snapshot = Indexer(repo).scan()
    rec = next(r for r in snapshot.records if r.path == "catalog/no-fm.md")
    assert "missing-frontmatter" in rec.issues


def test_malformed_frontmatter_flagged(fixture_repo: Path, tmp_path: Path) -> None:
    import shutil

    repo = tmp_path / "repo"
    shutil.copytree(fixture_repo, repo)
    (repo / "catalog" / "bad-fm.md").write_text(
        "---\nname: bad\nkind: [unclosed\n---\nbody\n", encoding="utf-8"
    )
    snapshot = Indexer(repo).scan()
    rec = next(r for r in snapshot.records if r.path == "catalog/bad-fm.md")
    assert "malformed-frontmatter" in rec.issues
