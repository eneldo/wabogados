"""The shared rate limit store.

Why this module exists: the limiter counted requests in a `dict` inside the
middleware object. That is correct for one process and wrong the moment there are
two, because each worker keeps its own count and the effective limit becomes
`limit * workers`. It also forgets everything on restart, so a restart is a free
retry budget for whoever is guessing passwords.

The counter itself is the easy part. What matters here is the failure policy,
because a shared store introduces a new way for the API to be unavailable: if
Redis is down and the limiter treats that as "no limit", the login throttle
disappears exactly when an attacker is most likely to be hammering it. So a store
failure is **loud** and degrades to the in-process counter instead of silently
opening the door.
"""

import time
import uuid
from typing import Any, Protocol, runtime_checkable

#: Recorded so `rate_limit.py` can report which store is actually in use. A
#: deployment that thinks it has a shared store and does not is the failure mode
#: this exists to make visible.
STORE_BACKEND_MEMORY = "memory"
STORE_BACKEND_REDIS = "redis"


class RateLimitStoreError(Exception):
    """The shared store could not be reached or answered wrongly."""


@runtime_checkable
class RateLimitStore(Protocol):
    """Counts hits in a sliding window.

    `hit` records one request and returns how many are inside the window
    **including** the one just recorded. The caller therefore admits `limit`
    requests and blocks the one after, which is why the comparison is `> limit`
    and not `>= limit`.

    There is no `reset` in this protocol on purpose: the limiter never clears
    anything, and the two implementations cannot do it the same way (one is a
    dict, the other needs a server round trip). It exists on each class for
    tests and for an operator who needs a clean slate.

    `backend` is part of the contract because the middleware reports which one is
    in use. A deployment that believes it shares its counters and does not is
    exactly the failure this module exists to make visible.
    """

    backend: str

    async def hit(self, key: str, window: int) -> int: ...


def create_redis_client(url: str) -> Any:
    """A Redis client for the limiter.

    The single place the library is touched, so the one type it does not provide
    is confined to one line. `redis` ships no stubs, so `from_url` is untyped and
    mypy strict refuses to call it; the object it returns is duck typed here
    (`register_script`, `delete`, `scan_iter`) and every one of those calls is
    exercised against a real server in `test_rate_limit_store.py`.
    """
    import redis.asyncio as redis_asyncio

    return redis_asyncio.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]


class InMemoryRateLimitStore:
    """The original behaviour, kept as the fallback and for single-process runs.

    Same sliding window and same pruning as before, so switching stores does not
    change which requests are allowed — only whether the count is shared.
    """

    backend = STORE_BACKEND_MEMORY

    def __init__(self) -> None:
        self.requests: dict[str, list[float]] = {}

    async def hit(self, key: str, window: int) -> int:
        now = time.time()
        self._prune(now, window)
        recent = [t for t in self.requests.get(key, []) if now - t < window]
        recent.append(now)
        self.requests[key] = recent
        return len(recent)

    def reset(self) -> None:
        """Synchronous on purpose.

        The middleware exposes a synchronous `reset()` that tests and an operator
        call; making this one `async` returned a coroutine that was never awaited,
        the dict was never cleared, and the counts leaked from one test into the
        next. That failure looked like "the limiter is too strict".
        """
        self.requests.clear()

    def _prune(self, now: float, window: int) -> None:
        for existing in list(self.requests):
            recent = [t for t in self.requests[existing] if now - t < window]
            if recent:
                self.requests[existing] = recent
            else:
                del self.requests[existing]


#: Sliding window in one round trip, and atomically.
#:
#: Without the script the three steps race: two workers can both count, both see
#: room, and both admit the request. That is the whole reason for the shared
#: store, so the increment has to be indivisible rather than merely shared.
_LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local member = ARGV[3]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return redis.call('ZCARD', key)
"""


class RedisRateLimitStore:
    """Sliding window counter kept in a Redis sorted set.

    A sorted set rather than `INCR` + `EXPIRE` because a fixed window admits
    twice the budget across the boundary: ten requests at 11:59:55 and ten more
    at 12:00:00 is twenty in one second. The limiter's whole purpose on
    `/auth/login` is to make a burst expensive.
    """

    backend = STORE_BACKEND_REDIS

    def __init__(self, client: Any) -> None:
        self._client = client
        self._script = client.register_script(_LUA_SLIDING_WINDOW)

    async def hit(self, key: str, window: int) -> int:
        now_ms = int(time.time() * 1000)
        # The member must be unique, not the timestamp. A sorted set is keyed by
        # member, so two requests inside the same millisecond would replace each
        # other and `ZCARD` would stay at 1: the limiter would allow an unlimited
        # burst exactly when one arrives. The tests caught it by comparing this
        # store with the in-process one over a burst.
        member = f"{now_ms}-{uuid.uuid4().hex[:12]}"
        try:
            count = await self._script(
                keys=[key], args=[now_ms, window * 1000, member], client=self._client
            )
        except Exception as error:
            raise RateLimitStoreError(str(error)) from error

        if not isinstance(count, int):
            raise RateLimitStoreError(f"conteo inesperado del store: {count!r}")
        return count

    async def reset(self) -> None:
        """Drop every limiter key.

        Asynchronous because it needs the server, and because `scan_iter` is an
        async generator — treating it as a list raises before the delete.
        """
        try:
            keys = [key async for key in self._client.scan_iter(match="ratelimit:*")]
            if keys:
                await self._client.delete(*keys)
        except Exception as error:
            raise RateLimitStoreError(str(error)) from error


def build_rate_limit_store(
    redis_url: str | None, client: Any | None = None
) -> RateLimitStore:
    """The store the middleware should use.

    Redis when there is a URL, memory otherwise. Returning memory silently would
    be how a deployment ends up believing it shares its counters when it does not,
    so the caller logs which one it got.
    """
    if not redis_url:
        return InMemoryRateLimitStore()

    if client is None:
        client = create_redis_client(redis_url)

    return RedisRateLimitStore(client)


__all__ = [
    "STORE_BACKEND_MEMORY",
    "STORE_BACKEND_REDIS",
    "InMemoryRateLimitStore",
    "RateLimitStore",
    "RateLimitStoreError",
    "RedisRateLimitStore",
    "build_rate_limit_store",
    "create_redis_client",
]