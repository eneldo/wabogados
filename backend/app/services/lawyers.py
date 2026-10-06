from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, Lawyer, LegalArea
from app.schemas.lawyers import LawyerCreate, LawyerUpdate
from app.services.history import record_changes

LAWYER_ENTITY = "lawyers"

TRACKED_LAWYER_FIELDS = (
    "full_name",
    "professional_card",
    "email",
    "phone",
    "status",
    "photo_url",
    "user_id",
)


class LawyerError(Exception):
    """Raised when a lawyer operation violates a business rule."""


class LawyerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_lawyers(
        self,
        skip: int,
        limit: int,
        *,
        include_inactive: bool = False,
        search: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Lawyer], int]:
        filters: list[ColumnElement[bool]] = []
        if not include_inactive:
            filters.append(Lawyer.is_active.is_(True))
        if status:
            filters.append(Lawyer.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                Lawyer.full_name.ilike(pattern)
                | Lawyer.document_number.ilike(pattern)
                | Lawyer.professional_card.ilike(pattern)
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Lawyer).where(*filters)
        )
        result = await self.session.execute(
            select(Lawyer)
            .where(*filters)
            .order_by(Lawyer.full_name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_lawyer(self, lawyer_id: UUID) -> Lawyer | None:
        return await self.session.get(Lawyer, lawyer_id)

    async def get_by_document(
        self, document_type: str, document_number: str
    ) -> Lawyer | None:
        result = await self.session.execute(
            select(Lawyer).where(
                Lawyer.document_type == document_type,
                Lawyer.document_number == document_number,
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_legal_areas(self, area_ids: list[UUID]) -> list[LegalArea]:
        if not area_ids:
            return []
        result = await self.session.execute(
            select(LegalArea).where(LegalArea.id.in_(area_ids))
        )
        areas = list(result.scalars().all())
        if len(areas) != len(set(area_ids)):
            raise LawyerError("Alguna área jurídica indicada no existe")
        return areas

    async def create_lawyer(
        self, payload: LawyerCreate, *, actor_id: UUID | None = None
    ) -> Lawyer:
        if await self.get_by_document(
            payload.document_type, payload.document_number
        ):
            raise LawyerError("Ya existe un abogado con ese documento")

        if payload.professional_card:
            duplicate = await self.session.scalar(
                select(Lawyer).where(Lawyer.professional_card == payload.professional_card)
            )
            if duplicate is not None:
                raise LawyerError("Ya existe un abogado con esa tarjeta profesional")

        lawyer = Lawyer(
            document_type=payload.document_type,
            document_number=payload.document_number,
            full_name=payload.full_name,
            professional_card=payload.professional_card,
            email=payload.email,
            phone=payload.phone,
            specialties=payload.specialties,
            status=payload.status,
            photo_url=payload.photo_url,
            user_id=payload.user_id,
            is_active=True,
        )
        lawyer.legal_areas = await self._resolve_legal_areas(payload.legal_area_ids)
        self.session.add(lawyer)
        await self.session.flush()

        record_changes(
            self.session,
            entity=LAWYER_ENTITY,
            entity_id=lawyer.id,
            before={},
            after={
                **payload.model_dump(exclude={"legal_area_ids"}),
                "legal_areas": [area.name for area in lawyer.legal_areas],
            },
            changed_by=actor_id,
            fields=(*TRACKED_LAWYER_FIELDS, "legal_areas"),
        )
        await self.session.flush()
        return lawyer

    async def update_lawyer(
        self,
        lawyer: Lawyer,
        payload: LawyerUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> Lawyer:
        data = payload.model_dump(exclude_unset=True)
        area_ids = data.pop("legal_area_ids", None)
        before: dict[str, object] = {
            field: getattr(lawyer, field, None) for field in TRACKED_LAWYER_FIELDS
        }
        before["legal_areas"] = [area.name for area in lawyer.legal_areas]

        if data.get("professional_card"):
            duplicate = await self.session.scalar(
                select(Lawyer).where(
                    Lawyer.professional_card == data["professional_card"],
                    Lawyer.id != lawyer.id,
                )
            )
            if duplicate is not None:
                raise LawyerError("Ya existe un abogado con esa tarjeta profesional")

        for field, value in data.items():
            setattr(lawyer, field, value)

        after: dict[str, object] = {**data}
        if area_ids is not None:
            lawyer.legal_areas = await self._resolve_legal_areas(area_ids)
            after["legal_areas"] = [area.name for area in lawyer.legal_areas]

        record_changes(
            self.session,
            entity=LAWYER_ENTITY,
            entity_id=lawyer.id,
            before=before,
            after=after,
            changed_by=actor_id,
            fields=(*TRACKED_LAWYER_FIELDS, "legal_areas"),
        )
        await self.session.flush()
        await self.session.refresh(lawyer)
        return lawyer

    async def deactivate_lawyer(
        self, lawyer: Lawyer, *, actor_id: UUID | None = None
    ) -> Lawyer:
        lawyer.is_active = False
        lawyer.status = "inactivo"
        lawyer.deleted_at = datetime.now(UTC)
        lawyer.deleted_by = actor_id
        record_changes(
            self.session,
            entity=LAWYER_ENTITY,
            entity_id=lawyer.id,
            before={"is_active": True, "status": "activo"},
            after={"is_active": False, "status": "inactivo"},
            changed_by=actor_id,
            fields=("is_active", "status"),
        )
        await self.session.flush()
        await self.session.refresh(lawyer)
        return lawyer

    async def list_legal_areas(self) -> list[LegalArea]:
        result = await self.session.execute(
            select(LegalArea).where(LegalArea.is_active.is_(True)).order_by(LegalArea.name)
        )
        return list(result.scalars().all())

    async def list_history(self, lawyer_id: UUID, limit: int) -> list[ChangeLog]:
        result = await self.session.execute(
            select(ChangeLog)
            .where(ChangeLog.entity == LAWYER_ENTITY, ChangeLog.entity_id == lawyer_id)
            .order_by(ChangeLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
