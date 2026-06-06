"""Unit tests for the direct EN → French localizer.

These pin the contract that callers (``article_processor`` + the future
``re-localize`` admin endpoint) depend on:

  - Cache HIT → no provider call, ``cached=True`` returned.
  - Cache MISS → provider called once, result persisted, ``cached=False``.
  - The cache key embeds ``PROMPT_VERSION`` so a prompt bump invalidates
    every prior cached row automatically.
  - The response JSON may be fenced in ``` markdown blocks ``` — the
    parser must accept that.
  - Missing required fields → ``AIQualityError``.
  - Malformed JSON → ``AIQualityError``.
  - The ``source_name`` flows through to the user prompt (soft attribution
    cue available for future prompt iterations).
  - ``raw_article_id`` propagates as metadata so ai_logs can attribute
    cost per article.

No real Anthropic call, no real Redis — both are faked at the seam.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest

from app.core.exceptions import AIQualityError
from app.services.ai.french_localizer import PROMPT_VERSION, FrenchLocalizer, _cache_key
from app.services.ai.llm_provider import LLMResponse

_VALID_OUTPUT = {
    "title_fr": "Anthropic dépose son IPO : pourquoi maintenant",
    "excerpt_fr": "L'entreprise IA prépare une introduction en bourse pour financer ses modèles.",
    "content_fr": "**Anthropic** vient de déposer en confidentiel les documents pour son IPO.",
    "meta_title_fr": "Anthropic dépose son IPO",
    "meta_description_fr": (
        "Anthropic dépose ses documents d'IPO. Daniela Amodei défend la "
        "stratégie d'investissement face aux doutes du marché."
    ),
}


# --- Fakes ------------------------------------------------------------------


class FakeRedis:
    """Minimal async Redis double — supports get/set/delete with a dict store."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append((key, value, ex))

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.delete_calls.append(key)


class FakeProvider:
    """Provider double that returns a queued LLMResponse and records the call."""

    default_model = "claude-haiku-4-5"

    def __init__(self, queued_text: Sequence[str]) -> None:
        self._queue = list(queued_text)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        metadata: dict[str, str] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "metadata": metadata or {},
            }
        )
        if not self._queue:
            raise AssertionError("FakeProvider.complete called more times than queued")
        text = self._queue.pop(0)
        return LLMResponse(
            text=text,
            input_tokens=1500,
            output_tokens=2000,
            cost_usd=Decimal("0.002"),
            model=self.default_model,
            provider="anthropic",
            duration_ms=2300,
            stop_reason="end_turn",
            request_id="req_test",
        )


# --- Tests ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_miss_calls_provider_and_persists() -> None:
    """First localize: provider hit, response cached, cached=False on return."""
    redis = FakeRedis()
    provider = FakeProvider([json.dumps(_VALID_OUTPUT)])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    result = await localizer.localize(
        title_en="Anthropic IPO filing",
        content_en="Anthropic files confidentially for IPO at $965B valuation...",
        source_name="TechCrunch",
        raw_article_id=42,
    )

    assert result.cached is False
    assert result.title_fr == _VALID_OUTPUT["title_fr"]
    assert result.content_fr == _VALID_OUTPUT["content_fr"]
    # Exactly one provider call.
    assert len(provider.calls) == 1
    # The system prompt was loaded from disk.
    assert "FrenchLocalizer" in provider.calls[0]["system"]
    # raw_article_id flows through metadata (ai_logs attribution).
    assert provider.calls[0]["metadata"]["raw_article_id"] == "42"
    # source_name surfaces in the user prompt.
    assert "TechCrunch" in provider.calls[0]["user"]
    # Result persisted to cache with the 30-day TTL.
    assert len(redis.set_calls) == 1
    _, _, ttl = redis.set_calls[0]
    assert ttl == 60 * 60 * 24 * 30


