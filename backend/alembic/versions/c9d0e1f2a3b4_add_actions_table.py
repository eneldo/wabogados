"""Add actions table.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("responsible_lawyer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["responsible_lawyer_id"], ["lawyers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_actions_action_type"), "actions", ["action_type"], unique=False)
    op.create_index(op.f("ix_actions_occurred_at"), "actions", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_actions_visibility"), "actions", ["visibility"], unique=False)
    op.create_index(
        op.f("ix_actions_next_action_at"), "actions", ["next_action_at"], unique=False
    )
    op.create_index(
        "ix_actions_case_occurred", "actions", ["case_id", "occurred_at"], unique=False
    )
    op.create_index(
        "ix_actions_case_visibility", "actions", ["case_id", "visibility"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_actions_case_visibility", table_name="actions")
    op.drop_index("ix_actions_case_occurred", table_name="actions")
    op.drop_index(op.f("ix_actions_next_action_at"), table_name="actions")
    op.drop_index(op.f("ix_actions_visibility"), table_name="actions")
    op.drop_index(op.f("ix_actions_occurred_at"), table_name="actions")
    op.drop_index(op.f("ix_actions_action_type"), table_name="actions")
    op.drop_table("actions")
