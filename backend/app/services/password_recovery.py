"""Anonymous intake never looks up accounts or waits for SMTP.

Requests (including unknown addresses) enter an encrypted, durable outbox. The
worker resolves eligibility and issues one-use tokens outside HTTP response time.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.recovery_config import RecoverySettings, get_recovery_settings
from app.models import PasswordRecoveryToken, RecoveryMail, User
from app.services.credentials import change_password, lock_user

GENERIC_RECOVERY_MESSAGE = (
    "Si existe una cuenta habilitada con ese correo, "
    "recibirás instrucciones para recuperar tu acceso."
)
INVALID_LINK_MESSAGE = "El enlace no es válido o ha caducado. Solicite uno nuevo."


def utcnow() -> datetime:
    return datetime.now(UTC)


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def private_digest(value: str, settings: RecoverySettings | None = None) -> str:
    resolved = settings or get_recovery_settings()
    return hmac.new(
        resolved.encryption_key.get_secret_value().encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def encrypt_payload(payload: dict[str, str], settings: RecoverySettings) -> str:
    cipher = Fernet(settings.encryption_key.get_secret_value().encode())
    return cipher.encrypt(json.dumps(payload).encode()).decode()


def decrypt_payload(value: str, settings: RecoverySettings) -> dict[str, str]:
    cipher = Fernet(settings.encryption_key.get_secret_value().encode())
    decoded: object = json.loads(cipher.decrypt(value.encode()))
    if not isinstance(decoded, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in decoded.items()
    ):
        raise ValueError("Invalid encrypted recovery payload")
    return decoded


def eligible(
    user: User, token: PasswordRecoveryToken, now: datetime, settings: RecoverySettings
) -> bool:
    return (
        user.is_active
        and user.is_verified
        and token.used_at is None
        and token.revoked_at is None
        and token.expires_at > now
        and token.credential_version == user.token_version
        and hmac.compare_digest(token.email_digest, private_digest(user.email, settings))
    )


class RecoveryError(Exception):
    pass


class PasswordRecoveryService:
    def __init__(self, session: AsyncSession, settings: RecoverySettings | None = None):
        self.session = session
        self.settings = settings or get_recovery_settings()

    async def request(self, email: str) -> None:
        now = utcnow()
        self.session.add(
            RecoveryMail(
                encrypted_payload=encrypt_payload({"email": email}, self.settings),
                status="pending",
                attempts=0,
                created_at=now,
                expires_at=now + timedelta(minutes=self.settings.ttl_minutes),
                next_attempt_at=now,
            )
        )
        await self.session.flush()

    async def confirm(self, raw_token: str, password: str) -> UUID:
        # First lookup does not lock token: every mutation must lock user first.
        candidate = (
            await self.session.execute(
                select(PasswordRecoveryToken.id, PasswordRecoveryToken.user_id).where(
                    PasswordRecoveryToken.token_hash == digest_token(raw_token)
                )
            )
        ).one_or_none()
        if candidate is None:
            raise RecoveryError(INVALID_LINK_MESSAGE)
        user = await lock_user(self.session, candidate.user_id)
        token = await self.session.scalar(
            select(PasswordRecoveryToken)
            .where(PasswordRecoveryToken.id == candidate.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        now = utcnow()
        if user is None or token is None or not eligible(user, token, now, self.settings):
            raise RecoveryError(INVALID_LINK_MESSAGE)
        token.used_at = now
        await change_password(
            self.session, user, password, action="password_recovery_completed", actor_id=user.id
        )
        return user.id
