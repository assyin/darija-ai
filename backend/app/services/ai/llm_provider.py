from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    cost_usd: Decimal
    stop_reason: str
    request_id: str | None


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def default_model(self) -> str: ...

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        metadata: dict[str, str] | None = None,
    ) -> LLMResponse: ...
