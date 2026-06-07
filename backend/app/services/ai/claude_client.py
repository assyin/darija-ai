from __future__ import annotations

import time

import anthropic
from anthropic import AsyncAnthropic
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.services.ai.llm_provider import LLMResponse
from app.services.ai.pricing import (  # noqa: F401  (re-exported for back-compat)
    MODEL_PRICING,
    compute_cost,
)

try:  # pragma: no cover - depends on prod settings module
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

logger = get_logger("services.ai.claude_client")

DEFAULT_TIMEOUT_SECONDS = 60.0
PROVIDER_NAME = "claude"

_RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)

_FATAL_AUTH_ERRORS: tuple[type[BaseException], ...] = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
)

# Substring matchers (case-insensitive) for Anthropic billing/quota errors.
# These come back as BadRequestError with a free-text message — there is no
# typed exception class for them. When one is detected the pipeline must
# raise an immediate, loud alert (Sentry + structured log) so the operator
# knows the outage is OPERATIONAL (recharge needed), not a platform issue.
_BILLING_ERROR_PATTERNS: tuple[str, ...] = (
    "credit balance",
    "insufficient",
    "billing",
    "quota",
    "payment",
)


def _is_billing_error(message: str) -> bool:
    """Heuristic match against Anthropic's free-text billing/quota errors."""
    lowered = message.lower()
    return any(pattern in lowered for pattern in _BILLING_ERROR_PATTERNS)


class ClaudeClient:
    DEFAULT_MODEL = "claude-haiku-4-5"

    def __init__(
        self,
        api_key: str,
        default_model: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)
        self._default_model = default_model or self.DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return PROVIDER_NAME

    @property
    def default_model(self) -> str:
        return self._default_model

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
        model_to_use = model or self._default_model

        api_metadata: dict[str, str] | None = None
        if metadata and "user_id" in metadata:
            api_metadata = {"user_id": metadata["user_id"]}

        logger.info(
            "ai.claude.request_started",
            model=model_to_use,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=metadata,
            cache_system=cache_system,
        )

        start = time.perf_counter()
        try:
            response = await self._call_with_retry(
                model=model_to_use,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
                api_metadata=api_metadata,
                cache_system=cache_system,
            )
        except _FATAL_AUTH_ERRORS as exc:
            logger.error(
                "ai.claude.auth_failed",
                model=model_to_use,
                error=str(exc),
            )
            raise ExternalServiceError(
                "Claude authentication failed",
                details={"provider": PROVIDER_NAME, "error": str(exc)},
            ) from exc
        except anthropic.APIError as exc:
            # Operational vs platform split: if Anthropic is telling us the
            # account is out of credit (or quota), the pipeline must alert
            # loudly — recharge is on the operator, no amount of retry helps.
            # Sentry + a CRITICAL structured log give the admin two signals.
            if _is_billing_error(str(exc)):
                logger.critical(
                    "ai.billing_error_detected",
                    provider=PROVIDER_NAME,
                    model=model_to_use,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    action_required="recharge Anthropic credits at console.anthropic.com",
                )
                if sentry_sdk is not None:
                    sentry_sdk.capture_message(
                        f"Anthropic billing/quota error on {model_to_use}: {str(exc)[:200]}",
                        level="error",
                    )
            else:
                logger.error(
                    "ai.claude.request_failed",
                    model=model_to_use,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                )
            raise ExternalServiceError(
                f"Claude request failed: {exc.__class__.__name__}",
                details={"provider": PROVIDER_NAME, "error": str(exc)},
            ) from exc
        except RetryError as exc:
            last = exc.last_attempt.exception()
            logger.error(
                "ai.claude.retries_exhausted",
                model=model_to_use,
                error=str(last) if last else "unknown",
            )
            raise ExternalServiceError(
                "Claude request failed after retries",
                details={
                    "provider": PROVIDER_NAME,
                    "error": str(last) if last else "unknown",
                },
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)

        text_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        text = "".join(text_parts)

        # Anthropic returns cache stats separately when cache_control was used.
        # When caching is off (or the SDK is older than 0.40), getattr defaults
        # to 0 so the cost calc still works.
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        cost = compute_cost(
            model_to_use,
            input_tokens,
            output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )
        request_id = getattr(response, "id", None)

        # Cache hit ratio is a useful observability signal — surface in the
        # structured log so /admin/costs or grep can show how well caching
        # is performing per batch. Avoid log spam by computing only what we
        # already have.
        total_input_billed = input_tokens + cache_creation + cache_read
        cache_hit_ratio = float(cache_read) / total_input_billed if total_input_billed else 0.0
        logger.info(
            "ai.claude.request_completed",
            model=model_to_use,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            cache_hit_ratio=round(cache_hit_ratio, 3),
            cost_usd=str(cost),
            stop_reason=response.stop_reason,
            request_id=request_id,
        )

        # ai_logs schema stores `input_tokens` as a single number — we sum the
        # three categories so the dashboards still reflect total billable input.
        # Detail is preserved in the structured log above.
        return LLMResponse(
            text=text,
            provider=PROVIDER_NAME,
            model=model_to_use,
            input_tokens=input_tokens + cache_creation + cache_read,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost_usd=cost,
            stop_reason=str(response.stop_reason or ""),
            request_id=request_id,
        )

    async def _call_with_retry(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        api_metadata: dict[str, str] | None,
        cache_system: bool,
    ) -> anthropic.types.Message:
        # When caching is on, wrap the system prompt in a TextBlockParam with
        # ephemeral cache_control. Anthropic stores the tokenized prefix for
        # 5 minutes; subsequent calls hitting the same prefix pay 10% of the
        # input price instead of 100%. First call in a window pays a 25%
        # write surcharge — still a net win after the second call.
        if cache_system:
            system_param: str | list[dict[str, object]] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system

        retrying = AsyncRetrying(
            retry=retry_if_exception_type(_RETRYABLE_ERRORS),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=False,
        )
        async for attempt in retrying:
            with attempt:
                kwargs: dict[str, object] = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_param,
                    "messages": [{"role": "user", "content": user}],
                }
                if api_metadata is not None:
                    kwargs["metadata"] = api_metadata
                return await self._client.messages.create(**kwargs)  # type: ignore[arg-type]

        raise RuntimeError("unreachable: AsyncRetrying with reraise=False exited without yielding")
