"""Add case milestones with controlled publication.

Revision ID: fc3d4e5f6071
Revises: fb2c3d4e5f60
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fc3d4e5f6071"
down_revision: str | Sequence[str] | None = "fb2c3d4e5f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_key", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "published_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_case_milestones_case_published",
        "case_milestones",
        ["case_id", "is_published"],
    )
    op.create_index(
        "ix_case_milestones_case_order", "case_milestones", ["case_id", "sort_order"]
    )
    op.create_index("ix_case_milestones_case_id", "case_milestones", ["case_id"])
    op.create_index("ix_case_milestones_status", "case_milestones", ["status"])
    op.create_index("ix_case_milestones_is_published", "case_milestones", ["is_published"])


def downgrade() -> None:
    op.drop_index("ix_case_milestones_is_published", table_name="case_milestones")
    op.drop_index("ix_case_milestones_status", table_name="case_milestones")
    op.drop_index("ix_case_milestones_case_id", table_name="case_milestones")
    op.drop_index("ix_case_milestones_case_order", table_name="case_milestones")
    op.drop_index("ix_case_milestones_case_published", table_name="case_milestones")
    op.drop_table("case_milestones")
