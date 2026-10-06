"""Case numbering and access scope for expedientes.

Case numbers follow `WA-AAAA-000001`. The counter lives in its own table and is
locked with ``SELECT ... FOR UPDATE`` so concurrent opens cannot collide.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models import (
    Case,
    CaseLawyer,
    CaseNumberSequence,
    CaseParty,
    ChangeLog,
    Client,
    Lawyer,
    User,
)
from app.schemas.cases import CaseCreate, CaseUpdate
from app.services.history import record_changes

CASE_ENTITY = "cases"

TRACKED_CASE_FIELDS = (
    "title",
    "responsible_lawyer_id",
    "legal_area_id",
    "process_type",
    "jurisdiction",
    "court",
    "file_number",
    "status",
    "priority",
    "closed_at",
    "description",
    "amount",
    "notes",
)

RESPONSIBLE_ROLE = "responsable"
COLLABORATOR_ROLE = "colaborador"


class CaseScope(StrEnum):
    """How much of the case book a caller may see."""

    ALL = "all"
    ASSIGNED = "assigned"
    OWN_PUBLISHED = "own_published"
    NONE = "none"


class CaseError(Exception):
    """Raised when a case operation violates a business rule."""


async def next_case_number(session: AsyncSession, reference: date) -> str:
    """Return the next sequential number for the year of ``reference``."""
    year = reference.year
    result = await session.execute(
        select(CaseNumberSequence)
        .where(CaseNumberSequence.year == year)
        .with_for_update()
    )
    sequence = result.scalar_one_or_none()

    if sequence is None:
        sequence = CaseNumberSequence(year=year, last_number=0)
        session.add(sequence)
        await session.flush()
        sequence = (
            await session.execute(
                select(CaseNumberSequence)
                .where(CaseNumberSequence.year == year)
                .with_for_update()
            )
        ).scalar_one()

    sequence.last_number += 1
    await session.flush()
    return f"WA-{year}-{sequence.last_number:06d}"


async def resolve_scope(session: AsyncSession, user: User) -> CaseScope:
    """Decide the caller's visibility over the case book."""
    from app.api.deps import get_user_permission_names

    permissions = get_user_permission_names(user)
    if user.is_superuser or "cases:read_all" in permissions:
        return CaseScope.ALL
    if "cases:read_assigned" in permissions:
        return CaseScope.ASSIGNED
    if "cases:read_published" in permissions:
        return CaseScope.OWN_PUBLISHED
    return CaseScope.NONE


async def own_client_ids(session: AsyncSession, user: User) -> list[UUID]:
    """Ids of the client records linked to the caller's portal identity."""
    result = await session.execute(
        select(Client.id).where(Client.user_id == user.id, Client.is_active.is_(True))
    )
    return list(result.scalars().all())


async def assigned_case_ids(session: AsyncSession, user: User) -> list[UUID]:
    """Ids of the cases where the user is the responsible lawyer or a collaborator."""
    result = await session.execute(select(Lawyer.id).where(Lawyer.user_id == user.id))
    lawyer_ids = list(result.scalars().all())
    if not lawyer_ids:
        return []

    result = await session.execute(
        select(Case.id).where(
            Case.responsible_lawyer_id.in_(lawyer_ids)
            | Case.id.in_(
                select(CaseLawyer.case_id).where(
                    CaseLawyer.lawyer_id.in_(lawyer_ids)
                )
            )
        )
    )
    return list(result.scalars().all())


def case_scoped(
    case_id_column: InstrumentedAttribute[UUID | None],
    clause: ColumnElement[bool] | None,
) -> ColumnElement[bool] | None:
    """Translate a ``cases`` predicate into a restriction on a child ``case_id``.

    ``scope_filter`` builds predicates over the ``cases`` table. Applying one of
    them directly to a query over a child entity (``calendar_events``,
    ``hearings``) without joining ``cases`` makes SQLAlchemy add ``cases`` as a
    cross product. The predicate then holds whenever *any* case in the table
    matches, which silently disables the scope restriction and leaks rows.

    Wrapping the predicate in a subquery over ``cases.id`` keeps the semantics
    correct and lets PostgreSQL plan it as a semi join.

    A nullable ``case_id`` is handled by SQL rather than here: ``NULL IN (...)`` is
    never true, so a row that belongs to no expediente is excluded from a
    restricted caller and included for ``CaseScope.ALL`` (which passes ``None``).
    That is the desired behaviour for ``Invoice.case_id``, which is nullable on
    purpose, and it is also why the column is typed ``UUID | None`` above.
    """
    if clause is None:
        return None
    return case_id_column.in_(select(Case.id).where(clause))


async def scope_filter(
    session: AsyncSession, user: User, scope: CaseScope
) -> ColumnElement[bool] | None:
    """Return a SQL filter restricting the query to what the caller may see."""
    if scope is CaseScope.ALL:
        return None
    if scope is CaseScope.OWN_PUBLISHED:
        client_ids = await own_client_ids(session, user)
        if not client_ids:
            return literal(False)
        return Case.client_id.in_(client_ids)

    case_ids = await assigned_case_ids(session, user)
    if not case_ids:
        # An explicit false avoids leaking cases through an empty IN list.
        return literal(False)
    return Case.id.in_(case_ids)


