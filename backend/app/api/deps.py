from collections.abc import AsyncGenerator, Callable, Coroutine, Sequence
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import SessionFactory
from app.models import Role, User
from app.security import decode_token
from app.services.cases import CaseScope

authorization_loader = selectinload(User.roles).selectinload(Role.permissions)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


async def get_current_user(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    authorization: str | None = Header(default=None),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exception

    token = authorization.split(" ")[1]

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception from None

    if payload.get("type") != "access":
        raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    user_id = UUID(user_id_str)
    result = await session.execute(
        select(User).options(authorization_loader).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo",
        )

    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos suficientes",
        )
    return current_user


def get_user_permission_names(user: User) -> set[str]:
    return {permission.name for role in user.roles for permission in role.permissions}


def get_user_role_names(user: User) -> list[str]:
    return [role.name for role in user.roles]


def require_permission(
    permission: str,
) -> Callable[[User], Coroutine[None, None, User]]:
    """Build a dependency that enforces a single RBAC permission.

    Superusers bypass the check by design so the platform can always be
    recovered administratively; every other role must hold the permission.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:  # noqa: B008
        if current_user.is_superuser:
            return current_user
        if permission not in get_user_permission_names(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {permission}",
            )
        return current_user

    return dependency


async def get_user_scope(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> CaseScope:
    """Resolve how much of the case book the caller may see."""
    from app.services.cases import resolve_scope

    return await resolve_scope(session, current_user)


def get_client_ip(request: Request, trusted_proxies: Sequence[str] = ()) -> str:
    """The address to rate limit and audit against.

    `X-Forwarded-For` is believed **only** when the peer is a proxy we declared,
    and then only from the right. That header is a list a client can write: taking
    its first entry unconditionally meant anybody could mint a fresh budget per
    request, which defeated the authentication throttle and the public
    consultation form — the two budgets whose whole purpose is to make a guess
    expensive. It also wrote whatever the caller chose into `audit_logs.ip_address`.

    Reading it from the right is what makes the trusted case correct: a chain
    `spoofed, real-client` arrives with our own proxy having appended
    `real-client`, so the rightmost entry is the last address a host we control
    actually observed.

    An empty `trusted_proxies` — the default, and what this project has today,
    because nothing sits in front of the API in Compose — means the header is
    never believed.
    """
    peer = request.client.host if request.client else None

    if peer and peer in set(trusted_proxies):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            for candidate in reversed(forwarded.split(",")):
                candidate = candidate.strip()
                if candidate and candidate != peer:
                    return candidate

    return peer or "unknown"


def _trusted_proxies() -> Sequence[str]:
    """The declared proxies, read from settings at call time.

    Every audit and access-log site calls this instead of passing a literal. The
    first version of the `X-Forwarded-For` fix changed `get_client_ip` and then
    updated only the rate limiter, so behind a real proxy the audit trail recorded
    the proxy's address for every single request: safe from spoofing, useless for
    forensics. Keeping the lookup here means a call site cannot forget it.

    Read at call time rather than import time because settings are overridable in
    tests, and an audit log that disagrees with the configuration under test is
    worse than no audit log.
    """
    from app.core.config import get_settings

    return get_settings().trusted_proxies
