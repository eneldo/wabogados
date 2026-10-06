"""Add media_derivatives and media_processing_jobs for the multimedia pipeline.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-10-05

Why this migration exists: ADR-055 left transcoding, thumbnails, measured
duration and large-file processing as the four things the library still lacked,
and every one of them needs somewhere to put its output or its pending work.
There was no table for either, and `evidence_processing_jobs` cannot hold them:
its `evidence_id` is NOT NULL, and the whole point of ADR-055 is that a library
asset is **not** evidence.

These tables are storage and bookkeeping only. Nothing writes to them yet; the
service that does is the next piece, and this migration is the floor it stands on.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_derivatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # One derivative per kind per asset: regenerating replaces the row instead
        # of accumulating copies nobody will ever list.
        sa.UniqueConstraint("media_id", "kind", name="uq_media_derivative_kind"),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0", name="ck_media_derivative_size"
        ),
    )
    op.create_index("ix_media_derivative_media", "media_derivatives", ["media_id"])

    op.create_table(
        "media_processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(length=40), server_default="process", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("worker", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_media_job_attempts"),
    )
    # The worker claims with `status IN ('queued','running') ORDER BY created_at`,
    # so the index has to be on that pair and not on the column alone.
    op.create_index("ix_media_job_status", "media_processing_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_media_job_status", table_name="media_processing_jobs")
    op.drop_table("media_processing_jobs")
    op.drop_index("ix_media_derivative_media", table_name="media_derivatives")
    op.drop_table("media_derivatives")