from __future__ import annotations

from decimal import Decimal

from app.core.logging import get_logger

logger = get_logger("services.ai.pricing")

# Per 1M tokens: (input, output) in USD.
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
    "claude-opus-4-7": (Decimal("5"), Decimal("25")),
    # OpenAI
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10")),
}

# Anthropic prompt-cache multipliers (relative to base input rate). Published
# pricing: writes cost 25% more than a normal input token (the API has to
# tokenize + store the block), reads cost 90% less (the model reads from the
# pre-warmed KV cache). The same ratios apply across all Claude families
# (Haiku/Sonnet/Opus), so we keep one pair of constants.
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
CACHE_READ_MULTIPLIER = Decimal("0.10")


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Decimal:
    """Returns USD cost for a single LLM completion.

    ``input_tokens`` is the count of fresh, uncached input tokens. The two
    cache-related counters are optional (default 0, preserving the v1
    behaviour) and only meaningful for Anthropic providers that returned
    ``Usage.cache_creation_input_tokens`` / ``Usage.cache_read_input_tokens``.

    Pricing model (all per 1M tokens):

      - uncached input : base in_rate
      - cache write    : in_rate * 1.25
      - cache read     : in_rate * 0.10
      - output         : base out_rate

    Returns ``Decimal('0')`` with a warning when the model is unknown — the
    cost dashboard will then show $0 for the call rather than crashing.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        logger.warning("ai.pricing.unknown_model", model=model)
        return Decimal("0")
    in_rate, out_rate = pricing
    cost = (
        Decimal(input_tokens) * in_rate
        + Decimal(cache_creation_tokens) * in_rate * CACHE_WRITE_MULTIPLIER
        + Decimal(cache_read_tokens) * in_rate * CACHE_READ_MULTIPLIER
        + Decimal(output_tokens) * out_rate
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))
