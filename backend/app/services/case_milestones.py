from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseMilestone, Client, User
from app.schemas.case_milestones import CaseMilestoneCreate, CaseMilestoneUpdate
from app.services.cases import resolve_scope, scope_filter
from app.services.messaging import MessagingService, NotificationType


class CaseMilestoneError(Exception):
    pass


class CaseMilestoneService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _load_case(self, case_id: UUID, user: User) -> Case:
        scope = await resolve_scope(self.session, user)
        clause = await scope_filter(self.session, user, scope)
        filters: list[ColumnElement[bool]] = [Case.id == case_id, Case.is_active.is_(True)]
        if clause is not None:
            filters.append(clause)
        result = await self.session.execute(select(Case).where(*filters))
        case = result.scalar_one_or_none()
        if case is None:
            raise CaseMilestoneError("El expediente no existe o no está en su alcance")
        return case

    async def list_for_case(
        self, case_id: UUID, user: User, *, published_only: bool
    ) -> list[CaseMilestone]:
        await self._load_case(case_id, user)
        filters = [CaseMilestone.case_id == case_id, CaseMilestone.is_active.is_(True)]
        if published_only:
            filters.append(CaseMilestone.is_published.is_(True))
        result = await self.session.execute(
            select(CaseMilestone)
            .where(*filters)
            .order_by(CaseMilestone.sort_order.asc(), CaseMilestone.created_at.asc())
        )
        return list(result.scalars().all())

    async def create(
        self, case_id: UUID, payload: CaseMilestoneCreate, *, actor: User
    ) -> CaseMilestone:
        await self._load_case(case_id, actor)
        item = CaseMilestone(
            case_id=case_id,
            created_by=actor.id,
            **payload.model_dump(),
            is_active=True,
        )
        if item.is_published:
            item.published_at = datetime.now(UTC)
            item.published_by = actor.id
        self.session.add(item)
        await self.session.flush()
        if item.is_published:
            await self._notify_published(item)
        return item

    async def get_visible(
        self, milestone_id: UUID, user: User, *, published_only: bool
    ) -> CaseMilestone | None:
        item = await self.session.get(CaseMilestone, milestone_id)
        if item is None or not item.is_active:
            return None
        if published_only and not item.is_published:
            return None
        try:
            await self._load_case(item.case_id, user)
        except CaseMilestoneError:
            return None
        return item

    async def update(
        self, item: CaseMilestone, payload: CaseMilestoneUpdate, *, actor: User
    ) -> CaseMilestone:
        data = payload.model_dump(exclude_unset=True)
        became_published = data.get("is_published") is True and not item.is_published
        if became_published:
            item.published_at = datetime.now(UTC)
            item.published_by = actor.id
        if data.get("is_published") is False and item.is_published:
            item.published_at = None
            item.published_by = None
        for k, v in data.items():
            setattr(item, k, v)
        await self.session.flush()
        if became_published:
            await self._notify_published(item)
        return item

    async def _notify_published(self, item: CaseMilestone) -> None:
        row = await self.session.execute(
            select(User)
            .join(Client, Client.user_id == User.id)
            .join(Case, Case.client_id == Client.id)
            .where(
                Case.id == item.case_id,
                Case.is_active.is_(True),
                Client.is_active.is_(True),
                Client.user_id.is_not(None),
                User.is_active.is_(True),
            )
        )
        target = row.scalars().first()
        if target is None:
            return
        case = await self.session.get(Case, item.case_id)
        case_label = case.case_number if case else "su expediente"
        await MessagingService(self.session).notify(
            target,
            NotificationType.CASE_UPDATE,
            title=f"Actualización de etapa en {case_label}",
            body=item.title[:240],
            entity="case_milestones",
            entity_id=item.id,
        )
