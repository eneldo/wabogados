import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.middleware.audit import (
    AuditLogMiddleware,
    extract_user_id,
    resolve_entity,
)
from app.middleware.rate_limit import RateLimitMiddleware
from app.models import AuditLog, User
from app.security import create_access_token

AUTH = "/api/v1/auth"
ADMIN = "/api/v1/admin"


def build_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
        }
    )


def limit_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    global_limit: int = 100,
    global_window: int = 60,
    auth_limit: int = 10,
    auth_window: int = 300,
) -> Settings:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", global_limit)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", global_window)
    monkeypatch.setattr(settings, "auth_rate_limit_requests", auth_limit)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", auth_window)
    return settings


def test_extract_user_id_from_access_token(test_user_in_db: User) -> None:
    token = create_access_token(subject=test_user_in_db.id)
    request = build_request({"Authorization": f"Bearer {token}"})

    assert extract_user_id(request) == test_user_in_db.id


def test_extract_user_id_ignores_invalid_headers() -> None:
    assert extract_user_id(build_request()) is None
    assert extract_user_id(build_request({"Authorization": "Basic abc"})) is None
    assert extract_user_id(build_request({"Authorization": "Bearer not-a-jwt"})) is None


async def test_extract_user_id_ignores_refresh_token(test_user_in_db: User) -> None:
    from app.security import create_refresh_token

    token = create_refresh_token(subject=test_user_in_db.id, jti="abc")

    assert extract_user_id(build_request({"Authorization": f"Bearer {token}"})) is None


async def test_login_is_audited(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    response = await client.post(
        f"{AUTH}/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    result = await database_session.execute(
        select(AuditLog).where(AuditLog.action == "POST /api/v1/auth/login")
    )
    entries = list(result.scalars().all())

    assert response.status_code == 200
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entity == "auth"
    assert entry.entity_id is None
    assert entry.result == "success"
    assert entry.ip_address == "127.0.0.1"
    after = entry.after
    assert after is not None
    assert after == {
        "status_code": 200,
        "method": "POST",
        "path": "/api/v1/auth/login",
    }


async def test_audit_never_stores_credentials(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    await client.post(
        f"{AUTH}/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    entry = (
        await database_session.execute(
            select(AuditLog).where(AuditLog.action == "POST /api/v1/auth/login")
        )
    ).scalar_one()

    serialized = str(entry.after) + str(entry.before)
    assert "testpassword123" not in serialized


async def test_request_body_survives_audit_middleware(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    """The audit middleware must never consume the payload the route needs."""

    response = await client.post(
        f"{AUTH}/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_failed_admin_call_is_audited_as_error(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    from uuid import uuid4

    target = uuid4()
    response = await client.patch(
        f"{ADMIN}/users/{target}",
        json={"full_name": "No existe"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    result = await database_session.execute(
        select(AuditLog).where(AuditLog.user_id == admin_user.id)
    )
    entries = list(result.scalars().all())

    assert response.status_code == 404
    assert len(entries) == 1
    assert entries[0].result == "error"
    assert entries[0].action == f"PATCH {ADMIN}/users/{target}"
    assert entries[0].entity == "users"
    assert entries[0].entity_id == target


def test_resolve_entity_understands_api_paths() -> None:
    from uuid import uuid4

    record = uuid4()

    assert resolve_entity(f"/api/v1/admin/users/{record}") == ("users", record)
    assert resolve_entity(f"/api/v1/admin/users/{record}/roles") == ("users", record)
    assert resolve_entity("/api/v1/auth/login") == ("auth", None)
    assert resolve_entity("/api/v1/auth/me") == ("auth", None)
    assert resolve_entity("/") == ("unknown", None)


async def test_audit_logs_endpoint_serializes_uuid_entity(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    from uuid import uuid4

    target = uuid4()
    await client.patch(
        f"{ADMIN}/users/{target}",
        json={"full_name": "No existe"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    logs = await client.get(
        f"{ADMIN}/audit-logs", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert logs.status_code == 200
    entry = next(
        item for item in logs.json()["items"] if item["entity_id"] == str(target)
    )
    assert entry["user_id"] == str(admin_user.id)
    assert entry["entity"] == "users"
    assert entry["user_email"] == admin_user.email


async def test_read_operations_are_not_audited(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    audit_in_test_transaction: AuditLogMiddleware,
) -> None:
    await client.get(f"{ADMIN}/users", headers={"Authorization": f"Bearer {admin_token}"})

    result = await database_session.execute(select(AuditLog))

    assert list(result.scalars().all()) == []


async def test_rate_limit_blocks_after_threshold(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit_settings(monkeypatch, auth_limit=2, auth_window=60)
    payload = {"email": "a@b.com", "password": "x"}

    first = await client.post(f"{AUTH}/login", json=payload)
    second = await client.post(f"{AUTH}/login", json=payload)
    third = await client.post(f"{AUTH}/login", json=payload)

    assert first.status_code == 422
    assert second.status_code == 422
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limit_exceeded"
    assert third.headers["Retry-After"] == "60"


async def test_auth_rate_limit_is_stricter_than_global(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    reset_rate_limiter: RateLimitMiddleware,
) -> None:
    limit_settings(monkeypatch, global_limit=100, auth_limit=1, auth_window=300)
    payload = {"email": "a@b.com", "password": "x"}

    first = await client.post(f"{AUTH}/login", json=payload)
    limited = await client.post(f"{AUTH}/login", json=payload)
    health = await client.get("/api/v1/health/live")

    assert first.status_code == 422
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "300"
    assert health.status_code == 200


async def test_rate_limit_state_is_released_after_reset(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    reset_rate_limiter: RateLimitMiddleware,
) -> None:
    limit_settings(monkeypatch, auth_limit=1, auth_window=1)
    payload = {"email": "a@b.com", "password": "x"}

    await client.post(f"{AUTH}/login", json=payload)
    blocked = await client.post(f"{AUTH}/login", json=payload)

    reset_rate_limiter.reset()
    allowed = await client.post(f"{AUTH}/login", json=payload)

    assert blocked.status_code == 429
    assert allowed.status_code == 422


async def test_rate_limit_window_expiry_prunes_entries(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    reset_rate_limiter: RateLimitMiddleware,
) -> None:
    limit_settings(monkeypatch, auth_limit=1, auth_window=1)
    payload = {"email": "a@b.com", "password": "x"}

    await client.post(f"{AUTH}/login", json=payload)

    reset_rate_limiter.requests = {
        key: [value - 5 for value in entries]
        for key, entries in reset_rate_limiter.requests.items()
    }
    allowed = await client.post(f"{AUTH}/login", json=payload)

    assert allowed.status_code == 422
    assert all(
        len(entries) == 1
        for key, entries in reset_rate_limiter.requests.items()
        if key.startswith("ratelimit:ip:")
    )


def test_rate_limit_keys_by_authenticated_user(
    reset_rate_limiter: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit_settings(monkeypatch)
    token = create_access_token(subject="11111111-1111-1111-1111-111111111111")

    user_key = reset_rate_limiter._client_key(
        build_request({"Authorization": f"Bearer {token}"})
    )
    ip_key = reset_rate_limiter._client_key(build_request())

    assert user_key == "user:11111111-1111-1111-1111-111111111111"
    assert ip_key == "ip:127.0.0.1"
