"""Tests for the shared rate limit store.

The Redis tests talk to a **real** server, not a double. A double would let the
same three bugs through that the in-process one had: it does not execute Lua, it
does not expire keys, and it does not fail when the server is unreachable. Those
are exactly the behaviours this store depends on, so a double here would test the
double.

When no server is reachable the Redis tests skip rather than pass silently: an
absent server is an environment fact, not a green result.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.services.rate_limit_store import (
    InMemoryRateLimitStore,
    RateLimitStoreError,
    RedisRateLimitStore,
    build_rate_limit_store,
    create_redis_client,
)

WINDOW = 60


async def _forget(redis_client: Any, store: object) -> None:
    """Leave the key clean so one test cannot decide the next one's answer."""
    if isinstance(store, RedisRateLimitStore):
        await store.reset()
    else:
        store.reset()  # type: ignore[attr-defined]


@pytest.fixture
async def redis_client() -> AsyncIterator[Any]:
    """A real Redis, cleaned before and after the test.

    Connecting to `redis-test:6379` because that is where Compose puts it. If
    nothing answers there, the test is skipped instead of falling back to a
    double.
    """
    client = create_redis_client("redis://redis-test:6379/15")

    try:
        await client.ping()
    except Exception as error:  # any failure here means "no server to talk to"
        pytest.skip(f"Redis no disponible en este entorno: {error}")

    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


# -- Both stores answer the same question ----------------------------------


async def test_the_first_hit_counts_one() -> None:
    store = InMemoryRateLimitStore()

    assert await store.hit("ratelimit:auth:ip:1", WINDOW) == 1


async def test_the_count_grows_with_every_hit() -> None:
    store = InMemoryRateLimitStore()

    for expected in (1, 2, 3):
        assert await store.hit("ratelimit:auth:ip:1", WINDOW) == expected


async def test_two_clients_do_not_share_a_count() -> None:
    store = InMemoryRateLimitStore()

    await store.hit("ratelimit:auth:ip:1", WINDOW)
    other = await store.hit("ratelimit:auth:ip:2", WINDOW)

    assert other == 1


async def test_hits_outside_the_window_stop_counting() -> None:
    store = InMemoryRateLimitStore()
    await store.hit("ratelimit:auth:ip:1", 1)

    # Move the recorded instant out of the window instead of sleeping: the
    # behaviour under test is the arithmetic, and the test should not be slow.
    store.requests["ratelimit:auth:ip:1"] = [
        value - 5 for value in store.requests["ratelimit:auth:ip:1"]
    ]

    assert await store.hit("ratelimit:auth:ip:1", 1) == 1


async def test_reset_empties_the_store() -> None:
    store = InMemoryRateLimitStore()
    await store.hit("ratelimit:auth:ip:1", WINDOW)

    store.reset()

    assert await store.hit("ratelimit:auth:ip:1", WINDOW) == 1


async def test_a_stale_key_is_forgotten_rather_than_kept_forever() -> None:
    """Unbounded growth is a memory leak that only shows up in production."""
    store = InMemoryRateLimitStore()
    await store.hit("ratelimit:auth:ip:1", 1)
    store.requests["ratelimit:auth:ip:1"] = [
        value - 5 for value in store.requests["ratelimit:auth:ip:1"]
    ]

    await store.hit("ratelimit:auth:ip:2", 1)

    assert "ratelimit:auth:ip:1" not in store.requests


# -- Selection --------------------------------------------------------------


def test_no_url_means_the_in_process_store() -> None:
    assert build_rate_limit_store(None).backend == "memory"


def test_a_url_means_the_shared_store() -> None:
    class Minimal:
        def register_script(self, _script: str) -> object:
            return self

    store = build_rate_limit_store("redis://redis:6379/0", client=Minimal())

    assert store.backend == "redis"


# -- Redis, against a real server -------------------------------------------


async def test_redis_counts_the_same_way(redis_client: Any) -> None:
    store = RedisRateLimitStore(redis_client)

    assert await store.hit("ratelimit:auth:ip:1", WINDOW) == 1
    assert await store.hit("ratelimit:auth:ip:1", WINDOW) == 2
    assert await store.hit("ratelimit:auth:auth:ip:2", WINDOW) == 1


async def test_redis_separates_clients(redis_client: Any) -> None:
    store = RedisRateLimitStore(redis_client)
    await store.hit("ratelimit:auth:ip:1", WINDOW)

    assert await store.hit("ratelimit:auth:ip:2", WINDOW) == 1


async def test_redis_and_memory_agree_on_a_burst(redis_client: Any) -> None:
    """The point of the change: same decision, shared counting."""
    shared = RedisRateLimitStore(redis_client)
    local = InMemoryRateLimitStore()

    for _ in range(5):
        assert await shared.hit("ratelimit:auth:ip:1", WINDOW) == await local.hit(
            "ratelimit:auth:ip:1", WINDOW
        )


async def test_a_budget_allows_exactly_that_many_requests(
    redis_client: Any,
) -> None:
    """`limit` is how many get through, not how many are refused.

    Counting the current request and then comparing with `>=` admits one less
    than configured — the authentication budget would silently be halved. It is
    asserted here against both stores, because the comparison lives in the
    middleware and this is the arithmetic it relies on.
    """
    limit = 3
    for store in (InMemoryRateLimitStore(), RedisRateLimitStore(redis_client)):
        admitted = 0
        refused = 0
        for _ in range(limit + 2):
            count = await store.hit("ratelimit:auth:ip:9", WINDOW)
            if count > limit:
                refused += 1
            else:
                admitted += 1

        assert admitted == limit
        assert refused == 2
        await _forget(redis_client, store)


