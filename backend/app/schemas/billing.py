"""Schemas for billing (MASTER_PROMPT V3).

**There is no `total` field on any write schema, and that is the point.** A browser
that can send a total can send any total. What the client sends is concepts
(description, quantity, unit price) and the server derives the money; `total`
appears only on responses, where it is something the firm is quoting rather than
something the browser is asserting.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

InvoiceStatus = Literal["borrador", "emitida", "pagada", "anulada"]
PaymentMethod = Literal["efectivo", "transferencia", "tarjeta", "cheque"]


class InvoiceLineInput(BaseModel):
    description: str = Field(min_length=3, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    @field_validator("description")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("El concepto es demasiado corto")
        return cleaned


class InvoiceCreate(BaseModel):
    client_id: UUID
    case_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    #: Zero means "no tax applied". The rate is the firm's to bring, not a default.
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, max_digits=5, decimal_places=4)
    due_at: date | None = None
    lines: list[InvoiceLineInput] = Field(default_factory=list)


class InvoiceUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    tax_rate: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=5, decimal_places=4
    )
    due_at: date | None = None
    case_id: UUID | None = None
    #: The whole concept list is replaced, not patched: a bill is read as a whole.
    lines: list[InvoiceLineInput] | None = None


class InvoiceIssue(BaseModel):
    issued_at: date | None = None


class InvoiceVoid(BaseModel):
    #: Mandatory, and the service refuses an empty one. An unexplained void cannot
    #: be explained to an accountant six months later.
    reason: str = Field(min_length=5, max_length=1000)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    method: PaymentMethod = "transferencia"
    paid_at: date = Field(default_factory=date.today)
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    method: PaymentMethod
    paid_at: date
    reference: str | None
    notes: str | None
    recorded_by: UUID | None
    created_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    client_id: UUID
    client_name: str | None = None
    case_id: UUID | None
    case_number: str | None = None
    status: InvoiceStatus
    issued_at: date | None
    due_at: date | None
    tax_rate: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    #: Derived from the payments, never stored.
    paid_amount: Decimal
    balance: Decimal
    notes: str | None
    void_reason: str | None
    voided_at: datetime | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineResponse]
    payments: list[PaymentResponse]


class PaginatedInvoices(BaseModel):
    items: list[InvoiceResponse]
    total: int
    skip: int
    limit: int


class AgingReport(BaseModel):
    """What is owed and how late it is, in the buckets an accountant asks for."""

    vigente: Decimal
    d1_30: Decimal = Field(alias="1_30")
    d31_60: Decimal = Field(alias="31_60")
    d61_90: Decimal = Field(alias="61_90")
    mas_90: Decimal

    model_config = ConfigDict(populate_by_name=True)


__all__ = [
    "AgingReport",
    "InvoiceCreate",
    "InvoiceIssue",
    "InvoiceLineInput",
    "InvoiceLineResponse",
    "InvoiceResponse",
    "InvoiceStatus",
    "InvoiceUpdate",
    "InvoiceVoid",
    "PaginatedInvoices",
    "PaymentCreate",
    "PaymentMethod",
    "PaymentResponse",
]
