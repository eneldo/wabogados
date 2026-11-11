"""Add client requests table and permissions.

Revision ID: fb2c3d4e5f60
Revises: fa1b2c3d4e5f
Create Date: 2026-11-08
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fb2c3d4e5f60"
down_revision: str | Sequence[str] | None = "fa1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    (
        "client_requests:read",
        "client_requests",
        "read",
        "Consultar solicitudes al cliente en expedientes con alcance",
    ),
    (
        "client_requests:create",
        "client_requests",
        "create",
        "Crear solicitudes o tareas para el cliente",
    ),
    (
        "client_requests:update",
        "client_requests",
        "update",
        "Actualizar, revisar o cerrar solicitudes al cliente",
    ),
    (
        "client_requests:respond",
        "client_requests",
        "respond",
        "Responder solicitudes propias como cliente",
    ),
]
ROLE_GRANTS = {
    "administrador": [
        "client_requests:read",
        "client_requests:create",
        "client_requests:update",
        "client_requests:respond",
    ],
    "abogado": ["client_requests:read", "client_requests:create", "client_requests:update"],
    "asistente": ["client_requests:read", "client_requests:create", "client_requests:update"],
    "cliente": ["client_requests:read", "client_requests:respond"],
}


def upgrade() -> None:
    op.create_table(
        "client_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "responded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_client_requests_case_status", "client_requests", ["case_id", "status"])
    op.create_index("ix_client_requests_client_status", "client_requests", ["client_id", "status"])
    op.create_index("ix_client_requests_due_at", "client_requests", ["due_at"])
    op.create_index("ix_client_requests_case_id", "client_requests", ["case_id"])
    op.create_index("ix_client_requests_client_id", "client_requests", ["client_id"])
    op.create_index("ix_client_requests_request_type", "client_requests", ["request_type"])
    op.create_index("ix_client_requests_status", "client_requests", ["status"])

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
    op.drop_index("ix_client_requests_status", table_name="client_requests")
    op.drop_index("ix_client_requests_request_type", table_name="client_requests")
    op.drop_index("ix_client_requests_client_id", table_name="client_requests")
    op.drop_index("ix_client_requests_case_id", table_name="client_requests")
    op.drop_index("ix_client_requests_due_at", table_name="client_requests")
    op.drop_index("ix_client_requests_client_status", table_name="client_requests")
    op.drop_index("ix_client_requests_case_status", table_name="client_requests")
    op.drop_table("client_requests")
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
