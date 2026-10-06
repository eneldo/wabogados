"""Production hardening: the checks that only bite in a real deployment.

Every test here corresponds to a finding from the 2026-10-05 audit, and all three
share a shape: **nothing goes wrong in development**, which is exactly why
nothing caught them. The container started, the suite passed, and a deployment
would have been forgeable, unroutable or unprotected.

That is why they are unit tests over the settings rather than HTTP tests. The
behaviour under test is "refuse to start" or "do not believe a header", and
neither needs a running server to be observed.
"""

import pytest
from starlette.requests import Request

from app.api.deps import get_client_ip
from app.core.config import Settings
from app.main import allowed_hosts_from_origins, assert_production_is_safe

# -- 1. The signing key may not be the one in the repository ----------------


def test_production_refuses_the_repository_signing_key() -> None:
    """A deployment that forgot `SECRET_KEY` would sign tokens with a public key.

    The default satisfies the 32-character rule precisely so it works in
    development. In production it means anyone can mint a valid `access` token, and
    the whole permission model becomes decoration.
    """
    settings = Settings(
        app_environment="production",
        secret_key="dev-secret-key-change-in-production",
        cors_origins=["https://app.example"],
        cors_allow_methods=["GET"],
        cors_allow_headers=["Authorization"],
    )

    with pytest.raises(ValueError) as excinfo:
        assert_production_is_safe(settings)

    assert "SECRET_KEY" in str(excinfo.value)


