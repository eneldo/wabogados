from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import User
from app.schemas.website_analytics import WebsiteEvent, WebsiteSummary
from app.services import website_analytics as analytics

router = APIRouter(tags=["website-analytics"])


@router.post("/public/analytics/events", status_code=204)
async def collect_event(
    payload: WebsiteEvent,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    # Neither cookie/session credentials nor incoming IP/UA enter the service.
    if (
        not analytics.analytics_enabled()
        or request.headers.get("DNT") == "1"
        or (request.headers.get("Sec-GPC") == "1")
    ):
        return Response(status_code=204)
    try:
        await analytics.record_event(session, payload, datetime.now(UTC))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    await session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/admin/metrics/website", response_model=WebsiteSummary)
async def website_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("website_analytics:read"))],
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
) -> WebsiteSummary:
    del actor
    now = datetime.now(UTC)
    until = end or now.astimezone(analytics.ZONE).date()
    since = start or until - timedelta(days=29)
    try:
        return await analytics.summary(session, since, until, now)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
