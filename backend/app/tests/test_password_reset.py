import asyncio
import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AuditLog, User
from app.security import create_access_token, decode_token, hash_password, verify_password
from app.services.auth import TokenService, UserService
from app.services.identity import UserAdminService

PASSWORD = "  synthetic-new-password  "
PAYLOAD = {"new_password": PASSWORD, "confirm_password": PASSWORD}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_reset_revokes_only_target_and_preserves_profile(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    plain_user: User,
    database_session: AsyncSession,
) -> None:
    sessions = TokenService(database_session)
    old_access, old_refresh = await sessions.issue_session(plain_user)
    second_access, second_refresh = await sessions.issue_session(plain_user)
    admin_access, admin_refresh = await sessions.issue_session(admin_user)
    original = (
        plain_user.email,
        plain_user.full_name,
        plain_user.is_active,
        [role.name for role in plain_user.roles],
    )
    response = await client.post(
        f"/api/v1/admin/users/{plain_user.id}/reset-password",
        json=PAYLOAD,
        headers=bearer(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 2
    assert plain_user.token_version == 1
    assert verify_password(PASSWORD, plain_user.hashed_password)
    assert original == (
        plain_user.email,
        plain_user.full_name,
        plain_user.is_active,
        [role.name for role in plain_user.roles],
    )
    for access in (old_access, second_access, create_access_token(plain_user.id)):
        assert (await client.get("/api/v1/auth/me", headers=bearer(access))).status_code == 401
    for refresh in (old_refresh, second_refresh):
        assert (
            await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        ).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=bearer(admin_access))).status_code == 200
    assert await sessions.refresh_access_token(admin_refresh) is not None
    for password, code in (("testpassword123", 401), (PASSWORD.strip(), 401), (PASSWORD, 200)):
        login = await client.post(
            "/api/v1/auth/login", json={"email": plain_user.email, "password": password}
        )
        assert login.status_code == code
        if code == 200:
            assert decode_token(login.json()["access_token"])["token_version"] == 1
            assert (
                await client.get("/api/v1/auth/me", headers=bearer(login.json()["access_token"]))
            ).status_code == 200
            rotated = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
            )
            assert rotated.status_code == 200
            assert decode_token(rotated.json()["access_token"])["token_version"] == 1
    audit = await database_session.scalar(
        select(AuditLog).where(AuditLog.action == "admin_password_reset")
    )
    assert audit is not None
    assert audit.user_id == admin_user.id and audit.entity_id == plain_user.id
    assert audit.after == {"revoked_sessions": 2}
    assert PASSWORD not in response.text + json.dumps(audit.after)


