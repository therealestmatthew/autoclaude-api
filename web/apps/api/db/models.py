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

from sqlalchemy import Boolean, Column, Float, Index, Integer, String, Text
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
    delivery_functions = Column(JSON, nullable=False, default=list)
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

    # 8.3: optimistic-lock token. Equal to `content_hash` after sync;
    # diverges briefly during an in-flight write while the file has been
    # written but the sync hasn't re-read it yet. PUT/POST requests carry
    # an `If-Match` header that must equal this value; mismatch -> 409.
    version = Column(String(64), nullable=False, default="")

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


class AuditEvent(Base):
    """Append-only log of every UI-driven write.

    Created in `pending` state at the start of a write, finalised to
    `committed` or `failed` after the file + git operations complete.
    A row that stays in `pending` longer than one sync cycle (60s)
    indicates a crash mid-write — the sweeper surfaces it in /health.
    """

    __tablename__ = "audit_event"

    id = Column(String(36), primary_key=True)         # uuid4 hex
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    # actor: 'operator' | 'reviewer-agent' | ...
    actor = Column(String(64), nullable=False)
    # action: edit-frontmatter | edit-body | edit-full | triage-keep |
    # triage-merge | triage-discard | create-asset | archive
    action = Column(String(64), nullable=False)
    target_path = Column(String(1024), nullable=False)
    target_bucket = Column(String(32), nullable=False)
    # status: 'pending' | 'committed' | 'failed'
    status = Column(String(16), nullable=False)
    # intent: request payload (also captures pre-state snapshot)
    intent = Column(JSON, nullable=False)
    # result: commit_sha, error trace, etc.
    result = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_event_target_path", "target_path"),
        Index("ix_audit_event_status", "status"),
        Index("ix_audit_event_created_at", "created_at"),
    )


class Proposal(Base):
    """Reviewer-agent recommendations (or operator drafts) awaiting a
    decision. Phase 9.0 fills this with `source='reviewer-agent'` rows;
    the triage UI surfaces them and writes the decision to the audit
    log on accept/reject."""

    __tablename__ = "proposal"

    id = Column(String(36), primary_key=True)
    created_at = Column(Float, nullable=False)
    # source: 'operator' | 'reviewer-agent'
    source = Column(String(64), nullable=False)
    target_path = Column(String(1024), nullable=False)
    target_bucket = Column(String(32), nullable=False)
    # action_kind: keep | merge | discard | edit
    action_kind = Column(String(32), nullable=False)
    # payload: action-specific args (target_slug, notes, ...)
    payload = Column(JSON, nullable=False)
    summary = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    # confidence: 0..1, reviewer-agent only
    confidence = Column(Float, nullable=True)
    # status: 'pending' | 'accepted' | 'rejected' | 'expired' | 'superseded'
    status = Column(String(16), nullable=False)
    decided_at = Column(Float, nullable=True)
    decided_by = Column(String(64), nullable=True)
    decision_audit_id = Column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_proposal_source", "source"),
        Index("ix_proposal_target_path", "target_path"),
        Index("ix_proposal_status", "status"),
        Index("ix_proposal_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# Phase 10.1 — Company Edition entities
# ---------------------------------------------------------------------------


class Client(Base):
    """Lightweight lookup record for a named client engagement context.

    Not a tenant boundary — just enough to default a brand and carry
    engagement context into generator prompts for repeat exports.
    """

    __tablename__ = "client"

    slug = Column(String(128), primary_key=True)
    name = Column(String(256), nullable=False)
    industry = Column(String(128), nullable=True)
    brand_slug = Column(String(128), nullable=True)        # soft FK → asset.slug WHERE bucket='brand'
    engagement_context = Column(Text, nullable=True)       # free-text injected into generator prompts
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_client_brand_slug", "brand_slug"),
    )


class BusinessProcess(Base):
    """Controlled vocabulary of finance-transformation process areas."""

    __tablename__ = "business_process"

    slug = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    parent_slug = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)


class UserPreference(Base):
    """Per-user configuration store (sidebar layout, theme, etc.).

    `user_id` is 'default' until auth lands in Phase 11.
    """

    __tablename__ = "user_preference"

    user_id = Column(String(128), primary_key=True)
    key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(Float, nullable=False)
