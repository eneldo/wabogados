import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.auth import UserCreate, UserUpdate
from app.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.services.auth import UserService


@pytest.mark.asyncio
async def test_hash_and_verify_password() -> None:
    password = "testpassword123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


@pytest.mark.asyncio
async def test_create_access_token() -> None:
    from uuid import uuid4
    user_id = uuid4()
    token = create_access_token(subject=user_id)
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_user_service_create_get_and_update(database_session: AsyncSession) -> None:
    service = UserService(database_session)
    user = await service.create(
        UserCreate(
            email="service-user@example.com",
            password="testpassword123",
            full_name="Initial Name",
        )
    )

    stored_user = await service.get_by_id(user.id)
    updated_user = await service.update(user, UserUpdate(full_name="Updated Name"))

    assert stored_user is user
    assert updated_user.full_name == "Updated Name"
    assert verify_password("testpassword123", updated_user.hashed_password)


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_in_db: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, test_user_in_db: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "http_error"
    assert "Credenciales inválidas" in data["error"]["message"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(
    client: AsyncClient, test_user_in_db: User
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "wrongpassword"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(
    client: AsyncClient, test_user_in_db: User
) -> None:
    test_user_in_db.is_active = False

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_email_format(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_user_in_db: User) -> None:
    # First login to get refresh token
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    # Now refresh
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "http_error"
    assert "Refresh token inválido" in data["error"]["message"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(
    client: AsyncClient, test_user_in_db: User
) -> None:
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": create_access_token(subject=test_user_in_db.id)},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_user(client: AsyncClient) -> None:
    from uuid import uuid4

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": create_refresh_token(subject=uuid4())},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_info(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user_in_db.email
    assert data["id"] == str(test_user_in_db.id)


@pytest.mark.asyncio
async def test_get_current_user_info_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_token(
    client: AsyncClient, test_user_in_db: User
) -> None:
    token = create_refresh_token(subject=test_user_in_db.id)

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    test_user_in_db.is_active = False

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_all_sessions(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Se revocaron 1 sesiones activas"


@pytest.mark.asyncio
async def test_logout_revokes_only_given_session(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    first = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )
    second = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first.json()["refresh_token"]},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Sesión revocada"

    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first.json()["refresh_token"]},
    )
    survivor = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second.json()["refresh_token"]},
    )
    assert reused.status_code == 401
    assert survivor.status_code == 200


@pytest.mark.asyncio
async def test_logout_accepts_empty_body(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    response = await client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Se revocaron 0 sesiones activas"


@pytest.mark.asyncio
async def test_logout_reports_unknown_session(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "token-inexistente"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Sesión no encontrada"


@pytest.mark.asyncio
async def test_me_exposes_roles_and_permissions(
    client: AsyncClient, admin_user: User, admin_token: str
) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["administrador"]
    assert "users:read" in payload["permissions"]

    roles = await client.get(
        "/api/v1/auth/me/roles", headers={"Authorization": f"Bearer {admin_token}"}
    )
    permissions = await client.get(
        "/api/v1/auth/me/permissions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert roles.json() == ["administrador"]
    assert "audit_logs:read" in permissions.json()


@pytest.mark.asyncio
async def test_sessions_endpoint_lists_active_sessions(
    client: AsyncClient, test_user_in_db: User, user_token: str
) -> None:
    await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    response = await client.get(
        "/api/v1/auth/me/sessions", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert "token_hash" not in sessions[0]


@pytest.mark.asyncio
async def test_login_persists_refresh_session(
    client: AsyncClient, test_user_in_db: User, database_session: AsyncSession
) -> None:
    from app.models import RefreshToken

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user_in_db.email, "password": "testpassword123"},
    )

    stored = await database_session.execute(select(RefreshToken))
    records = list(stored.scalars().all())

    assert response.status_code == 200
    assert len(records) == 1
    assert records[0].token_hash not in response.json()["refresh_token"]
