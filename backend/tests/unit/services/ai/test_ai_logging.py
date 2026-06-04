"""Unit tests for the AI cost-tracking layer.

Validates :class:`LoggingLLMProvider` and :func:`persist_ai_log` against an
in-process fake session — no Postgres, no aiosqlite, no Anthropic API. Keeps
the test focused on the behaviour the production incident depended on (RCA
2026-06-04): rows are constructed with the right shape, sessions get
committed, and a broken DB never breaks the AI call.

Integration tests with a real Postgres connection live separately under
``tests/integration/`` and are not duplicated here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.exceptions import ExternalServiceError
from app.models.ai_log import AILog
from app.services.ai.ai_logging import (
    LoggingLLMProvider,
    _extract_raw_article_id,
    persist_ai_log,
)
from app.services.ai.llm_provider import LLMResponse

# --- Fake session ------------------------------------------------------------


class _FakeSession:
    """Captures every ``add()`` and asserts ``commit()`` was called.

    Implements only the surface ``persist_ai_log`` uses. The real
    ``AsyncSession`` is far larger; that breadth doesn't need testing
    here — SQLAlchemy is.
    """

    def __init__(self) -> None:
        self.added: list[AILog] = []
        self.committed = False
        self.closed = False

    def add(self, row: AILog) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True


def _fake_factory() -> tuple[_FakeSession, callable]:
    """Return (the captured session, a factory callable that returns it)."""
    session = _FakeSession()

    def factory() -> _FakeSession:
        return session

    return session, factory


# --- Fake LLM provider -------------------------------------------------------


class _FakeProvider:
    def __init__(
        self,
        response: LLMResponse | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._response = response
        self._raises = raises
        self.last_metadata: dict[str, str] | None = None

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return "fake-model"

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
        self.last_metadata = metadata
        if self._raises is not None:
            raise self._raises
        assert self._response is not None
        return self._response


def _make_response(**overrides: object) -> LLMResponse:
    defaults: dict[str, object] = {
        "text": "ok",
        "provider": "fake",
        "model": "fake-model",
        "input_tokens": 100,
        "output_tokens": 50,
        "duration_ms": 250,
        "cost_usd": Decimal("0.000175"),
        "stop_reason": "end_turn",
        "request_id": "req_abc",
    }
    defaults.update(overrides)
    return LLMResponse(**defaults)  # type: ignore[arg-type]


# --- _extract_raw_article_id -------------------------------------------------


def test_extract_raw_article_id_from_string() -> None:
    assert _extract_raw_article_id({"raw_article_id": "42"}) == 42


def test_extract_raw_article_id_missing() -> None:
    assert _extract_raw_article_id(None) is None
    assert _extract_raw_article_id({}) is None
    assert _extract_raw_article_id({"user_id": "x"}) is None


def test_extract_raw_article_id_invalid_returns_none() -> None:
    # Never poison the INSERT with a bad FK — drop it instead.
    assert _extract_raw_article_id({"raw_article_id": "not-a-number"}) is None


# --- persist_ai_log ----------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_ai_log_writes_row_and_commits() -> None:
    session, factory = _fake_factory()
    await persist_ai_log(
        provider="replicate",
        model="black-forest-labs/flux-schnell",
        success=True,
        cost_usd=Decimal("0.003"),
        duration_ms=1200,
        raw_article_id=7,
        session_factory=factory,  # type: ignore[arg-type]
    )
    assert session.committed is True
    assert session.closed is True
    assert len(session.added) == 1
    row = session.added[0]
    assert row.provider == "replicate"
    assert row.success is True
    assert row.cost_usd == Decimal("0.003")
    assert row.raw_article_id == 7
    assert row.duration_ms == 1200


@pytest.mark.asyncio
async def test_persist_ai_log_records_failure_shape() -> None:
    session, factory = _fake_factory()
    await persist_ai_log(
        provider="claude",
        model="claude-haiku-4-5",
        success=False,
        cost_usd=Decimal("0"),
        raw_article_id=42,
        error="rate limited",
        session_factory=factory,  # type: ignore[arg-type]
    )
    row = session.added[0]
    assert row.success is False
    assert row.error == "rate limited"
    assert row.cost_usd == Decimal("0")


@pytest.mark.asyncio
async def test_persist_ai_log_swallows_factory_error() -> None:
    """A broken session factory must NOT propagate — observability is best-effort."""

    def broken_factory() -> _FakeSession:
        raise RuntimeError("DB exploded")

    # Should not raise. The structlog warning is the backup record.
    await persist_ai_log(
        provider="claude",
        model="claude-haiku-4-5",
        success=True,
        cost_usd=Decimal("0.001"),
        session_factory=broken_factory,  # type: ignore[arg-type]
    )


# --- LoggingLLMProvider ------------------------------------------------------


@pytest.mark.asyncio
async def test_logging_provider_persists_success() -> None:
    session, factory = _fake_factory()
    inner = _FakeProvider(response=_make_response(provider="claude", model="claude-haiku-4-5"))
    wrapper = LoggingLLMProvider(inner, session_factory=factory)  # type: ignore[arg-type]

    result = await wrapper.complete(
        system="sys",
        user="usr",
        metadata={"user_id": "translator", "raw_article_id": "13"},
    )

    assert result.text == "ok"
    assert session.committed is True
    row = session.added[0]
    assert row.provider == "claude"
    assert row.model == "claude-haiku-4-5"
    assert row.success is True
    assert row.input_tokens == 100
    assert row.output_tokens == 50
    assert row.cost_usd == Decimal("0.000175")
    assert row.raw_article_id == 13
    assert row.duration_ms == 250


@pytest.mark.asyncio
async def test_logging_provider_strips_raw_article_id_from_forwarded_metadata() -> None:
    """raw_article_id is ours; never forward it to the upstream API."""
    _, factory = _fake_factory()
    inner = _FakeProvider(response=_make_response())
    wrapper = LoggingLLMProvider(inner, session_factory=factory)  # type: ignore[arg-type]

    await wrapper.complete(
        system="sys",
        user="usr",
        metadata={"user_id": "translator", "raw_article_id": "13"},
    )

    assert inner.last_metadata == {"user_id": "translator"}


@pytest.mark.asyncio
async def test_logging_provider_persists_failure_and_reraises() -> None:
    session, factory = _fake_factory()
    inner = _FakeProvider(
        raises=ExternalServiceError("Claude down", details={"provider": "claude", "error": "503"})
    )
    wrapper = LoggingLLMProvider(inner, session_factory=factory)  # type: ignore[arg-type]

    with pytest.raises(ExternalServiceError):
        await wrapper.complete(system="sys", user="usr", metadata={"raw_article_id": "99"})

    assert session.committed is True
    row = session.added[0]
    assert row.success is False
    assert row.raw_article_id == 99
    assert "Claude down" in (row.error or "")


@pytest.mark.asyncio
async def test_logging_provider_db_failure_does_not_break_ai_call() -> None:
    """If the DB hiccups during persist, the AI response still returns."""

    def broken_factory() -> _FakeSession:
        raise RuntimeError("DB exploded")

    inner = _FakeProvider(response=_make_response())
    wrapper = LoggingLLMProvider(inner, session_factory=broken_factory)  # type: ignore[arg-type]

    result = await wrapper.complete(system="sys", user="usr")
    assert result.text == "ok"
