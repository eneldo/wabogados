from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_permission_names
from app.models import Case, Client, ClientRequest, User
from app.schemas.client_requests import (
    ClientRequestCreate,
    ClientRequestRespond,
    ClientRequestUpdate,
)
from app.services.cases import case_scoped, resolve_scope, scope_filter
from app.services.messaging import MessagingService, NotificationType


class ClientRequestError(Exception):
    pass


class ClientRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _own_client_ids(self, user: User) -> list[UUID]:
        result = await self.session.execute(
            select(Client.id).where(Client.user_id == user.id, Client.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def _scope_clause(self, user: User) -> ColumnElement[bool] | None:
        scope = await resolve_scope(self.session, user)
        return case_scoped(ClientRequest.case_id, await scope_filter(self.session, user, scope))

    async def _load_case(self, case_id: UUID, user: User) -> Case:
        scope = await resolve_scope(self.session, user)
        clause = await scope_filter(self.session, user, scope)
        filters: list[ColumnElement[bool]] = [Case.id == case_id, Case.is_active.is_(True)]
        if clause is not None:
            filters.append(clause)
        result = await self.session.execute(select(Case).where(*filters))
        case = result.scalar_one_or_none()
        if case is None:
            raise ClientRequestError("El expediente no existe o no está en su alcance")
        return case

    async def create_for_case(
        self, case_id: UUID, payload: ClientRequestCreate, *, actor: User
    ) -> ClientRequest:
        case = await self._load_case(case_id, actor)
        if case.client_id is None:
            raise ClientRequestError("El expediente no tiene un cliente asociado")
        request = ClientRequest(
            case_id=case.id,
            client_id=case.client_id,
            request_type=payload.request_type,
            title=payload.title,
            description=payload.description,
            status="pendiente",
            priority=payload.priority,
            due_at=payload.due_at,
            requested_by=actor.id,
            is_active=True,
        )
        self.session.add(request)
        await self.session.flush()
        await self._notify_created(request)
        return request

    async def _notify_created(self, request: ClientRequest) -> None:
        row = await self.session.execute(
            select(User)
            .join(Client, Client.user_id == User.id)
            .where(
                Client.id == request.client_id,
                Client.is_active.is_(True),
                User.is_active.is_(True),
            )
        )
        target = row.scalars().first()
        if target is None:
            return
        case = await self.session.get(Case, request.case_id)
        case_label = case.case_number if case else "su expediente"
        due = f" · vence {request.due_at.date().isoformat()}" if request.due_at else ""
        await MessagingService(self.session).notify(
            target,
            NotificationType.CASE_UPDATE,
            title=f"Nueva solicitud en {case_label}",
            body=f"{request.title}{due}"[:240],
            entity="client_requests",
            entity_id=request.id,
        )

    async def list_for_case(self, case_id: UUID, user: User) -> list[ClientRequest]:
        await self._load_case(case_id, user)
        result = await self.session.execute(
            select(ClientRequest)
            .where(ClientRequest.case_id == case_id, ClientRequest.is_active.is_(True))
            .order_by(ClientRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_own(self, user: User) -> list[ClientRequest]:
        client_ids = await self._own_client_ids(user)
        if not client_ids:
            return []
        result = await self.session.execute(
            select(ClientRequest)
            .where(
                ClientRequest.client_id.in_(client_ids),
                ClientRequest.is_active.is_(True),
                ClientRequest.status.in_(("pendiente", "respondida", "revisada")),
            )
            .order_by(ClientRequest.due_at.asc().nullslast(), ClientRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_visible(self, request_id: UUID, user: User) -> ClientRequest | None:
        request = await self.session.get(ClientRequest, request_id)
        if request is None or not request.is_active:
            return None
        perms = get_user_permission_names(user)
        if (
            "client_requests:respond" in perms
            and "client_requests:create" not in perms
            and not user.is_superuser
        ):
            own = await self._own_client_ids(user)
            return request if request.client_id in own else None
        # staff: check case scope
        try:
            await self._load_case(request.case_id, user)
            return request
        except ClientRequestError:
            return None

    async def update(
        self, request: ClientRequest, payload: ClientRequestUpdate, *, actor: User
    ) -> ClientRequest:
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] == "revisada":
            request.reviewed_at = datetime.now(UTC)
            request.reviewed_by = actor.id
        for key, value in data.items():
            setattr(request, key, value)
        await self.session.flush()
        return request

    async def respond(
        self, request: ClientRequest, payload: ClientRequestRespond, *, actor: User
    ) -> ClientRequest:
        own = await self._own_client_ids(actor)
        if request.client_id not in own:
            raise ClientRequestError("No puede responder esta solicitud")
        if request.status == "cancelada":
            raise ClientRequestError("La solicitud está cancelada")
        request.response_text = payload.response_text
        request.responded_at = datetime.now(UTC)
        request.responded_by = actor.id
        request.status = "respondida"
        await self.session.flush()
        return request
