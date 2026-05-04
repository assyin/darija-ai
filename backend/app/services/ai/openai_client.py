from __future__ import annotations

import time

import openai
from openai import AsyncOpenAI
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
from app.services.ai.pricing import compute_cost

logger = get_logger("services.ai.openai_client")

DEFAULT_TIMEOUT_SECONDS = 60.0
PROVIDER_NAME = "openai"

_RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)

_FATAL_ERRORS: tuple[type[BaseException], ...] = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.BadRequestError,
)


class OpenAIClient:
    PROVIDER_NAME = PROVIDER_NAME
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        default_model: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self._default_model = default_model or self.DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return self.PROVIDER_NAME

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
    ) -> LLMResponse:
        model_to_use = model or self._default_model

        logger.info(
            "ai.llm.request_started",
            provider=PROVIDER_NAME,
            model=model_to_use,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=metadata,
        )

        start = time.perf_counter()
        try:
            response = await self._call_with_retry(
                model=model_to_use,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except _FATAL_ERRORS as exc:
            logger.error(
                "ai.llm.request_failed",
                provider=PROVIDER_NAME,
                model=model_to_use,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            raise ExternalServiceError(
                f"OpenAI request failed: {exc.__class__.__name__}",
                details={"provider": PROVIDER_NAME, "error": str(exc)},
            ) from exc
        except openai.APIError as exc:
            logger.error(
                "ai.llm.request_failed",
                provider=PROVIDER_NAME,
                model=model_to_use,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            raise ExternalServiceError(
                f"OpenAI request failed: {exc.__class__.__name__}",
                details={"provider": PROVIDER_NAME, "error": str(exc)},
            ) from exc
        except RetryError as exc:
            last = exc.last_attempt.exception()
            logger.error(
                "ai.llm.retries_exhausted",
                provider=PROVIDER_NAME,
                model=model_to_use,
                error=str(last) if last else "unknown",
            )
            raise ExternalServiceError(
                "OpenAI request failed after retries",
                details={
                    "provider": PROVIDER_NAME,
                    "error": str(last) if last else "unknown",
                },
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)

        choice = response.choices[0]
        text = choice.message.content or ""
        finish_reason = choice.finish_reason or ""

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = compute_cost(model_to_use, input_tokens, output_tokens)
        request_id = response.id

        logger.info(
            "ai.llm.request_completed",
            provider=PROVIDER_NAME,
            model=model_to_use,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=str(cost),
            stop_reason=finish_reason,
            request_id=request_id,
        )

        return LLMResponse(
            text=text,
            provider=PROVIDER_NAME,
            model=model_to_use,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost_usd=cost,
            stop_reason=finish_reason,
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
    ):  # type: ignore[no-untyped-def]
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(_RETRYABLE_ERRORS),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=False,
        )
        async for attempt in retrying:
            with attempt:
                return await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

        raise RuntimeError("unreachable: AsyncRetrying with reraise=False exited without yielding")
