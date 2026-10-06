"""Seed `evidences:update`, the permission `PATCH /evidences/{id}` already required.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-10-05

Found by the 2026-10-05 audit: `PATCH /api/v1/evidences/{evidence_id}` has required
`evidences:update` since the module was written, and that name was **never in the
catalog**. Not in the definition list, not in the role matrix, not in the database.
So the endpoint answered 403 for every profile except a superuser, and no test
noticed because none of them ever called it.

It fails closed, so it was not a leak — it was a route that could not be used. The
alternative was deleting the route, and that would have been worse: editing
evidence metadata is real work the firm needs.

Granted to the same operational roles that already hold `evidences:classify` and
`evidences:archive`, because "may change the metadata" is the union of those. The
finer-grained permissions are still the ones that matter for the sensitive part:
`evidences:publish_to_client` remains separate and is *not* what this migration
relaxes.
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.security.permissions import (
    PermissionDefinition,
    get_permission_definitions,
    get_permissions_for_role,
)

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The client role is deliberately absent. A client may *see* published evidence;
#: it never edits it.
ROLES = ("administrador", "abogado", "asistente")

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.Uuid),
    sa.column("name", sa.String),
    sa.column("resource", sa.String),
    sa.column("action", sa.String),
    sa.column("description", sa.Text),
)


def _owned() -> list[PermissionDefinition]:
    return [
        definition
        for definition in get_permission_definitions()
        if definition.name == "evidences:update"
    ]


def upgrade() -> None:
    connection = op.get_bind()

    for definition in _owned():
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

    for role in ROLES:
        if "evidences:update" not in get_permissions_for_role(role):
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = :role AND p.name = 'evidences:update'
                ON CONFLICT DO NOTHING
                """
            ),
            {"role": role},
        )


def downgrade() -> None:
    """Remove only what this migration added.

    The permission row goes with the grants, because leaving a catalog entry that
    no role holds would make `test_every_catalog_permission_reaches_the_database`
    fail against a database that no longer has it.
    """
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE name = 'evidences:update'
            )
            """
        )
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE name = 'evidences:update'")
    )