"""Add the consultation_requests table for the public site form.

Revision ID: f4c5d6e7a8b9
Revises: e3f4a5b6c7d8
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f4c5d6e7a8b9"
down_revision: str | Sequence[str] | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consultation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # A name, two ways to reach the person and a description of a legal
        # problem. Personal data, and the reason the consent columns below are
        # NOT NULL with no server default: a row that cannot say what was
        # agreed to must not be creatable.
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("area", sa.String(length=60), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("privacy_notice_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="nueva", nullable=False),
        sa.Column("handled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["handled_by"],
            ["users.id"],
            name="fk_consultation_requests_handled_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name="fk_consultation_requests_client_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consultation_requests_area", "consultation_requests", ["area"])
    op.create_index("ix_consultation_requests_status", "consultation_requests", ["status"])
    op.create_index(
        "ix_consultation_requests_area_created",
        "consultation_requests",
        ["area", "created_at"],
    )
    op.create_index(
        "ix_consultation_requests_status_created",
        "consultation_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_consultation_requests_status_created", table_name="consultation_requests")
    op.drop_index("ix_consultation_requests_area_created", table_name="consultation_requests")
    op.drop_index("ix_consultation_requests_status", table_name="consultation_requests")
    op.drop_index("ix_consultation_requests_area", table_name="consultation_requests")
    op.drop_table("consultation_requests")


__all__ = ["downgrade", "upgrade"]