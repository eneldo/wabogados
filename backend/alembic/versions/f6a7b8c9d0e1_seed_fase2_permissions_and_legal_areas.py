"""Seed legal areas and extend the RBAC matrix for Fase 2.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-30
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.security.permissions import (
    ROLE_DEFINITIONS,
    get_legal_areas,
    get_permission_definitions,
    get_permissions_for_role,
)

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", sa.Uuid),
    sa.column("permission_id", sa.Uuid),
    sa.column("assigned_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

legal_areas_table = sa.table(
    "legal_areas",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("is_active", sa.Boolean),
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

    for role_name in _role_names():
        for permission_name in get_permissions_for_role(role_name):
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

    for name, description in get_legal_areas():
        exists = connection.scalar(
            sa.select(legal_areas_table.c.id).where(legal_areas_table.c.name == name)
        )
        if exists is not None:
            continue
        connection.execute(
            legal_areas_table.insert().values(
                id=uuid4(),
                name=name,
                description=description,
                is_active=True,
            )
        )


def _role_names() -> tuple[str, ...]:
    return tuple(ROLE_DEFINITIONS)


def downgrade() -> None:
    connection = op.get_bind()
    names = [definition.name for definition in get_permission_definitions()]

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
    connection.execute(
        sa.text("DELETE FROM legal_areas WHERE name = ANY(CAST(:names AS text[]))"),
        {"names": [name for name, _ in get_legal_areas()]},
    )


__all__ = ["downgrade", "upgrade"]
