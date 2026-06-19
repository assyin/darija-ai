"""Unit tests for the pipeline SHADOW recorder (ERE MVP — Step 5).

No DB here: we pin the two safety contracts that don't need one —
  * flag OFF  → no-op, returns False, the session factory is NEVER called;
  * ranker/DB error → swallowed (fail-soft), returns False, never propagates.
The flag-ON write path (records shadow cols, leaves status untouched) is covered
by the integration test against a real Postgres.
"""

from __future__ import annotations

import pytest

from app.services.editorial.shadow_recorder import maybe_record_shadow_ranking


@pytest.mark.asyncio
async def test_flag_off_is_a_noop_and_never_opens_a_session() -> None:
    called = {"factory": False}

    def _factory():  # type: ignore[no-untyped-def]
        called["factory"] = True
        raise AssertionError("session factory must NOT be called when flag is OFF")

    result = await maybe_record_shadow_ranking(
        123,
        enabled=False,
        threshold=55,
        tiers={},
        session_factory=_factory,  # type: ignore[arg-type]
    )

    assert result is False
    assert called["factory"] is False


@pytest.mark.asyncio
async def test_error_is_fail_soft_and_never_propagates() -> None:
    def _boom():  # type: ignore[no-untyped-def]
        raise RuntimeError("db down")

    # enabled=True but the session factory blows up → must be swallowed.
    result = await maybe_record_shadow_ranking(
        123,
        enabled=True,
        threshold=55,
        tiers={},
        session_factory=_boom,  # type: ignore[arg-type]
    )

    assert result is False  # swallowed, no exception raised
