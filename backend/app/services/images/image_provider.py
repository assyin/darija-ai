from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    cost_usd: Decimal
    provider: str
    model: str
    duration_ms: int


@runtime_checkable
class ImageProvider(Protocol):
    """Protocol for any image generation backend."""

    async def generate(
        self, *, prompt: str, aspect_ratio: str = "16:9"
    ) -> ImageGenerationResult: ...
