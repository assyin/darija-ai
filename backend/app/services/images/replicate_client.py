from __future__ import annotations

import time
from decimal import Decimal

import httpx
import replicate
from replicate.exceptions import ReplicateError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.services.images.image_provider import ImageGenerationResult

try:  # pragma: no cover - depends on prod settings module
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None  # type: ignore[assignment]

logger = get_logger("services.images.replicate_client")

PROVIDER_NAME = "replicate"
DEFAULT_MODEL = "black-forest-labs/flux-schnell"
PRICE_PER_IMAGE_USD = Decimal("0.003")
DOWNLOAD_TIMEOUT_SECONDS = 30.0

# Substring matchers for Replicate's anti-abuse low-credit throttle. When a
# Replicate account drops below $5 of remaining credit, the API enforces a
# 6 req/min rate cap with burst 1 — even though the model accepts the
# request shape and the token is valid. The pipeline normally pushes 50+
# req/min on cron bursts, so 95%+ of calls 429 with this exact message.
# Detect it loudly so the operator recharges *before* the cascade wastes
# upstream Claude calls (RCA 2026-06-07: $27 of Claude spend wasted on
# articles that died at the image step over 48h).
_LOW_CREDIT_THROTTLE_PATTERNS: tuple[str, ...] = (
    "less than $",
    "while you have less than",
    "rate limit for creating predictions is reduced",
)


def _is_low_credit_throttle(message: str, status: int | None) -> bool:
    """Heuristic match against Replicate's free-text low-credit throttle error.

    Only treats 429 status codes — a generic rate-limit (without the credit
    angle) is a real burst and should retry, not page the operator.
    """
    if status != 429:
        return False
    lowered = message.lower()
    return any(pattern in lowered for pattern in _LOW_CREDIT_THROTTLE_PATTERNS)


# Aspect ratio → (width, height) at Flux Schnell's ~1MP default.
_ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1024, 576),
    "9:16": (576, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "3:2": (1024, 683),
    "2:3": (683, 1024),
}

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (httpx.HTTPError,)


class ReplicateClient:
    """Replicate API wrapper using the official `replicate` SDK.

    Implements the ImageProvider Protocol. Uses Flux Schnell, which returns
    one or more images as `FileOutput` objects (newer SDK) or URLs (older).
    """

    PROVIDER_NAME = PROVIDER_NAME
    DEFAULT_MODEL = DEFAULT_MODEL
    PRICE_PER_IMAGE_USD = PRICE_PER_IMAGE_USD

    def __init__(self, api_token: str, model: str = DEFAULT_MODEL):
        self._client = replicate.Client(api_token=api_token)
        self._model = model

    async def generate(self, *, prompt: str, aspect_ratio: str = "16:9") -> ImageGenerationResult:
        input_payload: dict[str, object] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "webp",
            "num_outputs": 1,
        }

        logger.info(
            "image.replicate.request_started",
            model=self._model,
            aspect_ratio=aspect_ratio,
            prompt_chars=len(prompt),
        )

        start = time.perf_counter()
        try:
            output = await self._client.async_run(self._model, input=input_payload)
        except ReplicateError as exc:
            status = getattr(exc, "status", None)
            error_message = str(exc)

            # Operational vs platform split. 429 with the low-credit pattern
            # means recharge is required — paging the operator is the right
            # response. Any other Replicate error stays at ERROR level so the
            # admin isn't woken up by a transient 5xx or a content-policy
            # rejection.
            if _is_low_credit_throttle(error_message, status):
                logger.critical(
                    "image.replicate.low_credit_throttle_detected",
                    provider=PROVIDER_NAME,
                    model=self._model,
                    status=status,
                    error=error_message,
                    action_required=(
                        "recharge Replicate credits at "
                        "replicate.com/account/billing (min $20 recommended)"
                    ),
                )
                if sentry_sdk is not None:
                    sentry_sdk.capture_message(
                        f"Replicate low-credit throttle on {self._model}: {error_message[:200]}",
                        level="error",
                    )
            else:
                logger.error(
                    "image.replicate.request_failed",
                    model=self._model,
                    status=status,
                    error=error_message,
                )
            # Wrap with a richer message: the upstream caller (article_processor)
            # only persists `str(exc)` to ai_logs, so the message itself has to
            # carry enough signal to diagnose later. Truncated at 300 to stay
            # inside the column display budget while preserving the status +
            # the first chunk of the Replicate detail.
            preview = error_message.replace("\n", " ").strip()[:300]
            raise ExternalServiceError(
                f"Replicate request failed: {exc.__class__.__name__} (status={status}): {preview}",
                details={
                    "provider": PROVIDER_NAME,
                    "model": self._model,
                    "status": status,
                    "error": error_message,
                    "low_credit_throttle": _is_low_credit_throttle(error_message, status),
                },
            ) from exc

        try:
            image_bytes, mime_type = await self._read_first_image(output)
        except RetryError as exc:
            last = exc.last_attempt.exception()
            logger.error(
                "image.replicate.download_failed",
                model=self._model,
                error=str(last) if last else "unknown",
            )
            raise ExternalServiceError(
                "Replicate image download failed after retries",
                details={
                    "provider": PROVIDER_NAME,
                    "error": str(last) if last else "unknown",
                },
            ) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        width, height = _ASPECT_DIMENSIONS.get(aspect_ratio, (1024, 1024))

        logger.info(
            "image.replicate.request_completed",
            model=self._model,
            duration_ms=duration_ms,
            bytes_received=len(image_bytes),
            mime_type=mime_type,
            width=width,
            height=height,
            cost_usd=str(PRICE_PER_IMAGE_USD),
        )

        return ImageGenerationResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            width=width,
            height=height,
            cost_usd=PRICE_PER_IMAGE_USD,
            provider=PROVIDER_NAME,
            model=self._model,
            duration_ms=duration_ms,
        )

    async def _read_first_image(self, output: object) -> tuple[bytes, str]:
        """Resolve the first item in `output` to (bytes, mime_type).

        The newer `replicate` SDK (>=1.0) returns ``FileOutput`` objects with
        ``.read()`` for sync and ``.aread()`` for async, plus a ``.url`` attr.
        Older versions return raw URL strings.
        """
        first = output[0] if isinstance(output, list) else output

        # FileOutput-like (async)
        aread = getattr(first, "aread", None)
        if callable(aread):
            data = await aread()
            return bytes(data), self._guess_mime(getattr(first, "url", None))

        # FileOutput-like (sync read)
        read = getattr(first, "read", None)
        if callable(read):
            data = read()
            return bytes(data), self._guess_mime(getattr(first, "url", None))

        # URL string
        if isinstance(first, str):
            data = await self._download(first)
            return data, self._guess_mime(first)

        raise ExternalServiceError(
            "Replicate output type not understood",
            details={"provider": PROVIDER_NAME, "type": type(first).__name__},
        )

    async def _download(self, url: str) -> bytes:
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            reraise=False,
        )
        async for attempt in retrying:
            with attempt:
                async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.content
        raise RuntimeError("unreachable: download retry exited without yielding")

    @staticmethod
    def _guess_mime(url: str | None) -> str:
        if not url:
            return "image/webp"
        u = url.lower()
        if u.endswith(".png"):
            return "image/png"
        if u.endswith(".jpg") or u.endswith(".jpeg"):
            return "image/jpeg"
        return "image/webp"
