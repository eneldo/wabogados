"""Add legal_analyses table for Thought Leadership.

Revision ID: f9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-10-22
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = ("f8a9b0c1d2e3", "b2c3d4e5f6a7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    (
        "analyses:read",
        "analyses",
        "read",
        "Consultar análisis jurídicos",
    ),
    (
        "analyses:create",
        "analyses",
        "create",
        "Crear análisis jurídicos",
    ),
    (
        "analyses:update",
        "analyses",
        "update",
        "Actualizar análisis jurídicos",
    ),
    (
        "analyses:delete",
        "analyses",
        "delete",
        "Desactivar análisis jurídicos",
    ),
]

ROLE_GRANTS = {
    "administrador": [
        "analyses:read",
        "analyses:create",
        "analyses:update",
        "analyses:delete",
    ],
    "abogado": ["analyses:read", "analyses:create"],
    "asistente": ["analyses:read"],
}


def upgrade() -> None:
    op.create_table(
        "legal_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_legal_analyses_slug", "legal_analyses", ["slug"], unique=True)
    op.create_index(
        "ix_legal_analyses_published",
        "legal_analyses",
        ["is_published", "published_at"],
    )

    connection = op.get_bind()
    for name, resource, action, description in PERMISSIONS:
        exists = connection.scalar(
            sa.text("SELECT id FROM permissions WHERE name = :name"), {"name": name}
        )
        if exists is None:
            connection.execute(
                sa.text(
                    "INSERT INTO permissions (id, name, resource, action, description,"
                    " created_at, updated_at) "
                    "VALUES (:id, :name, :resource, :action, :description, now(), now())"
                ),
                {
                    "id": str(uuid4()),
                    "name": name,
                    "resource": resource,
                    "action": action,
                    "description": description,
                },
            )
    for role_name, permission_names in ROLE_GRANTS.items():
        for permission_name in permission_names:
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
                ),
                {"role_name": role_name, "permission_name": permission_name},
            )


def downgrade() -> None:
    connection = op.get_bind()
    names = [p[0] for p in PERMISSIONS]
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
    op.drop_index("ix_legal_analyses_published", table_name="legal_analyses")
    op.drop_index("ix_legal_analyses_slug", table_name="legal_analyses")
    op.drop_table("legal_analyses")