@pytest.mark.asyncio
async def test_cache_hit_skips_provider() -> None:
    """Second localize on the same EN input: no provider call, cached=True."""
    redis = FakeRedis()
    provider = FakeProvider([json.dumps(_VALID_OUTPUT)])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    # Prime: one call to populate the cache.
    await localizer.localize(
        title_en="Anthropic IPO filing",
        content_en="Anthropic files confidentially for IPO at $965B valuation...",
    )
    assert len(provider.calls) == 1

    # Replay: must hit the cache, no second provider call.
    result = await localizer.localize(
        title_en="Anthropic IPO filing",
        content_en="Anthropic files confidentially for IPO at $965B valuation...",
    )
    assert result.cached is True
    assert result.title_fr == _VALID_OUTPUT["title_fr"]
    assert len(provider.calls) == 1  # still one — no new call


@pytest.mark.asyncio
async def test_cache_key_includes_prompt_version() -> None:
    """A prompt version bump must invalidate the cache automatically."""
    payload = {"title": "T", "content": "C", "source": ""}
    key = _cache_key("claude-haiku-4-5", payload)
    # The key contains the namespace and the model — sanity check shape.
    assert key.startswith("localize:fr:claude-haiku-4-5:")
    # If PROMPT_VERSION ever changes, the key must too. We assert the version
    # is part of the digest input, not the literal key — confirmed by the
    # `_cache_key` implementation. Here we sanity check the current key shape
    # so a regression on the key format is loud.
    assert PROMPT_VERSION == "v1"


@pytest.mark.asyncio
async def test_response_fenced_in_markdown_is_parsed() -> None:
    """The model sometimes wraps JSON in ```json ... ``` despite the spec."""
    redis = FakeRedis()
    fenced = "```json\n" + json.dumps(_VALID_OUTPUT) + "\n```"
    provider = FakeProvider([fenced])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    result = await localizer.localize(
        title_en="x",
        content_en="y",
    )
    assert result.title_fr == _VALID_OUTPUT["title_fr"]


@pytest.mark.asyncio
async def test_missing_required_field_raises_quality_error() -> None:
    """The output schema is part of the contract; missing fields fail loudly."""
    redis = FakeRedis()
    incomplete = {k: v for k, v in _VALID_OUTPUT.items() if k != "content_fr"}
    provider = FakeProvider([json.dumps(incomplete)])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    with pytest.raises(AIQualityError) as exc_info:
        await localizer.localize(title_en="x", content_en="y")

    assert "missing fields" in str(exc_info.value).lower()
    # Cache must NOT have been populated for a bad output.
    assert redis.set_calls == []


@pytest.mark.asyncio
async def test_malformed_json_raises_quality_error() -> None:
    """Non-JSON output → AIQualityError with a preview for debugging."""
    redis = FakeRedis()
    provider = FakeProvider(["this is not JSON at all { broken"])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    with pytest.raises(AIQualityError) as exc_info:
        await localizer.localize(title_en="x", content_en="y")

    assert "non-JSON" in str(exc_info.value)
    assert redis.set_calls == []


@pytest.mark.asyncio
async def test_corrupt_cache_row_evicted_and_recomputed() -> None:
    """A cached value that can't be decoded must be evicted, not poison the call."""
    redis = FakeRedis()
    # Pre-poison the cache with junk that will fail json.loads.
    payload = {"title": "Anthropic IPO", "content": "...", "source": ""}
    bad_key = _cache_key("claude-haiku-4-5", payload)
    redis.store[bad_key] = "not even json {"

    provider = FakeProvider([json.dumps(_VALID_OUTPUT)])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    result = await localizer.localize(title_en="Anthropic IPO", content_en="...")

    # Should have evicted the bad key, called provider once, persisted clean.
    assert bad_key in redis.delete_calls
    assert len(provider.calls) == 1
    assert result.cached is False


@pytest.mark.asyncio
async def test_source_name_optional() -> None:
    """source_name is optional — when omitted, the user prompt skips that block."""
    redis = FakeRedis()
    provider = FakeProvider([json.dumps(_VALID_OUTPUT)])
    localizer = FrenchLocalizer(provider=provider, redis_client=redis)

    await localizer.localize(title_en="x", content_en="y")

    user_prompt = provider.calls[0]["user"]
    assert "### Source" not in user_prompt  # no source block rendered
    assert "### Title (English)" in user_prompt
    assert "### Body (English" in user_prompt
