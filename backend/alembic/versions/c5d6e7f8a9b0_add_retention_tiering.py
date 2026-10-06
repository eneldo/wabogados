"""Add version tiering, legal hold and retention audit reason.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | Sequence[str] | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tiering columns. Every existing version starts on the hot tier, which is
    # the conservative choice: nothing is archived implicitly.
    op.add_column(
        "document_versions",
        sa.Column(
            "tier",
            sa.String(length=20),
            nullable=False,
            server_default="hot",
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column("tiered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_document_versions_tier"), "document_versions", ["tier"], unique=False
    )
    # Supports the retention plan: hot, not current, older than the cutoff.
    op.create_index(
        "ix_document_versions_tier_current_created",
        "document_versions",
        ["tier", "is_current", "created_at"],
        unique=False,
    )

    op.add_column(
        "documents",
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "documents",
        sa.Column("legal_hold_reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("legal_hold_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "change_logs",
        sa.Column("change_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("change_logs", "change_reason")

    op.drop_column("documents", "legal_hold_at")
    op.drop_column("documents", "legal_hold_reason")
    op.drop_column("documents", "legal_hold")

    op.drop_index("ix_document_versions_tier_current_created", table_name="document_versions")
    op.drop_index(op.f("ix_document_versions_tier"), table_name="document_versions")
    op.drop_column("document_versions", "tiered_at")
    op.drop_column("document_versions", "tier")
