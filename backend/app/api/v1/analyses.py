from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import LegalAnalysis, User

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def _slug_taken(
    session: AsyncSession, slug: str, *, exclude_id: UUID | None = None
) -> bool:
    """Whether another analysis already owns the slug.

    `slug` is unique in the schema and the public site addresses an analysis by it,
    so a collision is a caller decision to make, not a 500 to debug. Checking here
    turns the constraint violation into a 409 with the field named.
    """
    statement = select(LegalAnalysis.id).where(LegalAnalysis.slug == slug)
    if exclude_id is not None:
        statement = statement.where(LegalAnalysis.id != exclude_id)
    return (await session.execute(statement)).first() is not None


class AnalysisCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    content: str = Field(min_length=1)
    author_name: str | None = None
    is_published: bool = False
    published_at: str | None = None


class AnalysisUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    content: str | None = None
    author_name: str | None = None
    is_published: bool | None = None
    published_at: str | None = None


class AnalysisResponse(BaseModel):
    id: str
    title: str
    slug: str
    summary: str | None
    content: str
    author_name: str | None
    is_published: bool
    published_at: str | None
    is_active: bool


def _to_response(a: LegalAnalysis) -> AnalysisResponse:
    return AnalysisResponse(
        id=str(a.id),
        title=a.title,
        slug=a.slug,
        summary=a.summary,
        content=a.content,
        author_name=a.author_name,
        is_published=a.is_published,
        published_at=a.published_at.isoformat() if a.published_at else None,
        is_active=a.is_active,
    )


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("analyses:read"))],
    include_inactive: bool = Query(default=False),
) -> list[AnalysisResponse]:
    stmt = select(LegalAnalysis).order_by(LegalAnalysis.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(LegalAnalysis.deleted_at.is_(None))
    result = await session.execute(stmt)
    return [_to_response(a) for a in result.scalars().all()]


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: AnalysisCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("analyses:create"))],
) -> AnalysisResponse:
    published_at = None
    if payload.published_at:
        published_at = datetime.fromisoformat(payload.published_at)
    if await _slug_taken(session, payload.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un análisis con ese slug",
        )
    analysis = LegalAnalysis(
        title=payload.title,
        slug=payload.slug,
        summary=payload.summary,
        content=payload.content,
        author_name=payload.author_name,
        is_published=payload.is_published,
        published_at=published_at,
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    return _to_response(analysis)


@router.patch("/{analysis_id}", response_model=AnalysisResponse)
async def update_analysis(
    analysis_id: UUID,
    payload: AnalysisUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("analyses:update"))],
) -> AnalysisResponse:
    result = await session.execute(select(LegalAnalysis).where(LegalAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Análisis no encontrado")
    if payload.slug is not None and await _slug_taken(
        session, payload.slug, exclude_id=analysis_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un análisis con ese slug",
        )
    if payload.title is not None:
        analysis.title = payload.title
    if payload.slug is not None:
        analysis.slug = payload.slug
    if payload.summary is not None:
        analysis.summary = payload.summary
    if payload.content is not None:
        analysis.content = payload.content
    if payload.author_name is not None:
        analysis.author_name = payload.author_name
    if payload.is_published is not None:
        analysis.is_published = payload.is_published
    if payload.published_at is not None:
        analysis.published_at = (
            datetime.fromisoformat(payload.published_at) if payload.published_at else None
        )
    await session.commit()
    await session.refresh(analysis)
    return _to_response(analysis)


@router.delete("/{analysis_id}", response_model=AnalysisResponse)
async def deactivate_analysis(
    analysis_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("analyses:delete"))],
) -> AnalysisResponse:
    result = await session.execute(select(LegalAnalysis).where(LegalAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Análisis no encontrado")
    analysis.is_active = False
    analysis.deleted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(analysis)
    return _to_response(analysis)