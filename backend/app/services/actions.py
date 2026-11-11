from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_permission_names
from app.models import Action, Case, ChangeLog, Client, Lawyer, User
from app.schemas.actions import ActionCreate, ActionUpdate
from app.services.history import record_changes

ACTION_ENTITY = "actions"

INTERNAL_VISIBILITY = ("interna", "equipo")
PUBLISHED_VISIBILITY = "publicada"

TRACKED_ACTION_FIELDS = (
    "action_type",
    "occurred_at",
    "description",
    "result",
    "responsible_lawyer_id",
    "visibility",
    "next_action",
    "next_action_at",
)


class ActionError(Exception):
    """Raised when an action operation violates a business rule."""


def visible_visibilities(user: User) -> tuple[str, ...]:
    """Return the visibility levels the caller may read.

    Staff holding `actions:read` see every level; anyone else is limited to
    what the firm has published.
    """
    permissions = get_user_permission_names(user)
    if user.is_superuser or "actions:read" in permissions:
        return (*INTERNAL_VISIBILITY, PUBLISHED_VISIBILITY)
    if "actions:read_published" in permissions:
        return (PUBLISHED_VISIBILITY,)
    return ()


class ActionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _visibility_filter(
        self, user: User, allowed: tuple[str, ...]
    ) -> ColumnElement[bool]:
        return Action.visibility.in_(allowed) if allowed else self._never()

    @staticmethod
    def _never() -> ColumnElement[bool]:
        from sqlalchemy import literal

        return literal(False)

    async def list_actions(
        self,
        skip: int,
        limit: int,
        *,
        user: User,
        case_ids: list[UUID] | None = None,
        case_id: UUID | None = None,
        action_type: str | None = None,
        visibility: str | None = None,
        pending_only: bool = False,
        due_after: datetime | None = None,
        due_before: datetime | None = None,
    ) -> tuple[list[Action], int]:
        allowed = visible_visibilities(user)
        filters: list[ColumnElement[bool]] = [Action.is_active.is_(True)]
        filters.append(self._visibility_filter(user, allowed))

        if case_id is not None:
            filters.append(Action.case_id == case_id)
        elif case_ids is not None:
            filters.append(
                Action.case_id.in_(case_ids) if case_ids else self._never()
            )
        if action_type:
            filters.append(Action.action_type == action_type)
        if visibility:
            if visibility not in allowed:
                return [], 0
            filters.append(Action.visibility == visibility)
        if pending_only:
            filters.append(Action.next_action_at.is_not(None))
            filters.append(Action.next_action_at <= datetime.now(UTC))
        if due_after is not None or due_before is not None:
            filters.append(Action.next_action_at.is_not(None))
        if due_after is not None:
            filters.append(Action.next_action_at >= due_after)
        if due_before is not None:
            filters.append(Action.next_action_at <= due_before)

        total = await self.session.scalar(
            select(func.count()).select_from(Action).where(*filters)
        )
        result = await self.session.execute(
            select(Action)
            .where(*filters)
            .order_by(Action.occurred_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_action(self, action_id: UUID) -> Action | None:
        return await self.session.get(Action, action_id)

    async def get_visible_action(
        self, action_id: UUID, user: User
    ) -> Action | None:
        action = await self.get_action(action_id)
        if action is None or not action.is_active:
            return None
        if action.visibility not in visible_visibilities(user):
            return None
        return action

    async def _require_case(self, case_id: UUID) -> Case:
        result = await self.session.execute(
            select(Case).where(Case.id == case_id, Case.is_active.is_(True))
        )
        case = result.scalar_one_or_none()
        if case is None:
            raise ActionError("El expediente no existe o está inactivo")
        return case

    async def _require_lawyer(self, lawyer_id: UUID) -> Lawyer:
        result = await self.session.execute(
            select(Lawyer).where(Lawyer.id == lawyer_id, Lawyer.is_active.is_(True))
        )
        lawyer = result.scalar_one_or_none()
        if lawyer is None:
            raise ActionError("El abogado responsable no existe o está inactivo")
        return lawyer



    async def _notify_published_action(self, action: Action, *, actor_id: UUID | None) -> None:
        """Notify the case's portal client when an action is published."""
        if action.visibility != PUBLISHED_VISIBILITY or not action.is_active:
            return
        row = await self.session.execute(
            select(User)
            .join(Client, Client.user_id == User.id)
            .join(Case, Case.client_id == Client.id)
            .where(
                Case.id == action.case_id,
                Case.is_active.is_(True),
                Client.is_active.is_(True),
                Client.user_id.is_not(None),
                User.is_active.is_(True),
            )
        )
        target = row.scalars().first()
        if target is None or (actor_id is not None and target.id == actor_id):
            return
        from app.services.messaging import MessagingService, NotificationType

        case = await self.session.get(Case, action.case_id)
        case_label = case.case_number if case else "su expediente"
        await MessagingService(self.session).notify(
            target,
            NotificationType.CASE_UPDATE,
            title=f"Actualización en el expediente {case_label}",
            body=(
                action.next_action or action.description or "Hay una nueva actuación publicada."
            )[:240],
            entity="actions",
            entity_id=action.id,
        )

    async def create_action(
        self, payload: ActionCreate, *, actor_id: UUID | None = None
    ) -> Action:
        await self._require_case(payload.case_id)
        if payload.responsible_lawyer_id is not None:
            await self._require_lawyer(payload.responsible_lawyer_id)

        action = Action(
            case_id=payload.case_id,
            action_type=payload.action_type,
            occurred_at=payload.occurred_at,
            description=payload.description,
            result=payload.result,
            responsible_lawyer_id=payload.responsible_lawyer_id,
            visibility=payload.visibility,
            next_action=payload.next_action,
            next_action_at=payload.next_action_at,
            created_by=actor_id,
            is_active=True,
        )
        self.session.add(action)
        await self.session.flush()

        record_changes(
            self.session,
            entity=ACTION_ENTITY,
            entity_id=action.id,
            before={},
            after=payload.model_dump(),
            changed_by=actor_id,
            fields=TRACKED_ACTION_FIELDS,
        )
        await self.session.flush()
        await self._notify_published_action(action, actor_id=actor_id)
        return action

    async def update_action(
        self, action: Action, payload: ActionUpdate, *, actor_id: UUID | None = None
    ) -> Action:
        data = payload.model_dump(exclude_unset=True)
        if data.get("responsible_lawyer_id") is not None:
            await self._require_lawyer(data["responsible_lawyer_id"])
        if data.get("next_action_at") is not None and not (
            data.get("next_action") or action.next_action
        ):
            raise ActionError("next_action_at requiere next_action")

        before = {field: getattr(action, field, None) for field in TRACKED_ACTION_FIELDS}
        for field, value in data.items():
            setattr(action, field, value)

        became_published = (
            before.get("visibility") != PUBLISHED_VISIBILITY
            and action.visibility == PUBLISHED_VISIBILITY
        )
        record_changes(
            self.session,
            entity=ACTION_ENTITY,
            entity_id=action.id,
            before=before,
            after=data,
            changed_by=actor_id,
            fields=TRACKED_ACTION_FIELDS,
        )
        await self.session.flush()
        await self.session.refresh(action)
        if became_published:
            await self._notify_published_action(action, actor_id=actor_id)
        return action

    async def history_for_action(
        self, action_id: UUID, limit: int
    ) -> list[ChangeLog]:
        result = await self.session.execute(
            select(ChangeLog)
            .where(ChangeLog.entity == ACTION_ENTITY, ChangeLog.entity_id == action_id)
            .order_by(ChangeLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


__all__ = [
    "ACTION_ENTITY",
    "PUBLISHED_VISIBILITY",
    "ActionError",
    "ActionService",
    "visible_visibilities",
]
