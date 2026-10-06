from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.health import ErrorResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(
        status="ok", service=get_settings().app_name, checks={"application": "up"}
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def readiness(session: AsyncSession = Depends(get_session)) -> HealthResponse | JSONResponse:  # noqa: B008
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "service_unavailable",
                    "message": "Service is not ready",
                    "details": {"database": "down"},
                }
            },
        )
    return HealthResponse(
        status="ready", service=get_settings().app_name, checks={"database": "up"}
    )
