"""Add cases, case lawyers, case parties and numbering.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATED_AT = sa.Column(
    "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
)
UPDATED_AT = sa.Column(
    "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
)


def upgrade() -> None:
    op.create_table(
        "case_number_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("responsible_lawyer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legal_area_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("process_type", sa.String(length=50), nullable=False),
        sa.Column("jurisdiction", sa.String(length=150), nullable=True),
        sa.Column("court", sa.String(length=200), nullable=True),
        sa.Column("file_number", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("opened_at", sa.Date(), nullable=False),
        sa.Column("closed_at", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        CREATED_AT,
        UPDATED_AT,
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["responsible_lawyer_id"], ["lawyers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["legal_area_id"], ["legal_areas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_number"),
    )
    op.create_index(op.f("ix_cases_case_number"), "cases", ["case_number"], unique=True)
    op.create_index(op.f("ix_cases_process_type"), "cases", ["process_type"], unique=False)
    op.create_index(op.f("ix_cases_status"), "cases", ["status"], unique=False)
    op.create_index(op.f("ix_cases_priority"), "cases", ["priority"], unique=False)
    op.create_index(op.f("ix_cases_file_number"), "cases", ["file_number"], unique=False)
    op.create_index("ix_cases_client_id", "cases", ["client_id"], unique=False)
    op.create_index(
        "ix_cases_status_priority", "cases", ["status", "priority"], unique=False
    )

    op.create_table(
        "case_lawyers",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lawyer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        CREATED_AT,
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lawyer_id"], ["lawyers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("case_id", "lawyer_id"),
    )
    op.create_index(
        "ix_case_lawyers_lawyer_id", "case_lawyers", ["lawyer_id"], unique=False
    )

    op.create_table(
        "case_parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("party_role", sa.String(length=30), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=True),
        sa.Column("document_number", sa.String(length=50), nullable=True),
        sa.Column("is_external", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        CREATED_AT,
        UPDATED_AT,
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_case_parties_party_role"), "case_parties", ["party_role"], unique=False
    )
    op.create_index("ix_case_parties_case_id", "case_parties", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_case_parties_case_id", table_name="case_parties")
    op.drop_index(op.f("ix_case_parties_party_role"), table_name="case_parties")
    op.drop_table("case_parties")

    op.drop_index("ix_case_lawyers_lawyer_id", table_name="case_lawyers")
    op.drop_table("case_lawyers")

    op.drop_index("ix_cases_status_priority", table_name="cases")
    op.drop_index("ix_cases_client_id", table_name="cases")
    op.drop_index(op.f("ix_cases_file_number"), table_name="cases")
    op.drop_index(op.f("ix_cases_priority"), table_name="cases")
    op.drop_index(op.f("ix_cases_status"), table_name="cases")
    op.drop_index(op.f("ix_cases_process_type"), table_name="cases")
    op.drop_index(op.f("ix_cases_case_number"), table_name="cases")
    op.drop_table("cases")

    op.drop_table("case_number_sequences")
