"""Persistent mail jobs, leased before work; every identity mutation locks user first."""

import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.recovery_config import RecoverySettings, get_recovery_settings
from app.models import PasswordRecoveryToken, RecoveryMail, User
from app.services.credentials import lock_user, revoke_recovery_links
from app.services.password_recovery import (
    decrypt_payload,
    digest_token,
    eligible,
    encrypt_payload,
    private_digest,
    utcnow,
)
from app.services.recovery_mail import RecoveryDeliveryError, send_recovery_mail

logger = logging.getLogger(__name__)
SessionFactoryType = Callable[[], AsyncSession]
MailSender = Callable[[RecoverySettings, str, str, UUID], Awaitable[None]]


def finish(job: RecoveryMail, status: str) -> None:
    job.status = status
    job.encrypted_payload = None
    job.lease_id = None
    job.leased_until = None


class RecoveryWorker:
    def __init__(
        self,
        factory: SessionFactoryType,
        settings: RecoverySettings | None = None,
        sender: MailSender = send_recovery_mail,
    ):
        self.factory = factory
        self.settings = settings or get_recovery_settings()
        self.sender = sender

    async def maintenance(self) -> None:
        now = utcnow()
        async with self.factory() as session:
            # Clearing payloads never requires a user lock; consumption is also
            # gated on the enable flag, so disabling stops both sides of recovery.
            conditions: list[ColumnElement[bool]] = [RecoveryMail.status.in_(("pending", "ready"))]
            if self.settings.enabled:
                conditions.append(
                    or_(
                        RecoveryMail.expires_at <= now,
                        (RecoveryMail.attempts >= self.settings.max_attempts)
                        & or_(
                            RecoveryMail.leased_until.is_(None), RecoveryMail.leased_until <= now
                        ),
                    )
                )
            await session.execute(
                update(RecoveryMail)
                .where(*conditions)
                .values(
                    status="cancelled", encrypted_payload=None, lease_id=None, leased_until=None
                )
            )
            cutoff = now - timedelta(hours=24)
            await session.execute(delete(RecoveryMail).where(RecoveryMail.expires_at < cutoff))
            await session.execute(
                delete(PasswordRecoveryToken).where(PasswordRecoveryToken.expires_at < cutoff)
            )
            await session.commit()

    async def claim(self) -> tuple[UUID, UUID] | None:
        now = utcnow()
        async with self.factory() as session:
            job = await session.scalar(
                select(RecoveryMail)
                .where(
                    RecoveryMail.status.in_(("pending", "ready")),
                    RecoveryMail.next_attempt_at <= now,
                    RecoveryMail.expires_at > now,
                    RecoveryMail.attempts < self.settings.max_attempts,
                    or_(RecoveryMail.leased_until.is_(None), RecoveryMail.leased_until <= now),
                )
                .order_by(RecoveryMail.created_at, RecoveryMail.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            job.lease_id = uuid4()
            # SMTP is bounded below this lease; a crash can duplicate the same
            # Message-ID, never regenerate a different token for a retry.
            job.leased_until = now + timedelta(seconds=120)
            job.attempts += 1
            result = job.id, job.lease_id
            await session.commit()
            return result

    async def prepare(self, job_id: UUID, lease_id: UUID) -> bool:
        async with self.factory() as session:
            snapshot = await session.get(RecoveryMail, job_id)
            if snapshot is None or snapshot.lease_id != lease_id:
                return False
            if snapshot.status == "ready":
                return True
            if snapshot.status != "pending" or snapshot.encrypted_payload is None:
                return False
            try:
                email = decrypt_payload(snapshot.encrypted_payload, self.settings)["email"]
            except Exception:
                return await self._cancel(session, snapshot, "payload_invalid")
            # A legacy case-collision is ambiguous: never choose the wrong account.
            ids = list(
                (
                    await session.scalars(
                        select(User.id).where(func.lower(User.email) == email.casefold()).limit(2)
                    )
                ).all()
            )
            user = await lock_user(session, ids[0]) if len(ids) == 1 else None
            # User is locked before outbox, matching admin/reset/cancellation.
            job = await session.scalar(
                select(RecoveryMail)
                .where(RecoveryMail.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None or job.lease_id != lease_id or job.status != "pending":
                return False
            now = utcnow()
            if (
                not self.settings.enabled
                or user is None
                or not user.is_active
                or not user.is_verified
                or user.email.casefold() != email.casefold()
                or job.expires_at <= now
                or (
                    user.recovery_invalidated_at is not None
                    and job.created_at <= user.recovery_invalidated_at
                )
            ):
                return await self._cancel(session, job)
            newest_request = await session.scalar(
                select(func.max(PasswordRecoveryToken.created_at)).where(
                    PasswordRecoveryToken.user_id == user.id
                )
            )
            if newest_request is not None and newest_request >= job.created_at:
                return await self._cancel(session, job)
            # Cancel previous issued links and deliveries, not this anonymous job.
            await revoke_recovery_links(session, user)
            token_value = secrets.token_urlsafe(32)
            token = PasswordRecoveryToken(
                user_id=user.id,
                token_hash=digest_token(token_value),
                email_digest=private_digest(user.email, self.settings),
                credential_version=user.token_version,
                created_at=job.created_at,
                expires_at=job.expires_at,
            )
            session.add(token)
            await session.flush()
            job.user_id = user.id
            job.token_id = token.id
            job.status = "ready"
            job.encrypted_payload = encrypt_payload(
                {"email": user.email, "token": token_value}, self.settings
            )
            await session.commit()
            return True

    async def _cancel(
        self, session: AsyncSession, job: RecoveryMail, error: str | None = None
    ) -> bool:
        finish(job, "cancelled")
        job.last_error = error
        await session.commit()
        return False

    async def deliver(self, job_id: UUID, lease_id: UUID) -> bool:
        async with self.factory() as session:
            snapshot = await session.get(RecoveryMail, job_id)
            if snapshot is None or snapshot.user_id is None or snapshot.token_id is None:
                return False
            user = await lock_user(session, snapshot.user_id)
            token = await session.scalar(
                select(PasswordRecoveryToken)
                .where(PasswordRecoveryToken.id == snapshot.token_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            job = await session.scalar(
                select(RecoveryMail)
                .where(RecoveryMail.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None or job.lease_id != lease_id or job.status != "ready":
                return False
            now = utcnow()
            if (
                not self.settings.enabled
                or user is None
                or token is None
                or not eligible(user, token, now, self.settings)
                or not job.encrypted_payload
            ):
                return await self._cancel(session, job)
            try:
                payload = decrypt_payload(job.encrypted_payload, self.settings)
                if (
                    payload["email"] != user.email
                    or digest_token(payload["token"]) != token.token_hash
                ):
                    return await self._cancel(session, job, "payload_invalid")
            except Exception:
                return await self._cancel(session, job, "payload_invalid")
            try:
                # Hold identity lock through bounded SMTP: a cancelled token
                # cannot be selected for delivery concurrently with a reset.
                await self.sender(self.settings, payload["email"], payload["token"], job.id)
            except RecoveryDeliveryError:
                job.last_error = "smtp_delivery_failed"
                job.lease_id = None
                job.leased_until = None
                job.next_attempt_at = now + timedelta(seconds=30 * job.attempts)
                if job.attempts >= self.settings.max_attempts:
                    finish(job, "failed")
                    token.revoked_at = utcnow()
                logger.warning(
                    "Recovery mail delivery failed; job=%s attempt=%s", job.id, job.attempts
                )
                await session.commit()
                return False
            finish(job, "sent")
            job.sent_at = utcnow()
            job.last_error = None
            await session.commit()
            return True

    async def run_once(self, limit: int = 10) -> int:
        if self.settings.enabled:
            self.settings.validate_enabled(get_settings().app_environment)
        await self.maintenance()
        if not self.settings.enabled:
            return 0
        sent = 0
        for _ in range(limit):
            claim = await self.claim()
            if claim is None:
                break
            if await self.prepare(*claim) and await self.deliver(*claim):
                sent += 1
        return sent
