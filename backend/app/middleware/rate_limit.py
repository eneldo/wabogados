import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.services.rate_limit_store import (
    InMemoryRateLimitStore,
    RateLimitStore,
    RateLimitStoreError,
    build_rate_limit_store,
)

logger = logging.getLogger(__name__)

AUTH_PATH_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/refresh")

#: Sending a message is a write with a database round trip and is the easiest
#: endpoint to abuse, so it gets its own much tighter budget.
MESSAGE_PATH_PREFIXES = ("/api/v1/messages", "/api/v1/conversations")

#: The public consultation form. It is unauthenticated **and** it writes to the
#: database, so it needs a budget of its own rather than the default one: the
#: default allows a hundred requests a minute, which is a hundred rows of
#: somebody's legal problem per person per minute. This is the lowest budget in
#: the application, and it is keyed by IP because there is no user yet.
CONTACT_PATH_PREFIXES = ("/api/v1/consultations",)

#: Each profile names the two settings attributes holding its budget.
LIMIT_PROFILES: dict[str, tuple[str, str]] = {
    "auth": ("auth_rate_limit_requests", "auth_rate_limit_window_seconds"),
    "message": ("message_rate_limit_requests", "message_rate_limit_window_seconds"),
    "contact": ("contact_rate_limit_requests", "contact_rate_limit_window_seconds"),
    "default": ("rate_limit_requests", "rate_limit_window_seconds"),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window limiter keyed by authenticated user or IP.

    Each limit profile keeps its own counter, so exhausting the authentication
    budget does not silently throttle messaging and the other way round.

    The counter lives in a store rather than in this object: a shared Redis when
    `REDIS_URL` is set, and the process itself otherwise (ADR-008). The in
    process choice is correct for one worker and wrong for several, so which one
    is in use is logged rather than inferred.

    **What happens when the shared store fails.** The request is still counted, in
    memory, and an error is logged. Treating an unreachable store as "no limit"
    would open `/auth/login` exactly when somebody is guessing passwords, and
    treating it as "refuse everything" would turn a Redis outage into an outage
    of the whole firm. A louder option exists for deployments that prefer to
    refuse: set `RATE_LIMIT_FAIL_CLOSED=true`.
    """

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(app, *args, **kwargs)
        settings = get_settings()
        # Always present so a store outage has somewhere to count, and so the
        # tests can inspect what the in process store knows.
        self.local_store = InMemoryRateLimitStore()
        # One object, not two. Building a separate in-memory store here and a
        # second one for `reset()` produced a limiter whose counters nothing
        # could clear, and the symptom was "the limiter is too strict" in tests
        # that had nothing to do with limits.
        self.store: RateLimitStore = (
            self.local_store
            if not settings.redis_url
            else build_rate_limit_store(settings.redis_url)
        )
        if settings.redis_url:
            logger.info("Limitador de peticiones usando Redis")
        else:
            logger.warning(
                "Limitador de peticiones en memoria: el presupuesto se aplica por "
                "proceso. Defina REDIS_URL antes de ejecutar varios workers de API."
            )

    def reset(self) -> None:
        self.local_store.reset()

    @property
    def requests(self) -> dict[str, list[float]]:
        """The in process counters, for inspection.

        Kept because it was the middleware's own attribute before the store
        existed, and the tests that age a recorded timestamp reach for it. A
        property rather than a copy, so ageing an entry through it really does
        change what the store will see.
        """
        return self.local_store.requests

    @requests.setter
    def requests(self, value: dict[str, list[float]]) -> None:
        self.local_store.requests = value

    def _client_key(self, request: Request) -> str:
        from app.api.deps import get_client_ip
        from app.middleware.audit import extract_user_id

        user_id = extract_user_id(request)
        if user_id:
            return f"user:{user_id}"
        return f"ip:{get_client_ip(request, get_settings().trusted_proxies)}"

    def _profile_for(self, request: Request) -> str:
        path = request.url.path
        if path.startswith(AUTH_PATH_PREFIXES):
            return "auth"
        if path.startswith(MESSAGE_PATH_PREFIXES) and request.method == "POST":
            return "message"
        # Only the write is expensive. Letting staff read the queue at their own
        # pace means this must not also throttle GET.
        if path.startswith(CONTACT_PATH_PREFIXES) and request.method == "POST":
            return "contact"
        return "default"

    def _limits_for(self, request: Request) -> tuple[int, int]:
        settings = get_settings()
        limit_attr, window_attr = LIMIT_PROFILES[self._profile_for(request)]
        return (
            getattr(settings, limit_attr),
            getattr(settings, window_attr),
        )

    async def _count(self, key: str, window: int) -> int:
        """Record the hit in the store, degrading loudly instead of silently.

        The fallback is a real counter, not a bypass: a Redis outage must not
        turn into an unlimited login budget.
        """
        if self.store is self.local_store:
            return await self.store.hit(key, window)
        try:
            return await self.store.hit(key, window)
        except RateLimitStoreError as error:
            logger.error(
                "El limitador compartido falló (%s). Se cuenta en memoria: el "
                "presupuesto sigue existiendo pero solo para este proceso.",
                error,
            )
            if get_settings().rate_limit_fail_closed:
                return window + 1
            return await self.local_store.hit(key, window)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        profile = self._profile_for(request)
        limit, window = self._limits_for(request)
        # The profile is part of the key: each budget counts independently.
        key = f"ratelimit:{profile}:{self._client_key(request)}"

        count = await self._count(key, window)

        # Strictly greater, not greater or equal: `limit` is the number of
        # requests that get through, and `count` already includes the one in
        # front of us. Comparing with `>=` would allow `limit - 1` and quietly
        # halve the authentication budget.
        if count > limit:
            retry_after = window
            return Response(
                content=(
                    '{"error": {"code": "rate_limit_exceeded", '
                    '"message": "Demasiadas solicitudes", "details": null}}'
                ),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        response: Response = await call_next(request)
        return response