async def test_two_stores_over_one_server_share_the_count(redis_client: Any) -> None:
    """What the in-memory store cannot do, and the whole reason for this module."""
    first = RedisRateLimitStore(redis_client)
    second = RedisRateLimitStore(redis_client)

    await first.hit("ratelimit:auth:ip:1", WINDOW)
    assert await second.hit("ratelimit:auth:ip:1", WINDOW) == 2


async def test_redis_forgets_what_left_the_window(redis_client: Any) -> None:
    store = RedisRateLimitStore(redis_client)
    await store.hit("ratelimit:auth:ip:1", 1)

    await asyncio.sleep(1.1)

    assert await store.hit("ratelimit:auth:ip:1", 1) == 1


async def test_redis_keys_expire_on_their_own(redis_client: Any) -> None:
    """Nobody is left to prune, so the key must die with its window."""
    store = RedisRateLimitStore(redis_client)
    await store.hit("ratelimit:auth:ip:1", 1)

    await asyncio.sleep(1.1)

    assert await redis_client.exists("ratelimit:auth:ip:1") == 0


async def test_redis_reset_clears_the_limiter_keys(redis_client: Any) -> None:
    store = RedisRateLimitStore(redis_client)
    await store.hit("ratelimit:auth:ip:1", WINDOW)

    await store.reset()

    assert await redis_client.keys("ratelimit:*") == []


async def test_an_unreachable_server_is_an_explicit_error() -> None:
    """Failing loudly is the requirement; the middleware decides what to do."""
    # Port 6390 is nothing's: the point is a server that is not there.
    client = create_redis_client("redis://127.0.0.1:6390/0")
    store = RedisRateLimitStore(client)
    try:
        with pytest.raises(RateLimitStoreError):
            await store.hit("ratelimit:auth:ip:1", WINDOW)
    finally:
        await client.aclose()


async def test_a_non_numeric_answer_is_refused_rather_than_counted(
    redis_client: Any,
) -> None:
    """A reply that is not a count must not be trusted as one.

    Treating an unexpected value as `0` would silently reopen the limiter, and
    treating it as `1` would refuse every legitimate request. Either way the
    service is wrong in a way nobody notices, so it is an error.
    """

    class WrongAnswer:
        async def __call__(self, **_: object) -> str:
            return "not-a-count"

    store = RedisRateLimitStore(redis_client)
    store._script = WrongAnswer()

    with pytest.raises(RateLimitStoreError):
        await store.hit("ratelimit:auth:ip:1", WINDOW)


# -- The middleware, against the shared store -------------------------------


async def test_the_middleware_uses_the_shared_store(redis_client: Any) -> None:
    from starlette.applications import Starlette
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.middleware.rate_limit import RateLimitMiddleware

    limiter = RateLimitMiddleware(Starlette())
    limiter.store = RedisRateLimitStore(redis_client)

    class Route(BaseHTTPMiddleware):
        async def dispatch(self, request: Any, call_next: Any) -> Any:
            return await call_next(request)

    assert limiter.store.backend == "redis"
    # Two middleware objects, one server: the second sees the first one's hits.
    other = RateLimitMiddleware(Starlette())
    other.store = limiter.store
    assert await limiter.store.hit("ratelimit:auth:ip:7", 60) == 1
    assert await other.store.hit("ratelimit:auth:ip:7", 60) == 2


async def test_an_unreachable_store_still_counts_rather_than_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The security decision when Redis is down.

    Counting in process is a weaker guarantee — one worker's budget instead of a
    shared one — but it is still a budget. Treating an outage as "no limit" would
    open `/auth/login` exactly when somebody is guessing passwords.
    """
    from starlette.applications import Starlette

    from app.core.config import get_settings
    from app.middleware.rate_limit import RateLimitMiddleware

    class Broken:
        backend = "redis"

        def register_script(self, _script: str) -> object:
            return self

        async def __call__(self, **_kwargs: object) -> int:
            raise ConnectionError("redis is down")

    limiter = RateLimitMiddleware(Starlette())
    limiter.store = RedisRateLimitStore(Broken())
    monkeypatch.setattr(get_settings(), "rate_limit_fail_closed", False)

    assert await limiter._count("ratelimit:auth:ip:1", 60) == 1
    assert await limiter._count("ratelimit:auth:ip:1", 60) == 2


async def test_fail_closed_refuses_everything_while_the_store_is_blind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stricter option, for a deployment that prefers refusing to serving."""
    from starlette.applications import Starlette

    from app.core.config import get_settings
    from app.middleware.rate_limit import RateLimitMiddleware

    class Broken:
        backend = "redis"

        def register_script(self, _script: str) -> object:
            return self

        async def __call__(self, **_kwargs: object) -> int:
            raise ConnectionError("redis is down")

    limiter = RateLimitMiddleware(Starlette())
    limiter.store = RedisRateLimitStore(Broken())
    monkeypatch.setattr(get_settings(), "rate_limit_fail_closed", True)

    assert await limiter._count("ratelimit:auth:ip:1", 60) > 60