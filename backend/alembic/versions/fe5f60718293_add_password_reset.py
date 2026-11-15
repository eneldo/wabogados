"""Credential version and dedicated administrative password reset permission.

Revision ID: fe5f60718293
Revises: fd4e5f607182
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "fe5f60718293"
down_revision: str | Sequence[str] | None = "fd4e5f607182"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (id, name, resource, action, description) "
            "VALUES (:id, 'users:reset_password', 'users', 'reset_password', "
            "'Restablecer contraseñas de otros usuarios') ON CONFLICT (name) DO NOTHING"
        ),
        {"id": uuid4()},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions "
            "(role_id, permission_id, assigned_at, created_at, updated_at) "
            "SELECT r.id, p.id, now(), now(), now() FROM roles r, permissions p "
            "WHERE r.name = 'administrador' AND p.name = 'users:reset_password' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name = 'users:reset_password')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE name = 'users:reset_password'"))
    op.drop_column("users", "token_version")
