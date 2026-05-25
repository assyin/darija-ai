from __future__ import annotations

from decimal import Decimal

from app.core.logging import get_logger

logger = get_logger("services.ai.pricing")

# Per 1M tokens: (input, output) in USD
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
    "claude-opus-4-7": (Decimal("5"), Decimal("25")),
    # OpenAI
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10")),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Returns USD cost for a completion. Decimal('0') with a warning if model is unknown."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        logger.warning("ai.pricing.unknown_model", model=model)
        return Decimal("0")
    in_rate, out_rate = pricing
    cost = (Decimal(input_tokens) * in_rate + Decimal(output_tokens) * out_rate) / Decimal(
        1_000_000
    )
    return cost.quantize(Decimal("0.000001"))
