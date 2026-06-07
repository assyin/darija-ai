"""Cost-tracking persistence for AI calls.

Wires the existing ``ai_logs`` table (defined in ``app/models/ai_log.py`` but
historically never written to — see RCA 2026-06-04) to every AI call the
platform makes.

Two surfaces:

1. :class:`LoggingLLMProvider` — decorator implementing the
   :class:`~app.services.ai.llm_provider.LLMProvider` Protocol. Wraps any
   inner LLM provider (Claude, OpenAI, …) and persists one ``ai_logs`` row
   per call. The :class:`Localizer` and :class:`Translator` go through this.

2. :func:`persist_ai_log` — direct helper for code paths that don't flow
   through ``LLMProvider``: Replicate image generation, the Proofreader's
   raw ``AsyncOpenAI`` client. Same row shape.

Both surfaces are **fail-soft**: a database error during persistence emits a
structured-log warning and is swallowed. The AI call's result (or error) is
always honoured. This trades observability completeness for not making the
pipeline brittle on a DB hiccup — the structlog event is the backup record.

The wrapper reads ``metadata["raw_article_id"]`` (string-encoded int) when
present, so the row is joinable to ``raw_articles`` for per-article cost
attribution. Callers that don't have a raw article id simply omit it.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING

from app.core.db import AsyncSessionLocal
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.models.ai_log import AILog
from app.services.ai.llm_provider import LLMProvider, LLMResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("services.ai.logging")

# Type alias for the session factory dependency — kept as a callable so tests
# can inject a fake without monkey-patching the global ``AsyncSessionLocal``.
SessionFactory = Callable[[], "AsyncSession"]


def _extract_raw_article_id(metadata: dict[str, str] | None) -> int | None:
    """Pull ``raw_article_id`` out of a Claude/OpenAI ``metadata`` dict.

    The dict carries string values (Anthropic SDK constraint). We accept the
    common shapes and return ``None`` for anything we can't parse — better a
    missing FK than a poisoned INSERT.
    """
    if not metadata:
        return None
    raw = metadata.get("raw_article_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("ai_logging.bad_raw_article_id", value=str(raw))
        return None


async def persist_ai_log(
    *,
    provider: str,
    model: str,
    success: bool,
    cost_usd: Decimal,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    duration_ms: int | None = None,
    raw_article_id: int | None = None,
    error: str | None = None,
    session_factory: SessionFactory = AsyncSessionLocal,
) -> None:
    """Insert one row into ``ai_logs``. Fail-soft on DB errors.

    Designed for code paths that don't go through ``LLMProvider`` (image
    generation, Proofreader's direct OpenAI client). The wrapper
    :class:`LoggingLLMProvider` is preferred for LLM calls.
    """
    try:
        async with session_factory() as session:
            row = AILog(
                raw_article_id=raw_article_id,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                success=success,
                error=error,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:  # fail-soft: never let log failure break the AI call
        # Surface the failure to structlog so it's still observable, but DO
        # NOT propagate. The AI call already happened; the user request must
        # not break because we couldn't log it.
        logger.warning(
            "ai_logging.persist_failed",
            provider=provider,
            model=model,
            success=success,
            cost_usd=str(cost_usd),
            raw_article_id=raw_article_id,
            error=str(exc),
            error_type=exc.__class__.__name__,
        )


class LoggingLLMProvider:
    """Decorator that wraps an LLM provider and writes ``ai_logs`` per call.

    Implements the :class:`LLMProvider` Protocol so callers (Localizer,
    Translator, …) are agnostic to the wrapping. Pass an instance wherever a
    raw :class:`ClaudeClient` or :class:`OpenAIClient` would have gone.

    Example::

        provider = LoggingLLMProvider(ClaudeClient(api_key))
        localizer = Localizer(provider=provider, ...)
        translator = Translator(provider=provider, ...)

    A call is logged with ``success=True`` after a clean response, and with
    ``success=False`` after the inner provider raises (the exception is
    re-raised intact).
    """

    def __init__(
        self,
        inner: LLMProvider,
        *,
        session_factory: SessionFactory = AsyncSessionLocal,
    ) -> None:
        self._inner = inner
        self._session_factory = session_factory

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def default_model(self) -> str:
        return self._inner.default_model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        metadata: dict[str, str] | None = None,
        cache_system: bool = False,
    ) -> LLMResponse:
        raw_article_id = _extract_raw_article_id(metadata)

        # Strip raw_article_id from the metadata we forward — Anthropic only
        # honours specific keys (user_id) and unknown keys may be rejected
        # depending on the API version. We keep our own key out of the wire.
        forwarded_metadata = (
            {k: v for k, v in metadata.items() if k != "raw_article_id"}
            if metadata is not None
            else None
        )

        try:
            response = await self._inner.complete(
                system=system,
                user=user,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                metadata=forwarded_metadata,
                cache_system=cache_system,
            )
        except ExternalServiceError as exc:
            await persist_ai_log(
                provider=self._inner.provider_name,
                model=model or self._inner.default_model,
                success=False,
                cost_usd=Decimal("0"),
                raw_article_id=raw_article_id,
                error=str(exc),
                session_factory=self._session_factory,
            )
            raise

        await persist_ai_log(
            provider=response.provider,
            model=response.model,
            success=True,
            cost_usd=response.cost_usd,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_ms=response.duration_ms,
            raw_article_id=raw_article_id,
            error=None,
            session_factory=self._session_factory,
        )
        return response
