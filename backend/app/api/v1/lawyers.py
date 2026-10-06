from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import Lawyer, User
from app.schemas.clients import ChangeLogResponse
from app.schemas.lawyers import (
    LawyerCreate,
    LawyerResponse,
    LawyerUpdate,
    LegalAreaResponse,
    PaginatedLawyers,
)
from app.services.lawyers import LawyerError, LawyerService

router = APIRouter(prefix="/lawyers", tags=["lawyers"])


async def _require_lawyer(service: LawyerService, lawyer_id: UUID) -> Lawyer:
    lawyer = await service.get_lawyer(lawyer_id)
    if lawyer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Abogado no encontrado"
        )
    return lawyer


@router.get("", response_model=PaginatedLawyers)
async def list_lawyers(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("lawyers:read"))],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=120),
    lawyer_status: str | None = Query(
        default=None, alias="status", pattern="^(activo|inactivo|suspendido)$"
    ),
    include_inactive: bool = Query(default=False),
) -> PaginatedLawyers:
    lawyers, total = await LawyerService(session).list_lawyers(
        skip, limit, include_inactive=include_inactive, search=search, status=lawyer_status
    )
    return PaginatedLawyers(
        items=[LawyerResponse.model_validate(lawyer) for lawyer in lawyers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=LawyerResponse, status_code=status.HTTP_201_CREATED)
async def create_lawyer(
    payload: LawyerCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("lawyers:create"))],
) -> LawyerResponse:
    service = LawyerService(session)
    try:
        lawyer = await service.create_lawyer(payload, actor_id=actor.id)
        await session.commit()
    except LawyerError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return LawyerResponse.model_validate(lawyer)


@router.get("/legal-areas", response_model=list[LegalAreaResponse])
async def list_legal_areas(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("legal_areas:read"))],
) -> list[LegalAreaResponse]:
    areas = await LawyerService(session).list_legal_areas()
    return [LegalAreaResponse.model_validate(area) for area in areas]


@router.get("/{lawyer_id}", response_model=LawyerResponse)
async def get_lawyer(
    lawyer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("lawyers:read"))],
) -> LawyerResponse:
    lawyer = await _require_lawyer(LawyerService(session), lawyer_id)
    return LawyerResponse.model_validate(lawyer)


@router.patch("/{lawyer_id}", response_model=LawyerResponse)
async def update_lawyer(
    lawyer_id: UUID,
    payload: LawyerUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("lawyers:update"))],
) -> LawyerResponse:
    service = LawyerService(session)
    lawyer = await _require_lawyer(service, lawyer_id)
    try:
        updated = await service.update_lawyer(lawyer, payload, actor_id=actor.id)
        await session.commit()
    except LawyerError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return LawyerResponse.model_validate(updated)


@router.delete("/{lawyer_id}", response_model=LawyerResponse)
async def deactivate_lawyer(
    lawyer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("lawyers:delete"))],
) -> LawyerResponse:
    service = LawyerService(session)
    lawyer = await _require_lawyer(service, lawyer_id)
    deactivated = await service.deactivate_lawyer(lawyer, actor_id=actor.id)
    await session.commit()
    return LawyerResponse.model_validate(deactivated)


@router.get("/{lawyer_id}/history", response_model=list[ChangeLogResponse])
async def get_lawyer_history(
    lawyer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("lawyers:read"))],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChangeLogResponse]:
    service = LawyerService(session)
    await _require_lawyer(service, lawyer_id)
    entries = await service.list_history(lawyer_id, limit)
    return [ChangeLogResponse.model_validate(entry) for entry in entries]
