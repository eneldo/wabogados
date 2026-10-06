from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router
from app.core.config import Settings, get_settings
from app.middleware.audit import AuditLogMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.storage import initialize_storage

settings = get_settings()

#: The signing key that lives in the public repository. It satisfies the length
#: rule so development works out of the box, which is exactly why it must never
#: reach production: with it anyone can mint a valid token and the permission
#: model becomes decoration.
KNOWN_SECRET_KEY = "dev-secret-key-change-in-production"


def assert_production_is_safe(resolved: Settings) -> None:
    """Refuse to serve with a configuration that is only safe in development.

    Called from the lifespan, so the process exits instead of starting. Every
    condition here was reachable in a deployment that booted normally: the
    container started, the suite passed and nothing complained. Refusing to start
    is the loudest thing the application can do.

    Deliberately limited to what a bad deployment would actually get wrong. It is
    not a substitute for provisioning: `S3_CREATE_BUCKET=true` in production, for
    instance, is a smell but not a forgery.
    """
    if resolved.app_environment != "production":
        return

    if resolved.secret_key == KNOWN_SECRET_KEY or len(resolved.secret_key) < 32:
        raise ValueError(
            "SECRET_KEY no puede ser el valor de ejemplo ni tener menos de 32 "
            "caracteres en producción: con esa clave cualquier persona puede "
            "firmar un token válido. Genere una con `openssl rand -hex 32`."
        )

    if any(origin == "*" for origin in resolved.cors_origins):
        raise ValueError(
            "CORS_ORIGINS no puede contener '*' en producción: desactiva también "
            "la protección de cabecera Host. Enumere los dominios."
        )

    if "*" in resolved.cors_allow_methods or "*" in resolved.cors_allow_headers:
        raise ValueError(
            "CORS_ALLOW_METHODS y CORS_ALLOW_HEADERS no pueden contener '*' en "
            "producción. Enumere los verbos y las cabeceras."
        )


def allowed_hosts_from_origins(origins: Sequence[str]) -> list[str]:
    """Turn CORS origins into the hostnames `TrustedHostMiddleware` compares.

    Starlette matches the raw `Host` header, which never carries a scheme, so
    passing the origins verbatim compared `https://app.example` against
    `app.example` and answered 400 to everything. Extracting the netloc is what
    makes the middleware work at all.
    """
    hosts: list[str] = []
    for origin in origins:
        parts = urlsplit(origin)
        if not parts.netloc or parts.netloc == "*":
            continue
        if parts.netloc not in hosts:
            hosts.append(parts.netloc)
    return hosts


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    del application
    assert_production_is_safe(settings)
    await initialize_storage(settings)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Audit logging (disabled in test environment)
app.add_middleware(AuditLogMiddleware, enabled=settings.app_environment != "test")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Trusted hosts (only in production)
if settings.app_environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts_from_origins(settings.cors_origins),
    )

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> JSONResponse:
    response: JSONResponse = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    if settings.app_environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(router)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    del request
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "not_found",
                    "message": "Resource not found",
                    "details": None,
                }
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": "http_error", "message": str(exc.detail), "details": None}
        },
    )


def safe_validation_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Make validation errors JSON serializable.

    Pydantic places the original exception instance inside ``ctx``; encoding it
    directly raises TypeError and would turn a 422 into an unhandled 500.
    """
    cleaned: list[dict[str, Any]] = []
    for error in errors:
        item = {key: value for key, value in error.items() if key != "ctx"}
        context = error.get("ctx")
        if isinstance(context, dict):
            item["ctx"] = {key: str(value) for key, value in context.items()}
        cleaned.append(item)
    return cleaned


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": {"errors": safe_validation_errors(exc.errors())},
            }
        },
    )
