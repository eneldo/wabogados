from datetime import UTC, datetime
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session
from app.models import Lawyer, LegalAnalysis, LegalArea, SystemSetting
from app.schemas.lawyers import LegalAreaResponse
from app.services.lawyers import LawyerService


class PublicLawyerResponse(BaseModel):
    id: str
    full_name: str
    photo_url: str | None
    specialties: list[str]
    legal_areas: list[str]


class PublicAnnouncementResponse(BaseModel):
    key: str
    value: str
    description: str | None
    updated_at: str


class PublicAnalysisItem(BaseModel):
    id: str
    title: str
    slug: str
    summary: str | None
    author_name: str | None
    published_at: str | None


class PublicAnalysisDetail(PublicAnalysisItem):
    content: str

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/legal-areas", response_model=list[LegalAreaResponse])
async def list_public_legal_areas(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[LegalAreaResponse]:
    """Áreas de práctica publicadas (solo lectura, sin autenticación)."""
    areas = await LawyerService(session).list_legal_areas()
    return [LegalAreaResponse.model_validate(area) for area in areas if area.is_active]


@router.get("/lawyers", response_model=list[PublicLawyerResponse])
async def list_public_lawyers(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicLawyerResponse]:
    """Perfiles públicos de abogados activos (solo lectura, sin autenticación)."""
    result = await session.execute(
        select(Lawyer)
        .options(selectinload(Lawyer.legal_areas))
        .where(Lawyer.status == "activo", Lawyer.deleted_at.is_(None))
        .order_by(Lawyer.full_name)
    )
    lawyers = list(result.scalars().all())
    return [
        PublicLawyerResponse(
            id=str(lawyer.id),
            full_name=lawyer.full_name,
            photo_url=lawyer.photo_url,
            specialties=list(lawyer.specialties or []),
            legal_areas=[area.name for area in (lawyer.legal_areas or [])],
        )
        for lawyer in lawyers
    ]


@router.get("/announcements", response_model=list[PublicAnnouncementResponse])
async def list_public_announcements(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicAnnouncementResponse]:
    """Avisos públicos gestionados desde administración (solo lectura)."""
    result = await session.execute(
        select(SystemSetting)
        .where(SystemSetting.category == "public")
        .order_by(SystemSetting.updated_at.desc())
        .limit(10)
    )
    items = list(result.scalars().all())
    return [
        PublicAnnouncementResponse(
            key=item.key,
            value=item.value,
            description=item.description,
            updated_at=item.updated_at.isoformat(),
        )
        for item in items
    ]


@router.get("/analyses")
async def list_public_analyses(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = 1,
    page_size: int = 6,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 24)
    now = datetime.now(UTC)
    base = select(LegalAnalysis).where(
        LegalAnalysis.is_published.is_(True),
        LegalAnalysis.deleted_at.is_(None),
        (LegalAnalysis.published_at.is_(None)) | (LegalAnalysis.published_at <= now),
    )
    total_result = await session.execute(
        select(sa.func.count()).select_from(base.subquery())
    )
    total = total_result.scalar_one()
    result = await session.execute(
        base.order_by(
            LegalAnalysis.published_at.desc().nullslast(),
            LegalAnalysis.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    return {
        "items": [
            PublicAnalysisItem(
                id=str(a.id),
                title=a.title,
                slug=a.slug,
                summary=a.summary,
                author_name=a.author_name,
                published_at=a.published_at.isoformat() if a.published_at else None,
            ).model_dump()
            for a in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/analyses/{slug}", response_model=PublicAnalysisDetail)
async def get_public_analysis(
    slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicAnalysisDetail:
    now = datetime.now(UTC)
    result = await session.execute(
        select(LegalAnalysis).where(
            LegalAnalysis.slug == slug,
            LegalAnalysis.is_published.is_(True),
            LegalAnalysis.deleted_at.is_(None),
            (LegalAnalysis.published_at.is_(None)) | (LegalAnalysis.published_at <= now),
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Análisis no encontrado")
    return PublicAnalysisDetail(
        id=str(analysis.id),
        title=analysis.title,
        slug=analysis.slug,
        summary=analysis.summary,
        author_name=analysis.author_name,
        published_at=analysis.published_at.isoformat() if analysis.published_at else None,
        content=analysis.content,
    )


__all__ = ["LegalArea", "router"]