async def test_reset_authorization_and_superuser_protection(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    plain_user: User,
    plain_user_token: str,
    database_session: AsyncSession,
) -> None:
    path = f"/api/v1/admin/users/{plain_user.id}/reset-password"
    assert (await client.post(path, json=PAYLOAD)).status_code == 401
    assert (
        await client.post(path, json=PAYLOAD, headers=bearer(plain_user_token))
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/admin/users/{admin_user.id}/reset-password",
            json=PAYLOAD,
            headers=bearer(admin_token),
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/v1/admin/users/{uuid4()}/reset-password",
            json=PAYLOAD,
            headers=bearer(admin_token),
        )
    ).status_code == 404
    plain_user.is_active = False
    await database_session.flush()
    assert (await client.post(path, json=PAYLOAD, headers=bearer(admin_token))).status_code == 400
    plain_user.is_active = True
    plain_user.is_superuser = True
    await database_session.flush()
    assert (await client.post(path, json=PAYLOAD, headers=bearer(admin_token))).status_code == 403
    # Cannot bypass the protected-target rule by first removing superuser status.
    assert (
        await client.patch(
            f"/api/v1/admin/users/{plain_user.id}",
            json={"is_superuser": False},
            headers=bearer(admin_token),
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/admin/users/{admin_user.id}",
            json={"is_superuser": True},
            headers=bearer(admin_token),
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/users",
            json={"email": "blocked@example.com", "password": PASSWORD, "is_superuser": True},
            headers=bearer(admin_token),
        )
    ).status_code == 403
    admin_user.is_superuser = True
    await database_session.flush()
    assert (await client.post(path, json=PAYLOAD, headers=bearer(admin_token))).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"new_password": "short", "confirm_password": "short"},
        {"new_password": "x" * 129, "confirm_password": "x" * 129},
        {"new_password": PASSWORD, "confirm_password": "not-the-same"},
        {"new_password": {"nested_secret": PASSWORD}, "confirm_password": PASSWORD},
        {**PAYLOAD, "unexpected_secret": PASSWORD},
        {},
    ],
)
async def test_invalid_password_never_echoed(
    client: AsyncClient,
    admin_token: str,
    plain_user: User,
    payload: dict[str, object],
) -> None:
    before = plain_user.hashed_password
    response = await client.post(
        f"/api/v1/admin/users/{plain_user.id}/reset-password",
        json=payload,
        headers=bearer(admin_token),
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all(
        "input" not in error and "ctx" not in error
        for error in response.json()["error"]["details"]["errors"]
    )
    assert plain_user.hashed_password == before and plain_user.token_version == 0


async def test_reset_rollback_is_atomic(
    database_session: AsyncSession,
    admin_user: User,
    plain_user: User,
) -> None:
    user_id = plain_user.id
    original_hash = plain_user.hashed_password
    access, refresh = await TokenService(database_session).issue_session(plain_user)
    async with database_session.begin_nested() as transaction:
        locked = await UserAdminService(database_session).get_user(user_id, lock=True)
        assert locked is not None
        await UserAdminService(database_session).reset_password(locked, PASSWORD, admin_user.id)
        await transaction.rollback()
    await database_session.refresh(plain_user)
    assert plain_user.token_version == 0 and plain_user.hashed_password == original_hash
    assert await TokenService(database_session).refresh_access_token(refresh) is not None
    assert decode_token(access).get("token_version", 0) == 0
    assert (
        await database_session.scalar(
            select(AuditLog).where(AuditLog.action == "admin_password_reset")
        )
        is None
    )


async def test_reset_has_separate_sensitive_rate_budget(
    client: AsyncClient,
    admin_token: str,
    plain_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "auth_rate_limit_requests", 1)
    path = f"/api/v1/admin/users/{plain_user.id}/reset-password"
    assert (await client.post(path, json=PAYLOAD, headers=bearer(admin_token))).status_code == 200
    assert (await client.post(path, json=PAYLOAD, headers=bearer(admin_token))).status_code == 429
    assert (await client.get("/api/v1/auth/me", headers=bearer(admin_token))).status_code == 200


@pytest.mark.parametrize("operation", ["login", "refresh"])
@pytest.mark.parametrize("reset_first", [True, False])
async def test_reset_serializes_with_credential_issuance(
    test_engine: AsyncEngine,
    operation: str,
    reset_first: bool,
) -> None:
    """Independent real PostgreSQL transactions, with an observed lock wait.

    No shared savepoint: that would never exercise a race between connections.
    Only synthetic rows in the isolated test database are committed and removed.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id = uuid4()
    email = f"race-{user_id}@example.com"
    async with factory() as seed:
        seed.add(User(id=user_id, email=email, hashed_password=hash_password("old-password")))
        await seed.commit()
        user = await seed.get(User, user_id)
        assert user is not None
        _, old_refresh = await TokenService(seed).issue_session(user)
        await seed.commit()

    async def reset(session: AsyncSession) -> None:
        user = await UserAdminService(session).get_user(user_id, lock=True)
        assert user is not None
        await UserAdminService(session).reset_password(user, PASSWORD, user_id)

    async def issue(session: AsyncSession) -> tuple[str, str] | None:
        if operation == "refresh":
            return await TokenService(session).refresh_access_token(old_refresh)
        user = await UserService(session).authenticate(email, "old-password")
        return await TokenService(session).issue_session(user) if user else None

    try:
        async with factory() as first, factory() as second:
            issued = None
            if reset_first:
                await reset(first)
            else:
                issued = await issue(first)
                assert issued is not None
            pid = await second.scalar(text("SELECT pg_backend_pid()"))

            async def waiting_operation() -> tuple[str, str] | None:
                result = None
                if reset_first:
                    result = await issue(second)
                else:
                    await reset(second)
                await second.commit()
                return result

            task = asyncio.create_task(waiting_operation())
            try:
                async with asyncio.timeout(5):
                    async with factory() as observer:
                        # Observe the database lock, not a guessed time delay.
                        # There is no in-process Event for a PostgreSQL wait.
                        for _ in range(500):
                            if await observer.scalar(
                                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                                {"pid": pid},
                            ):
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("Expected a real PostgreSQL row-lock wait")
                await first.commit()
                result = await asyncio.wait_for(task, 5)
                if reset_first:
                    assert result is None
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            async with factory() as check:
                stored = await check.get(User, user_id)
                assert stored is not None and stored.token_version == 1
                assert verify_password(PASSWORD, stored.hashed_password)
                if issued:
                    assert decode_token(issued[0])["token_version"] == 0
                    assert await TokenService(check).refresh_access_token(issued[1]) is None
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
