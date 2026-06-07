"""Unit tests for ``_is_billing_error`` in ``claude_client``.

The function classifies Anthropic's free-text error messages into "billing
incident" vs everything else. The pipeline uses that classification to:

  - Log a CRITICAL structured event (operator sees it in stdout).
  - Capture a Sentry message at error level (operator gets paged).
  - Power the ``/admin/ai-logs/provider-health`` banner.

If we miss a real billing message → the alert never fires.
If we false-positive on a normal error → the operator gets pinged for
nothing and stops trusting the alert.

This file pins the substring matchers against the real-world messages
Anthropic has been observed to return.
"""

from __future__ import annotations

import pytest

from app.services.ai.claude_client import _is_billing_error


@pytest.mark.parametrize(
    "message",
    [
        # The exact string returned to TitritAI prod on 2026-06-06 when credits ran out.
        "Your credit balance is too low to access the Anthropic API. "
        "Please go to Plans & Billing to upgrade or purchase credits.",
        # Possible variants Anthropic may emit (lower / no period / wrapped).
        "Insufficient credits",
        "BadRequestError: insufficient quota for this account",
        "Billing issue: subscription expired",
        "Payment failed: card declined",
        # Mixed case + extra prefix from our wrapper.
        "Claude request failed: BadRequestError: Your credit balance is too low",
    ],
)
def test_real_billing_messages_match(message: str) -> None:
    assert _is_billing_error(message) is True


@pytest.mark.parametrize(
    "message",
    [
        # Normal transient errors — must NOT page the operator.
        "Connection reset by peer",
        "Read timed out",
        "InternalServerError: backend unavailable",
        "Request was aborted",
        # Plausible model-side rejections.
        "Model returned malformed JSON",
        "Output blocked by content filter",
        # An empty message — must not crash and must not match.
        "",
    ],
)
def test_non_billing_messages_do_not_match(message: str) -> None:
    assert _is_billing_error(message) is False


def test_case_insensitive_match() -> None:
    """Anthropic sometimes capitalises; the matcher must not care."""
    assert _is_billing_error("CREDIT BALANCE too low") is True
    assert _is_billing_error("Credit Balance Too Low") is True
    assert _is_billing_error("credit balance too low") is True
