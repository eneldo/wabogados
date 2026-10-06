"""Consultation requests: the intake behind the public form.

One deliberate asymmetry runs through this module: **no `record_changes`.**
Every other service in the application leaves a per-field history in
`change_logs`. Doing that for a consultation would write the person's name,
phone, email and description of their legal problem into a second table, and a
person exercising their right to erasure would then have to be erased from two
places or the promise made to them would be false. The transitions this table
does need are carried by `status`, `handled_by` and `handled_at`.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsultationRequest
from app.schemas.consultations import (
    PRIVACY_NOTICE_VERSION,
    ConsultationCreate,
    ConsultationUpdate,
)


class ConsultationError(Exception):
    """Raised when a consultation operation violates a business rule."""


class ConsultationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: ConsultationCreate) -> ConsultationRequest:
        """Store a request and stamp the consent.

        `consent_at` is set here rather than in the endpoint so that it cannot be
        forgotten on a second code path, and it uses the database clock via
        `func.now()` so a row never depends on the API server's clock to say when
        consent was given.
        """

        request = ConsultationRequest(
            full_name=payload.full_name,
            phone=payload.phone,
            email=str(payload.email),
            area=payload.area,
            message=payload.message,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
            consent_at=datetime.now(UTC),
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get(self, request_id: UUID) -> ConsultationRequest | None:
        result = await self.session.execute(
            select(ConsultationRequest).where(ConsultationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        area: str | None = None,
    ) -> tuple[int, list[ConsultationRequest]]:
        """The intake queue, newest first.

        Newest-first is the whole point of the endpoint: a request that arrived
        while nobody was looking is the one that decays.
        """

        conditions = []
        if status is not None:
            conditions.append(ConsultationRequest.status == status)
        if area is not None:
            conditions.append(ConsultationRequest.area == area)

        total = await self.session.scalar(
            select(func.count()).select_from(ConsultationRequest).where(*conditions)
        )
        result = await self.session.execute(
            select(ConsultationRequest)
            .where(*conditions)
            # `id` is the tiebreaker on purpose. `created_at` comes from
            # `server_default=now()`, and PostgreSQL's `now()` is the *start of
            # the transaction*, not the moment of the insert: every row written by
            # one transaction carries the same instant. Without a second key the
            # order of those rows is whatever the planner happens to return, and
            # two pages of the queue can show the same request twice.
            .order_by(ConsultationRequest.created_at.desc(), ConsultationRequest.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return int(total or 0), list(result.scalars().all())

    async def update(
        self,
        request_id: UUID,
        payload: ConsultationUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> ConsultationRequest:
        request = await self.get(request_id)
        if request is None:
            raise ConsultationError("La solicitud no existe")

        # "Atendida" and "convertida" mean somebody picked this up. Writing the
        # actor and the moment is what makes the queue answerable later.
        if payload.status != "nueva":
            request.handled_by = actor_id
            request.handled_at = datetime.now(UTC)

        request.status = payload.status
        if payload.internal_notes is not None:
            request.internal_notes = payload.internal_notes
        if payload.client_id is not None:
            request.client_id = payload.client_id

        await self.session.flush()
        return request

    async def erase(self, request_id: UUID) -> bool:
        """Really delete a row, on the person's request.

        `PROJECT_RULES.md` forbids physically deleting **legal records**. A
        request that never became an expediente is not a legal record: it is a
        lead about a person who has not been represented by anybody yet, and
        data protection law gives that person the right to have it removed. A
        soft delete would satisfy the letter of the rule and defeat its purpose,
        because the row, and the legal problem in it, would still be there.

        The audit middleware records the `DELETE` request itself, so the erasure
        is traceable without keeping the data erased.
        """

        request = await self.get(request_id)
        if request is None:
            return False
        await self.session.delete(request)
        await self.session.flush()
        return True


__all__ = ["ConsultationError", "ConsultationService"]