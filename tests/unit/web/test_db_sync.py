"""Unit tests for the sync engine.

Covers the explicit invariants the milestone plan calls out: idempotent
no-op runs, change detection, deletion + reconciliation, primary-key moves
when a file's frontmatter slug changes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.db import sync
from web.apps.api.db.models import Asset, IndexMeta
from web.apps.api.db.session import SCHEMA_VERSION
from web.apps.api.db.sync import _hash_record, _normalize_json
from web.apps.api.indexer import Indexer


@pytest.fixture
def repo(fixture_repo: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(fixture_repo, dest)
    return dest


def test_first_sync_writes_all_records(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    result = sync(Indexer(repo), db_factory)
    assert result.records > 0
    assert result.rows_written == result.records
    assert result.rows_skipped == 0
    assert result.rows_deleted == 0


def test_second_sync_is_noop(repo: Path, db_factory: sessionmaker[Session]) -> None:
    first = sync(Indexer(repo), db_factory)
    second = sync(Indexer(repo), db_factory)
    assert second.rows_written == 0
    assert second.rows_deleted == 0
    assert second.rows_skipped == first.records


def test_changed_body_triggers_write(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    sync(Indexer(repo), db_factory)
    asset = repo / "catalog" / "alpha-tool.md"
    asset.write_text(asset.read_text() + "\nadded a new line\n", encoding="utf-8")
    result = sync(Indexer(repo), db_factory)
    assert result.rows_written == 1
    assert result.rows_skipped == result.records - 1


def test_deleted_file_is_removed(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    sync(Indexer(repo), db_factory)
    (repo / "catalog" / "alpha-tool.md").unlink()
    result = sync(Indexer(repo), db_factory)
    assert result.rows_deleted == 1
    with db_factory() as session:
        assert session.get(Asset, "catalog/alpha-tool.md") is None


def test_slug_rename_updates_row(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    """The PK is `path`, so renaming the slug in frontmatter is a single-row
    update — not a delete + insert. The (bucket, slug) index moves with the
    row's new value."""
    sync(Indexer(repo), db_factory)
    asset = repo / "catalog" / "alpha-tool.md"
    text = asset.read_text()
    asset.write_text(text.replace("name: alpha-tool", "name: alpha-renamed"))
    result = sync(Indexer(repo), db_factory)
    assert result.rows_written == 1
    assert result.rows_deleted == 0
    with db_factory() as session:
        row = session.get(Asset, "catalog/alpha-tool.md")
        assert row is not None
        assert row.slug == "alpha-renamed"


def test_many_readmes_coexist(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    """README.md files all default to slug='readme' but have distinct paths.
    The path PK accommodates them; nothing collides."""
    (repo / "extra" / "nested").mkdir(parents=True)
    (repo / "extra" / "README.md").write_text("# extra\n")
    (repo / "extra" / "nested" / "README.md").write_text("# nested\n")
    result = sync(Indexer(repo), db_factory)
    # No exceptions; both readmes landed.
    paths_with_readme_slug = []
    with db_factory() as session:
        for asset in session.execute(select(Asset)).scalars():
            if asset.slug == "readme":
                paths_with_readme_slug.append(asset.path)
    assert "extra/README.md" in paths_with_readme_slug
    assert "extra/nested/README.md" in paths_with_readme_slug
    assert result.rows_written == result.records


def test_meta_row_stamped(repo: Path, db_factory: sessionmaker[Session]) -> None:
    result = sync(Indexer(repo), db_factory)
    with db_factory() as session:
        meta = session.get(IndexMeta, 1)
    assert meta is not None
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.last_sync_run_id == result.run_id
    assert meta.last_sync_record_count == result.records


def test_hash_ignores_mtime(repo: Path, db_factory: sessionmaker[Session]) -> None:
    """`touch` shouldn't cause a write — the hash excludes mtime by design."""
    sync(Indexer(repo), db_factory)
    (repo / "catalog" / "alpha-tool.md").touch()
    result = sync(Indexer(repo), db_factory)
    assert result.rows_written == 0


def test_hash_is_dict_key_order_independent(
    repo: Path, db_factory: sessionmaker[Session]
) -> None:
    """Two records with the same frontmatter in different key orders hash
    identically. Guards against a regression where dict insertion order
    sneaks into the hash."""
    snapshot = Indexer(repo).scan()
    rec = next(r for r in snapshot.records if r.bucket == "catalog")
    if rec.source is None:
        pytest.skip("fixture has no source dict to permute")
    h1 = _hash_record(rec)
    reordered_source = dict(reversed(list(rec.source.items())))
    rec2 = type(rec)(**{**rec.__dict__, "source": reordered_source})  # type: ignore[arg-type]
    assert _hash_record(rec2) == h1


def test_normalize_json_handles_yaml_quirks() -> None:
    """YAML 1.1 surprises that bit us in development:
    - `on:` parses as boolean True
    - ISO dates parse as `datetime.date`
    """
    import datetime as dt

    result = _normalize_json({True: dt.date(2026, 6, 16), "via": "manual"})
    assert result == {"True": "2026-06-16", "via": "manual"}
