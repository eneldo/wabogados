import asyncio
import hashlib
import hmac
import json
import secrets
import socket
import time
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import timedelta
from email import policy
from email.parser import BytesParser
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from aiosmtpd.controller import Controller
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.recovery_config import RecoverySettings, get_recovery_settings
from app.models import AuditLog, PasswordRecoveryToken, RecoveryMail, User
from app.schemas.auth import UserUpdate
from app.security import hash_password, verify_password
from app.services.auth import TokenService, UserService
from app.services.credentials import lock_user
from app.services.identity import UserAdminService
from app.services.password_recovery import (
    GENERIC_RECOVERY_MESSAGE,
    PasswordRecoveryService,
    RecoveryError,
    digest_token,
    utcnow,
)
from app.services.rate_limit_store import RateLimitStoreError
from app.services.recovery_limits import recovery_store
from app.services.recovery_mail import RecoveryDeliveryError, send_recovery_mail
from app.services.recovery_worker import RecoveryWorker

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
PASSWORD = "  synthetic-recovered-password  "


@pytest.fixture(autouse=True)
def recovery_config(monkeypatch: pytest.MonkeyPatch) -> Iterator[RecoverySettings]:
    for name, value in {
        "ENABLED": "true",
        "PUBLIC_URL": "http://127.0.0.1:3013",
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "PROXY_KEY": secrets.token_urlsafe(32),
        "SMTP_HOST": "127.0.0.1",
        "SMTP_SECURITY": "plain",
        "MAIL_FROM": "recovery@example.com",
    }.items():
        monkeypatch.setenv(f"PASSWORD_RECOVERY_{name}", value)
    get_recovery_settings.cache_clear()
    recovery_store.cache_clear()
    yield get_recovery_settings()
    get_recovery_settings.cache_clear()
    recovery_store.cache_clear()


@pytest.fixture
def delivered() -> list[tuple[str, str, UUID]]:
    return []


def capturing_sender(delivered: list[tuple[str, str, UUID]]) -> Callable[..., Any]:
    async def send(config: RecoverySettings, email: str, token: str, job: UUID) -> None:
        delivered.append((email, token, job))

    return send


async def issue(
    session: AsyncSession,
    factory: Callable[[], AsyncSession],
    email: str,
    delivered: list[tuple[str, str, UUID]],
) -> str:
    await PasswordRecoveryService(session).request(email)
    await session.commit()
    worker = RecoveryWorker(factory, sender=capturing_sender(delivered))
    assert await worker.run_once() == 1
    return delivered[-1][1]


async def test_generic_intake_resolves_eligibility_only_in_worker(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user_in_db: User,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
) -> None:
    before = test_user_in_db.hashed_password
    for email in (test_user_in_db.email, "not-registered@example.com"):
        response = await client.post(FORGOT, json={"email": email})
        assert response.status_code == 202 and response.json() == {
            "message": GENERIC_RECOVERY_MESSAGE
        }
        assert response.headers["cache-control"] == "no-store"
    jobs = list((await database_session.scalars(select(RecoveryMail))).all())
    assert len(jobs) == 2
    assert all(job.user_id is None and job.token_id is None for job in jobs)
    assert test_user_in_db.email not in json.dumps([job.encrypted_payload for job in jobs])
    assert await RecoveryWorker(session_factory, sender=capturing_sender(delivered)).run_once() == 1
    assert delivered[0][0] == test_user_in_db.email
    await database_session.refresh(test_user_in_db)
    assert test_user_in_db.hashed_password == before and test_user_in_db.token_version == 0
    rows = list(
        (
            await database_session.scalars(
                select(RecoveryMail).execution_options(populate_existing=True)
            )
        ).all()
    )
    assert {row.status for row in rows} == {"sent", "cancelled"}
    assert all(row.encrypted_payload is None for row in rows)


@pytest.mark.parametrize("field", ["is_active", "is_verified"])
async def test_ineligible_accounts_never_receive_mail(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
    field: str,
) -> None:
    setattr(test_user_in_db, field, False)
    await database_session.flush()
    assert (await client.post(FORGOT, json={"email": test_user_in_db.email})).status_code == 202
    assert await RecoveryWorker(session_factory, sender=capturing_sender(delivered)).run_once() == 0
    assert delivered == []


