"""Add the billing tables for Fase V3 (MASTER_PROMPT "Futuro", facturación).

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_number_sequences",
        sa.Column("year", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
    )

    op.create_table(
        "invoices",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        # Unique because the number is what a client is quoted and what an
        # accountant reconciles; two rows sharing one is not recoverable.
        sa.Column("number", sa.String(length=20), unique=True, nullable=False),
        # RESTRICT, not CASCADE: a client with invoices cannot be deleted out from
        # under them, and neither can a case. Both would destroy billing history.
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="borrador", nullable=False
        ),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("due_at", sa.Date(), nullable=True),
        # 0 means "no tax applied". Writing a real rate here would be asserting the
        # firm's tax position on its behalf, so the rate is data, not a default.
        sa.Column(
            "tax_rate",
            sa.Numeric(precision=5, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "subtotal", sa.Numeric(14, 2), server_default="0", nullable=False
        ),
        sa.Column(
            "tax_amount", sa.Numeric(14, 2), server_default="0", nullable=False
        ),
        sa.Column("total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "voided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoice_subtotal_positive"),
        sa.CheckConstraint("tax_rate >= 0", name="ck_invoice_tax_rate_positive"),
    )
    op.create_index("ix_invoices_number", "invoices", ["number"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_case_id", "invoices", ["case_id"])
    op.create_index("ix_invoices_status_issued", "invoices", ["status", "issued_at"])

    op.create_table(
        "invoice_lines",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        # CASCADE here is the one place it belongs: the lines have no meaning
        # without their invoice, and an invoice is never deleted anyway.
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(12, 2), server_default="1", nullable=False
        ),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "line_total", sa.Numeric(14, 2), server_default="0", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_invoice_line_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_invoice_line_price_positive"
        ),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "payments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        # RESTRICT: a payment that removes its invoice would take the money with it.
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "method",
            sa.String(length=30),
            server_default="transferencia",
            nullable=False,
        ),
        sa.Column(
            # `CURRENT_DATE` rather than a Python default: the database stamps the
            # payment date, so a row inserted by a script outside the ORM is dated
            # the same way as one inserted by the service.
            "paid_at",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Money in is always positive. A refund is an invoice, so "total received"
        # stays a plain sum with no sign convention to remember.
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("idx_payments_method", "payments", ["method"])


def downgrade() -> None:
    op.drop_index("idx_payments_method", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_status_issued", table_name="invoices")
    op.drop_index("ix_invoices_case_id", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_number", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("invoice_number_sequences")


__all__ = ["downgrade", "upgrade"]
