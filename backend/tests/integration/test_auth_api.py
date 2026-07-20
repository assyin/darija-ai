from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis import get_redis_client

TOKEN_URL = "/api/v1/auth/token"
WRONG_CREDS = {"email": "nobody@example.com", "password": "wrongpassword"}

# All test IPs live in 10.9.x.x so cleanup is scoped and collision-free.
_KEY_PATTERN = "auth:login:10.9.*"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_rate_limit_keys() -> AsyncIterator[None]:
    yield
    try:
        redis = get_redis_client()
        keys = await redis.keys(_KEY_PATTERN)
        if keys:
            await redis.delete(*keys)
    except Exception:  # noqa: S110
        pass


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Correct credentials below the rate limit → 200 with JWT."""
    settings = get_settings()
    response = await client.post(
        TOKEN_URL,
        json={
            "email": settings.admin_email,
            "password": settings.admin_password.get_secret_value(),
        },
        headers={"X-Forwarded-For": "10.9.0.1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_wrong_credentials_below_limit(client: AsyncClient) -> None:
    """Wrong credentials below the rate limit → 401, not blocked."""
    response = await client.post(
        TOKEN_URL,
        json=WRONG_CREDS,
        headers={"X-Forwarded-For": "10.9.0.2"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_second_admin_login_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A credential from ADMIN_ACCOUNTS (not the primary) can sign in."""
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_accounts", "second-admin@example.com:secondpass123")
    response = await client.post(
        TOKEN_URL,
        json={"email": "second-admin@example.com", "password": "secondpass123"},
        headers={"X-Forwarded-For": "10.9.4.1"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_second_admin_wrong_password_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured second-admin email with the wrong password is still 401."""
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_accounts", "second-admin@example.com:secondpass123")
    response = await client.post(
        TOKEN_URL,
        json={"email": "second-admin@example.com", "password": "nope"},
        headers={"X-Forwarded-For": "10.9.4.2"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_primary_admin_still_works_with_extra_accounts(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adding ADMIN_ACCOUNTS must not break the primary admin login."""
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_accounts", "second-admin@example.com:secondpass123")
    response = await client.post(
        TOKEN_URL,
        json={
            "email": settings.admin_email,
            "password": settings.admin_password.get_secret_value(),
        },
        headers={"X-Forwarded-For": "10.9.4.3"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(client: AsyncClient) -> None:
    """Six requests from the same IP: first five reach auth check, sixth is blocked."""
    ip = "10.9.1.1"
    headers = {"X-Forwarded-For": ip}
    for _ in range(5):
        r = await client.post(TOKEN_URL, json=WRONG_CREDS, headers=headers)
        assert r.status_code == 401

    blocked = await client.post(TOKEN_URL, json=WRONG_CREDS, headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_isolates_by_ip(client: AsyncClient) -> None:
    """Exhausting one IP's limit does not affect a different IP."""
    ip_a = "10.9.2.1"
    ip_b = "10.9.2.2"
    for _ in range(5):
        await client.post(TOKEN_URL, json=WRONG_CREDS, headers={"X-Forwarded-For": ip_a})

    response = await client.post(TOKEN_URL, json=WRONG_CREDS, headers={"X-Forwarded-For": ip_b})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_redis_failure_fail_open(client: AsyncClient) -> None:
    """Redis error during rate limit check → fail open, auth still runs → 401."""
    mock_redis = MagicMock()
    mock_redis.pipeline.side_effect = RedisError("connection refused")
    with patch("app.api.v1.auth.get_redis_client", return_value=mock_redis):
        response = await client.post(
            TOKEN_URL,
            json=WRONG_CREDS,
            headers={"X-Forwarded-For": "10.9.3.1"},
        )
    assert response.status_code == 401
