from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_permission
from app.models import AuditLog, User
from app.schemas.auth import UserResponse
from app.schemas.identity import (
    AuditLogResponse,
    PaginatedAuditLogs,
    PaginatedUsers,
    PermissionResponse,
    RoleAssignmentRequest,
    RoleResponse,
    UserCreateAdmin,
    UserUpdateAdmin,
)
from app.services.identity import IdentityError, UserAdminService

router = APIRouter(prefix="/admin", tags=["admin"])


def _handle_identity_error(error: IdentityError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    )


def _audit_entry(log: AuditLog) -> AuditLogResponse:
    entry = AuditLogResponse.model_validate(log)
    entry.user_email = log.user.email if log.user else None
    return entry


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:read"))],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
    role: str | None = Query(default=None, max_length=100),
    is_active: bool | None = Query(default=None),
) -> PaginatedUsers:
    users, total = await UserAdminService(session).list_users(
        skip,
        limit,
        search=search,
        role=role,
        is_active=is_active,
    )
    return PaginatedUsers(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:read"))],
) -> UserResponse:
    user = await UserAdminService(session).get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    return UserResponse.model_validate(user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:create"))],
) -> UserResponse:
    service = UserAdminService(session)
    try:
        user = await service.create_user(payload)
        for role_name in payload.role_names:
            await service.assign_role(user, role_name)
        # Commit before the response is written. A service that only flushes
        # leaves the row inside the request's transaction, and `get_session`
        # closes that transaction without committing: the API answers 201 and
        # the account does not exist. Every other write router commits here for
        # that reason.
        await session.commit()
    except IdentityError as error:
        raise _handle_identity_error(error) from error
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateAdmin,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:update"))],
) -> UserResponse:
    service = UserAdminService(session)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    updated = await service.update_user(user, payload)
    await session.commit()
    return UserResponse.model_validate(updated)


@router.delete("/users/{user_id}", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("users:delete"))],
) -> UserResponse:
    service = UserAdminService(session)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta",
        )
    deactivated = await service.deactivate_user(user, actor.id)
    await session.commit()
    return UserResponse.model_validate(deactivated)


@router.post("/users/{user_id}/roles", response_model=UserResponse)
async def assign_role(
    user_id: UUID,
    payload: RoleAssignmentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:assign_roles"))],
) -> UserResponse:
    service = UserAdminService(session)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    try:
        updated = await service.assign_role(user, payload.role_name)
        await session.commit()
    except IdentityError as error:
        raise _handle_identity_error(error) from error
    return UserResponse.model_validate(updated)


@router.delete("/users/{user_id}/roles/{role_name}", response_model=UserResponse)
async def revoke_role(
    user_id: UUID,
    role_name: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("users:assign_roles"))],
) -> UserResponse:
    service = UserAdminService(session)
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )
    try:
        updated = await service.revoke_role(user, role_name)
        await session.commit()
    except IdentityError as error:
        raise _handle_identity_error(error) from error
    return UserResponse.model_validate(updated)


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("roles:read"))],
) -> list[RoleResponse]:
    roles = await UserAdminService(session).list_roles()
    return [RoleResponse.from_role(role) for role in roles]


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("permissions:read"))],
) -> list[PermissionResponse]:
    permissions = await UserAdminService(session).list_permissions()
    return [PermissionResponse.model_validate(item) for item in permissions]


@router.get("/audit-logs", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_permission("audit_logs:read"))],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    search: Annotated[str | None, Query(max_length=200)] = None,
    user_id: Annotated[UUID | None, Query()] = None,
    result: Annotated[str | None, Query(max_length=50)] = None,
) -> PaginatedAuditLogs:
    logs, total = await UserAdminService(session).list_audit_logs(
        skip,
        limit,
        search=search,
        user_id=user_id,
        result=result,
    )
    return PaginatedAuditLogs(
        items=[_audit_entry(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )
