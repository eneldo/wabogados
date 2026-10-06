"""Add clients, lawyers, legal areas and change history.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_COLUMN = sa.Column(
    "created_at",
    sa.DateTime(timezone=True),
    server_default=sa.text("now()"),
    nullable=False,
)
UPDATED_AT_COLUMN = sa.Column(
    "updated_at",
    sa.DateTime(timezone=True),
    server_default=sa.text("now()"),
    nullable=False,
)


def upgrade() -> None:
    op.create_table(
        "legal_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        TIMESTAMP_COLUMN,
        UPDATED_AT_COLUMN,
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_legal_areas_name"), "legal_areas", ["name"], unique=True)

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_type", sa.String(length=20), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("document_number", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("commercial_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        TIMESTAMP_COLUMN,
        UPDATED_AT_COLUMN,
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_type", "document_number", name="uq_client_document"),
    )
    op.create_index(op.f("ix_clients_client_type"), "clients", ["client_type"], unique=False)
    op.create_index(
        op.f("ix_clients_document_number"), "clients", ["document_number"], unique=False
    )
    op.create_index(op.f("ix_clients_email"), "clients", ["email"], unique=False)
    op.create_index(
        "ix_clients_type_status", "clients", ["client_type", "is_active"], unique=False
    )

    op.create_table(
        "lawyers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("document_number", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("professional_card", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("specialties", postgresql.ARRAY(sa.String(length=150)), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        TIMESTAMP_COLUMN,
        UPDATED_AT_COLUMN,
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_type", "document_number", name="uq_lawyer_document"),
        sa.UniqueConstraint("professional_card"),
    )
    op.create_index(
        op.f("ix_lawyers_document_number"), "lawyers", ["document_number"], unique=False
    )
    op.create_index(op.f("ix_lawyers_email"), "lawyers", ["email"], unique=False)
    op.create_index(op.f("ix_lawyers_status"), "lawyers", ["status"], unique=False)
    op.create_index(
        op.f("ix_lawyers_professional_card"), "lawyers", ["professional_card"], unique=True
    )

    op.create_table(
        "lawyer_legal_areas",
        sa.Column("lawyer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_area_id", postgresql.UUID(as_uuid=True), nullable=False),
        TIMESTAMP_COLUMN,
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lawyer_id"], ["lawyers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["legal_area_id"], ["legal_areas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("lawyer_id", "legal_area_id"),
    )

    op.create_table(
        "change_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_change_logs_entity"), "change_logs", ["entity"], unique=False)
    op.create_index(op.f("ix_change_logs_entity_id"), "change_logs", ["entity_id"], unique=False)
    op.create_index(
        "ix_change_logs_entity_entity_id",
        "change_logs",
        ["entity", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_change_logs_entity_entity_id", table_name="change_logs")
    op.drop_index(op.f("ix_change_logs_entity_id"), table_name="change_logs")
    op.drop_index(op.f("ix_change_logs_entity"), table_name="change_logs")
    op.drop_table("change_logs")

    op.drop_table("lawyer_legal_areas")

    op.drop_index(op.f("ix_lawyers_professional_card"), table_name="lawyers")
    op.drop_index(op.f("ix_lawyers_status"), table_name="lawyers")
    op.drop_index(op.f("ix_lawyers_email"), table_name="lawyers")
    op.drop_index(op.f("ix_lawyers_document_number"), table_name="lawyers")
    op.drop_table("lawyers")

    op.drop_index("ix_clients_type_status", table_name="clients")
    op.drop_index(op.f("ix_clients_email"), table_name="clients")
    op.drop_index(op.f("ix_clients_document_number"), table_name="clients")
    op.drop_index(op.f("ix_clients_client_type"), table_name="clients")
    op.drop_table("clients")

    op.drop_index(op.f("ix_legal_areas_name"), table_name="legal_areas")
    op.drop_table("legal_areas")
