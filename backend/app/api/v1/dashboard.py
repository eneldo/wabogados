"""Dashboards by scope.

There is no endpoint per role. Every caller gets the same dashboard, built from
their own scope, because the difference between an administrator and a lawyer
is *which rows they may see*, not *which figures exist*. A separate endpoint per
role would duplicate the queries and give a place for the scope to be forgotten.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_user_scope, require_permission
from app.models import CalendarEvent, Client, Hearing, User
from app.schemas.dashboard import (
    DashboardActionEntry,
    DashboardCaseItem,
    DashboardDeadlineItem,
    DashboardDocumentItem,
    DashboardEvidenceItem,
    DashboardHearingItem,
    DashboardKpis,
    DashboardResponse,
    DashboardSummaryResponse,
)
from app.services.cases import CaseScope
from app.services.dashboard import (
    DEFAULT_HORIZON_DAYS,
    DEFAULT_LIST_LIMIT,
    DashboardService,
    dashboard_view_for,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _hearing_item(hearing: Hearing, event: CalendarEvent) -> DashboardHearingItem:
    return DashboardHearingItem(
        id=hearing.id,
        event_id=hearing.event_id,
        case_id=hearing.case_id,
        title=event.title,
        starts_at=event.starts_at,
        status=hearing.status,
        court=hearing.court,
        courtroom=hearing.courtroom,
        procedural_stage=hearing.procedural_stage,
    )


async def _client_names(session: AsyncSession, case_ids: list[UUID]) -> dict[UUID, str]:
    """Names of the clients behind the listed cases, in one query."""
    if not case_ids:
        return {}
    from sqlalchemy import select

    from app.models import Case

    rows = await session.execute(
        select(Case.id, Client.full_name, Client.legal_name, Client.commercial_name)
        .join(Client, Client.id == Case.client_id)
        .where(Case.id.in_(case_ids))
    )
    names: dict[UUID, str] = {}
    for case_id, full_name, legal_name, commercial_name in rows:
        names[case_id] = legal_name or commercial_name or full_name or ""
    return names


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("dashboard:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    days: int = Query(default=DEFAULT_HORIZON_DAYS, ge=1, le=365),
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=50),
) -> DashboardResponse:
    """The caller's dashboard, already scoped to what they may see."""
    service = DashboardService(session, actor)
    await service.prepare()

    kpis = await service.kpis()
    cases = await service.my_cases(limit=limit)
    names = await _client_names(session, [case.id for case in cases])

    next_hearing = await service.next_hearing()
    hearings = await service.upcoming_hearings_list(days=days, limit=limit)

    return DashboardResponse(
        view=dashboard_view_for(actor, service.scope),
        generated_at=datetime.now(UTC),
        kpis=DashboardKpis(**kpis),
        cases=[
            DashboardCaseItem.from_case(case, names.get(case.id, "")) for case in cases
        ],
        next_hearing=_hearing_item(*next_hearing) if next_hearing else None,
        hearings=[_hearing_item(hearing, event) for hearing, event in hearings],
        deadlines=[
            DashboardDeadlineItem(**asdict(item))
            for item in await service.deadlines_list(days=days, limit=limit)
        ],
        recent_actions=[
            DashboardActionEntry.from_action(action)
            for action in await service.recent_actions(limit=limit)
        ],
        documents=[
            DashboardDocumentItem.from_document(document)
            for document in await service.published_documents(limit=limit)
        ],
        evidences=[
            DashboardEvidenceItem.from_evidence(evidence)
            for evidence in await service.visible_evidences(limit=limit)
        ],
    )


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("dashboard:read"))],
) -> DashboardSummaryResponse:
    """Header counters. Kept separate so the badge can poll cheaply."""
    service = DashboardService(session, actor)
    await service.prepare()

    return DashboardSummaryResponse(**(await service.summary()))


__all__ = ["get_dashboard", "get_dashboard_summary", "router"]