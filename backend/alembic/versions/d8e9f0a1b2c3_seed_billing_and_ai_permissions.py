"""Seed the billing and legal-AI permissions.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-04

`test_every_catalog_permission_reaches_the_database` exists because a permission can
be consistent across `permissions.py` and the role matrix and still be absent from
the database: every endpoint that requires it then answers 403 in production, and
only the test fixture hides it by seeding the row itself. This revision is the
difference between the two modules working and answering 403 everywhere.
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.security.permissions import get_permission_definitions, get_permissions_for_role

revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Only the permissions this migration owns. Anything else belongs to another
#: revision, and deleting it here would corrupt unrelated state.
PREFIXES = ("invoices:", "payments:", "ai:")

#: The client role is deliberately absent from all three resources. A firm's
#: invoice is not published to the portal in this scope, and a legal-AI index that
#: a client could reach would hand them the whole firm's material by relevance
#: search. Adding either here would break the exact permission set that
#: `test_client_role_only_sees_published_own_data` pins.
ROLES = ("administrador", "abogado", "asistente")

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("resource", sa.String),
    sa.column("action", sa.String),
    sa.column("description", sa.Text),
)


def _owned() -> list[str]:
    return [
        definition.name
        for definition in get_permission_definitions()
        if definition.name.startswith(PREFIXES)
    ]


def upgrade() -> None:
    connection = op.get_bind()

    for definition in get_permission_definitions():
        if not definition.name.startswith(PREFIXES):
            continue
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
        for permission_name in get_permissions_for_role(role_name):
            if not permission_name.startswith(PREFIXES):
                continue
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
    names = _owned()
    if not names:
        return

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
