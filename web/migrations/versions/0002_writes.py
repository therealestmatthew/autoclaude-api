"""Phase 8.3 — write-back tables + asset version column.

Adds:
- `asset.version` column (optimistic-lock token; backfilled from
  `content_hash` for existing rows).
- `audit_event` table — append-only log of every UI-driven write,
  including pending → committed / failed transitions for atomicity.
- `proposal` table — operator drafts and (later) reviewer-agent
  recommendations awaiting triage.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("asset") as batch:
        batch.add_column(
            sa.Column(
                "version",
                sa.String(length=64),
                nullable=False,
                server_default="",
            )
        )
    # Backfill existing rows so the optimistic-lock token is meaningful
    # immediately. SQLite can't UPDATE FROM a column expression in batch
    # mode, but a straight UPDATE works.
    op.execute("UPDATE asset SET version = content_hash WHERE version = ''")

    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_path", sa.String(length=1024), nullable=False),
        sa.Column("target_bucket", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("intent", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_event_target_path", "audit_event", ["target_path"])
    op.create_index("ix_audit_event_status", "audit_event", ["status"])
    op.create_index("ix_audit_event_created_at", "audit_event", ["created_at"])

    op.create_table(
        "proposal",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("target_path", sa.String(length=1024), nullable=False),
        sa.Column("target_bucket", sa.String(length=32), nullable=False),
        sa.Column("action_kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_at", sa.Float(), nullable=True),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decision_audit_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_proposal_source", "proposal", ["source"])
    op.create_index("ix_proposal_target_path", "proposal", ["target_path"])
    op.create_index("ix_proposal_status", "proposal", ["status"])
    op.create_index("ix_proposal_created_at", "proposal", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_proposal_created_at", table_name="proposal")
    op.drop_index("ix_proposal_status", table_name="proposal")
    op.drop_index("ix_proposal_target_path", table_name="proposal")
    op.drop_index("ix_proposal_source", table_name="proposal")
    op.drop_table("proposal")

    op.drop_index("ix_audit_event_created_at", table_name="audit_event")
    op.drop_index("ix_audit_event_status", table_name="audit_event")
    op.drop_index("ix_audit_event_target_path", table_name="audit_event")
    op.drop_table("audit_event")

    with op.batch_alter_table("asset") as batch:
        batch.drop_column("version")
