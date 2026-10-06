"""Seed canonical RBAC roles and permissions.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-30
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.security.permissions import (
    ROLE_DEFINITIONS,
    get_permission_definitions,
    get_permissions_for_role,
)

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAMES = tuple(ROLE_DEFINITIONS)


def upgrade() -> None:
    connection = op.get_bind()

    for definition in get_permission_definitions():
        exists = connection.scalar(
            sa.select(sa.text("1")).select_from(sa.table("permissions")).where(
                sa.column("name") == definition.name
            )
        )
        if exists:
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO permissions
                    (id, name, resource, action, description, created_at, updated_at)
                VALUES (:id, :name, :resource, :action, :description, now(), now())
                """
            ).bindparams(
                id=uuid4(),
                name=definition.name,
                resource=definition.resource,
                action=definition.action,
                description=definition.description,
            )
        )

    for role_name, description in ROLE_DEFINITIONS.items():
        exists = connection.scalar(
            sa.select(sa.text("1")).select_from(sa.table("roles")).where(
                sa.column("name") == role_name
            )
        )
        if exists:
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO roles (id, name, description, created_at, updated_at)
                VALUES (:id, :name, :description, now(), now())
                """
            ).bindparams(id=uuid4(), name=role_name, description=description)
        )

    for role_name in ROLE_NAMES:
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


def _delete_where_name_in(statement: str, names: Sequence[str]) -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(statement).bindparams(
            sa.bindparam("names", value=list(names), type_=sa.ARRAY(sa.Text))
        )
    )


def downgrade() -> None:
    _delete_where_name_in(
        "DELETE FROM role_permissions "
        "WHERE role_id IN (SELECT id FROM roles WHERE name = ANY(:names))",
        ROLE_NAMES,
    )
    _delete_where_name_in("DELETE FROM roles WHERE name = ANY(:names)", ROLE_NAMES)
    _delete_where_name_in(
        "DELETE FROM permissions WHERE name = ANY(:names)",
        [definition.name for definition in get_permission_definitions()],
    )


__all__ = ["downgrade", "upgrade"]
