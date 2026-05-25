from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.core.logging import get_logger
from app.services.images.image_provider import ImageProvider
from app.services.images.r2_storage import R2Storage

logger = get_logger("services.images.image_generator")

_MIME_TO_EXT: dict[str, str] = {
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
}


@dataclass(frozen=True)
class ImageGenerationOutcome:
    public_url: str
    storage_key: str
    cost_usd: Decimal
    duration_ms: int
    width: int
    height: int


class ImageGenerator:
    """Orchestrates: provider generates → R2 stores → returns public URL."""

    def __init__(self, provider: ImageProvider, storage: R2Storage):
        self._provider = provider
        self._storage = storage

    async def generate_and_upload(
        self,
        *,
        prompt: str,
        article_slug: str,
        aspect_ratio: str = "16:9",
    ) -> ImageGenerationOutcome:
        logger.info(
            "image_generator.started",
            article_slug=article_slug,
            aspect_ratio=aspect_ratio,
            prompt_chars=len(prompt),
        )
        start = time.perf_counter()

        result = await self._provider.generate(prompt=prompt, aspect_ratio=aspect_ratio)

        now = datetime.now(UTC)
        ext = _MIME_TO_EXT.get(result.mime_type, "webp")
        key = f"articles/{now:%Y}/{now:%m}/{article_slug}.{ext}"

        public_url = await self._storage.upload(
            key=key,
            body=result.image_bytes,
            content_type=result.mime_type,
        )

        total_duration_ms = int((time.perf_counter() - start) * 1000)
        outcome = ImageGenerationOutcome(
            public_url=public_url,
            storage_key=key,
            cost_usd=result.cost_usd,
            duration_ms=total_duration_ms,
            width=result.width,
            height=result.height,
        )
        logger.info(
            "image_generator.completed",
            article_slug=article_slug,
            public_url=public_url,
            duration_ms=total_duration_ms,
            cost_usd=str(result.cost_usd),
            width=result.width,
            height=result.height,
        )
        return outcome
