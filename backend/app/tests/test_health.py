from collections.abc import AsyncIterator

from httpx import AsyncClient


async def test_liveness_returns_uniform_success(health_client: AsyncClient) -> None:
    response = await health_client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "wabogados-api",
        "checks": {"application": "up"},
    }


async def test_readiness_checks_database(health_client: AsyncClient) -> None:
    response = await health_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "wabogados-api",
        "checks": {"database": "up"},
    }


async def test_readiness_returns_uniform_error() -> None:
    from unittest.mock import AsyncMock

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.session import get_session
    from app.main import app

    # Create a client with mocked database that fails
    async def mock_session() -> AsyncIterator[AsyncSession]:
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=ConnectionError("database unavailable"))
        yield session

    app.dependency_overrides[get_session] = mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "Service is not ready",
            "details": {"database": "down"},
        }
    }


async def test_unknown_route_returns_uniform_error(health_client: AsyncClient) -> None:
    response = await health_client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Resource not found",
            "details": None,
        }
    }
