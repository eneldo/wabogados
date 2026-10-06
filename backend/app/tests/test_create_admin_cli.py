"""Tests for the bootstrap administrator CLI.

The CLI assigns a role through an explicit query. Reading the `roles`
collection instead would trigger a lazy load outside the async greenlet
context and raise MissingGreenlet, which is why it is covered here.

The CLI opens its own session, so every test injects a factory bound to the
rolled back transaction and no administrator survives the test.
"""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import create_admin as create_admin_module
from app.core.config import get_settings
from app.models import Role, User, UserRole
from app.security import verify_password

PASSWORD = "Clave-Fuerte-De-Prueba-2026"


@pytest.fixture
def admin_email(monkeypatch: pytest.MonkeyPatch) -> str:
    email = "bootstrap@example.com"
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_email", email, raising=False)
    monkeypatch.setattr(settings, "admin_password", PASSWORD, raising=False)
    return email


@pytest.fixture
def run_cli(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[], Awaitable[int]]:
    async def runner() -> int:
        return await create_admin_module.create_admin(session_factory)

    return runner


@pytest.mark.asyncio
async def test_creates_administrator_with_role(
    admin_email: str,
    run_cli: Callable[[], Awaitable[int]],
    session_factory: Callable[[], AsyncSession],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = await run_cli()

    assert exit_code == 0
    assert admin_email in capsys.readouterr().out

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == admin_email))
        assert user is not None
        assert user.is_superuser is True
        assert user.is_verified is True
        assert user.is_active is True
        assert verify_password(PASSWORD, user.hashed_password) is True

        roles = await session.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        assert roles.scalars().all() == ["administrador"]


@pytest.mark.asyncio
async def test_rerun_is_idempotent_and_does_not_duplicate_the_role(
    admin_email: str,
    run_cli: Callable[[], Awaitable[int]],
    session_factory: Callable[[], AsyncSession],
) -> None:
    assert await run_cli() == 0
    assert await run_cli() == 0

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == admin_email))
        assert user is not None
        rows = list(
            (
                await session.execute(
                    select(UserRole).where(UserRole.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_missing_credentials_are_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_email", None, raising=False)
    monkeypatch.setattr(settings, "admin_password", None, raising=False)

    exit_code = await create_admin_module.create_admin()

    assert exit_code == 2
    assert "ADMIN_EMAIL" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_administrator_can_sign_in_after_bootstrap(
    client: AsyncClient,
    admin_email: str,
    run_cli: Callable[[], Awaitable[int]],
) -> None:
    assert await run_cli() == 0

    response = await client.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == admin_email
    assert me.json()["is_superuser"] is True
    assert me.json()["roles"] == ["administrador"]
    assert "users:read" in me.json()["permissions"]
