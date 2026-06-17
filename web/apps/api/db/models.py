"""SQLAlchemy ORM models for the persistent index.

Two tables only:

- `asset`       — one row per indexed markdown record. Mirrors the on-the-wire
                  shape of `AssetRecord` from `indexer.py`. The composite
                  primary key `(bucket, slug)` matches the invariant the 8.1
                  `IndexSnapshot.by_slug()` already enforces.
- `index_meta`  — single-row table holding sync state (last run id, schema
                  version, repo root). One row keyed by `id = 1`.

Anything that the API serializes goes through Pydantic; this module knows
about storage only. Conversions live in `sync.py` (write) and `query.py`
(read).
"""

from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model and the Alembic env."""


class Asset(Base):
    __tablename__ = "asset"

    # `path` is the natural primary key: the indexer emits one record per
    # file, and the filesystem guarantees path uniqueness. The earlier draft
    # used `(bucket, slug)` as a composite PK but every unnamed README.md in
    # the repo falls back to slug='readme', so that PK isn't actually unique
    # against real content. `(bucket, slug)` survives as a non-unique
    # composite index — `GET /<bucket>/{slug}` still walks the rows it
    # matches and picks first-seen.
    path = Column(String(1024), primary_key=True)

    bucket = Column(String(32), nullable=False)
    slug = Column(String(255), nullable=False)

    kind = Column(String(64), nullable=True)
    title = Column(String(512), nullable=True)
    status = Column(String(32), nullable=True)
    quality = Column(Integer, nullable=True)

    tags = Column(JSON, nullable=False, default=list)
    source = Column(JSON, nullable=True)
    discovered = Column(JSON, nullable=True)
    relations = Column(JSON, nullable=True)
    issues = Column(JSON, nullable=False, default=list)

    # Frontmatter dates ride the wire as ISO YYYY-MM-DD strings, so store
    # them as strings too. Avoids a date <-> string round-trip on every read.
    created_at = Column(String(10), nullable=True)
    updated_at = Column(String(10), nullable=True)

    mtime = Column(Float, nullable=False)
    body = Column(Text, nullable=False, default="")

    # Hash of everything that ends up on the wire. The sync engine compares
    # this against the new record's hash to decide whether to write.
    content_hash = Column(String(64), nullable=False)

    # Stamped by every sync that "sees" this row. The reconciliation pass
    # deletes rows whose `sync_run_id` is older than the current run, which
    # is how we drop files that were removed from the repo.
    sync_run_id = Column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_asset_bucket_slug", "bucket", "slug"),
        Index("ix_asset_kind", "kind"),
        Index("ix_asset_status", "status"),
        Index("ix_asset_updated_at", "updated_at"),
        Index("ix_asset_sync_run_id", "sync_run_id"),
    )


class IndexMeta(Base):
    __tablename__ = "index_meta"

    id = Column(Integer, primary_key=True)
    repo_root = Column(String(1024), nullable=False)
    last_sync_at = Column(Float, nullable=False)
    last_sync_run_id = Column(String(64), nullable=False)
    last_sync_record_count = Column(Integer, nullable=False, default=0)
    schema_version = Column(String(16), nullable=False)