async def test_recovery_consumes_token_revokes_sessions_and_preserves_other_accounts(
    client: AsyncClient,
    test_user_in_db: User,
    admin_user: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
) -> None:
    sessions = TokenService(database_session)
    old_access, old_refresh = await sessions.issue_session(test_user_in_db)
    other_access, _ = await sessions.issue_session(admin_user)
    roles = [role.name for role in test_user_in_db.roles]
    token = await issue(database_session, session_factory, test_user_in_db.email, delivered)
    stored = await database_session.scalar(select(PasswordRecoveryToken))
    assert stored is not None and stored.token_hash == digest_token(token)
    assert stored.token_hash != token and len(token) == 43
    payload = {"token": token, "new_password": PASSWORD, "confirm_password": PASSWORD}
    response = await client.post(RESET, json=payload)
    assert response.status_code == 200
    assert token not in response.text and PASSWORD not in response.text
    assert (await client.post(RESET, json=payload)).status_code == 400
    await database_session.refresh(test_user_in_db)
    assert test_user_in_db.token_version == 1 and verify_password(
        PASSWORD, test_user_in_db.hashed_password
    )
    assert test_user_in_db.is_active and test_user_in_db.is_verified
    assert [role.name for role in test_user_in_db.roles] == roles
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    ).status_code == 401
    assert await sessions.refresh_access_token(old_refresh) is None
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other_access}"})
    ).status_code == 200
    for password, code in (("testpassword123", 401), (PASSWORD, 200)):
        assert (
            await client.post(
                "/api/v1/auth/login", json={"email": test_user_in_db.email, "password": password}
            )
        ).status_code == code
    audit = await database_session.scalar(
        select(AuditLog).where(AuditLog.action == "password_recovery_completed")
    )
    assert audit is not None and audit.entity_id == test_user_in_db.id
    assert token not in json.dumps(audit.after) and PASSWORD not in json.dumps(audit.after)


@pytest.mark.parametrize("mutation", ["expired", "used", "revoked", "version", "email", "inactive"])
async def test_invalid_link_variants_have_same_error(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
    mutation: str,
) -> None:
    raw = await issue(database_session, session_factory, test_user_in_db.email, delivered)
    token = await database_session.scalar(select(PasswordRecoveryToken))
    assert token is not None
    if mutation == "expired":
        token.expires_at = utcnow() - timedelta(seconds=1)
    elif mutation == "used":
        token.used_at = utcnow()
    elif mutation == "revoked":
        token.revoked_at = utcnow()
    elif mutation == "version":
        test_user_in_db.token_version += 1
    elif mutation == "email":
        test_user_in_db.email = "different@example.com"
    else:
        test_user_in_db.is_active = False
    await database_session.flush()
    # Do not let the API's deliberate rollback discard the synthetic setup.
    await database_session.commit()
    response = await client.post(
        RESET, json={"token": raw, "new_password": PASSWORD, "confirm_password": PASSWORD}
    )
    assert response.status_code == 400
    assert (
        response.json()["error"]["message"]
        == "El enlace no es válido o ha caducado. Solicite uno nuevo."
    )


@pytest.mark.parametrize("operation", ["admin", "email", "deactivate", "unverify"])
async def test_identity_mutations_cancel_issued_and_pending_requests(
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
    operation: str,
) -> None:
    raw = await issue(database_session, session_factory, test_user_in_db.email, delivered)
    await PasswordRecoveryService(database_session).request(test_user_in_db.email)
    service = UserAdminService(database_session)
    user = await service.get_user(test_user_in_db.id, lock=True)
    assert user is not None
    if operation == "admin":
        await service.reset_password(user, "administrative-test-password", user.id)
    elif operation == "email":
        email = user.email
        await service.update_user(user, UserUpdate(email="changed@example.com", is_verified=True))
        assert not user.is_verified
        await service.update_user(user, UserUpdate(email=email, is_verified=True))
        await service.update_user(user, UserUpdate(is_verified=True))
    elif operation == "deactivate":
        await service.deactivate_user(user, user.id)
        await service.update_user(user, UserUpdate(is_active=True))
    else:
        await service.update_user(user, UserUpdate(is_verified=False))
        await service.update_user(user, UserUpdate(is_verified=True))
    await database_session.commit()
    assert await RecoveryWorker(session_factory, sender=capturing_sender(delivered)).run_once() == 0
    with pytest.raises(RecoveryError):
        await PasswordRecoveryService(database_session).confirm(raw, PASSWORD)


