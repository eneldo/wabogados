from collections.abc import Callable
from contextlib import AbstractAsyncContextManager as AsyncContextManager
from logging import getLogger
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.deps import _trusted_proxies, get_client_ip
from app.db.session import SessionFactory
from app.models import AuditLog

logger = getLogger(__name__)
AUDITED_AUTH_PATHS = ("/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/logout-all")
SKIPPED_PREFIXES = ("/api/v1/health", "/api/v1/docs", "/openapi.json", "/redoc")


def extract_user_id(request: Request) -> UUID | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    from app.security import decode_token

    try:
        payload = decode_token(auth_header.split(" ")[1])
    except Exception:
        return None

    if payload.get("type") != "access":
        return None

    try:
        return UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        return None


def parse_entity_id(value: str | None) -> UUID | None:
    """Return the segment as UUID when it identifies a record, else None."""
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def resolve_entity(path: str) -> tuple[str, UUID | None]:
    """Derive the audited entity from an ``/api/v1/<router>/<resource>/<id>`` path.

    The resource is the segment right before the record identifier. Paths
    without an identifier fall back to the router segment.
    """
    segments = [part for part in path.strip("/").split("/") if part]
    if len(segments) < 3:
        return "unknown", None

    router = segments[2]
    for index, segment in enumerate(segments[3:], start=3):
        record_id = parse_entity_id(segment)
        if record_id is not None:
            return segments[index - 1], record_id
    return router, None


SessionFactoryLike = Callable[[], AsyncContextManager[AsyncSession]]


class SessionAdapter:
    """Adapt an already open session to the async context manager protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class AuditLogMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        enabled: bool = True,
        session_factory: SessionFactoryLike | None = None,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.session_factory: SessionFactoryLike = session_factory or SessionFactory

    def _should_skip(self, request: Request) -> bool:
        # Traffic counters must not duplicate visitors' IP/UA in the audit trail.
        # Only this fixed anonymous intake is exempt; admin reads keep normal RBAC.
        if request.url.path == "/api/v1/public/analytics/events":
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if request.url.path.startswith(SKIPPED_PREFIXES):
            return True
        return False

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not self.enabled:
            disabled_response: Response = await call_next(request)
            return disabled_response

        if self._should_skip(request):
            skipped_response: Response = await call_next(request)
            return skipped_response

        user_id = extract_user_id(request)

        # The request body is deliberately not read here: consuming the stream
        # in a BaseHTTPMiddleware can leave the downstream handler without a
        # payload. Field level before/after lives in `change_logs`.
        response: Response = await call_next(request)

        entity, entity_id = resolve_entity(str(request.url.path))

        audit_log = AuditLog(
            user_id=user_id,
            action=f"{request.method} {request.url.path}",
            entity=entity,
            entity_id=entity_id,
            ip_address=get_client_ip(request, _trusted_proxies()),
            user_agent=request.headers.get("User-Agent", ""),
            before=None,
            after={
                "status_code": response.status_code,
                "method": request.method,
                "path": str(request.url.path),
            },
            result="success" if response.status_code < 400 else "error",
        )

        session = getattr(request.state, "db_session", None)
        try:
            if session is not None:
                session.add(audit_log)
                await session.commit()
            else:
                async with self.session_factory() as new_session:
                    new_session.add(audit_log)
                    await new_session.commit()
        except Exception:
            logger.exception(
                "No se pudo persistir la entrada de auditoría %s", audit_log.action
            )

        return response


__all__ = [
    "AUDITED_AUTH_PATHS",
    "AuditLogMiddleware",
    "SessionAdapter",
    "extract_user_id",
    "parse_entity_id",
    "resolve_entity",
]
