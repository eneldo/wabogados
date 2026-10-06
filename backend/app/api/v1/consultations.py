"""Consultation requests.

One endpoint on this router is reachable **without credentials**, and it is the
only public write in the whole application besides authentication. `POST
/consultations` is listed in `PUBLIC_PATHS` in `test_hardening.py`, and that
test is what stops a third one from appearing by accident.

Everything else here is behind a permission, because the rows hold a name, two
ways to call the person and a description of their legal problem.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.core.http_status import (
    HTTP_422_UNPROCESSABLE,
)
from app.models import User
from app.schemas.consultations import (
    CONSULTATION_STATUSES,
    ConsultationCreate,
    ConsultationPublicAck,
    ConsultationResponse,
    ConsultationUpdate,
    PaginatedConsultations,
)
from app.services.consultations import ConsultationError, ConsultationService

router = APIRouter(prefix="/consultations", tags=["consultations"])


@router.post(
    "",
    response_model=ConsultationPublicAck,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar una solicitud de consulta (público)",
)
async def create_consultation(
    payload: ConsultationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConsultationPublicAck:
    """Receive a consultation request from the public site.

    The response is a reference and a sentence, never the stored row. Echoing
    the row back would repeat the legal problem the person just typed and prove
    that it landed somewhere they know nothing about.
    """

    service = ConsultationService(session)
    request = await service.create(payload)
    await session.commit()
    return ConsultationPublicAck(
        reference=request.id,
        status=request.status,
        message=(
            "Su solicitud quedó registrada. El despacho la revisará y le "
            "contactará por el medio que indique."
        ),
    )


@router.get("", response_model=PaginatedConsultations)
async def list_consultations(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("consultations:read"))],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
) -> PaginatedConsultations:
    """The intake queue, newest first."""

    if status_filter is not None and status_filter not in CONSULTATION_STATUSES:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=f"Estado no válido. Use uno de: {', '.join(CONSULTATION_STATUSES)}",
        )

    service = ConsultationService(session)
    total, items = await service.list(
        skip=skip, limit=limit, status=status_filter, area=None
    )
    return PaginatedConsultations(
        total=total,
        skip=skip,
        limit=limit,
        items=[ConsultationResponse.model_validate(item) for item in items],
    )


@router.get("/{request_id}", response_model=ConsultationResponse)
async def get_consultation(
    request_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("consultations:read"))],
) -> ConsultationResponse:
    service = ConsultationService(session)
    request = await service.get(request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    return ConsultationResponse.model_validate(request)


@router.patch("/{request_id}", response_model=ConsultationResponse)
async def update_consultation(
    request_id: UUID,
    payload: ConsultationUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("consultations:update"))],
) -> ConsultationResponse:
    service = ConsultationService(session)
    try:
        request = await service.update(request_id, payload, actor_id=actor.id)
    except ConsultationError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    await session.commit()
    return ConsultationResponse.model_validate(request)


@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una solicitud por petición del titular",
)
async def erase_consultation(
    request_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("consultations:erase"))],
) -> Response:
    """Erase a request at the person's request. This is a real delete.

    Not a soft delete: see `ConsultationService.erase` for why a request that
    never became an expediente is not covered by the project's rule against
    deleting legal records.
    """

    service = ConsultationService(session)
    if not await service.erase(request_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
