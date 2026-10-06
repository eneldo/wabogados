"""Add the media_items table for the multimedia library (V4).

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: str | Sequence[str] | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_items",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="activo", nullable=False
        ),
        sa.Column(
            "confidentiality",
            sa.String(length=20),
            server_default="interno",
            nullable=False,
        ),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        # Unique so two rows can never claim the same object, which would make
        # deactivating one of them hide the other's file.
        sa.Column("storage_key", sa.String(length=500), unique=True, nullable=True),
        sa.Column("storage_tier", sa.String(length=20), server_default="hot", nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # `is_active` is the deactivation record (ADR-051): no delete anywhere, and
        # this is what a deactivation writes instead of removing the row.
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0", name="ck_media_size"
        ),
    )
    op.create_index("ix_media_items_kind", "media_items", ["kind"])
    op.create_index("ix_media_items_status", "media_items", ["status"])
    op.create_index(
        "ix_media_items_confidentiality", "media_items", ["confidentiality"]
    )
    op.create_index("ix_media_items_case_id", "media_items", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_media_items_case_id", table_name="media_items")
    op.drop_index("ix_media_items_confidentiality", table_name="media_items")
    op.drop_index("ix_media_items_status", table_name="media_items")
    op.drop_index("ix_media_items_kind", table_name="media_items")
    op.drop_table("media_items")


__all__ = ["downgrade", "upgrade"]
