"""Billing: invoices, their lines and the payments received (MASTER_PROMPT V3).

Three rules carry the module:

1. **The browser never sends a total.** It sends concepts; `subtotal`,
   `tax_amount` and `total` are recomputed here on every write. A total that
   arrives from the client is a number somebody typed, and a bill whose number can
   be typed is not a bill.
2. **`Decimal`, never a float.** Every column is `Numeric(14, 2)` and every
   computation goes through `Decimal`. `0.1 + 0.2` is `0.30000000000000004` in
   binary, and a ledger that drifts by cents cannot be reconciled at the end of a
   month, which is the only time anybody looks at it.
3. **Nothing is deleted.** `void` keeps the number and demands a reason. A number
   that was issued and later vanished cannot be explained to an accountant, and
   that explanation is the whole reason the ledger exists (ADR-051).
"""

import logging
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ChangeLog,
    Client,
    Invoice,
    InvoiceLine,
    InvoiceNumberSequence,
    Payment,
    User,
)
from app.schemas.billing import InvoiceLineInput, PaymentCreate
from app.services.history import record_changes

logger = logging.getLogger(__name__)

INVOICE_ENTITY = "invoices"
PAYMENT_ENTITY = "payments"

#: Every money amount is rounded to cents at the moment it is computed, with
#: ROUND_HALF_UP because that is the convention on an invoice. Rounding at the end
#: instead of at each step is how a total ends up a cent away from the sum of the
#: lines printed above it.
CENTS = Decimal("0.01")

#: Lines whose sum rounds to zero are refused: an invoice with nothing on it is a
#: row someone will later ask about.
ZERO_TOLERANCE = Decimal("0.005")

TRACKED_INVOICE_FIELDS = (
    "client_id",
    "case_id",
    "status",
    "issued_at",
    "due_at",
    "tax_rate",
    "notes",
    "subtotal",
    "tax_amount",
    "total",
    "void_reason",
)

#: The columns a refresh is allowed to reload.
#:
#: `session.refresh(invoice)` with no argument expires **everything**, relationships
#: included, and the next read of `invoice.payments` becomes a lazy load — from
#: `balance`, a plain `@property`, which is synchronous, which raises
#: `MissingGreenlet` and turns a bookkeeping call into a 500. This is the same trap
#: as the `updated_at` of a setting, one level deeper.
INVOICE_SCALARS = (
    "number",
    "status",
    "issued_at",
    "due_at",
    "tax_rate",
    "subtotal",
    "tax_amount",
    "total",
    "notes",
    "void_reason",
    "voided_at",
    "voided_by",
    "created_at",
    "updated_at",
)


class BillingError(Exception):
    """Raised when a billing request cannot be honoured."""


