from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _trusted_proxies, get_client_ip, get_current_user, get_session
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    Token,
    UserResponse,
)
from app.schemas.identity import SessionInfo
from app.services.auth import SessionMeta, TokenService, UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_meta(request: Request) -> SessionMeta:
    return get_client_ip(request, _trusted_proxies()), request.headers.get("User-Agent")


@router.post(
    "/login",
    response_model=Token,
    responses={401: {"model": MessageResponse}},
)
async def login(
    credentials: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Token:
    user_service = UserService(session)
    user = await user_service.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    access_token, refresh_token = await TokenService(session).issue_session(
        user, _session_meta(request)
    )
    await session.commit()
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh",
    response_model=Token,
    responses={401: {"model": MessageResponse}},
)
async def refresh_token(
    request: RefreshRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Token:
    tokens = await TokenService(session).refresh_access_token(
        request.refresh_token, _session_meta(http_request)
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )
    access_token, refresh_token = tokens
    await session.commit()
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: LogoutRequest | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> MessageResponse:
    token_service = TokenService(session)
    if payload and payload.refresh_token:
        session_revoked = await token_service.revoke_session(payload.refresh_token)
        message = "Sesión revocada" if session_revoked else "Sesión no encontrada"
    else:
        total_revoked = await token_service.revoke_all_for_user(current_user.id)
        message = f"Se revocaron {total_revoked} sesiones activas"
    await session.commit()
    return MessageResponse(message=message)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/me/roles", response_model=list[str])
async def get_current_user_roles(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[str]:
    return [role.name for role in current_user.roles]


@router.get("/me/permissions", response_model=list[str])
async def get_current_user_permissions(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[str]:
    return sorted(
        {permission.name for role in current_user.roles for permission in role.permissions}
    )


@router.get("/me/sessions", response_model=list[SessionInfo])
async def list_active_sessions(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[SessionInfo]:
    records = await TokenService(session).list_active_sessions(current_user.id)
    return [SessionInfo.model_validate(record) for record in records]