async def test_newest_request_supersedes_and_worker_retry_keeps_same_token(
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
) -> None:
    old = await issue(database_session, session_factory, test_user_in_db.email, delivered)
    attempted: list[str] = []

    async def failing(config: RecoverySettings, email: str, token: str, job: UUID) -> None:
        attempted.append(token)
        raise RecoveryDeliveryError("redacted")

    await PasswordRecoveryService(database_session).request(test_user_in_db.email)
    await database_session.commit()
    worker = RecoveryWorker(session_factory, sender=failing)
    assert await worker.run_once() == 0
    with pytest.raises(RecoveryError):
        await PasswordRecoveryService(database_session).confirm(old, PASSWORD)
    await database_session.execute(
        update(RecoveryMail).where(RecoveryMail.status == "ready").values(next_attempt_at=utcnow())
    )
    await database_session.commit()
    worker.sender = capturing_sender(delivered)
    assert await worker.run_once() == 1
    assert attempted[0] == delivered[-1][1] and old != delivered[-1][1]


async def test_worker_exhaustion_expiry_disable_and_maintenance(
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    recovery_config: RecoverySettings,
) -> None:
    async def failing(config: RecoverySettings, email: str, token: str, job: UUID) -> None:
        raise RecoveryDeliveryError("redacted")

    await PasswordRecoveryService(database_session).request(test_user_in_db.email)
    await database_session.commit()
    worker = RecoveryWorker(session_factory, sender=failing)
    for _ in range(3):
        assert await worker.run_once() == 0
        await database_session.execute(update(RecoveryMail).values(next_attempt_at=utcnow()))
        await database_session.commit()
    job = await database_session.scalar(
        select(RecoveryMail).execution_options(populate_existing=True)
    )
    assert job is not None and job.status == "failed" and job.attempts == 3
    assert job.encrypted_payload is None
    await PasswordRecoveryService(database_session).request(test_user_in_db.email)
    await database_session.commit()
    recovery_config.enabled = False
    assert await worker.run_once() == 0
    assert (
        await database_session.scalar(
            select(RecoveryMail.id).where(RecoveryMail.encrypted_payload.is_not(None))
        )
        is None
    )
    await database_session.execute(
        update(RecoveryMail).values(expires_at=utcnow() - timedelta(days=2))
    )
    await database_session.execute(
        update(PasswordRecoveryToken).values(expires_at=utcnow() - timedelta(days=2))
    )
    await database_session.commit()
    await worker.maintenance()
    assert await database_session.scalar(select(RecoveryMail.id)) is None
    assert await database_session.scalar(select(PasswordRecoveryToken.id)) is None


