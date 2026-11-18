"""One-use recovery tokens and encrypted durable mail outbox.

Revision ID: ff60718293a4
Revises: fe5f60718293
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ff60718293a4"
down_revision: str | Sequence[str] | None = "fe5f60718293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    timestamp = sa.DateTime(timezone=True)
    op.add_column("users", sa.Column("recovery_invalidated_at", timestamp, nullable=True))
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email_digest", sa.String(64), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("expires_at", timestamp, nullable=False),
        sa.Column("used_at", timestamp, nullable=True),
        sa.Column("revoked_at", timestamp, nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    op.create_index(
        "uq_password_reset_live_user",
        "password_reset_tokens",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_table(
        "password_recovery_outbox",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "token_id",
            uuid,
            sa.ForeignKey("password_reset_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("expires_at", timestamp, nullable=False),
        sa.Column("next_attempt_at", timestamp, nullable=False),
        sa.Column("lease_id", uuid, nullable=True),
        sa.Column("leased_until", timestamp, nullable=True),
        sa.Column("sent_at", timestamp, nullable=True),
        sa.Column("last_error", sa.String(40), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','ready','sent','cancelled','failed')",
            name="ck_recovery_mail_status",
        ),
    )
    op.create_index("ix_password_recovery_outbox_user_id", "password_recovery_outbox", ["user_id"])
    op.create_index(
        "ix_recovery_mail_due", "password_recovery_outbox", ["status", "next_attempt_at"]
    )
    op.create_index("ix_recovery_mail_expires", "password_recovery_outbox", ["expires_at"])


def downgrade() -> None:
    op.drop_table("password_recovery_outbox")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "recovery_invalidated_at")
