"""Initial schema — asset and index_meta tables.

Revision ID: 0001
Revises:
Create Date: 2026-06-17

Path is the primary key (every record corresponds to a unique file; the
filesystem enforces this naturally). `(bucket, slug)` is a non-unique
composite index because unnamed README.md files all fall back to
slug='readme' but have distinct paths.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "asset",
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("quality", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=True),
        sa.Column("discovered", sa.JSON(), nullable=True),
        sa.Column("relations", sa.JSON(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=10), nullable=True),
        sa.Column("updated_at", sa.String(length=10), nullable=True),
        sa.Column("mtime", sa.Float(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("sync_run_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("path"),
    )
    op.create_index("ix_asset_bucket_slug", "asset", ["bucket", "slug"])
    op.create_index("ix_asset_kind", "asset", ["kind"])
    op.create_index("ix_asset_status", "asset", ["status"])
    op.create_index("ix_asset_updated_at", "asset", ["updated_at"])
    op.create_index("ix_asset_sync_run_id", "asset", ["sync_run_id"])

    op.create_table(
        "index_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repo_root", sa.String(length=1024), nullable=False),
        sa.Column("last_sync_at", sa.Float(), nullable=False),
        sa.Column("last_sync_run_id", sa.String(length=64), nullable=False),
        sa.Column("last_sync_record_count", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("index_meta")
    op.drop_index("ix_asset_sync_run_id", table_name="asset")
    op.drop_index("ix_asset_updated_at", table_name="asset")
    op.drop_index("ix_asset_status", table_name="asset")
    op.drop_index("ix_asset_kind", table_name="asset")
    op.drop_index("ix_asset_bucket_slug", table_name="asset")
    op.drop_table("asset")
