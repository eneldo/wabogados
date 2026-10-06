"""Legal AI API (MASTER_PROMPT V5).

Three routes, and one of them exists to say **no**:

- `GET /ai/search` — real lexical search over the firm's material, filtered by the
  same case scope every other module uses.
- `GET /ai/documents/{id}/summary` — an **extractive** summary: the document's own
  sentences, chosen and labelled, never rewritten.
- `GET /ai/provider` — what a generation backend would need, and which of it is
  absent. It is a route rather than a comment because the screen has to be able to
  show it, and because a capability that is only documented is a capability nobody
  checks.

There is no generate route, and that is deliberate: without a provider there is
nothing behind it, and a route that answers with fiction is worse than a 404.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_user_scope, require_permission
from app.models import User
from app.schemas.legal_ai import (
    ProviderStatusResponse,
    SearchResponse,
    SummaryResponse,
)
from app.services.cases import CaseScope
from app.services.legal_ai import (
    LegalSearchService,
    meaningful_terms,
    provider_configured,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/search", response_model=SearchResponse)
async def search_material(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_permission("ai:search"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponse:
    """Search cases, documents and the multimedia library.

    Every row is one the caller could already open through the screen that owns it.
    A profile with no case scope gets an empty result rather than another client's
    material, which is the failure ADR-045 warns about.
    """
    service = LegalSearchService(session)
    hits = await service.search(q, user, scope, limit=limit)
    return SearchResponse(
        query=q,
        terms=meaningful_terms(q),
        total=len(hits),
        items=[
            {
                "kind": hit.kind,
                "id": hit.id,
                "title": hit.title,
                "excerpt": hit.excerpt,
                "case_id": hit.case_id,
                "case_number": hit.case_number,
                "score": hit.score,
            }
            for hit in hits
        ],
    )


@router.get("/documents/{document_id}/summary", response_model=SummaryResponse)
async def summarize_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_permission("ai:summarize"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> SummaryResponse:
    """An extractive summary of a document.

    The sentences are the document's own. They are returned in the order they
    appear, not ranked, so the result reads as a passage of the file rather than as
    a list of fragments.
    """
    summary = await LegalSearchService(session).summarize_document(document_id, user, scope)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado"
        )
    return SummaryResponse(
        kind=summary.kind,
        id=summary.id,
        title=summary.title,
        sentences=summary.sentences,
        method=summary.method,
        terms=summary.terms,
    )


@router.get("/provider", response_model=ProviderStatusResponse)
async def read_provider_status(
    _: Annotated[User, Depends(require_permission("ai:search"))],
) -> ProviderStatusResponse:
    """What is missing before this module can generate anything.

    A capability the screen states rather than one it hides: the firm can see that
    the assistant is off and exactly which of the four pieces is absent, instead of
    finding a text box that quietly does nothing.
    """
    return ProviderStatusResponse(**provider_configured())


__all__ = ["read_provider_status", "router", "search_material", "summarize_document"]
