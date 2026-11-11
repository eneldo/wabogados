from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    WebsiteAnalyticsDaily,
    WebsiteAnalyticsDedup,
    WebsiteAnalyticsPage,
)
from app.schemas.website_analytics import WebsiteEvent
from app.services import website_analytics as analytics

COLLECT = "/api/v1/public/analytics/events"
REPORT = "/api/v1/admin/metrics/website"
NOW = datetime(2026, 11, 11, 17, tzinfo=UTC)


def event(**overrides: object) -> WebsiteEvent:
    return WebsiteEvent.model_validate(
        {
            "event_id": str(uuid4()),
            "visitor_id": str(uuid4()),
            "path": "/",
            "kind": "page_view",
            **overrides,
        }
    )


async def test_idempotent_events_and_navigation_dedup(database_session: AsyncSession) -> None:
    payload = event()
    assert await analytics.record_event(database_session, payload, NOW)
    assert not await analytics.record_event(database_session, payload, NOW)
    second = event(visitor_id=payload.visitor_id, path="/servicios/derecho-penal")
    await analytics.record_event(database_session, second, NOW)
    await analytics.record_event(database_session, event(kind="phone_click"), NOW)
    data = await analytics.summary(database_session, NOW.date(), NOW.date(), NOW)
    assert data.totals.page_views == 2
    assert data.totals.estimated_visitors == 1
    assert data.totals.phone_clicks == 1
    assert len(data.pages) == 2
    assert data.areas[0].path == "/servicios/derecho-penal"


async def test_independent_visitors_and_bogota_day_boundary(database_session: AsyncSession) -> None:
    visitor = uuid4()
    before = datetime(2026, 11, 11, 4, 59, tzinfo=UTC)
    after = before + timedelta(minutes=2)
    await analytics.record_event(database_session, event(visitor_id=visitor), before)
    await analytics.record_event(database_session, event(visitor_id=visitor), after)
    await analytics.record_event(database_session, event(), after)
    data = await analytics.summary(
        database_session, before.date() - timedelta(days=1), after.date(), after
    )
    assert [item.estimated_visitors for item in data.daily] == [1, 2]
    assert data.totals.estimated_visitors == 3
    assert data.monthly[0].estimated_visitors == 3


async def test_retry_after_midnight_does_not_count_again(database_session: AsyncSession) -> None:
    payload = event()
    await analytics.record_event(database_session, payload, NOW)
    assert not await analytics.record_event(database_session, payload, NOW + timedelta(days=1))


async def test_rollback_also_rolls_back_dedup(database_session: AsyncSession) -> None:
    payload = event()
    await analytics.record_event(database_session, payload, NOW)
    await database_session.rollback()
    assert await analytics.record_event(database_session, payload, NOW)
    row = await database_session.get(WebsiteAnalyticsDaily, NOW.date())
    assert row is not None and row.page_views == 1


@pytest.mark.parametrize(
    "path",
    [
        "/admin",
        "/portal",
        "/login",
        "/expedientes/privado",
        "/?email=persona@example.com",
        "/servicios/persona-privada",
        "/analisis/no-publicado",
        "https://otro.example/",
    ],
)
async def test_private_unknown_and_sensitive_paths_are_rejected(
    client: AsyncClient, path: str
) -> None:
    payload = {
        "event_id": str(uuid4()),
        "visitor_id": str(uuid4()),
        "kind": "page_view",
        "path": path,
    }
    assert (await client.post(COLLECT, json=payload)).status_code == 422


async def test_extra_personal_fields_are_rejected(client: AsyncClient) -> None:
    payload = event().model_dump(mode="json") | {"email": "not-stored@example.com"}
    assert (await client.post(COLLECT, json=payload)).status_code == 422


@pytest.mark.parametrize("headers", [{"DNT": "1"}, {"Sec-GPC": "1"}])
async def test_opt_out_does_not_write(
    client: AsyncClient,
    database_session: AsyncSession,
    headers: dict[str, str],
) -> None:
    assert (
        await client.post(COLLECT, json=event().model_dump(mode="json"), headers=headers)
    ).status_code == 204
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDaily)) == 0
    )


async def test_disabled_collection(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBSITE_ANALYTICS_ENABLED", "false")
    assert (await client.post(COLLECT, json=event().model_dump(mode="json"))).status_code == 204
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDedup)) == 0
    )


async def test_report_is_private(
    client: AsyncClient,
    admin_token: str,
    staff_token: str,
    portal_token: str,
) -> None:
    assert (await client.get(REPORT)).status_code == 401
    for token in (staff_token, portal_token):
        assert (
            await client.get(REPORT, headers={"Authorization": f"Bearer {token}"})
        ).status_code == 403
    response = await client.get(REPORT, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["daily"]) == 30
    assert data["totals"]["page_views"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "start=2026-11-10&end=2026-11-01",
        "start=2020-01-01&end=2026-01-01",
        "start=2099-01-01&end=2099-01-02",
        "start=no-es-fecha",
    ],
)
async def test_invalid_ranges(client: AsyncClient, admin_token: str, query: str) -> None:
    response = await client.get(
        f"{REPORT}?{query}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


async def test_purge_removes_tokens_but_keeps_aggregate_totals(
    database_session: AsyncSession,
) -> None:
    await analytics.record_event(database_session, event(), NOW)
    await analytics.cleanup(database_session, NOW + timedelta(hours=49))
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDedup)) == 0
    )
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDaily)) == 1
    )
    await analytics.cleanup(database_session, NOW + timedelta(days=401))
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDaily)) == 0
    )
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsPage)) == 0
    )


async def test_no_audit_copy_of_visitor_metadata(
    client: AsyncClient,
    database_session: AsyncSession,
    enabled_audit: object,
) -> None:
    del enabled_audit
    response = await client.post(COLLECT, json=event().model_dump(mode="json"))
    assert response.status_code == 204
    assert response.content == b""
    assert await database_session.scalar(select(func.count()).select_from(AuditLog)) == 0
    assert set(WebsiteAnalyticsDedup.__table__.columns.keys()) == {"token", "expires_at"}


async def test_accepted_consultations_count_without_personal_fields(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    payload = {
        "full_name": "Persona de prueba",
        "phone": "3000000000",
        "email": "test@example.com",
        "area": "Otra consulta",
        "message": "Consulta sintética dentro de una transacción revertida.",
        "consent": False,
        "website": "",
    }
    assert (await client.post("/api/v1/consultations", json=payload)).status_code == 422
    assert (
        await database_session.scalar(select(func.count()).select_from(WebsiteAnalyticsDaily)) == 0
    )
    payload["consent"] = True
    assert (await client.post("/api/v1/consultations", json=payload)).status_code == 201
    row = (await database_session.scalars(select(WebsiteAnalyticsDaily))).one()
    assert row.consultations == 1
    assert row.page_views == 0
