"""Credential mutations shared by separately authorised admin/recovery flows."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, PasswordRecoveryToken, RecoveryMail, User
from app.security import hash_password


async def lock_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def invalidate_recovery(session: AsyncSession, user: User) -> None:
    """Caller owns user lock; prevent pending requests surviving identity changes."""
    user.recovery_invalidated_at = datetime.now(UTC)
    await revoke_recovery_links(session, user)


async def revoke_recovery_links(session: AsyncSession, user: User) -> None:
    """Superseding a link is not an identity change; do not suppress newer requests."""
    await session.execute(
        update(PasswordRecoveryToken)
        .where(
            PasswordRecoveryToken.user_id == user.id,
            PasswordRecoveryToken.used_at.is_(None),
            PasswordRecoveryToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await session.execute(
        update(RecoveryMail)
        .where(RecoveryMail.user_id == user.id, RecoveryMail.status.in_(("pending", "ready")))
        .values(status="cancelled", encrypted_payload=None, lease_id=None, leased_until=None)
    )


async def change_password(
    session: AsyncSession, user: User, password: str, *, action: str, actor_id: UUID | None
) -> int:
    """User lock precedes recovery/refresh row locks; caller commits the transaction."""
    from app.services.auth import TokenService

    user.hashed_password = hash_password(password)
    user.token_version += 1
    await invalidate_recovery(session, user)
    revoked = await TokenService(session).revoke_all_for_user(user.id)
    session.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity="users",
            entity_id=user.id,
            result="success",
            after={"revoked_sessions": revoked},
        )
    )
    await session.flush()
    return revoked


async def apply_identity_update(session: AsyncSession, user: User, data: dict[str, object]) -> None:
    email_changed = "email" in data and data["email"] != user.email
    if email_changed or data.get("is_active") is False or data.get("is_verified") is False:
        await invalidate_recovery(session, user)
    if email_changed:
        # Verification cannot be inherited by a different mailbox, even if a
        # profile PATCH includes is_verified=True alongside the new address.
        data["is_verified"] = False
    for field, value in data.items():
        setattr(user, field, value)