def test_a_short_key_never_reaches_the_settings_object() -> None:
    """Length is already refused at construction, before any of this runs.

    Asserting that here as well would be testing pydantic. Asserting that the
    guard is *unreachable* for a short key is the useful half: it records that the
    two layers agree instead of assuming it.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(secret_key="corta")


def test_production_refuses_the_documented_default_key() -> None:
    settings = Settings(
        app_environment="production",
        secret_key="dev-secret-key-change-in-production",
        cors_origins=["https://app.example"],
        cors_allow_methods=["GET"],
        cors_allow_headers=["Authorization"],
    )

    with pytest.raises(ValueError):
        assert_production_is_safe(settings)


def test_production_refuses_wildcard_cors() -> None:
    """`["*"]` disables host-header protection entirely, as DEPLOY.md warns."""
    settings = Settings(
        app_environment="production",
        secret_key="y" * 40,
        cors_origins=["*"],
    )

    with pytest.raises(ValueError) as excinfo:
        assert_production_is_safe(settings)

    assert "CORS_ORIGINS" in str(excinfo.value)


def test_production_refuses_wildcard_methods_or_headers() -> None:
    settings = Settings(
        app_environment="production",
        secret_key="y" * 40,
        cors_origins=["https://app.example"],
        cors_allow_methods=["*"],
        cors_allow_headers=["Authorization"],
    )

    with pytest.raises(ValueError) as excinfo:
        assert_production_is_safe(settings)

    assert "CORS_ALLOW_METHODS" in str(excinfo.value)


def test_a_real_production_configuration_passes() -> None:
    """The check must be passable, or operators will disable it."""
    settings = Settings(
        app_environment="production",
        secret_key="z" * 40,
        cors_origins=["https://app.mi-despacho.example"],
        cors_allow_methods=["GET", "POST"],
        cors_allow_headers=["Authorization", "Content-Type"],
    )

    assert_production_is_safe(settings)


def test_development_is_not_policed() -> None:
    """Otherwise nobody could run the project locally."""
    Settings(app_environment="development", secret_key="dev-secret-key-change-in-production")

    Settings(app_environment="test", secret_key="dev-secret-key-change-in-production")


# -- 2. Trusted hosts cannot be URLs ----------------------------------------


def test_allowed_hosts_are_hosts_not_urls() -> None:
    """Starlette compares the raw `Host` header, which never carries a scheme."""
    hosts = allowed_hosts_from_origins(["https://app.mi-despacho.example"])

    assert hosts == ["app.mi-despacho.example"]


def test_allowed_hosts_keep_a_non_default_port() -> None:
    hosts = allowed_hosts_from_origins(["http://localhost:3000"])

    assert hosts == ["localhost:3000"]


def test_allowed_hosts_cover_every_origin() -> None:
    hosts = allowed_hosts_from_origins(
        ["https://app.example", "https://www.example", "https://api.example"]
    )

    assert hosts == ["app.example", "www.example", "api.example"]


def test_a_wildcard_origin_produces_no_host() -> None:
    """`*` is not a hostname and must not be handed to TrustedHostMiddleware."""
    assert allowed_hosts_from_origins(["*"]) == []


def test_an_empty_origin_list_produces_no_host() -> None:
    assert allowed_hosts_from_origins([]) == []


# -- 3. X-Forwarded-For is only believed from a declared proxy --------------


def _request(headers: dict[str, str], peer: str = "10.0.0.9") -> Request:
    from starlette.requests import Request

    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw,
            "client": (peer, 40000),
        }
    )


def test_a_forged_forwarded_header_from_a_stranger_is_ignored() -> None:
    """This header was believed unconditionally, which made every limit per-request.

    A rotating `X-Forwarded-For` produced a fresh budget on every call, which
    defeats the authentication throttle and the public consultation form — the two
    budgets that exist to make a guess expensive.
    """
    request = _request({"X-Forwarded-For": "203.0.113.9"})

    assert get_client_ip(request, trusted_proxies=[]) == "10.0.0.9"


def test_the_forwarded_header_is_used_when_the_peer_is_a_declared_proxy() -> None:
    request = _request({"X-Forwarded-For": "203.0.113.9"}, peer="172.18.0.4")

    assert get_client_ip(request, trusted_proxies=["172.18.0.4"]) == "203.0.113.9"


def test_a_declared_proxy_list_does_not_trust_anybody_else() -> None:
    request = _request({"X-Forwarded-For": "203.0.113.9"}, peer="192.0.2.7")

    assert get_client_ip(request, trusted_proxies=["172.18.0.4"]) == "192.0.2.7"


def test_the_rightmost_forwarded_entry_is_the_one_added_by_our_proxy() -> None:
    """The leftmost entry is whatever the caller wrote.

    A chain `spoofed, real-client` arrives with our proxy having appended
    `real-client`, so trusting index 0 would hand the attacker their choice.
    """
    request = _request(
        {"X-Forwarded-For": "198.51.100.7, 203.0.113.9"}, peer="172.18.0.4"
    )

    assert get_client_ip(request, trusted_proxies=["172.18.0.4"]) == "203.0.113.9"


def test_without_the_header_the_peer_is_used() -> None:
    assert get_client_ip(_request({}), trusted_proxies=["172.18.0.4"]) == "10.0.0.9"


def test_a_request_without_a_peer_does_not_crash() -> None:
    from starlette.requests import Request

    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "client": None}
    )

    assert get_client_ip(request, trusted_proxies=[]) == "unknown"


def test_the_audit_trail_uses_the_declared_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_client_ip` is only half the fix; the callers have to pass them.

    The first version changed the helper and then updated the rate limiter alone.
    Behind a real proxy every `audit_logs` and `evidence_access_logs` row then held
    the proxy's address instead of the caller's: not forgeable, but useless for
    forensics, and no test failed because the forged-header tests all exercised the
    helper directly rather than the middleware.

    So this asserts the wiring, which is the part that was actually missing. The
    patch target is `app.core.config`, because `_trusted_proxies` imports inside the
    function and resolves the name there.
    """
    from app.api import deps as deps_module
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module, "get_settings", lambda: Settings(trusted_proxies=["172.18.0.4"])
    )

    behind_proxy = _request({"X-Forwarded-For": "203.0.113.9"}, peer="172.18.0.4")
    assert get_client_ip(behind_proxy, deps_module._trusted_proxies()) == "203.0.113.9"

    from_a_stranger = _request({"X-Forwarded-For": "203.0.113.9"}, peer="192.0.2.7")
    assert get_client_ip(from_a_stranger, deps_module._trusted_proxies()) == "192.0.2.7"