"""Unit tests for the IndexNow notifier.

We patch ``httpx.AsyncClient`` so no real HTTP calls leave the test process,
and ``persist_ai_log`` to verify the observability path is hit on every code
branch (success / non-2xx / network error / disabled).

The contract these tests pin (failures here would surprise editors):
    - notify() returns False without making an HTTP call when api_key is None.
    - notify() returns False without making an HTTP call when urls is empty.
    - notify() returns True on a 200 or 202 response.
    - notify() returns False on a 4xx/5xx — and DOES NOT raise.
    - notify() returns False on a network error — and DOES NOT raise.
    - The persist_ai_log row records success=True/False matching the outcome.
    - The request body shape matches the IndexNow protocol (host, key,
      keyLocation, urlList).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.external.indexnow import notify


def _ok_response(status: int = 200) -> MagicMock:
    """Build a duck-typed httpx.Response with the given status code."""
    response = MagicMock()
    response.status_code = status
    response.text = ""
    return response


@pytest.mark.asyncio
async def test_notify_skips_when_api_key_missing() -> None:
    """No key configured (dev/staging) → silent no-op, no HTTP call, no log row."""
    with (
        patch("app.services.external.indexnow.httpx.AsyncClient") as MockClient,
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()) as mock_log,
    ):
        ok = await notify(
            urls=["https://titritai.com/articles/foo"],
            api_key=None,
            site_url="https://titritai.com",
        )

    assert ok is False
    MockClient.assert_not_called()
    mock_log.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_skips_when_url_list_empty() -> None:
    """Empty url list → no HTTP call. Defensive against accidental empty pings."""
    with (
        patch("app.services.external.indexnow.httpx.AsyncClient") as MockClient,
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()) as mock_log,
    ):
        ok = await notify(
            urls=[],
            api_key="a" * 32,
            site_url="https://titritai.com",
        )

    assert ok is False
    MockClient.assert_not_called()
    mock_log.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_success_returns_true_and_logs() -> None:
    """200 OK → True + ai_logs success row."""
    key = "ab56769f25ab9a5507265a7b465fc708"
    urls = [
        "https://titritai.com/articles/foo",
        "https://titritai.com/fr/articles/foo",
    ]
    posted_body: dict[str, Any] = {}

    async def fake_post(url: str, **kw: Any) -> MagicMock:
        posted_body["url"] = url
        posted_body["json"] = kw["json"]
        return _ok_response(200)

    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=fake_post))
    client_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.external.indexnow.httpx.AsyncClient", return_value=client_ctx),
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()) as mock_log,
    ):
        ok = await notify(urls=urls, api_key=key, site_url="https://titritai.com")

    assert ok is True
    # Body shape matches the IndexNow protocol exactly.
    assert posted_body["json"]["host"] == "titritai.com"
    assert posted_body["json"]["key"] == key
    assert posted_body["json"]["keyLocation"] == f"https://titritai.com/{key}.txt"
    assert posted_body["json"]["urlList"] == urls
    # Observability: success=True row landed in ai_logs.
    mock_log.assert_awaited_once()
    call_kwargs = mock_log.await_args.kwargs
    assert call_kwargs["provider"] == "indexnow"
    assert call_kwargs["success"] is True
    assert call_kwargs["cost_usd"] == Decimal("0")
    assert call_kwargs["error"] is None


@pytest.mark.asyncio
async def test_notify_202_accepted_is_success() -> None:
    """IndexNow returns 202 (queued) for many backends — treat as success."""

    async def fake_post(*_a: Any, **_kw: Any) -> MagicMock:
        return _ok_response(202)

    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=fake_post))
    client_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.external.indexnow.httpx.AsyncClient", return_value=client_ctx),
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()),
    ):
        ok = await notify(
            urls=["https://titritai.com/articles/foo"],
            api_key="x" * 32,
            site_url="https://titritai.com",
        )

    assert ok is True


@pytest.mark.asyncio
async def test_notify_4xx_returns_false_no_raise() -> None:
    """422 (key verification fails) → False, fail-soft, ai_logs success=False."""

    async def fake_post(*_a: Any, **_kw: Any) -> MagicMock:
        r = _ok_response(422)
        r.text = "key file not found"
        return r

    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=fake_post))
    client_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.external.indexnow.httpx.AsyncClient", return_value=client_ctx),
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()) as mock_log,
    ):
        ok = await notify(
            urls=["https://titritai.com/articles/foo"],
            api_key="x" * 32,
            site_url="https://titritai.com",
        )

    assert ok is False
    call_kwargs = mock_log.await_args.kwargs
    assert call_kwargs["success"] is False
    assert call_kwargs["error"] == "http_422"


@pytest.mark.asyncio
async def test_notify_network_error_returns_false_no_raise() -> None:
    """Connect timeout / DNS error → False, fail-soft, ai_logs records the error."""

    async def fake_post(*_a: Any, **_kw: Any) -> None:
        raise httpx.ConnectTimeout("dial timeout")

    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=fake_post))
    client_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.external.indexnow.httpx.AsyncClient", return_value=client_ctx),
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()) as mock_log,
    ):
        ok = await notify(
            urls=["https://titritai.com/articles/foo"],
            api_key="x" * 32,
            site_url="https://titritai.com",
        )

    assert ok is False
    call_kwargs = mock_log.await_args.kwargs
    assert call_kwargs["success"] is False
    assert "ConnectTimeout" in (call_kwargs["error"] or "")


@pytest.mark.asyncio
async def test_notify_trailing_slash_in_site_url_normalised() -> None:
    """`site_url` may arrive with or without trailing slash — keyLocation must be clean."""
    posted: dict[str, Any] = {}

    async def fake_post(*_a: Any, **kw: Any) -> MagicMock:
        posted["json"] = kw["json"]
        return _ok_response(200)

    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=fake_post))
    client_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.external.indexnow.httpx.AsyncClient", return_value=client_ctx),
        patch("app.services.external.indexnow.persist_ai_log", new=AsyncMock()),
    ):
        await notify(
            urls=["https://titritai.com/articles/foo"],
            api_key="abc",
            site_url="https://titritai.com/",  # trailing slash
        )

    # keyLocation should NOT have a double slash before the key.
    assert posted["json"]["keyLocation"] == "https://titritai.com/abc.txt"