class CaseService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_cases(
        self,
        skip: int,
        limit: int,
        *,
        scope_filter_clause: ColumnElement[bool] | None = None,
        include_closed: bool = True,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        legal_area_id: UUID | None = None,
        client_id: UUID | None = None,
    ) -> tuple[list[Case], int]:
        filters: list[ColumnElement[bool]] = [Case.is_active.is_(True)]
        if scope_filter_clause is not None:
            filters.append(scope_filter_clause)
        if not include_closed:
            filters.append(Case.status.notin_(("cerrado", "archivado")))
        if status:
            filters.append(Case.status == status)
        if priority:
            filters.append(Case.priority == priority)
        if legal_area_id:
            filters.append(Case.legal_area_id == legal_area_id)
        if client_id:
            filters.append(Case.client_id == client_id)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                Case.title.ilike(pattern)
                | Case.case_number.ilike(pattern)
                | Case.file_number.ilike(pattern)
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Case).where(*filters)
        )
        result = await self.session.execute(
            select(Case)
            .where(*filters)
            .order_by(Case.opened_at.desc(), Case.case_number.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_case(self, case_id: UUID) -> Case | None:
        return await self.session.get(Case, case_id)

    async def get_by_number(self, case_number: str) -> Case | None:
        result = await self.session.execute(
            select(Case).where(Case.case_number == case_number)
        )
        return result.scalar_one_or_none()

    async def _require_active_client(self, client_id: UUID) -> Client:
        result = await self.session.execute(
            select(Client).where(Client.id == client_id, Client.is_active.is_(True))
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise CaseError("El cliente no existe o está inactivo")
        return client

    async def _require_active_lawyer(self, lawyer_id: UUID) -> Lawyer:
        result = await self.session.execute(
            select(Lawyer).where(Lawyer.id == lawyer_id, Lawyer.is_active.is_(True))
        )
        lawyer = result.scalar_one_or_none()
        if lawyer is None:
            raise CaseError("El abogado no existe o está inactivo")
        return lawyer

    async def create_case(
        self, payload: CaseCreate, *, actor_id: UUID | None = None
    ) -> Case:
        await self._require_active_client(payload.client_id)

        responsible = None
        if payload.responsible_lawyer_id:
            responsible = await self._require_active_lawyer(payload.responsible_lawyer_id)

        case_number = await next_case_number(self.session, payload.opened_at)
        if await self.get_by_number(case_number):
            raise CaseError("No se pudo asignar un número de expediente único")

        case = Case(
            case_number=case_number,
            title=payload.title,
            client_id=payload.client_id,
            responsible_lawyer_id=payload.responsible_lawyer_id,
            legal_area_id=payload.legal_area_id,
            process_type=payload.process_type,
            jurisdiction=payload.jurisdiction,
            court=payload.court,
            file_number=payload.file_number,
            status="abierto",
            priority=payload.priority,
            opened_at=payload.opened_at,
            description=payload.description,
            amount=payload.amount,
            notes=payload.notes,
            is_active=True,
        )
        self.session.add(case)
        await self.session.flush()

        if responsible is not None:
            self.session.add(
                CaseLawyer(
                    case_id=case.id,
                    lawyer_id=responsible.id,
                    role=RESPONSIBLE_ROLE,
                    assigned_by=actor_id,
                )
            )
        record_changes(
            self.session,
            entity=CASE_ENTITY,
            entity_id=case.id,
            before={},
            after={
                **payload.model_dump(),
                "case_number": case_number,
                "status": "abierto",
            },
            changed_by=actor_id,
            fields=(*TRACKED_CASE_FIELDS, "case_number", "status"),
        )
        await self.session.flush()
        return case

    async def update_case(
        self, case: Case, payload: CaseUpdate, *, actor_id: UUID | None = None
    ) -> Case:
        data = payload.model_dump(exclude_unset=True)
        if data.get("client_id") is not None:
            await self._require_active_client(data["client_id"])
        if data.get("responsible_lawyer_id") is not None:
            await self._require_active_lawyer(data["responsible_lawyer_id"])

        before = {field: getattr(case, field, None) for field in TRACKED_CASE_FIELDS}
        for field, value in data.items():
            setattr(case, field, value)

        if data.get("responsible_lawyer_id"):
            await self._set_responsible(case, data["responsible_lawyer_id"], actor_id)
        record_changes(
            self.session,
            entity=CASE_ENTITY,
            entity_id=case.id,
            before=before,
            after=data,
            changed_by=actor_id,
            fields=TRACKED_CASE_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(case)
        return case

    async def _set_responsible(
        self, case: Case, lawyer_id: UUID, actor_id: UUID | None
    ) -> None:
        await self._set_lawyer_role(case, lawyer_id, RESPONSIBLE_ROLE, actor_id)
        result = await self.session.execute(
            select(CaseLawyer).where(
                CaseLawyer.case_id == case.id,
                CaseLawyer.lawyer_id != lawyer_id,
                CaseLawyer.role == RESPONSIBLE_ROLE,
            )
        )
        for stale in result.scalars().all():
            stale.role = COLLABORATOR_ROLE

    async def _set_lawyer_role(
        self, case: Case, lawyer_id: UUID, role: str, actor_id: UUID | None
    ) -> None:
        result = await self.session.execute(
            select(CaseLawyer).where(
                CaseLawyer.case_id == case.id, CaseLawyer.lawyer_id == lawyer_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            self.session.add(
                CaseLawyer(
                    case_id=case.id,
                    lawyer_id=lawyer_id,
                    role=role,
                    assigned_by=actor_id,
                )
            )
        else:
            existing.role = role
        await self.session.flush()

    async def assign_lawyer(
        self, case: Case, lawyer_id: UUID, *, actor_id: UUID | None = None
    ) -> CaseLawyer:
        lawyer = await self._require_active_lawyer(lawyer_id)
        result = await self.session.execute(
            select(CaseLawyer).where(
                CaseLawyer.case_id == case.id, CaseLawyer.lawyer_id == lawyer.id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        assignment = CaseLawyer(
            case_id=case.id,
            lawyer_id=lawyer.id,
            role=COLLABORATOR_ROLE,
            assigned_by=actor_id,
        )
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def revoke_lawyer(self, case: Case, lawyer_id: UUID) -> bool:
        if case.responsible_lawyer_id == lawyer_id:
            raise CaseError("No se puede retirar al abogado responsable")
        result = await self.session.execute(
            select(CaseLawyer).where(
                CaseLawyer.case_id == case.id, CaseLawyer.lawyer_id == lawyer_id
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment is None:
            return False
        await self.session.delete(assignment)
        await self.session.flush()
        return True

    async def list_case_lawyers(self, case_id: UUID) -> list[CaseLawyer]:
        result = await self.session.execute(
            select(CaseLawyer)
            .where(CaseLawyer.case_id == case_id)
            .order_by(CaseLawyer.role.desc(), CaseLawyer.assigned_at)
        )
        return list(result.scalars().all())

    async def close_case(
        self,
        case: Case,
        *,
        closed_at: date,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> Case:
        if case.status in ("cerrado", "archivado"):
            raise CaseError("El expediente ya está cerrado")

        before = {"status": case.status, "closed_at": case.closed_at}
        case.status = "cerrado"
        case.closed_at = closed_at
        if notes is not None:
            case.notes = notes
        record_changes(
            self.session,
            entity=CASE_ENTITY,
            entity_id=case.id,
            before=before,
            after={"status": case.status, "closed_at": closed_at, "notes": case.notes},
            changed_by=actor_id,
            fields=("status", "closed_at", "notes"),
        )
        await self.session.flush()
        await self.session.refresh(case)
        return case

    async def deactivate_case(
        self, case: Case, *, actor_id: UUID | None = None
    ) -> Case:
        case.is_active = False
        case.deleted_at = datetime.now(UTC)
        case.deleted_by = actor_id
        await self.session.flush()
        await self.session.refresh(case)
        return case

    async def add_party(
        self, case: Case, payload: dict[str, Any], *, actor_id: UUID | None = None
    ) -> CaseParty:
        client_id = payload.get("client_id")
        if client_id is not None:
            await self._require_active_client(UUID(str(client_id)))
        party = CaseParty(case_id=case.id, **payload)
        self.session.add(party)
        await self.session.flush()
        await self.session.refresh(party)
        return party

    async def list_parties(self, case_id: UUID) -> list[CaseParty]:
        result = await self.session.execute(
            select(CaseParty)
            .where(CaseParty.case_id == case_id)
            .order_by(CaseParty.created_at)
        )
        return list(result.scalars().all())

    async def list_history(self, case_id: UUID, limit: int) -> list[ChangeLog]:
        result = await self.session.execute(
            select(ChangeLog)
            .where(ChangeLog.entity == CASE_ENTITY, ChangeLog.entity_id == case_id)
            .order_by(ChangeLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def can_view(self, user: User, case_id: UUID) -> bool:
        """Return True when the caller is allowed to see the case."""
        scope = await resolve_scope(self.session, user)
        if scope is CaseScope.ALL:
            return True
        if scope is CaseScope.NONE:
            return False
        if scope is CaseScope.OWN_PUBLISHED:
            client_ids = await own_client_ids(self.session, user)
            if not client_ids:
                return False
            result = await self.session.execute(
                select(Case.id).where(Case.id == case_id, Case.client_id.in_(client_ids))
            )
            return result.scalar_one_or_none() is not None
        return case_id in await assigned_case_ids(self.session, user)

    async def lawyer_ids_for(self, case_id: UUID) -> list[UUID]:
        result = await self.session.execute(
            select(CaseLawyer.lawyer_id).where(CaseLawyer.case_id == case_id)
        )
        return list(result.scalars().all())


__all__ = [
    "COLLABORATOR_ROLE",
    "RESPONSIBLE_ROLE",
    "CaseError",
    "CaseScope",
    "CaseService",
    "assigned_case_ids",
    "case_scoped",
    "next_case_number",
    "resolve_scope",
    "scope_filter",
]
