"""Seed messaging permissions for Fase 8.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-10-01
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.security.permissions import get_permission_definitions, get_permissions_for_role

revision: str = "b0c1d2e3f4a5"
down_revision: str | Sequence[str] | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("administrador", "abogado", "asistente", "cliente")
MESSAGE_PREFIXES = ("messages:", "notifications:")

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("resource", sa.String),
    sa.column("action", sa.String),
    sa.column("description", sa.Text),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    connection = op.get_bind()

    for definition in get_permission_definitions():
        exists = connection.scalar(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.name == definition.name
            )
        )
        if exists is not None:
            continue
        connection.execute(
            permissions_table.insert().values(
                id=uuid4(),
                name=definition.name,
                resource=definition.resource,
                action=definition.action,
                description=definition.description,
            )
        )

    for role_name in ROLES:
        names = [
            permission
            for permission in get_permissions_for_role(role_name)
            if permission.startswith(MESSAGE_PREFIXES)
        ]
        for permission_name in names:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions
                        (role_id, permission_id, assigned_at, created_at, updated_at)
                    SELECT r.id, p.id, now(), now(), now()
                    FROM roles r, permissions p
                    WHERE r.name = :role_name AND p.name = :permission_name
                    ON CONFLICT DO NOTHING
                    """
                ).bindparams(role_name=role_name, permission_name=permission_name)
            )


def downgrade() -> None:
    connection = op.get_bind()
    names = [
        definition.name
        for definition in get_permission_definitions()
        if definition.name.startswith(MESSAGE_PREFIXES)
    ]

    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name = ANY(CAST(:names AS text[])))"
        ),
        {"names": names},
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE name = ANY(CAST(:names AS text[]))"),
        {"names": names},
    )


__all__ = ["downgrade", "upgrade"]