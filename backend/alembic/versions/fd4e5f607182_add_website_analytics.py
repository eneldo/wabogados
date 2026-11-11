"""Privacy-minimised website counters and administrator-only reporting.

Revision ID: fd4e5f607182
Revises: fc3d4e5f6071
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "fd4e5f607182"
down_revision: str | Sequence[str] | None = "fc3d4e5f6071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website_analytics_daily",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("page_views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("estimated_visitors", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("phone_clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("consultations", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "website_analytics_pages",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("path", sa.String(180), primary_key=True),
        sa.Column("page_views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("phone_clicks", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "website_analytics_dedup",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_website_analytics_dedup_expires_at",
        "website_analytics_dedup",
        ["expires_at"],
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (id, name, resource, action, description) "
            "VALUES (:id, 'website_analytics:read', 'website_analytics', 'read', "
            "'Consultar estadísticas de la web pública') ON CONFLICT (name) DO NOTHING"
        ),
        {"id": uuid4()},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions "
            "(role_id, permission_id, assigned_at, created_at, updated_at) "
            "SELECT r.id, p.id, now(), now(), now() FROM roles r, permissions p "
            "WHERE r.name = 'administrador' AND p.name = 'website_analytics:read' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name = 'website_analytics:read')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE name = 'website_analytics:read'"))
    op.drop_index("ix_website_analytics_dedup_expires_at", table_name="website_analytics_dedup")
    op.drop_table("website_analytics_dedup")
    op.drop_table("website_analytics_pages")
    op.drop_table("website_analytics_daily")
