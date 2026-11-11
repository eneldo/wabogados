from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_session,
    get_user_permission_names,
    require_permission,
)
from app.models import User
from app.schemas.case_milestones import (
    CaseMilestoneCreate,
    CaseMilestoneResponse,
    CaseMilestoneUpdate,
)
from app.services.case_milestones import CaseMilestoneError, CaseMilestoneService

router = APIRouter(tags=["case_milestones"])


def _published_only_for(user: User) -> bool:
    """Staff who manage cases can see unpublished; pure client portal users see only published."""
    names = get_user_permission_names(user)
    return (
        "client_requests:respond" in names
        and "cases:update" not in names
        and not user.is_superuser
    )


@router.get("/cases/{case_id}/milestones", response_model=list[CaseMilestoneResponse])
async def list_case_milestones(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(get_current_user)],
) -> list[CaseMilestoneResponse]:
    # Any authenticated user who can access the case; visibility filtered by role.
    service = CaseMilestoneService(session)
    try:
        items = await service.list_for_case(
            case_id, actor, published_only=_published_only_for(actor)
        )
    except CaseMilestoneError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return [CaseMilestoneResponse.model_validate(i) for i in items]


@router.post(
    "/cases/{case_id}/milestones",
    response_model=CaseMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_milestone(
    case_id: UUID,
    payload: CaseMilestoneCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:update"))],
) -> CaseMilestoneResponse:
    service = CaseMilestoneService(session)
    try:
        item = await service.create(case_id, payload, actor=actor)
        await session.commit()
    except CaseMilestoneError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    await session.refresh(item)
    return CaseMilestoneResponse.model_validate(item)


@router.patch("/milestones/{milestone_id}", response_model=CaseMilestoneResponse)
async def update_case_milestone(
    milestone_id: UUID,
    payload: CaseMilestoneUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("cases:update"))],
) -> CaseMilestoneResponse:
    service = CaseMilestoneService(session)
    item = await service.get_visible(milestone_id, actor, published_only=False)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hito no encontrado")
    item = await service.update(item, payload, actor=actor)
    await session.commit()
    await session.refresh(item)
    return CaseMilestoneResponse.model_validate(item)
