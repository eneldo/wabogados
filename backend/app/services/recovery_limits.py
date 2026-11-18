"""Recovery budgets ignore visitor bearer/cookies and never key by raw email."""

import hashlib
import hmac
import time
from functools import lru_cache
from ipaddress import ip_address

from fastapi import HTTPException, Request

from app.api.deps import _trusted_proxies, get_client_ip
from app.core.config import get_settings
from app.core.recovery_config import get_recovery_settings
from app.services.password_recovery import private_digest
from app.services.rate_limit_store import (
    RateLimitStore,
    RateLimitStoreError,
    build_rate_limit_store,
)


@lru_cache
def recovery_store() -> RateLimitStore:
    return build_rate_limit_store(get_settings().redis_url)


def recovery_client(request: Request) -> str:
    """A separate shared signing key authenticates Next's ingress assertion.

    No verified ingress configured on Next => one conservative shared web budget,
    not a forgeable client header. Direct API callers retain the socket IP budget.
    """
    client = request.headers.get("x-recovery-client", "")
    stamp = request.headers.get("x-recovery-time", "")
    signature = request.headers.get("x-recovery-signature", "")
    key = get_recovery_settings().proxy_key.get_secret_value()
    if client and stamp and signature and key:
        try:
            recent = abs(time.time() - int(stamp)) <= 30
            address = "shared-web" if client == "shared-web" else str(ip_address(client))
        except ValueError:
            recent, address = False, ""
        message = f"{request.url.path}|{stamp}|{client}"
        expected = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
        if recent and hmac.compare_digest(signature, expected):
            return address
    return get_client_ip(request, _trusted_proxies())


async def check_limits(request: Request, *, for_request: bool) -> None:
    settings = get_recovery_settings()
    profile = "request" if for_request else "confirm"
    limit = settings.request_ip_limit if for_request else settings.confirm_ip_limit
    store = recovery_store()
    # This sensitive flow fails closed if its shared counter is unavailable.
    try:
        global_count = await store.hit(f"ratelimit:recovery:{profile}:global", 900)
        ip_count = await store.hit(
            f"ratelimit:recovery:{profile}:ip:{private_digest(recovery_client(request))}", 900
        )
        if global_count > settings.global_limit or ip_count > limit:
            raise HTTPException(429, "Demasiadas solicitudes. Inténtelo más tarde.")
    except RateLimitStoreError:
        raise HTTPException(
            503, "La recuperación no está disponible. Inténtelo más tarde."
        ) from None


async def check_recipient_limit(email: str) -> bool:
    settings = get_recovery_settings()
    store = recovery_store()
    try:
        address = private_digest(email.casefold())
        hourly = await store.hit(f"ratelimit:recovery:email:{address}", 3600)
        cooldown = await store.hit(
            f"ratelimit:recovery:cooldown:{address}", settings.cooldown_seconds
        )
        # Suppression is generic, for known and unknown recipients alike.
        return hourly <= settings.recipient_limit and cooldown == 1
    except RateLimitStoreError:
        raise HTTPException(
            503, "La recuperación no está disponible. Inténtelo más tarde."
        ) from None
