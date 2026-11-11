from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import Case, ClientRequest, User
from app.schemas.client_requests import (
    ClientRequestCreate,
    ClientRequestRespond,
    ClientRequestResponse,
    ClientRequestUpdate,
)
from app.services.client_requests import ClientRequestError, ClientRequestService

router = APIRouter(tags=["client_requests"])


def _to_response(
    item: ClientRequest, case: Case | None = None, requester: User | None = None
) -> ClientRequestResponse:
    now = datetime.now(UTC)
    due = item.due_at
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    overdue = bool(due and item.status == "pendiente" and due < now)
    related_case = case if case is not None else getattr(item, "case", None)
    return ClientRequestResponse(
        id=item.id,
        case_id=item.case_id,
        case_number=related_case.case_number if related_case else None,
        case_title=related_case.title if related_case else None,
        client_id=item.client_id,
        request_type=item.request_type,
        title=item.title,
        description=item.description,
        status=item.status,
        priority=item.priority,
        due_at=item.due_at,
        requested_by=item.requested_by,
        requested_by_name=(
            (requester.full_name or requester.email)
            if requester is not None
            else (
                (requester_item.full_name or requester_item.email)
                if (requester_item := getattr(item, "requester", None)) is not None
                else None
            )
        ),
        response_text=item.response_text,
        responded_at=item.responded_at,
        responded_by=item.responded_by,
        reviewed_at=item.reviewed_at,
        reviewed_by=item.reviewed_by,
        review_note=item.review_note,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
        is_overdue=overdue,
    )


@router.get("/cases/{case_id}/client-requests", response_model=list[ClientRequestResponse])
async def list_case_client_requests(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("client_requests:read"))],
) -> list[ClientRequestResponse]:
    service = ClientRequestService(session)
    try:
        items = await service.list_for_case(case_id, actor)
    except ClientRequestError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    case = await session.get(Case, case_id)
    return [_to_response(item, case=case) for item in items]


@router.post(
    "/cases/{case_id}/client-requests",
    response_model=ClientRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_client_request(
    case_id: UUID,
    payload: ClientRequestCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("client_requests:create"))],
) -> ClientRequestResponse:
    service = ClientRequestService(session)
    try:
        item = await service.create_for_case(case_id, payload, actor=actor)
        await session.commit()
    except ClientRequestError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    await session.refresh(item)
    case = await session.get(Case, case_id)
    return _to_response(item, case=case, requester=actor)


@router.get("/client-requests", response_model=list[ClientRequestResponse])
async def list_own_client_requests(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("client_requests:read"))],
) -> list[ClientRequestResponse]:
    service = ClientRequestService(session)
    items = await service.list_own(actor)
    return [_to_response(item) for item in items]


@router.post("/client-requests/{request_id}/respond", response_model=ClientRequestResponse)
async def respond_client_request(
    request_id: UUID,
    payload: ClientRequestRespond,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("client_requests:respond"))],
) -> ClientRequestResponse:
    service = ClientRequestService(session)
    item = await service.get_visible(request_id, actor)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    try:
        item = await service.respond(item, payload, actor=actor)
        await session.commit()
    except ClientRequestError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    await session.refresh(item)
    return _to_response(item)


@router.patch("/client-requests/{request_id}", response_model=ClientRequestResponse)
async def update_client_request(
    request_id: UUID,
    payload: ClientRequestUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("client_requests:update"))],
) -> ClientRequestResponse:
    service = ClientRequestService(session)
    item = await service.get_visible(request_id, actor)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    try:
        item = await service.update(item, payload, actor=actor)
        await session.commit()
    except ClientRequestError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    await session.refresh(item)
    return _to_response(item)
