"""Billing API (MASTER_PROMPT V3).

Reading and drafting are staff work; **issuing and voiding are not**. Those two are
behind their own permissions, so a lawyer can prepare a bill and an administrator
decides what leaves the building. The separation is the whole reason the module can
be given to the front desk without giving it the power to quote the firm.

No route here accepts a total. The client sends concepts and the server derives the
money, which is why `InvoiceCreate` and `InvoiceUpdate` have no such field.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_user_scope, require_permission
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import Case, Invoice, User
from app.schemas.billing import (
    AgingReport,
    InvoiceCreate,
    InvoiceIssue,
    InvoiceResponse,
    InvoiceUpdate,
    InvoiceVoid,
    PaginatedInvoices,
    PaymentCreate,
    PaymentResponse,
)
from app.services.billing import BillingError, BillingService
from app.services.cases import CaseScope, case_scoped, scope_filter

router = APIRouter(prefix="/billing", tags=["billing"])


def _fail(error: BillingError) -> HTTPException:
    return HTTPException(
        status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada"
    )


def _response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        number=invoice.number,
        client_id=invoice.client_id,
        client_name=invoice.client.full_name if invoice.client else None,
        case_id=invoice.case_id,
        case_number=invoice.case.case_number if invoice.case else None,
        status=invoice.status,
        issued_at=invoice.issued_at,
        due_at=invoice.due_at,
        tax_rate=invoice.tax_rate,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total=invoice.total,
        paid_amount=invoice.paid_amount,
        balance=invoice.balance,
        notes=invoice.notes,
        void_reason=invoice.void_reason,
        voided_at=invoice.voided_at,
        created_by=invoice.created_by,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        lines=[line for line in invoice.lines],
        payments=[payment for payment in invoice.payments],
    )


async def _clause(
    session: AsyncSession, actor: User, scope: CaseScope
) -> ColumnElement[bool] | None:
    """What the caller may see of the invoice book.

    `None` means "everything", which is what `CaseScope.ALL` resolves to.

    An invoice carrying a `case_id` is bound to that expediente and is filtered on
    it. An invoice with **no** `case_id` is firm-wide, and stays visible to whoever
    holds `invoices:read`. That is a deliberate decision rather than an oversight:
    billing is charged to a client, not to a file, and several workflows legitimately
    produce expediente-less invoices. `test_a_firm_wide_invoice_is_not_case_scoped`
    pins it so a later change to a stricter reading is a visible decision.

    The tighter alternative, hiding them too, was rejected because it broke
    `test_staff_drafts_but_neither_issues_nor_voids`: the front desk drafts an
    expediente-less invoice and then got 404 instead of the 422 that explains a
    draft takes no payment, which is a worse answer than the one it replaced.
    """
    clause = case_scoped(Invoice.case_id, await scope_filter(session, actor, scope))
    if clause is None:
        return None
    return or_(Invoice.case_id.is_(None), clause)


async def _require_case_in_scope(
    session: AsyncSession, actor: User, scope: CaseScope, case_id: UUID | None
) -> None:
    """Refuse to bill an expediente the caller may not see.

    Without this, creating an invoice against somebody else's `case_id` produces a
    row the caller then cannot read, while still attaching a bill to that client's
    file. Writing is not covered by the read scope.
    """
    if case_id is None or scope is CaseScope.ALL:
        return
    clause = await scope_filter(session, actor, scope)
    if clause is None:
        return
    allowed = await session.execute(
        select(Case.id).where(Case.id == case_id, clause)
    )
    if not allowed.all():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a ese expediente",
        )


async def _require(
    session: AsyncSession,
    invoice_id: UUID,
    *,
    scope_clause: ColumnElement[bool] | None,
) -> Invoice:
    invoice = await BillingService(session).get(
        invoice_id, scope_clause=scope_clause
    )
    if invoice is None:
        raise _not_found()
    return invoice


@router.get("/invoices", response_model=PaginatedInvoices)
async def list_invoices(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    search: Annotated[str | None, Query(max_length=200)] = None,
    invoice_status: Annotated[
        str | None, Query(alias="status", max_length=20)
    ] = None,
    client_id: Annotated[UUID | None, Query()] = None,
    case_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedInvoices:
    invoices, total = await BillingService(session).list_invoices(
        skip,
        limit,
        scope_clause=await _clause(session, actor, scope),
        search=search,
        status=invoice_status,
        client_id=client_id,
        case_id=case_id,
    )
    return PaginatedInvoices(
        items=[_response(invoice) for invoice in invoices],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/aging", response_model=AgingReport)
async def aging(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> AgingReport:
    """What is owed and how late. The buckets an accountant asks for, in order."""
    buckets = await BillingService(session).aging(
        scope_clause=await _clause(session, actor, scope)
    )
    return AgingReport(**buckets)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def read_invoice(
    invoice_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> InvoiceResponse:
    return _response(
        await _require(session, invoice_id, scope_clause=await _clause(session, actor, scope))
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> InvoiceResponse:
    service = BillingService(session)
    await _require_case_in_scope(session, actor, scope, payload.case_id)
    try:
        invoice = await service.create_invoice(
            client_id=payload.client_id,
            actor=actor,
            case_id=payload.case_id,
            notes=payload.notes,
            tax_rate=payload.tax_rate,
            due_at=payload.due_at,
            lines=payload.lines,
        )
    except BillingError as error:
        raise _fail(error) from error
    await session.commit()
    return _response(invoice)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:update"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> InvoiceResponse:
    service = BillingService(session)
    invoice = await _require(
        session, invoice_id, scope_clause=await _clause(session, actor, scope)
    )
    try:
        if payload.lines is not None:
            await service.replace_lines(invoice, payload.lines, actor)
        updated = await service.update_invoice(
            invoice,
            actor=actor,
            notes=payload.notes,
            tax_rate=payload.tax_rate,
            due_at=payload.due_at,
            case_id=payload.case_id,
        )
    except BillingError as error:
        raise _fail(error) from error
    await session.commit()
    return _response(updated)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: UUID,
    payload: InvoiceIssue,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:issue"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> InvoiceResponse:
    """Send the invoice to the client. Administrator only.

    After this the concepts are frozen: a bill that changed after it was quoted is
    a bill the firm cannot explain.
    """
    service = BillingService(session)
    invoice = await _require(
        session, invoice_id, scope_clause=await _clause(session, actor, scope)
    )
    try:
        issued = await service.issue(invoice, actor, payload.issued_at)
    except BillingError as error:
        raise _fail(error) from error
    await session.commit()
    return _response(issued)


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice(
    invoice_id: UUID,
    payload: InvoiceVoid,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:void"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> InvoiceResponse:
    """Cancel an issued invoice. The number stays and the reason is mandatory."""
    service = BillingService(session)
    invoice = await _require(
        session, invoice_id, scope_clause=await _clause(session, actor, scope)
    )
    try:
        voided = await service.void_invoice(invoice, actor, payload.reason)
    except BillingError as error:
        raise _fail(error) from error
    await session.commit()
    return _response(voided)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_payment(
    invoice_id: UUID,
    payload: PaymentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("payments:create"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> PaymentResponse:
    """Record money received. The status follows the balance, not the request."""
    service = BillingService(session)
    invoice = await _require(
        session, invoice_id, scope_clause=await _clause(session, actor, scope)
    )
    try:
        payment = await service.record_payment(invoice, payload, actor)
    except BillingError as error:
        raise _fail(error) from error
    await session.commit()
    return PaymentResponse.model_validate(payment)


@router.get("/invoices/{invoice_id}/history")
async def invoice_history(
    invoice_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("invoices:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    await _require(session, invoice_id, scope_clause=await _clause(session, actor, scope))
    entries = await BillingService(session).history(invoice_id, limit)
    return [
        {
            "field_name": entry.field_name,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "change_reason": entry.change_reason,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in entries
    ]


__all__ = [
    "aging",
    "create_invoice",
    "invoice_history",
    "issue_invoice",
    "list_invoices",
    "read_invoice",
    "register_payment",
    "router",
    "update_invoice",
    "void_invoice",
]