def money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- numbering -------------------------------------------------------

    async def next_number(self, year: int) -> str:
        """Allocate `FE-AAAA-NNNNNN`.

        The counter is a table row locked with `FOR UPDATE`, the same shape
        `CaseService` uses for `WA-AAAA-000001`. An in-process counter would hand
        two invoices the same number the moment two requests overlapped, and a
        duplicated invoice number is the one billing error that is never
        recoverable.
        """
        result = await self.session.execute(
            select(InvoiceNumberSequence)
            .where(InvoiceNumberSequence.year == year)
            .with_for_update()
        )
        sequence = result.scalar_one_or_none()

        if sequence is None:
            sequence = InvoiceNumberSequence(year=year, last_number=0)
            self.session.add(sequence)
            await self.session.flush()
            # Re-read under the lock: the insert above may have raced another
            # transaction that inserted the same year.
            sequence = (
                await self.session.execute(
                    select(InvoiceNumberSequence)
                    .where(InvoiceNumberSequence.year == year)
                    .with_for_update()
                )
            ).scalar_one()

        sequence.last_number += 1
        await self.session.flush()
        return f"FE-{year}-{sequence.last_number:06d}"

    # --- totals ----------------------------------------------------------

    async def recalculate(self, invoice: Invoice) -> Invoice:
        """Recompute line totals, subtotal, tax and total from the lines.

        Called after every change to the lines or to the rate. The stored totals
        are a cache of this, never an input.
        """
        subtotal = Decimal("0")
        for position, line in enumerate(invoice.lines):
            line.position = position
            line.line_total = money(line.quantity * line.unit_price)
            subtotal += line.line_total

        tax = money(subtotal * invoice.tax_rate)
        invoice.subtotal = money(subtotal)
        invoice.tax_amount = tax
        invoice.total = money(subtotal + tax)
        return invoice

    async def _settle_status(self, invoice: Invoice) -> None:
        """Derive `pagada` from the payments, never from a request.

        A status written by hand is a claim about money; the payments are the
        money. When the two disagree the ledger is the one that has to move.

        The sum is a query rather than a walk over `invoice.payments` for two
        reasons: an instance created in this session has no payments loaded and
        touching the relationship would be a lazy load, which `AsyncSession`
        refuses; and the ledger is the authority even when the row in hand is not
        the freshest thing to have touched it.
        """
        if invoice.status in ("borrador", "anulada"):
            return
        paid = await self.session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice.id
            )
        )
        balance = invoice.total - Decimal(paid or 0)
        if balance <= ZERO_TOLERANCE:
            invoice.status = "pagada"
        elif invoice.status == "pagada":
            invoice.status = "emitida"

    async def _reloaded(self, invoice: Invoice) -> Invoice:
        """Return the invoice with everything the response needs already loaded.

        The API serialises into a plain Pydantic model from a **synchronous**
        function, so every relationship it touches has to be in hand. `refresh`
        without arguments expires relationships, and touching an expired one is a
        lazy load that `AsyncSession` refuses with `MissingGreenlet`. Re-querying
        with `selectinload` makes "the returned invoice is complete" a guarantee of
        this method rather than a coincidence of what the caller happened to do.
        """
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.id == invoice.id)
            .options(
                selectinload(Invoice.client),
                selectinload(Invoice.case),
                selectinload(Invoice.lines),
                selectinload(Invoice.payments),
            )
        )
        return result.scalar_one()

    async def _reloaded_payment(self, payment: Payment) -> Payment:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment.id)
        )
        return result.scalar_one()

    # --- reads -----------------------------------------------------------

    async def list_invoices(
        self,
        skip: int = 0,
        limit: int = 25,
        *,
        scope_clause: ColumnElement[bool] | None,
        search: str | None = None,
        status: str | None = None,
        client_id: UUID | None = None,
        case_id: UUID | None = None,
    ) -> tuple[list[Invoice], int]:
        conditions: list[ColumnElement[bool]] = []
        if scope_clause is not None:
            conditions.append(scope_clause)
        if status:
            conditions.append(Invoice.status == status)
        if client_id:
            conditions.append(Invoice.client_id == client_id)
        if case_id:
            conditions.append(Invoice.case_id == case_id)
        if search:
            needle = f"%{search.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Invoice.number).like(needle),
                    func.lower(func.coalesce(Invoice.notes, "")).like(needle),
                )
            )

        statement = select(Invoice).order_by(Invoice.number.desc())
        if conditions:
            statement = statement.where(*conditions)

        total = await self.session.scalar(
            select(func.count()).select_from(Invoice).where(*conditions)
        )
        result = await self.session.execute(statement.offset(skip).limit(limit))
        return list(result.scalars().all()), int(total or 0)

    async def get(
        self, invoice_id: UUID, *, scope_clause: ColumnElement[bool] | None
    ) -> Invoice | None:
        """Fetch one invoice inside the caller's scope.

        `scope_clause` has no default on purpose. A permissive default here is
        indistinguishable from a correct one in the happy path, and the only test
        that notices is the one where a lawyer reads somebody else's expediente.

        Note that an invoice with `case_id IS NULL` belongs to no expediente, so
        `Invoice.case_id.in_(...)` excludes it: a restricted caller does not see
        firm-wide invoices, while `CaseScope.ALL` passes `None` and still sees
        everything.
        """
        statement = select(Invoice).where(Invoice.id == invoice_id)
        if scope_clause is not None:
            statement = statement.where(scope_clause)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_number(self, number: str) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).where(Invoice.number == number)
        )
        return result.scalar_one_or_none()

    async def aging(
        self, *, scope_clause: ColumnElement[bool] | None
    ) -> dict[str, Decimal]:
        """Money owed, grouped by how late it is.

        The buckets are the ones an accountant asks for in that order, and the sum
        is over `total - SUM(payments)` rather than a stored balance, so it cannot
        drift from the ledger.

        `scope_clause` matters more here than on a list. A restricted caller would
        otherwise get firm-wide totals, which is a leak of the same money one
        invoice at a time, only harder to notice because no row is ever returned.
        """
        conditions: list[ColumnElement[bool]] = [
            Invoice.status.in_(("emitida", "pagada"))
        ]
        if scope_clause is not None:
            conditions.append(scope_clause)
        result = await self.session.execute(select(Invoice).where(*conditions))
        buckets = {
            "vigente": Decimal("0"),
            "1_30": Decimal("0"),
            "31_60": Decimal("0"),
            "61_90": Decimal("0"),
            "mas_90": Decimal("0"),
        }
        today = date.today()
        for invoice in result.scalars():
            balance = invoice.balance
            if balance <= ZERO_TOLERANCE:
                continue
            due = invoice.due_at
            if due is None or due >= today:
                buckets["vigente"] += balance
                continue
            days = (today - due).days
            if days <= 30:
                buckets["1_30"] += balance
            elif days <= 60:
                buckets["31_60"] += balance
            elif days <= 90:
                buckets["61_90"] += balance
            else:
                buckets["mas_90"] += balance
        return {key: money(value) for key, value in buckets.items()}

    # --- writes ----------------------------------------------------------

    async def create_invoice(
        self,
        *,
        client_id: UUID,
        actor: User,
        case_id: UUID | None = None,
        notes: str | None = None,
        tax_rate: Decimal = Decimal("0"),
        due_at: date | None = None,
        lines: list[InvoiceLineInput] | None = None,
    ) -> Invoice:
        client = await self.session.get(Client, client_id)
        if client is None:
            raise BillingError("El cliente no existe")

        # The number is allocated **before** the insert, because `number` is NOT
        # NULL and the flush that persists the row would go out without it. It does
        # not depend on the invoice id, so there is nothing to wait for.
        number = await self.next_number(date.today().year)
        invoice = Invoice(
            number=number,
            client_id=client_id,
            case_id=case_id,
            notes=notes,
            tax_rate=tax_rate,
            due_at=due_at,
            status="borrador",
            created_by=actor.id,
        )
        self.session.add(invoice)
        await self.session.flush()

        # The lines are added with the foreign key set rather than appended to the
        # relationship. `AsyncSession` does not allow an implicit lazy load, and
        # `invoice.lines.append(...)` on a freshly inserted row is exactly one —
        # `lazy="selectin"` populates on *query*, not on an instance already in
        # hand. The `refresh` below then loads the collection properly.
        await self._write_lines(invoice, lines or [])
        await self.recalculate(invoice)

        record_changes(
            self.session,
            entity=INVOICE_ENTITY,
            entity_id=invoice.id,
            before={},
            after={
                "client_id": str(client_id),
                "total": str(invoice.total),
                "status": invoice.status,
            },
            changed_by=actor.id,
            fields=TRACKED_INVOICE_FIELDS,
            reason="Factura creada",
        )
        await self.session.flush()
        return await self._reloaded(invoice)

    async def _write_lines(
        self, invoice: Invoice, lines: list[InvoiceLineInput]
    ) -> Invoice:
        """Replace the concepts of an invoice and reload them into the instance.

        Deleting by query rather than `invoice.lines.clear()` for the same reason
        as above: clearing touches the relationship, which is a lazy load.
        """
        await self.session.execute(
            delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        )
        await self.session.flush()
        for entry in lines:
            self.session.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    description=entry.description,
                    quantity=entry.quantity,
                    unit_price=entry.unit_price,
                )
            )
        await self.session.flush()
        await self.session.refresh(invoice, attribute_names=["lines"])
        return invoice

    async def replace_lines(
        self, invoice: Invoice, lines: list[InvoiceLineInput], actor: User
    ) -> Invoice:
        """Swap the concepts and recompute.

        Replaced rather than patched: a bill is read as a whole, and a concept
        changed from one hour to three hours is not an edit anybody can audit by
        looking at the difference.
        """
        if invoice.status != "borrador":
            raise BillingError(
                "Una factura emitida ya no cambia sus conceptos. Anúlela y emita "
                "otra: el número emitido no se reutiliza."
            )

        before = {"total": str(invoice.total), "subtotal": str(invoice.subtotal)}
        await self._write_lines(invoice, lines)
        await self.recalculate(invoice)

        record_changes(
            self.session,
            entity=INVOICE_ENTITY,
            entity_id=invoice.id,
            before=before,
            after={"total": str(invoice.total), "subtotal": str(invoice.subtotal)},
            changed_by=actor.id,
            fields=TRACKED_INVOICE_FIELDS,
            reason="Conceptos actualizados",
        )
        await self.session.flush()
        return await self._reloaded(invoice)

    async def update_invoice(
        self,
        invoice: Invoice,
        *,
        actor: User,
        notes: str | None = None,
        tax_rate: Decimal | None = None,
        due_at: date | None = None,
        case_id: UUID | None = None,
    ) -> Invoice:
        """Change the header. Refused once the invoice is out of draft."""
        if invoice.status not in ("borrador",):
            raise BillingError(
                "Una factura emitida no se edita. Anúlela y emita otra."
            )

        before = {field: getattr(invoice, field, None) for field in TRACKED_INVOICE_FIELDS}
        if notes is not None:
            invoice.notes = notes
        if tax_rate is not None:
            invoice.tax_rate = tax_rate
        if due_at is not None:
            invoice.due_at = due_at
        invoice.case_id = case_id

        await self.recalculate(invoice)
        record_changes(
            self.session,
            entity=INVOICE_ENTITY,
            entity_id=invoice.id,
            before=before,
            after={
                "notes": invoice.notes,
                "tax_rate": str(invoice.tax_rate),
                "due_at": invoice.due_at.isoformat() if invoice.due_at else None,
                "case_id": str(invoice.case_id) if invoice.case_id else None,
                "total": str(invoice.total),
            },
            changed_by=actor.id,
            fields=TRACKED_INVOICE_FIELDS,
            reason="Factura actualizada",
        )
        await self.session.flush()
        return await self._reloaded(invoice)

    async def issue(self, invoice: Invoice, actor: User, issued_at: date | None = None) -> Invoice:
        """Send the invoice to the client. The point of no return for the lines."""
        if invoice.status != "borrador":
            raise BillingError(f"Una factura en estado «{invoice.status}» no se emite.")
        if not invoice.lines:
            raise BillingError("Una factura sin conceptos no se emite.")

        before = {field: getattr(invoice, field, None) for field in TRACKED_INVOICE_FIELDS}
        invoice.status = "emitida"
        invoice.issued_at = issued_at or date.today()
        await self._settle_status(invoice)

        record_changes(
            self.session,
            entity=INVOICE_ENTITY,
            entity_id=invoice.id,
            before=before,
            after={
                "status": invoice.status,
                "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None,
            },
            changed_by=actor.id,
            fields=TRACKED_INVOICE_FIELDS,
            reason="Factura emitida",
        )
        await self.session.flush()
        return await self._reloaded(invoice)

    async def void_invoice(self, invoice: Invoice, actor: User, reason: str) -> Invoice:
        """Cancel an issued invoice, keeping its number and demanding a reason."""
        if invoice.status == "anulada":
            raise BillingError("La factura ya está anulada.")
        if not reason.strip():
            raise BillingError("Una anulación necesita un motivo.")

        before = {field: getattr(invoice, field, None) for field in TRACKED_INVOICE_FIELDS}
        invoice.status = "anulada"
        invoice.void_reason = reason.strip()
        invoice.voided_at = datetime.now(UTC)
        invoice.voided_by = actor.id

        record_changes(
            self.session,
            entity=INVOICE_ENTITY,
            entity_id=invoice.id,
            before=before,
            after={"status": "anulada", "void_reason": invoice.void_reason},
            changed_by=actor.id,
            fields=TRACKED_INVOICE_FIELDS,
            reason="Factura anulada",
        )
        await self.session.flush()
        return await self._reloaded(invoice)

    async def record_payment(
        self, invoice: Invoice, payload: PaymentCreate, actor: User
    ) -> Payment:
        """Record money in and let the balance decide the status."""
        if invoice.status == "borrador":
            raise BillingError(
                "Una factura en borrador no admite pagos: emítala primero."
            )
        if invoice.status == "anulada":
            raise BillingError("Una factura anulada no admite pagos.")
        if payload.amount <= ZERO_TOLERANCE:
            raise BillingError("El pago debe ser un importe mayor que cero.")

        payment = Payment(
            invoice_id=invoice.id,
            amount=money(payload.amount),
            method=payload.method,
            paid_at=payload.paid_at,
            reference=payload.reference,
            notes=payload.notes,
            recorded_by=actor.id,
        )
        self.session.add(payment)
        invoice.payments.append(payment)
        await self.session.flush()

        before_status = invoice.status
        await self._settle_status(invoice)
        record_changes(
            self.session,
            entity=PAYMENT_ENTITY,
            entity_id=payment.id,
            before={},
            after={
                "amount": str(payment.amount),
                "method": payment.method,
                "paid_at": payment.paid_at.isoformat(),
            },
            changed_by=actor.id,
            fields=("amount", "method", "paid_at"),
            reason="Pago registrado",
        )
        if invoice.status != before_status:
            record_changes(
                self.session,
                entity=INVOICE_ENTITY,
                entity_id=invoice.id,
                before={"status": before_status},
                after={"status": invoice.status},
                changed_by=actor.id,
                fields=TRACKED_INVOICE_FIELDS,
                reason="Estado derivado del saldo",
            )
        await self.session.flush()
        return await self._reloaded_payment(payment)

    async def history(self, invoice_id: UUID, limit: int = 50) -> list[ChangeLog]:
        result = await self.session.execute(
            select(ChangeLog)
            .where(
                ChangeLog.entity == INVOICE_ENTITY,
                ChangeLog.entity_id == invoice_id,
            )
            .order_by(ChangeLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


__all__ = [
    "CENTS",
    "INVOICE_ENTITY",
    "PAYMENT_ENTITY",
    "TRACKED_INVOICE_FIELDS",
    "ZERO_TOLERANCE",
    "BillingError",
    "BillingService",
    "money",
]