async def test_disabled_invalid_config_limits_and_secret_free_validation(
    client: AsyncClient,
    test_user_in_db: User,
    recovery_config: RecoverySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery_config.enabled = False
    assert (await client.get("/api/v1/auth/password-recovery")).json() == {"enabled": False}
    assert (await client.post(FORGOT, json={"email": test_user_in_db.email})).status_code == 503
    recovery_config.enabled = True
    recovery_config.public_url = "https://evil.example/path?query=yes"
    assert (await client.post(FORGOT, json={"email": test_user_in_db.email})).status_code == 503
    recovery_config.public_url = "http://127.0.0.1:3013"
    assert (await client.get("/api/v1/auth/password-recovery")).json() == {"enabled": True}
    for payload in (
        {"token": "x" * 43, "new_password": PASSWORD, "confirm_password": "mismatch"},
        {"token": "secret-token", "new_password": "short", "confirm_password": "short"},
    ):
        response = await client.post(RESET, json=payload)
        assert response.status_code == 422 and PASSWORD not in response.text
        assert all(
            "input" not in item and "ctx" not in item
            for item in response.json()["error"]["details"]["errors"]
        )
    recovery_config.request_ip_limit = 1
    assert (await client.post(FORGOT, json={"email": test_user_in_db.email})).status_code == 202
    assert (
        await client.post(
            FORGOT,
            json={"email": "other@example.com"},
            headers={"X-Forwarded-For": "192.0.2.5", "Authorization": "Bearer forged"},
        )
    ).status_code == 429


async def test_recipient_cooldown_is_generic_and_redis_failure_closed(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(2):
        assert (await client.post(FORGOT, json={"email": "unknown@example.com"})).status_code == 202
    assert len(list((await database_session.scalars(select(RecoveryMail))).all())) == 1

    async def broken(key: str, window: int) -> int:
        raise RateLimitStoreError("redacted")

    monkeypatch.setattr(recovery_store(), "hit", broken)
    assert (await client.post(FORGOT, json={"email": "another@example.com"})).status_code == 503


async def test_signed_ingress_ip_and_forged_headers(
    client: AsyncClient,
    recovery_config: RecoverySettings,
) -> None:
    recovery_config.request_ip_limit = 1
    stamp = str(int(time.time()))

    def signed(ip: str, when: str = stamp) -> dict[str, str]:
        signature = hmac.new(
            recovery_config.proxy_key.get_secret_value().encode(),
            f"{FORGOT}|{when}|{ip}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {"X-Recovery-Client": ip, "X-Recovery-Time": when, "X-Recovery-Signature": signature}

    assert (
        await client.post(FORGOT, json={"email": "one@example.com"}, headers=signed("192.0.2.1"))
    ).status_code == 202
    assert (
        await client.post(FORGOT, json={"email": "two@example.com"}, headers=signed("192.0.2.2"))
    ).status_code == 202
    assert (
        await client.post(FORGOT, json={"email": "three@example.com"}, headers=signed("192.0.2.1"))
    ).status_code == 429
    forged = signed("192.0.2.3")
    forged["X-Recovery-Signature"] = "f" * 64
    assert (
        await client.post(FORGOT, json={"email": "four@example.com"}, headers=forged)
    ).status_code == 202
    # Expired or malformed signatures share the real peer's budget.
    assert (
        await client.post(
            FORGOT, json={"email": "five@example.com"}, headers=signed("192.0.2.4", "1")
        )
    ).status_code == 429
    assert (
        await client.post(
            FORGOT, json={"email": "six@example.com"}, headers=signed("invalid-ip", "invalid-time")
        )
    ).status_code == 429


async def test_invalid_submissions_count_before_validation_and_have_small_body_limit(
    client: AsyncClient,
    recovery_config: RecoverySettings,
) -> None:
    recovery_config.request_ip_limit = 4
    response = await client.post(FORGOT, json={"email": "not-an-email"})
    assert response.status_code == 422
    response = await client.post(
        FORGOT, content="x" * 4097, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"email":"test@example.com"}'

    response = await client.post(
        FORGOT, content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 411
    response = await client.post(FORGOT, json={"email": "test@example.com"})
    assert response.status_code == 202
    response = await client.post(FORGOT, json={"email": "test@example.com"})
    assert response.status_code == 429


async def test_recovery_commit_failure_rolls_back_every_change(
    client: AsyncClient,
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = test_user_in_db.hashed_password
    raw = await issue(database_session, session_factory, test_user_in_db.email, delivered)
    with monkeypatch.context() as patch:
        patch.setattr(
            database_session, "commit", AsyncMock(side_effect=RuntimeError("private-details"))
        )
        response = await client.post(
            RESET, json={"token": raw, "new_password": PASSWORD, "confirm_password": PASSWORD}
        )
    assert response.status_code == 503
    assert "private-details" not in response.text and raw not in response.text
    await database_session.refresh(test_user_in_db)
    assert test_user_in_db.hashed_password == original and test_user_in_db.token_version == 0
    stored = await database_session.scalar(select(PasswordRecoveryToken))
    assert stored is not None and stored.used_at is None and stored.revoked_at is None
    assert (
        await database_session.scalar(
            select(AuditLog).where(AuditLog.action == "password_recovery_completed")
        )
        is None
    )


async def test_worker_reclaims_lease_and_older_request_cannot_supersede_newer(
    test_user_in_db: User,
    database_session: AsyncSession,
    session_factory: Callable[[], AsyncSession],
    delivered: list[tuple[str, str, UUID]],
) -> None:
    service = PasswordRecoveryService(database_session)
    await service.request(test_user_in_db.email)
    await database_session.commit()
    worker = RecoveryWorker(session_factory, sender=capturing_sender(delivered))
    older = await worker.claim()
    assert older is not None
    assert await worker.claim() is None
    await service.request(test_user_in_db.email)
    await database_session.commit()
    newer = await worker.claim()
    assert newer is not None
    assert await worker.prepare(*newer)
    assert not await worker.prepare(*older)
    assert not await worker.deliver(newer[0], uuid4())
    await database_session.execute(
        update(RecoveryMail)
        .where(RecoveryMail.id == newer[0])
        .values(leased_until=utcnow() - timedelta(seconds=1))
    )
    await database_session.commit()
    reclaimed = await worker.claim()
    assert reclaimed is not None and reclaimed[0] == newer[0] and reclaimed[1] != newer[1]
    assert await worker.prepare(*reclaimed) and await worker.deliver(*reclaimed)
    assert len(delivered) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("public_url", "ftp://localhost"),
        ("public_url", "https://user:pass@app.example.com"),
        ("encryption_key", "not-a-key"),
        ("proxy_key", "short"),
        ("mail_from", "bad@address with spaces"),
        ("smtp_user", "without-password"),
    ],
)
def test_invalid_enabled_configuration_is_refused(
    recovery_config: RecoverySettings,
    field: str,
    value: str,
) -> None:
    from pydantic import SecretStr

    setattr(recovery_config, field, SecretStr(value) if field.endswith("key") else value)
    with pytest.raises(ValueError):
        recovery_config.validate_enabled("test")


async def test_smtp_failure_never_contains_provider_details(
    recovery_config: RecoverySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import smtplib

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("private-token-and-recipient")

    monkeypatch.setattr(smtplib, "SMTP", broken)
    with pytest.raises(RecoveryDeliveryError) as error:
        await send_recovery_mail(
            recovery_config, "synthetic@example.com", secrets.token_urlsafe(32), uuid4()
        )
    assert str(error.value) == "smtp_delivery_failed"


def test_configuration_requires_secure_public_origin_and_keys(
    recovery_config: RecoverySettings,
) -> None:
    recovery_config.validate_enabled("test")
    with pytest.raises(ValueError):
        recovery_config.validate_enabled("production")
    recovery_config.public_url = "https://app.example.com"
    recovery_config.smtp_security = "starttls"
    recovery_config.validate_enabled("production")
    assert "encryption_key='" not in repr(recovery_config)


async def test_real_smtp_message_uses_fragment_and_no_password(
    recovery_config: RecoverySettings,
) -> None:
    messages: list[bytes] = []

    class Handler:
        async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
            messages.append(envelope.original_content)
            return "250 OK"

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = Controller(Handler(), hostname="127.0.0.1", port=port)
    server.start()
    recovery_config.smtp_port = port
    raw = secrets.token_urlsafe(32)
    try:
        await send_recovery_mail(recovery_config, "synthetic@example.com", raw, uuid4())
    finally:
        server.stop()
    assert len(messages) == 1
    message = BytesParser(policy=policy.default).parsebytes(messages[0])
    plain = message.get_body(preferencelist=("plain",))
    assert plain is not None
    body = str(plain.get_content())
    assert f"/restablecer-contrasena#token={raw}" in body
    assert PASSWORD not in body and "?token=" not in body


@pytest.mark.parametrize("operation", ["confirm", "admin", "email", "login", "refresh"])
@pytest.mark.parametrize("recovery_first", [True, False])
async def test_real_transactions_serialize_recovery(
    test_engine: AsyncEngine,
    operation: str,
    recovery_first: bool,
    delivered: list[tuple[str, str, UUID]],
) -> None:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id = uuid4()
    email = f"recovery-race-{user_id}@example.com"
    async with factory() as seed:
        user = User(
            id=user_id, email=email, hashed_password=hash_password("old-password"), is_verified=True
        )
        seed.add(user)
        await seed.commit()
        _, refresh = await TokenService(seed).issue_session(user)
        await seed.commit()
        raw = await issue(seed, factory, email, delivered)

    async def recover(session: AsyncSession) -> bool:
        try:
            await PasswordRecoveryService(session).confirm(raw, PASSWORD)
            return True
        except RecoveryError:
            return False

    async def other(session: AsyncSession) -> bool:
        if operation == "confirm":
            return await recover(session)
        if operation == "refresh":
            return await TokenService(session).refresh_access_token(refresh) is not None
        if operation == "login":
            return await UserService(session).authenticate(email, "old-password") is not None
        user = await lock_user(session, user_id)
        assert user is not None
        service = UserAdminService(session)
        if operation == "admin":
            await service.reset_password(user, "other-new-password", user.id)
        else:
            await service.update_user(user, UserUpdate(email=f"changed-{user_id}@example.com"))
        return True

    try:
        async with factory() as first, factory() as second:
            result_first = await recover(first) if recovery_first else await other(first)
            assert result_first
            pid = await second.scalar(text("SELECT pg_backend_pid()"))

            async def waiting() -> bool:
                result = await other(second) if recovery_first else await recover(second)
                await second.commit()
                return result

            task = asyncio.create_task(waiting())
            try:
                async with asyncio.timeout(5):
                    async with factory() as observer:
                        for _ in range(500):
                            if await observer.scalar(
                                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
                            ):
                                break
                            await asyncio.sleep(0.01)
                        else:
                            raise AssertionError("No PostgreSQL lock wait observed")
                await first.commit()
                result_second = await asyncio.wait_for(task, 5)
                if (
                    operation == "confirm"
                    or (recovery_first and operation in {"login", "refresh"})
                    or (not recovery_first and operation in {"admin", "email"})
                ):
                    assert not result_second
                else:
                    assert result_second
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
