from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import RefreshToken, Role, User
from app.schemas.auth import UserCreate, UserUpdate
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiry,
    hash_password,
    verify_password,
)

SessionMeta = tuple[str | None, str | None]


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, user_in: UserCreate) -> User:
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=hash_password(user_in.password),
            is_superuser=user_in.is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, user_in: UserUpdate) -> User:
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()
        return user


class TokenService:
    """Issues, rotates and revokes persisted refresh sessions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def issue_session(
        self, user: User, meta: SessionMeta = (None, None)
    ) -> tuple[str, str]:
        ip_address, user_agent = meta
        jti = uuid4().hex
        refresh_token = create_refresh_token(subject=user.id, jti=jti)
        access_token = create_access_token(subject=user.id)

        self.session.add(
            RefreshToken(
                user_id=user.id,
                jti=jti,
                token_hash=hash_token(refresh_token),
                expires_at=get_token_expiry(refresh_token),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.flush()
        return access_token, refresh_token

    async def refresh_access_token(
        self, refresh_token: str, meta: SessionMeta = (None, None)
    ) -> tuple[str, str] | None:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            return None

        if payload.get("type") != "refresh":
            return None

        jti = payload.get("jti")
        subject = payload.get("sub")
        if not jti or not subject:
            return None

        record = await self._get_active_session(jti, refresh_token)
        if record is None:
            return None

        user = await self.session.get(User, UUID(subject))
        if user is None or not user.is_active:
            return None
        ip_address, user_agent = meta
        new_jti = uuid4().hex
        new_refresh = create_refresh_token(subject=user.id, jti=new_jti)
        new_access = create_access_token(subject=user.id)

        record.revoked_at = datetime.now(UTC)
        record.replaced_by_jti = new_jti
        self.session.add(
            RefreshToken(
                user_id=user.id,
                jti=new_jti,
                token_hash=hash_token(new_refresh),
                expires_at=get_token_expiry(new_refresh),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        await self.session.flush()
        return new_access, new_refresh

    async def revoke_session(self, refresh_token: str) -> bool:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            return False

        jti = payload.get("jti")
        if not jti:
            return False

        record = await self._get_session(jti)
        if record is None or record.revoked_at is not None:
            return False

        record.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def list_active_sessions(self, user_id: UUID) -> list[RefreshToken]:
        result = await self.session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .order_by(RefreshToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        # `rowcount` is not part of the declared `Result` contract, and reaching
        # it with a `cast` would be an unchecked claim about a value the type
        # system refuses to promise. `RETURNING` puts the count in the result
        # rows themselves, so the number is typed and exact: how many sessions
        # PostgreSQL says it revoked, not how many the driver happened to
        # report.
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
            .returning(RefreshToken.id)
        )
        return len(result.all())

    async def _get_session(self, jti: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def _get_active_session(
        self, jti: str, refresh_token: str
    ) -> RefreshToken | None:
        record = await self._get_session(jti)
        if record is None or record.revoked_at is not None:
            return None
        if record.token_hash != hash_token(refresh_token):
            return None
        if record.expires_at <= datetime.now(UTC):
            return None
        return record
