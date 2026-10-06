from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import jwt

from app.core.config import get_settings

#: Argon2id with `argon2-cffi`'s defaults: t=3, m=64 MiB, p=4, 16 byte salt and
#: 16 byte hash. Those are the same values passlib used, which is the whole
#: point: every hash already in the database keeps verifying.
#:
#: Passlib was replaced by the library it delegated to. It is unmaintained, it
#: warns on import under Python 3.12, and it reaches into `crypt`, which Python
#: 3.13 removes. `app/tests/test_password_hashing.py` freezes one of its hashes
#: so this replacement cannot quietly lock anyone out.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return str(_hasher.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password, treating anything unreadable as a failed login.

    Two different failures arrive here and neither may escape: the password is
    wrong (`VerificationError`), and the stored value is not an Argon2 hash at
    all (`InvalidHashError`) because it came out of the database and could be
    anything. A login endpoint that raises on the second one turns one unusable
    row into a 500 for everybody.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: UUID | str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    claims = {
        "sub": str(subject),
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(
        claims, settings.secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(
    subject: UUID | str,
    expires_delta: timedelta | None = None,
    jti: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    if jti:
        claims["jti"] = jti

    return jwt.encode(
        claims, settings.secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return dict(
        jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    )


def get_token_expiry(token: str) -> datetime:
    payload = decode_token(token)
    exp = payload.get("exp")
    if exp:
        return datetime.fromtimestamp(exp, tz=UTC)
    raise ValueError("Token has no expiry")