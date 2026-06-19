"""Integration tests for the SHADOW recorder against a real Postgres.

Proves the flag-ON path: the recorder writes ONLY the decoupled editorial_*
columns and leaves the business ``processing_status`` untouched; flag-OFF writes
nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.editorial.shadow_recorder import maybe_record_shadow_ranking

_PUBLISHED = datetime(2026, 6, 18, 11, 0, tzinfo=UTC)
_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def pending_raw() -> AsyncIterator[tuple[int, str]]:
    token = uuid.uuid4().hex[:8]
    name = f"_test_src_{token}"
    async with AsyncSessionLocal() as session:
        source = Source(name=name, rss_url=f"http://t/{token}.xml")
        session.add(source)
        await session.commit()
        await session.refresh(source)
        raw = RawArticle(
            source_id=int(source.id),  # type: ignore[arg-type]
            external_url=f"http://t/{token}",
            url_hash=token.ljust(64, "0"),
            original_title="OpenAI raises $1 billion",
            original_content="AI startup machine learning gpt model platform",
            processing_status="pending",
            published_at=_PUBLISHED,
            fetched_at=_PUBLISHED,
        )
        session.add(raw)
        await session.commit()
        await session.refresh(raw)
        raw_id = int(raw.id)  # type: ignore[arg-type]
        source_id = int(source.id)  # type: ignore[arg-type]

    yield raw_id, name

    async with AsyncSessionLocal() as session:
        await session.execute(delete(RawArticle).where(col(RawArticle.id) == raw_id))
        await session.execute(delete(Source).where(col(Source.id) == source_id))
        await session.commit()


@pytest.mark.asyncio
async def test_shadow_on_writes_shadow_columns_without_touching_status(
    pending_raw: tuple[int, str],
) -> None:
    raw_id, name = pending_raw
    ok = await maybe_record_shadow_ranking(
        raw_id,
        enabled=True,
        threshold=55,
        tiers={name: "B"},
        now=_NOW,
    )
    assert ok is True

    async with AsyncSessionLocal() as session:
        raw = await session.get(RawArticle, raw_id)
        assert raw is not None
        assert raw.editorial_score is not None and raw.editorial_score > 0
        assert raw.editorial_decision in ("selected", "deferred")
        assert raw.score_breakdown is not None
        assert "computed_at" in raw.score_breakdown
        assert raw.score_breakdown["source_tier"] == "B"
        # SHADOW-default model is the tightened v1_1 importance composite.
        assert raw.score_breakdown["importance_detail"]["model"] == "v1_1"
        # The business status is NEVER touched by the shadow recorder.
        assert raw.processing_status == "pending"


@pytest.mark.asyncio
async def test_shadow_off_writes_nothing(pending_raw: tuple[int, str]) -> None:
    raw_id, name = pending_raw
    ok = await maybe_record_shadow_ranking(raw_id, enabled=False, threshold=55, tiers={name: "B"})
    assert ok is False

    async with AsyncSessionLocal() as session:
        raw = await session.get(RawArticle, raw_id)
        assert raw is not None
        assert raw.editorial_decision == "unranked"
        assert raw.editorial_score is None
        assert raw.processing_status == "pending"
