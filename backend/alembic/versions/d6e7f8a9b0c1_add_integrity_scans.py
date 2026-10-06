"""Add integrity verification history.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrity_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("backend", sa.String(length=50), nullable=False),
        sa.Column("checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ok_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corrupted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unreadable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphaned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("check_orphans", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integrity_scans_status"), "integrity_scans", ["status"], unique=False
    )
    # Supports the administrative report of the most recent runs.
    op.create_index(
        "ix_integrity_scans_started_at",
        "integrity_scans",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "integrity_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_type", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("actual_sha256", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["integrity_scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integrity_findings_finding_type"),
        "integrity_findings",
        ["finding_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_integrity_findings_scan_id"),
        "integrity_findings",
        ["scan_id"],
        unique=False,
    )
    # Lookup by version, used when an administrator investigates one document.
    op.create_index(
        "ix_integrity_findings_version_id",
        "integrity_findings",
        ["version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_integrity_findings_version_id", table_name="integrity_findings")
    op.drop_index(op.f("ix_integrity_findings_scan_id"), table_name="integrity_findings")
    op.drop_index(
        op.f("ix_integrity_findings_finding_type"), table_name="integrity_findings"
    )
    op.drop_table("integrity_findings")

    op.drop_index("ix_integrity_scans_started_at", table_name="integrity_scans")
    op.drop_index(op.f("ix_integrity_scans_status"), table_name="integrity_scans")
    op.drop_table("integrity_scans")