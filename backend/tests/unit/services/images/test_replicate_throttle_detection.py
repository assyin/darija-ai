"""Unit tests for Replicate low-credit throttle detection.

These pin the contract between ``_is_low_credit_throttle`` and the
patterns surfaced in ``_REPLICATE_THROTTLE_ILIKE_PATTERNS`` in
``api/v1/ai_logs.py``. The two are kept in lock-step manually (Python
tuple vs SQL ILIKE-ANY), so when a Replicate message format change
breaks one we want the other to flag too — at least via a failing
test.

Real Jun 7 message (verbatim, captured from worker stdout):

    Request was throttled. Your rate limit for creating predictions
    is reduced to 6 requests per minute with a burst of 1 requests
    while you have less than $5.0 in credit. Your rate limit resets
    in ~10s.

That's the canonical input we anchor on.
"""

from __future__ import annotations

import pytest

from app.services.images.replicate_client import _is_low_credit_throttle


def test_real_jun_7_message_matches() -> None:
    """The exact prod message we saw on 2026-06-07 must match."""
    msg = (
        "Request was throttled. Your rate limit for creating predictions is "
        "reduced to 6 requests per minute with a burst of 1 requests while "
        "you have less than $5.0 in credit. Your rate limit resets in ~10s."
    )
    assert _is_low_credit_throttle(msg, status=429) is True


@pytest.mark.parametrize(
    "msg",
    [
        # Future variants Replicate may emit (different threshold, plain phrasing).
        "Request throttled because you have less than $10 in credit",
        "Rate limit for creating predictions is reduced to 12 requests per minute",
        # Mixed case + extra prefix.
        "ReplicateError Details: status: 429 detail: while you have less than $5.0",
    ],
)
def test_plausible_variants_match(msg: str) -> None:
    assert _is_low_credit_throttle(msg, status=429) is True


def test_429_without_low_credit_does_not_match() -> None:
    """A plain 429 (real burst, not a credit incident) must NOT page the operator."""
    msg = "Too many concurrent requests. Try again in a few seconds."
    assert _is_low_credit_throttle(msg, status=429) is False


def test_500_with_credit_substring_does_not_match() -> None:
    """Status code is part of the gate — only 429 counts as a throttle."""
    # Theoretical 5xx response that happens to mention 'credit' in the body —
    # not a billing incident, just a coincidence. Must not match.
    msg = "InternalServerError: credit check service unavailable"
    assert _is_low_credit_throttle(msg, status=500) is False


def test_status_none_does_not_match() -> None:
    """A missing status code (e.g. when the SDK didn't expose it) must NOT match."""
    msg = "Request was throttled. Your rate limit for creating predictions is reduced"
    assert _is_low_credit_throttle(msg, status=None) is False


@pytest.mark.parametrize(
    "msg",
    [
        # Normal transient or downstream failures — must NOT match.
        "Connection reset by peer",
        "Read timed out",
        "InternalServerError: backend unavailable",
        "Model returned malformed JSON",
        "Output blocked by safety filter",
        # An empty message — must not crash and must not match.
        "",
    ],
)
def test_unrelated_failures_do_not_match(msg: str) -> None:
    # Even with a 429 status, the pattern needs to actually mention the
    # credit angle. A generic 429 message must not trigger the credit alert.
    assert _is_low_credit_throttle(msg, status=429) is False


def test_case_insensitive_match() -> None:
    """The matcher must canonicalize case."""
    msg = (
        "REQUEST WAS THROTTLED. YOUR RATE LIMIT FOR CREATING PREDICTIONS IS "
        "REDUCED TO 6 REQUESTS PER MINUTE WHILE YOU HAVE LESS THAN $5.0"
    )
    assert _is_low_credit_throttle(msg, status=429) is True
