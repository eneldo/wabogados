from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import authorization_loader
from app.models import AuditLog, Permission, Role, User
from app.schemas.auth import UserCreate, UserUpdate
from app.security import hash_password
from app.services.credentials import (
    apply_identity_update,
    change_password,
    invalidate_recovery,
    lock_user,
)


class IdentityError(Exception):
    """Raised when an identity operation violates a business rule."""


class UserAdminService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_users(
        self,
        skip: int,
        limit: int,
        *,
        search: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        filters: list[ColumnElement[bool]] = []
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(User.email.ilike(term), User.full_name.ilike(term)))
        if role:
            filters.append(User.roles.any(Role.name == role))
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))

        total = await self.session.scalar(select(func.count()).select_from(User).where(*filters))
        # Newest first: the user just created is the one being looked for, and
        # an alphabetical directory hides it at an arbitrary page.
        result = await self.session.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_user(self, user_id: UUID, *, lock: bool = False) -> User | None:
        query = select(User).options(authorization_loader).where(User.id == user_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def reset_password(self, user: User, password: str, actor_id: UUID) -> int:
        """Caller holds the user row lock; hash, revocations and audit commit together."""
        return await change_password(
            self.session, user, password, action="admin_password_reset", actor_id=actor_id
        )

    async def create_user(self, payload: UserCreate) -> User:
        existing = await self.session.scalar(select(User).where(User.email == payload.email))
        if existing:
            raise IdentityError("El correo ya está registrado")

        user = User(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            is_superuser=payload.is_superuser,
            is_verified=True,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_user(self, user: User, payload: UserUpdate) -> User:
        locked = await lock_user(self.session, user.id)
        if locked is None:
            raise IdentityError("Usuario no encontrado")
        user = locked
        data = payload.model_dump(exclude_unset=True)
        await apply_identity_update(self.session, user, data)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def deactivate_user(self, user: User, actor_id: UUID | None) -> User:
        locked = await lock_user(self.session, user.id)
        if locked is None:
            raise IdentityError("Usuario no encontrado")
        user = locked
        await invalidate_recovery(self.session, user)
        user.is_active = False
        user.deleted_at = datetime.now(UTC)
        user.deleted_by = actor_id
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def assign_role(self, user: User, role_name: str) -> User:
        role = await self._get_role(role_name)
        if role is None:
            raise IdentityError(f"Rol desconocido: {role_name}")
        if role not in user.roles:
            user.roles.append(role)
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def revoke_role(self, user: User, role_name: str) -> User:
        role = await self._get_role(role_name)
        if role is None:
            raise IdentityError(f"Rol desconocido: {role_name}")
        if role in user.roles:
            user.roles.remove(role)
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def _get_role(self, role_name: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.name == role_name))
        return result.scalar_one_or_none()

    async def get_role(self, role_id: UUID) -> Role | None:
        result = await self.session.execute(
            select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def list_permissions(self) -> list[Permission]:
        result = await self.session.execute(select(Permission).order_by(Permission.name))
        return list(result.scalars().all())

    async def _permissions_by_names(self, names: list[str]) -> list[Permission]:
        if not names:
            return []
        unique = list(dict.fromkeys(names))
        result = await self.session.execute(select(Permission).where(Permission.name.in_(unique)))
        found = {permission.name: permission for permission in result.scalars().all()}
        missing = [name for name in unique if name not in found]
        if missing:
            raise IdentityError(f"Permisos desconocidos: {', '.join(sorted(missing))}")
        return [found[name] for name in unique]

    async def create_role(
        self, *, name: str, description: str | None, permission_names: list[str]
    ) -> Role:
        existing = await self.session.scalar(select(Role).where(Role.name == name))
        if existing:
            raise IdentityError("El nombre del rol ya está en uso")
        role = Role(name=name, description=description)
        role.permissions = await self._permissions_by_names(permission_names)
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def update_role(
        self,
        role: Role,
        *,
        name: str | None = None,
        description: str | None = None,
        permission_names: list[str] | None = None,
    ) -> Role:
        if name is not None and name != role.name:
            existing = await self.session.scalar(
                select(Role).where(Role.name == name, Role.id != role.id)
            )
            if existing:
                raise IdentityError("El nombre del rol ya está en uso")
            role.name = name
        if description is not None:
            role.description = description
        if permission_names is not None:
            role.permissions = await self._permissions_by_names(permission_names)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def delete_role(self, role: Role) -> None:
        assigned = await self.session.scalar(
            select(func.count()).select_from(User).where(User.roles.any(Role.id == role.id))
        )
        if int(assigned or 0) > 0:
            raise IdentityError(
                "No se puede eliminar un rol asignado a usuarios. Retírelo primero."
            )
        await self.session.delete(role)
        await self.session.flush()

    async def list_audit_logs(
        self,
        skip: int,
        limit: int,
        *,
        search: str | None = None,
        user_id: UUID | None = None,
        result: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters: list[ColumnElement[bool]] = []
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(AuditLog.action.ilike(term), AuditLog.entity.ilike(term)))
        if user_id is not None:
            # `==`, not `is_()`: SQLAlchemy renders `IS $1` for the latter and
            # Postgres only accepts `IS NULL` or a boolean on the right.
            filters.append(AuditLog.user_id == user_id)
        if result:
            filters.append(AuditLog.result == result)

        total = await self.session.scalar(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        result_query = await self.session.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result_query.scalars().all()), int(total or 0)
