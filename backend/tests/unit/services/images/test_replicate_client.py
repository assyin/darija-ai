from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from replicate.exceptions import ReplicateError

from app.core.exceptions import ExternalServiceError
from app.services.images.image_provider import ImageGenerationResult, ImageProvider
from app.services.images.replicate_client import ReplicateClient


def _make_client_with_async_run(async_run_mock: AsyncMock) -> ReplicateClient:
    client = ReplicateClient(api_token="r8_test_token")
    client._client = MagicMock()
    client._client.async_run = async_run_mock
    return client


def _file_output(image_bytes: bytes, url: str = "https://example.com/x.webp") -> MagicMock:
    """Mimics the newer replicate SDK FileOutput with .aread() and .url."""
    fo = MagicMock()
    fo.aread = AsyncMock(return_value=image_bytes)
    fo.url = url
    return fo


def test_implements_image_provider_protocol():
    client = ReplicateClient(api_token="r8_test_token")
    assert isinstance(client, ImageProvider)


@pytest.mark.asyncio
async def test_input_dict_is_correct_for_default_aspect_ratio():
    captured: dict[str, object] = {}

    async def fake_async_run(model: str, input: dict[str, object]):
        captured["model"] = model
        captured["input"] = input
        return [_file_output(b"\x00\x01webp-bytes")]

    client = _make_client_with_async_run(AsyncMock(side_effect=fake_async_run))
    result = await client.generate(prompt="abstract blue gradient")

    assert captured["model"] == "black-forest-labs/flux-schnell"
    assert captured["input"] == {
        "prompt": "abstract blue gradient",
        "aspect_ratio": "16:9",
        "output_format": "webp",
        "num_outputs": 1,
    }
    assert isinstance(result, ImageGenerationResult)
    assert result.image_bytes == b"\x00\x01webp-bytes"
    assert result.cost_usd == Decimal("0.003")
    assert result.provider == "replicate"
    assert result.width == 1024 and result.height == 576


@pytest.mark.asyncio
async def test_aspect_ratio_is_forwarded():
    captured_input: dict[str, object] = {}

    async def fake_async_run(model: str, input: dict[str, object]):
        captured_input.update(input)
        return [_file_output(b"abc")]

    client = _make_client_with_async_run(AsyncMock(side_effect=fake_async_run))
    result = await client.generate(prompt="x", aspect_ratio="1:1")

    assert captured_input["aspect_ratio"] == "1:1"
    assert (result.width, result.height) == (1024, 1024)


@pytest.mark.asyncio
async def test_replicate_error_wraps_in_external_service_error():
    error = ReplicateError("Internal Server Error")
    client = _make_client_with_async_run(AsyncMock(side_effect=error))

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.generate(prompt="x")
    assert exc_info.value.details["provider"] == "replicate"
    assert "ReplicateError" in exc_info.value.message
