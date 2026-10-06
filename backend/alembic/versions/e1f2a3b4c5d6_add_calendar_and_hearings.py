"""Add calendar events and hearings.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
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
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("lawyer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reminder_minutes", sa.Integer(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        CREATED_AT,
        UPDATED_AT,
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lawyer_id"], ["lawyers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calendar_events_event_type"),
        "calendar_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calendar_events_starts_at"),
        "calendar_events",
        ["starts_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calendar_events_visibility"),
        "calendar_events",
        ["visibility"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calendar_events_status"), "calendar_events", ["status"], unique=False
    )
    op.create_index(
        "ix_calendar_events_case_start",
        "calendar_events",
        ["case_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_calendar_events_lawyer_start",
        "calendar_events",
        ["lawyer_id", "starts_at"],
        unique=False,
    )

    op.create_table(
        "hearings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("court", sa.String(length=200), nullable=True),
        sa.Column("courtroom", sa.String(length=100), nullable=True),
        sa.Column("judge", sa.String(length=200), nullable=True),
        sa.Column("procedural_stage", sa.String(length=30), nullable=False),
        sa.Column("file_number", sa.String(length=100), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attendance", sa.String(length=20), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rescheduled_from_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rescheduled_from_id"], ["hearings.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        op.f("ix_hearings_procedural_stage"),
        "hearings",
        ["procedural_stage"],
        unique=False,
    )
    op.create_index(op.f("ix_hearings_status"), "hearings", ["status"], unique=False)
    op.create_index(
        "ix_hearings_case_status", "hearings", ["case_id", "status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_hearings_case_status", table_name="hearings")
    op.drop_index(op.f("ix_hearings_status"), table_name="hearings")
    op.drop_index(op.f("ix_hearings_procedural_stage"), table_name="hearings")
    op.drop_table("hearings")

    op.drop_index("ix_calendar_events_lawyer_start", table_name="calendar_events")
    op.drop_index("ix_calendar_events_case_start", table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_status"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_visibility"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_starts_at"), table_name="calendar_events")
    op.drop_index(op.f("ix_calendar_events_event_type"), table_name="calendar_events")
    op.drop_table("calendar_events")
