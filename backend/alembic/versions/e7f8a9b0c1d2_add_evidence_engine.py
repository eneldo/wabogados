"""Add the evidence engine: 6 tables for chain of custody and processing.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="uploaded"
        ),
        sa.Column(
            "visibility", sa.String(length=20), nullable=False, server_default="interna"
        ),
        sa.Column(
            "confidentiality",
            sa.String(length=20),
            nullable=False,
            server_default="interno",
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("original_mime_type", sa.String(length=120), nullable=True),
        sa.Column("original_size", sa.BigInteger(), nullable=True),
        sa.Column("original_sha256", sa.String(length=64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_location", sa.String(length=255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_signed_pdf", sa.Boolean(), nullable=False, server_default=sa.false()
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidences_evidence_type"), "evidences", ["evidence_type"])
    op.create_index(op.f("ix_evidences_status"), "evidences", ["status"])
    op.create_index(op.f("ix_evidences_visibility"), "evidences", ["visibility"])
    op.create_index(
        op.f("ix_evidences_confidentiality"), "evidences", ["confidentiality"]
    )
    op.create_index(op.f("ix_evidences_original_sha256"), "evidences", ["original_sha256"])
    # Serves the 360 view and the per case list.
    op.create_index("ix_evidences_case_status", "evidences", ["case_id", "status"])

    op.create_table(
        "evidence_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("is_original", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "is_signed_pdf", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "signature_broken", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_files_evidence_id"), "evidence_files", ["evidence_id"]
    )
    op.create_index(op.f("ix_evidence_files_sha256"), "evidence_files", ["sha256"])
    # "At most one original per evidence", enforced by the database rather than
    # by application code, because two originals is a legal error. The predicate
    # is essential: a plain UNIQUE(evidence_id, is_original) would also cap the
    # number of non original rows at one.
    op.create_index(
        "uq_evidence_single_original",
        "evidence_files",
        ["evidence_id"],
        unique=True,
        postgresql_where=sa.text("is_original"),
    )

    op.create_table(
        "evidence_derivatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("derivative_type", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("compression_ratio", sa.Float(), nullable=True),
        sa.Column("profile", sa.String(length=30), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["evidence_files.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_derivatives_evidence_id"),
        "evidence_derivatives",
        ["evidence_id"],
    )
    op.create_index(
        op.f("ix_evidence_derivatives_derivative_type"),
        "evidence_derivatives",
        ["derivative_type"],
    )
    op.create_index(
        op.f("ix_evidence_derivatives_sha256"),
        "evidence_derivatives",
        ["sha256"],
    )

    op.create_table(
        "evidence_processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="queued"
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("worker", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_processing_jobs_evidence_id"),
        "evidence_processing_jobs",
        ["evidence_id"],
    )
    op.create_index(
        op.f("ix_evidence_processing_jobs_job_type"),
        "evidence_processing_jobs",
        ["job_type"],
    )
    # Serves the worker polling the queue.
    op.create_index(
        "ix_evidence_processing_jobs_status_created",
        "evidence_processing_jobs",
        ["status", "created_at"],
    )

    op.create_table(
        "evidence_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("access_type", sa.String(length=20), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["evidence_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_access_logs_evidence_id"),
        "evidence_access_logs",
        ["evidence_id"],
    )
    op.create_index(
        op.f("ix_evidence_access_logs_access_type"),
        "evidence_access_logs",
        ["access_type"],
    )

    op.create_table(
        "evidence_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_value", sa.String(length=255), nullable=True),
        sa.Column("to_value", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evidence_events_evidence_id"), "evidence_events", ["evidence_id"]
    )
    op.create_index(
        op.f("ix_evidence_events_event_type"), "evidence_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_events_event_type"), table_name="evidence_events")
    op.drop_index(op.f("ix_evidence_events_evidence_id"), table_name="evidence_events")
    op.drop_table("evidence_events")

    op.drop_index(
        op.f("ix_evidence_access_logs_access_type"), table_name="evidence_access_logs"
    )
    op.drop_index(
        op.f("ix_evidence_access_logs_evidence_id"), table_name="evidence_access_logs"
    )
    op.drop_table("evidence_access_logs")

    op.drop_index(
        "ix_evidence_processing_jobs_status_created",
        table_name="evidence_processing_jobs",
    )
    op.drop_index(
        op.f("ix_evidence_processing_jobs_job_type"),
        table_name="evidence_processing_jobs",
    )
    op.drop_index(
        op.f("ix_evidence_processing_jobs_evidence_id"),
        table_name="evidence_processing_jobs",
    )
    op.drop_table("evidence_processing_jobs")

    op.drop_index(op.f("ix_evidence_derivatives_sha256"), table_name="evidence_derivatives")
    op.drop_index(
        op.f("ix_evidence_derivatives_derivative_type"), table_name="evidence_derivatives"
    )
    op.drop_index(
        op.f("ix_evidence_derivatives_evidence_id"), table_name="evidence_derivatives"
    )
    op.drop_table("evidence_derivatives")

    op.drop_index(op.f("ix_evidence_files_sha256"), table_name="evidence_files")
    op.drop_index(op.f("ix_evidence_files_evidence_id"), table_name="evidence_files")
    op.drop_index("uq_evidence_single_original", table_name="evidence_files")
    op.drop_table("evidence_files")

    op.drop_index("ix_evidences_case_status", table_name="evidences")
    op.drop_index(op.f("ix_evidences_original_sha256"), table_name="evidences")
    op.drop_index(op.f("ix_evidences_confidentiality"), table_name="evidences")
    op.drop_index(op.f("ix_evidences_visibility"), table_name="evidences")
    op.drop_index(op.f("ix_evidences_status"), table_name="evidences")
    op.drop_index(op.f("ix_evidences_evidence_type"), table_name="evidences")
    op.drop_table("evidences")