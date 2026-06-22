"""Phase 10.1 — Company Edition: client, business_process, user_preference.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

_BUSINESS_PROCESSES = [
    ("order-to-cash",    "Order to Cash",      None, "Sales order through cash collection"),
    ("record-to-report", "Record to Report",   None, "Financial close, consolidation and reporting"),
    ("procure-to-pay",   "Procure to Pay",     None, "Purchase requisition through vendor payment"),
    ("hire-to-retire",   "Hire to Retire",     None, "Employee lifecycle management"),
    ("plan-to-perform",  "Plan to Perform",    None, "Financial planning and analysis (FP&A)"),
    ("acquire-to-retire","Acquire to Retire",  None, "Fixed asset management lifecycle"),
    ("requirements-gen", "Requirements Generation", None, "Functional and business requirements authoring"),
    ("user-story-gen",   "User Story Generation",   None, "Agile epic, user story and acceptance criteria"),
    ("estimation",       "Estimation",         None, "Project sizing and effort estimation"),
    ("status-reporting", "Status Reporting",   None, "Project status reports and steering committee decks"),
    ("change-mgmt",      "Change Management",  None, "Organizational change management"),
]


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("slug", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("industry", sa.String(128), nullable=True),
        sa.Column("brand_slug", sa.String(128), nullable=True),
        sa.Column("engagement_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_client_brand_slug", "client", ["brand_slug"])

    op.create_table(
        "business_process",
        sa.Column("slug", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_slug", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    for slug, name, parent_slug, description in _BUSINESS_PROCESSES:
        op.execute(
            sa.text(
                "INSERT INTO business_process (slug, name, parent_slug, description) "
                "VALUES (:slug, :name, :parent_slug, :description)"
            ).bindparams(slug=slug, name=name, parent_slug=parent_slug, description=description)
        )

    op.create_table(
        "user_preference",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_preference")
    op.drop_table("business_process")
    op.drop_index("ix_client_brand_slug", table_name="client")
    op.drop_table("client")
