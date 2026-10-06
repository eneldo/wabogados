from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, Client
from app.schemas.clients import ClientCreate, ClientUpdate
from app.services.history import TRACKED_CLIENT_FIELDS, record_changes

CLIENT_ENTITY = "clients"


class ClientError(Exception):
    """Raised when a client operation violates a business rule."""


class ClientService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_clients(
        self,
        skip: int,
        limit: int,
        *,
        include_inactive: bool = False,
        search: str | None = None,
        client_type: str | None = None,
    ) -> tuple[list[Client], int]:
        filters: list[ColumnElement[bool]] = []
        if not include_inactive:
            filters.append(Client.is_active.is_(True))
        if client_type:
            filters.append(Client.client_type == client_type)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                Client.document_number.ilike(pattern)
                | Client.full_name.ilike(pattern)
                | Client.legal_name.ilike(pattern)
                | Client.commercial_name.ilike(pattern)
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Client).where(*filters)
        )
        result = await self.session.execute(
            select(Client)
            .where(*filters)
            .order_by(Client.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_client(self, client_id: UUID) -> Client | None:
        return await self.session.get(Client, client_id)

    async def get_by_document(
        self, document_type: str, document_number: str
    ) -> Client | None:
        result = await self.session.execute(
            select(Client).where(
                Client.document_type == document_type,
                Client.document_number == document_number,
            )
        )
        return result.scalar_one_or_none()

    async def create_client(
        self, payload: ClientCreate, *, actor_id: UUID | None = None
    ) -> Client:
        existing = await self.get_by_document(
            payload.document_type, payload.document_number
        )
        if existing is not None:
            raise ClientError("Ya existe un cliente con ese documento")

        client = Client(
            client_type=payload.client_type,
            document_type=payload.document_type,
            document_number=payload.document_number,
            full_name=payload.full_name,
            legal_name=payload.legal_name,
            commercial_name=payload.commercial_name,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            notes=payload.notes,
            user_id=payload.user_id,
            is_active=True,
        )
        self.session.add(client)
        await self.session.flush()
        record_changes(
            self.session,
            entity=CLIENT_ENTITY,
            entity_id=client.id,
            before={},
            after=payload.model_dump(),
            changed_by=actor_id,
        )
        await self.session.flush()
        return client

    async def update_client(
        self,
        client: Client,
        payload: ClientUpdate,
        *,
        actor_id: UUID | None = None,
    ) -> Client:
        data = payload.model_dump(exclude_unset=True)
        before = {field: getattr(client, field, None) for field in TRACKED_CLIENT_FIELDS}
        for field, value in data.items():
            setattr(client, field, value)
        record_changes(
            self.session,
            entity=CLIENT_ENTITY,
            entity_id=client.id,
            before=before,
            after=data,
            changed_by=actor_id,
        )
        await self.session.flush()
        await self.session.refresh(client)
        return client

    async def deactivate_client(
        self, client: Client, *, actor_id: UUID | None = None
    ) -> Client:
        client.is_active = False
        client.deleted_at = datetime.now(UTC)
        client.deleted_by = actor_id
        record_changes(
            self.session,
            entity=CLIENT_ENTITY,
            entity_id=client.id,
            before={"is_active": True},
            after={"is_active": False},
            changed_by=actor_id,
            fields=("is_active",),
        )
        await self.session.flush()
        await self.session.refresh(client)
        return client

    async def list_history(self, client_id: UUID, limit: int) -> list[ChangeLog]:
        result = await self.session.execute(
            select(ChangeLog)
            .where(ChangeLog.entity == CLIENT_ENTITY, ChangeLog.entity_id == client_id)
            .order_by(ChangeLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
