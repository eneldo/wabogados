from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import Client, User
from app.schemas.clients import (
    ChangeLogResponse,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    PaginatedClients,
)
from app.services.clients import ClientError, ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


async def _require_client(service: ClientService, client_id: UUID) -> Client:
    client = await service.get_client(client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )
    return client


@router.get("", response_model=PaginatedClients)
async def list_clients(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("clients:read"))],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=120),
    client_type: str | None = Query(default=None, pattern="^(natural|juridica)$"),
    include_inactive: bool = Query(default=False),
) -> PaginatedClients:
    service = ClientService(session)
    clients, total = await service.list_clients(
        skip, limit, include_inactive=include_inactive, search=search, client_type=client_type
    )
    return PaginatedClients(
        items=[ClientResponse.model_validate(client) for client in clients],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("clients:create"))],
) -> ClientResponse:
    service = ClientService(session)
    try:
        client = await service.create_client(payload, actor_id=actor.id)
        await session.commit()
    except ClientError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return ClientResponse.model_validate(client)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("clients:read"))],
) -> ClientResponse:
    client = await _require_client(ClientService(session), client_id)
    return ClientResponse.model_validate(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("clients:update"))],
) -> ClientResponse:
    service = ClientService(session)
    client = await _require_client(service, client_id)
    updated = await service.update_client(client, payload, actor_id=actor.id)
    await session.commit()
    return ClientResponse.model_validate(updated)


@router.delete("/{client_id}", response_model=ClientResponse)
async def deactivate_client(
    client_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("clients:delete"))],
) -> ClientResponse:
    service = ClientService(session)
    client = await _require_client(service, client_id)
    deactivated = await service.deactivate_client(client, actor_id=actor.id)
    await session.commit()
    return ClientResponse.model_validate(deactivated)


@router.get("/{client_id}/history", response_model=list[ChangeLogResponse])
async def get_client_history(
    client_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("clients:read"))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChangeLogResponse]:
    service = ClientService(session)
    await _require_client(service, client_id)
    entries = await service.list_history(client_id, limit)
    return [ChangeLogResponse.model_validate(entry) for entry in entries]
