"""First-party public-site counters, deliberately independent of legal records."""

import asyncio
import hashlib
import logging
import os
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LegalAnalysis,
    LegalArea,
    WebsiteAnalyticsDaily,
    WebsiteAnalyticsDedup,
    WebsiteAnalyticsPage,
)
from app.schemas.website_analytics import (
    WebsiteCounts,
    WebsiteDay,
    WebsiteEvent,
    WebsiteMonth,
    WebsitePage,
    WebsiteSummary,
)

TIMEZONE = "America/Bogota"
ZONE = ZoneInfo(TIMEZONE)
RETENTION_DAYS = 400
logger = logging.getLogger(__name__)
FALLBACK_AREAS = (
    "derecho-penal",
    "ley-familiar",
    "derecho-laboral",
    "derecho-constitucional",
    "derecho-civil",
    "derecho-comercial",
    "asesorias-empresariales",
)


def analytics_enabled() -> bool:
    return os.getenv("WEBSITE_ANALYTICS_ENABLED", "true").lower() not in ("false", "0", "no")


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


async def is_public_path(session: AsyncSession, path: str) -> bool:
    if path == "/":
        return True
    if path.startswith("/servicios/"):
        slug = path.removeprefix("/servicios/")
        if slug in FALLBACK_AREAS:
            return True
        names = await session.scalars(select(LegalArea.name).where(LegalArea.is_active.is_(True)))
        return any(_slug(name) == slug for name in names)
    if path.startswith("/analisis/"):
        found = await session.scalar(
            select(LegalAnalysis.id).where(
                LegalAnalysis.slug == path.removeprefix("/analisis/"),
                LegalAnalysis.is_published.is_(True),
                LegalAnalysis.is_active.is_(True),
            )
        )
        return found is not None
    return False


async def cleanup(session: AsyncSession, now: datetime) -> None:
    await session.execute(
        delete(WebsiteAnalyticsDedup).where(WebsiteAnalyticsDedup.expires_at <= now)
    )
    cutoff = now.astimezone(ZONE).date() - timedelta(days=RETENTION_DAYS)
    await session.execute(delete(WebsiteAnalyticsDaily).where(WebsiteAnalyticsDaily.day < cutoff))
    await session.execute(delete(WebsiteAnalyticsPage).where(WebsiteAnalyticsPage.day < cutoff))


async def _new_token(session: AsyncSession, value: str, expires_at: datetime) -> bool:
    token = hashlib.sha256(value.encode()).hexdigest()
    result = await session.scalar(
        insert(WebsiteAnalyticsDedup)
        .values(
            token=token,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing()
        .returning(WebsiteAnalyticsDedup.token)
    )
    return result is not None


async def record_event(session: AsyncSession, event: WebsiteEvent, now: datetime) -> bool:
    """Idempotent and atomic; the caller commits all counters and dedup together."""
    if not await is_public_path(session, event.path):
        raise ValueError("Solo se admiten páginas públicas publicadas")
    await cleanup(session, now)
    day = now.astimezone(ZONE).date()
    if not await _new_token(session, f"event:{event.event_id}", now + timedelta(hours=48)):
        return False
    view = int(event.kind == "page_view")
    phone = int(event.kind == "phone_click")
    visitor = 0
    if view:
        visitor = int(
            await _new_token(
                session,
                f"{day}:visitor:{event.visitor_id}",
                now + timedelta(hours=48),
            )
        )
    daily = insert(WebsiteAnalyticsDaily).values(
        day=day,
        page_views=view,
        estimated_visitors=visitor,
        phone_clicks=phone,
    )
    await session.execute(
        daily.on_conflict_do_update(
            index_elements=[WebsiteAnalyticsDaily.day],
            set_={
                "page_views": WebsiteAnalyticsDaily.page_views + view,
                "estimated_visitors": WebsiteAnalyticsDaily.estimated_visitors + visitor,
                "phone_clicks": WebsiteAnalyticsDaily.phone_clicks + phone,
            },
        )
    )
    page = insert(WebsiteAnalyticsPage).values(
        day=day,
        path=event.path,
        page_views=view,
        phone_clicks=phone,
    )
    await session.execute(
        page.on_conflict_do_update(
            index_elements=[WebsiteAnalyticsPage.day, WebsiteAnalyticsPage.path],
            set_={
                "page_views": WebsiteAnalyticsPage.page_views + view,
                "phone_clicks": WebsiteAnalyticsPage.phone_clicks + phone,
            },
        )
    )
    return True


def _add(target: WebsiteCounts, source: WebsiteCounts) -> None:
    target.page_views += source.page_views
    target.estimated_visitors += source.estimated_visitors
    target.phone_clicks += source.phone_clicks
    target.consultations += source.consultations


async def record_consultation(session: AsyncSession, now: datetime) -> None:
    """Anonymous total in the same transaction as a real accepted consultation."""
    if not analytics_enabled():
        return
    stmt = insert(WebsiteAnalyticsDaily).values(day=now.astimezone(ZONE).date(), consultations=1)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[WebsiteAnalyticsDaily.day],
            set_={"consultations": WebsiteAnalyticsDaily.consultations + 1},
        )
    )


async def summary(session: AsyncSession, start: date, end: date, now: datetime) -> WebsiteSummary:
    today = now.astimezone(ZONE).date()
    if start > end or (end - start).days >= 366 or end > today:
        raise ValueError("Seleccione un rango válido de hasta 366 días, sin fechas futuras")
    rows = await session.scalars(
        select(WebsiteAnalyticsDaily).where(
            WebsiteAnalyticsDaily.day.between(start, end),
        )
    )
    days = {
        start + timedelta(days=offset): WebsiteDay(day=start + timedelta(days=offset))
        for offset in range((end - start).days + 1)
    }
    for row in rows:
        days[row.day].page_views = row.page_views
        days[row.day].estimated_visitors = row.estimated_visitors
        days[row.day].phone_clicks = row.phone_clicks
        days[row.day].consultations = row.consultations

    totals = WebsiteCounts()
    months: dict[str, WebsiteMonth] = {}
    for item in days.values():
        _add(totals, item)
        month = item.day.strftime("%Y-%m")
        _add(months.setdefault(month, WebsiteMonth(month=month)), item)
    pages = await session.execute(
        select(
            WebsiteAnalyticsPage.path,
            func.sum(WebsiteAnalyticsPage.page_views),
            func.sum(WebsiteAnalyticsPage.phone_clicks),
        )
        .where(WebsiteAnalyticsPage.day.between(start, end))
        .group_by(WebsiteAnalyticsPage.path)
        .order_by(func.sum(WebsiteAnalyticsPage.page_views).desc(), WebsiteAnalyticsPage.path)
    )
    items = [
        WebsitePage(path=path, page_views=int(views), phone_clicks=int(phones))
        for path, views, phones in pages
    ]
    return WebsiteSummary(
        start=start,
        end=end,
        timezone=TIMEZONE,
        generated_at=now,
        totals=totals,
        daily=list(days.values()),
        monthly=list(months.values()),
        pages=items[:30],
        areas=[item for item in items if item.path.startswith("/servicios/")][:30],
    )


async def retention_loop() -> None:
    """Purge dedup within 49 hours and aggregates after 400 days, even if idle."""
    from app.db.session import SessionFactory

    while True:
        await asyncio.sleep(3600)
        try:
            async with SessionFactory() as session:
                await cleanup(session, datetime.now(UTC))
                await session.commit()
        except Exception:
            logger.exception("No se pudo limpiar la analítica web")
