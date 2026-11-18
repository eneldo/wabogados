from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _trusted_proxies, get_client_ip, get_current_user, get_session
from app.core.config import get_settings
from app.core.recovery_config import get_recovery_settings
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
from app.schemas.password_recovery import ForgotPasswordRequest, RecoverPasswordRequest
from app.services.auth import SessionMeta, TokenService, UserService
from app.services.password_recovery import (
    GENERIC_RECOVERY_MESSAGE,
    PasswordRecoveryService,
    RecoveryError,
)
from app.services.recovery_limits import check_recipient_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_recovery() -> None:
    config = get_recovery_settings()
    if not config.enabled:
        raise HTTPException(
            503, "La recuperación por correo aún no está disponible. Contacte al administrador."
        )
    try:
        config.validate_enabled(get_settings().app_environment)
    except ValueError:
        raise HTTPException(
            503, "La recuperación no está disponible. Inténtelo más tarde."
        ) from None


@router.get("/password-recovery")
async def password_recovery_status() -> dict[str, bool]:
    try:
        _require_recovery()
    except HTTPException:
        return {"enabled": False}
    return {"enabled": True}


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MessageResponse:
    _require_recovery()
    if await check_recipient_limit(str(payload.email)):
        try:
            await PasswordRecoveryService(session).request(str(payload.email))
            await session.commit()
        except Exception:
            await session.rollback()
            raise HTTPException(
                503, "La recuperación no está disponible. Inténtelo más tarde."
            ) from None
    return MessageResponse(message=GENERIC_RECOVERY_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
async def recover_password(
    payload: RecoverPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MessageResponse:
    _require_recovery()
    try:
        await PasswordRecoveryService(session).confirm(
            payload.token.get_secret_value(), payload.new_password.get_secret_value()
        )
        await session.commit()
    except RecoveryError:
        await session.rollback()
        raise HTTPException(
            400, "El enlace no es válido o ha caducado. Solicite uno nuevo."
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            503, "La recuperación no está disponible. Inténtelo más tarde."
        ) from None
    return MessageResponse(message="Contraseña actualizada. Inicie sesión con su nueva contraseña.")


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
