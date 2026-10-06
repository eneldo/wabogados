"""Add timestamps required by identity models.

Revision ID: f19a2c4d7e10
Revises: cf07e9bac335
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f19a2c4d7e10"
down_revision: str | Sequence[str] | None = "cf07e9bac335"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "permissions",
    "roles",
    "audit_logs",
    "role_permissions",
    "user_roles",
)


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_column(table_name, "updated_at")
