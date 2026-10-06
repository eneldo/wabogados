"""Billing (MASTER_PROMPT V3).

The assertions that matter here are about money, and each one is a thing that can
go wrong in a way a status code will not show:

- a total that arrives from the browser,
- a rate of tax invented by a migration,
- a payment that marks an invoice paid without covering it,
- a number issued twice,
- a voided invoice that no longer explains itself.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseLawyer, ChangeLog, Client, Invoice, Lawyer, User
from app.schemas.billing import InvoiceLineInput, PaymentCreate
from app.services.billing import (
    INVOICE_ENTITY,
    BillingError,
    BillingService,
    money,
)

BILLING = "/api/v1/billing"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _line(
    description: str = "Consultoría", quantity: str = "2", price: str = "150000"
) -> InvoiceLineInput:
    return InvoiceLineInput(
        description=description, quantity=Decimal(quantity), unit_price=Decimal(price)
    )


async def _invoice(
    client: AsyncClient,
    token: str,
    client_id: UUID,
    case_id: UUID | None = None,
    total: str = "150000.00",
) -> dict[str, Any]:
    created = await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(client_id),
            "case_id": str(case_id) if case_id else None,
            "lines": [
                {
                    "description": "Honorarios",
                    "quantity": "1",
                    "unit_price": total,
                }
            ],
        },
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    return cast(dict[str, Any], created.json())


async def _assign_second_lawyer(
    database_session: AsyncSession, second_lawyer: Lawyer, case: Case
) -> None:
    """Make the case belong to the second lawyer.

    `CaseLawyer` is the row `assigned_case_ids` reads, so this is what turns a
    case from invisible into visible for that user.
    """
    database_session.add(
        CaseLawyer(
            case_id=case.id,
            lawyer_id=second_lawyer.id,
            role="titular",
            assigned_at=datetime.now(UTC),
        )
    )
    await database_session.flush()


# --- scope ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_invoice_of_an_unassigned_case_is_not_readable(
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """`invoices:read` was the only gate, so any lawyer could read any invoice.

    The billing router had no `get_user_scope` dependency at all. A user holding
    the permission but assigned to no case could read, list, amend and issue an
    invoice belonging to somebody else's expediente, because the permission says
    what you may do with billing and never said which billing.
    """
    _, token = second_lawyer_token
    invoice = await _invoice(client, admin_token, sample_client.id, other_case.id)

    response = await client.get(
        f"{BILLING}/invoices/{invoice['id']}", headers=_auth(token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unassigned_invoices_stay_out_of_the_list(
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """A restricted list that still leaks rows is a leak with extra steps."""
    _, token = second_lawyer_token
    mine = await _invoice(client, admin_token, sample_client.id, other_case.id)

    response = await client.get(f"{BILLING}/invoices", headers=_auth(token))

    assert response.status_code == 200
    assert mine["id"] not in {item["id"] for item in response.json()["items"]}


@pytest.mark.asyncio
async def test_an_invoice_of_your_own_case_is_readable(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    sample_client: Client,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """The counterpart, and the one that would catch a scope filter with no hole.

    Once the endpoints filter, the risk stops being the filter and becomes the
    filter being too tight, which would quietly break the firm's work while every
    security test stayed green.
    """
    second_lawyer, token = second_lawyer_token
    await _assign_second_lawyer(database_session, second_lawyer, sample_case)
    invoice = await _invoice(client, admin_token, sample_client.id, sample_case.id)

    response = await client.get(
        f"{BILLING}/invoices/{invoice['id']}", headers=_auth(token)
    )

    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_a_firm_wide_invoice_is_not_case_scoped(
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """An invoice with no `case_id` stays readable by any holder of the permission.

    This is the one place where the fix deliberately stops, and it is pinned so that
    tightening it later is a decision somebody makes rather than an accident. Billing
    is charged to a client, not to a file, and `invoices:read` is already the gate for
    these rows. If the firm ever decides expediente-less invoices must also be
    restricted, this test is what should be argued with first.
    """
    _, token = second_lawyer_token
    invoice = await _invoice(client, admin_token, sample_client.id)

    response = await client.get(
        f"{BILLING}/invoices/{invoice['id']}", headers=_auth(token)
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_creating_against_a_foreign_case_is_refused(
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """Write access needs the scope too, not only reads.

    Otherwise a restricted caller attaches a bill to somebody else's expediente and
    receives a row they can no longer open, which is both a data problem and a way to
    write into another client's file.
    """
    _, token = second_lawyer_token

    response = await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(sample_client.id),
            "case_id": str(other_case.id),
            "lines": [
                {"description": "Honorarios", "quantity": "1", "unit_price": "90000"}
            ],
        },
        headers=_auth(token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_an_administrator_still_sees_every_invoice(
    client: AsyncClient,
    admin_token: str,
    sample_client: Client,
    other_case: Case,
) -> None:
    """Scope must not quietly become a global restriction.

    An administrator with no case assignments would answer 404 on everything if
    the scope were applied where `CaseScope.ALL` means "no clause".
    """
    invoice = await _invoice(client, admin_token, sample_client.id, other_case.id)

    response = await client.get(
        f"{BILLING}/invoices/{invoice['id']}", headers=_auth(admin_token)
    )

    assert response.status_code == 200


# --- money ----------------------------------------------------------------


def test_money_rounds_half_up_to_cents() -> None:
    """Rounding a fee is a convention, and the convention is round half up."""
    assert money(Decimal("150000.005")) == Decimal("150000.01")
    assert money(Decimal("0.1")) + money(Decimal("0.2")) == money(Decimal("0.3"))


@pytest.mark.asyncio
async def test_totals_are_derived_and_never_received(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    """A browser that can send a total can send any total.

    The write schemas have no such field, so this is asserted the only way it can
    be: a payload carrying one is either ignored or refused, and the returned
    total is the arithmetic of the lines.
    """
    created = await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(sample_client.id),
            "tax_rate": "0.1900",
            "lines": [
                {"description": "Analisis", "quantity": "2", "unit_price": "150000.00"},
                {"description": "Redaccion", "quantity": "1", "unit_price": "800000.50"},
            ],
            # A client trying to be helpful. It must not reach the ledger.
            "total": "1",
            "subtotal": "1",
        },
        headers=_auth(admin_token),
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["subtotal"] == "1100000.50"
    assert payload["tax_amount"] == "209000.10"
    assert payload["total"] == "1309000.60"


@pytest.mark.asyncio
async def test_the_tax_rate_defaults_to_zero_and_says_so(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    """The rate is a fact about the firm. A migration does not get to assert it."""
    created = await client.post(
        f"{BILLING}/invoices",
        json={"client_id": str(sample_client.id), "lines": [_line().model_dump(mode="json")]},
        headers=_auth(admin_token),
    )

    assert created.status_code == 201
    payload = created.json()
    # Compared as a number, not as text: how PostgreSQL renders a `0` in a
    # `Numeric(5, 4)` column is a formatting detail, and the fact that matters is
    # that no tax was applied.
    assert Decimal(payload["tax_rate"]) == Decimal("0")
    assert Decimal(payload["tax_amount"]) == Decimal("0")


# --- numbering ------------------------------------------------------------


@pytest.mark.asyncio
async def test_numbers_are_sequential_and_unique(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    year = date.today().year

    first = await service.create_invoice(client_id=sample_client.id, actor=admin_user)
    second = await service.create_invoice(client_id=sample_client.id, actor=admin_user)

    assert first.number == f"FE-{year}-000001"
    assert second.number == f"FE-{year}-000002"


@pytest.mark.asyncio
async def test_an_invoice_without_a_client_is_refused(
    database_session: AsyncSession, admin_user: User
) -> None:
    service = BillingService(database_session)

    with pytest.raises(BillingError):
        await service.create_invoice(client_id=uuid4(), actor=admin_user)


# --- lifecycle ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_draft_keeps_its_concepts_editable(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    draft = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )

    updated = await service.replace_lines(
        draft,
        [_line("Revision", quantity="3", price="120000")],
        admin_user,
    )

    assert updated.total == Decimal("360000.00")
    assert len(updated.lines) == 1
    assert updated.lines[0].description == "Revision"


@pytest.mark.asyncio
async def test_an_issued_invoice_freezes_its_concepts(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    """After it is quoted, a bill cannot quietly change."""
    service = BillingService(database_session)
    invoice = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )
    issued = await service.issue(invoice, admin_user)

    with pytest.raises(BillingError):
        await service.replace_lines(issued, [_line("Otro", price="1")], admin_user)

    assert issued.status == "emitida"


@pytest.mark.asyncio
async def test_an_empty_invoice_is_not_issued(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    empty = await service.create_invoice(client_id=sample_client.id, actor=admin_user)

    with pytest.raises(BillingError):
        await service.issue(empty, admin_user)


@pytest.mark.asyncio
async def test_voiding_keeps_the_number_and_demands_a_reason(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    """The reason a void exists: an unexplained void cannot be audited later."""
    service = BillingService(database_session)
    invoice = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )
    issued = await service.issue(invoice, admin_user)
    number = issued.number

    with pytest.raises(BillingError):
        await service.void_invoice(issued, admin_user, "   ")

    voided = await service.void_invoice(issued, admin_user, "Error en el honored")
    assert voided.status == "anulada"
    assert voided.number == number
    assert voided.void_reason == "Error en el honored"
    assert voided.voided_at is not None
    assert voided.voided_by == admin_user.id

    result = await database_session.execute(
        select(ChangeLog).where(
            ChangeLog.entity == INVOICE_ENTITY,
            ChangeLog.entity_id == voided.id,
            ChangeLog.field_name == "status",
        )
    )
    reasons = {row.change_reason for row in result.scalars()}
    assert "Factura anulada" in reasons


# --- payments -------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_status_follows_the_balance_and_not_the_request(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    """A partial payment leaves the invoice issued; a full one marks it paid."""
    service = BillingService(database_session)
    invoice = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )
    issued = await service.issue(invoice, admin_user)
    assert issued.total == Decimal("300000.00")

    partial = await service.record_payment(
        issued, PaymentCreate(amount=Decimal("100000")), admin_user
    )
    assert partial.amount == Decimal("100000.00")
    assert issued.status == "emitida"
    assert issued.balance == Decimal("200000.00")

    await service.record_payment(issued, PaymentCreate(amount=Decimal("200000")), admin_user)
    assert issued.status == "pagada"
    assert issued.balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_a_draft_takes_no_payment(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    draft = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )

    with pytest.raises(BillingError):
        await service.record_payment(draft, PaymentCreate(amount=Decimal("1")), admin_user)


@pytest.mark.asyncio
async def test_a_voided_invoice_takes_no_payment(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    invoice = await service.create_invoice(
        client_id=sample_client.id, actor=admin_user, lines=[_line()]
    )
    issued = await service.issue(invoice, admin_user)
    voided = await service.void_invoice(issued, admin_user, "Cliente se retira")

    with pytest.raises(BillingError):
        await service.record_payment(
            voided, PaymentCreate(amount=Decimal("1000")), admin_user
        )


@pytest.mark.asyncio
async def test_a_zero_payment_is_refused_by_the_schema(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    """Money in is always positive: a refund is an invoice, not a negative receipt.

    The schema is the first line of defence and refuses it before the request ever
    reaches the service, so the assertion is on the 422 envelope rather than on a
    service exception. The `BillingService` guard behind it exists for callers that
    do not go through HTTP at all.
    """
    created = await client.post(
        f"{BILLING}/invoices",
        json={"client_id": str(sample_client.id), "lines": [_line().model_dump(mode="json")]},
        headers=_auth(admin_token),
    )
    issued = await client.post(
        f"{BILLING}/invoices/{created.json()['id']}/issue",
        json={},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200

    refused = await client.post(
        f"{BILLING}/invoices/{created.json()['id']}/payments",
        json={"amount": "0"},
        headers=_auth(admin_token),
    )

    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_aging_groups_the_money_that_is_late(
    database_session: AsyncSession, admin_user: User, sample_client: Client
) -> None:
    service = BillingService(database_session)
    today = date.today()

    async def issued(due_in_days: int, price: str = "100000") -> Invoice:
        invoice = await service.create_invoice(
            client_id=sample_client.id,
            actor=admin_user,
            # One unit, so a bucket holds one invoice's total and the numbers below
            # are readable at a glance.
            lines=[
                InvoiceLineInput(
                    description="Honorarios",
                    quantity=Decimal("1"),
                    unit_price=Decimal(price),
                )
            ],
            due_at=today + timedelta(days=due_in_days),
        )
        return await service.issue(invoice, admin_user)

    await issued(10)
    await issued(-10)
    await issued(-45)

    buckets = await service.aging(scope_clause=None)

    assert buckets["vigente"] == Decimal("100000.00")
    assert buckets["1_30"] == Decimal("100000.00")
    assert buckets["31_60"] == Decimal("100000.00")
    assert buckets["mas_90"] == Decimal("0")


# --- API and permissions --------------------------------------------------


@pytest.mark.asyncio
async def test_a_client_never_sees_the_ledger(
    client: AsyncClient, portal_token: str
) -> None:
    """A firm's invoice is not published here, and `total` says what the matter is
    worth to whoever is on the other side of it."""
    assert (await client.get(f"{BILLING}/invoices", headers=_auth(portal_token))).status_code == 403
    assert (await client.get(f"{BILLING}/aging", headers=_auth(portal_token))).status_code == 403
    assert (await client.get(f"{BILLING}/invoices")).status_code == 401


@pytest.mark.asyncio
async def test_staff_drafts_but_neither_issues_nor_voids(
    client: AsyncClient, staff_token: str, sample_client: Client
) -> None:
    """The front desk prepares the bill; an administrator decides what leaves.

    Also the assertion that `test_operational_roles_cannot_delete` cannot make:
    it only looks at permissions ending in `:delete`, and `invoices:issue` and
    `invoices:void` do not end that way. Without this test the matrix can hand a
    lawyer the power to issue and the RBAC suite stays green.
    """
    from app.security.permissions import get_permissions_for_role

    for role in ("abogado", "asistente", "cliente"):
        held = set(get_permissions_for_role(role))
        assert "invoices:issue" not in held, role
        assert "invoices:void" not in held, role
    assert {"invoices:issue", "invoices:void"} <= set(
        get_permissions_for_role("administrador")
    )

    created = await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(sample_client.id),
            "lines": [{"description": "Revision", "quantity": "1", "unit_price": "90000"}],
        },
        headers=_auth(staff_token),
    )
    assert created.status_code == 201
    invoice_id = created.json()["id"]

    payment = await client.post(
        f"{BILLING}/invoices/{invoice_id}/payments",
        json={"amount": "1000"},
        headers=_auth(staff_token),
    )
    # A draft takes no payment: the refusal is the module's, not the permission's.
    assert payment.status_code == 422

    issued = await client.post(
        f"{BILLING}/invoices/{invoice_id}/issue", json={}, headers=_auth(staff_token)
    )
    assert issued.status_code == 403
    assert issued.json()["error"]["message"] == "Permiso requerido: invoices:issue"

    voided = await client.post(
        f"{BILLING}/invoices/{invoice_id}/void",
        json={"reason": "No era el cliente"},
        headers=_auth(staff_token),
    )
    assert voided.status_code == 403


@pytest.mark.asyncio
async def test_the_full_lifecycle_over_http(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    created = await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(sample_client.id),
            "due_at": (date.today() + timedelta(days=30)).isoformat(),
            "notes": "Honorarios de la primera fase",
            "lines": [
                {"description": "Consultoria", "quantity": "4", "unit_price": "250000"},
                {"description": "Gastos", "quantity": "1", "unit_price": "45000.50"},
            ],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    invoice = created.json()
    assert invoice["status"] == "borrador"
    assert invoice["balance"] == invoice["total"]
    assert [line["position"] for line in invoice["lines"]] == [0, 1]

    issued = await client.post(
        f"{BILLING}/invoices/{invoice['id']}/issue",
        json={},
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "emitida"
    assert issued.json()["issued_at"] is not None

    paid = await client.post(
        f"{BILLING}/invoices/{invoice['id']}/payments",
        json={"amount": "1045000.50", "method": "transferencia", "reference": "TRF-99"},
        headers=_auth(admin_token),
    )
    assert paid.status_code == 201

    final = await client.get(
        f"{BILLING}/invoices/{invoice['id']}", headers=_auth(admin_token)
    )
    assert final.json()["status"] == "pagada"
    assert final.json()["balance"] == "0.00"

    voided = await client.post(
        f"{BILLING}/invoices/{invoice['id']}/void",
        json={"reason": "Cobro duplicado por error de teclado"},
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "anulada"
    assert voided.json()["number"] == invoice["number"]


@pytest.mark.asyncio
async def test_the_listing_filters_and_rejects_a_page_past_the_end(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    await client.post(
        f"{BILLING}/invoices",
        json={
            "client_id": str(sample_client.id),
            # The search covers the number and the notes; a concept is not part of
            # the header, so the phrase that has to be findable lives in the notes.
            "notes": "Honorarios fase 1",
            "lines": [_line().model_dump(mode="json")],
        },
        headers=_auth(admin_token),
    )

    found = await client.get(f"{BILLING}/invoices?search=fase", headers=_auth(admin_token))
    assert found.status_code == 200
    assert found.json()["total"] == 1

    assert (
        await client.get(f"{BILLING}/invoices?status=anulada", headers=_auth(admin_token))
    ).json()["total"] == 0
    assert (
        await client.get(f"{BILLING}/invoices?limit=500", headers=_auth(admin_token))
    ).status_code == 422


@pytest.mark.asyncio
async def test_an_unknown_invoice_is_a_404(
    client: AsyncClient, admin_token: str
) -> None:
    missing = uuid4()
    assert (
        await client.get(f"{BILLING}/invoices/{missing}", headers=_auth(admin_token))
    ).status_code == 404
    assert (
        await client.get(f"{BILLING}/invoices/{missing}/history", headers=_auth(admin_token))
    ).status_code == 404


@pytest.mark.asyncio
async def test_the_history_is_readable(
    client: AsyncClient, admin_token: str, sample_client: Client
) -> None:
    created = await client.post(
        f"{BILLING}/invoices",
        json={"client_id": str(sample_client.id), "lines": [_line().model_dump(mode="json")]},
        headers=_auth(admin_token),
    )
    await client.post(
        f"{BILLING}/invoices/{created.json()['id']}/issue",
        json={},
        headers=_auth(admin_token),
    )

    history = await client.get(
        f"{BILLING}/invoices/{created.json()['id']}/history", headers=_auth(admin_token)
    )

    assert history.status_code == 200
    reasons = {entry["change_reason"] for entry in history.json()}
    assert "Factura creada" in reasons
    assert "Factura emitida" in reasons
