"""Integration tests for ArticleProcessor against a real Postgres DB.

Collaborators (localizer, quality gate, image generator) are injected as fakes
so the test exercises orchestration, ``raw_article.processing_status``
transitions, and draft persistence without calling external APIs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.core.exceptions import AIQualityError
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.ai.localizer import LocalizedArticle
from app.services.ai.quality_gate import QualityCheckResult
from app.services.pipeline.article_processor import ArticleProcessor


def _make_localized(slug: str) -> LocalizedArticle:
    return LocalizedArticle(
        title_darija="عنوان تجريبي",
        slug=slug,
        excerpt_darija="مقتطف تجريبي",
        content_darija="هاد المقال هو محتوى تجريبي باش نختبرو البايبلاين ديال المعالجة.",
        meta_title="عنوان ميتا",
        meta_description="وصف ميتا",
        categories=["ai"],
        tags=["test"],
        image_prompt="a test image prompt",
    )


class _FakeLocalizer:
    def __init__(self, article: LocalizedArticle) -> None:
        self._article = article

    async def localize(self, **_: Any) -> LocalizedArticle:
        return self._article


class _FailingLocalizer:
    """Transient/parse-shaped failure — should stay `failed` (retryable)."""

    async def localize(self, **_: Any) -> LocalizedArticle:
        raise AIQualityError("bad json", details={"reason": "invalid_json"})


class _RejectingLocalizer:
    """Mirrors Localizer when the model returns {"reject": true} — a permanent,
    deterministic rejection that must NOT be retried."""

    async def localize(self, **_: Any) -> LocalizedArticle:
        raise AIQualityError(
            "Model rejected the source article",
            details={"reason": "rejected_by_model", "model_reason": "off-topic"},
        )


class _FakeQualityGate:
    def __init__(self, *, passed: bool, failures: list[str] | None = None) -> None:
        self._result = QualityCheckResult(
            passed=passed,
            failures=failures or [],
            warnings=[],
            word_count=120,
            detected_language="ar",
        )

    def check(self, _article: LocalizedArticle) -> QualityCheckResult:
        return self._result


class _FailingImageGenerator:
    async def generate_and_upload(self, **_: Any) -> Any:
        raise RuntimeError("image service down")


@pytest_asyncio.fixture
async def pending_raw_id() -> AsyncIterator[int]:
    """Insert a source + a pending raw article; clean up everything after."""
    token = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        source = Source(name=f"_test_src_{token}", rss_url=f"http://t/{token}.xml")
        session.add(source)
        await session.commit()
        await session.refresh(source)

        raw = RawArticle(
            source_id=int(source.id),  # type: ignore[arg-type]
            external_url=f"http://t/{token}",
            url_hash=token.ljust(64, "0"),
            original_title="Original title",
            original_content="Original English content to localize.",
            processing_status="pending",
        )
        session.add(raw)
        await session.commit()
        await session.refresh(raw)
        raw_id = int(raw.id)  # type: ignore[arg-type]
        source_id = int(source.id)  # type: ignore[arg-type]

    yield raw_id

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Article).where(col(Article.raw_article_id) == raw_id))
        await session.execute(delete(RawArticle).where(col(RawArticle.id) == raw_id))
        await session.execute(delete(Source).where(col(Source.id) == source_id))
        await session.commit()


async def _status_of(raw_id: int) -> str:
    async with AsyncSessionLocal() as session:
        raw = await session.get(RawArticle, raw_id)
        assert raw is not None
        return raw.processing_status


async def _draft_for(raw_id: int) -> Article | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Article).where(col(Article.raw_article_id) == raw_id))


@pytest.mark.asyncio
async def test_happy_path_creates_unpublished_draft(pending_raw_id: int) -> None:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    processor = ArticleProcessor(
        localizer=_FakeLocalizer(_make_localized(slug)),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(passed=True),  # type: ignore[arg-type]
        image_generator=None,
    )

    outcome = await processor.process(pending_raw_id)

    assert outcome.status == "translated"
    assert outcome.quality_passed is True
    assert outcome.article_id is not None
    assert await _status_of(pending_raw_id) == "translated"

    draft = await _draft_for(pending_raw_id)
    assert draft is not None
    assert draft.is_published is False
    assert draft.slug == slug


@pytest.mark.asyncio
async def test_quality_failure_rejects_without_draft(pending_raw_id: int) -> None:
    processor = ArticleProcessor(
        localizer=_FakeLocalizer(_make_localized("rej")),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(  # type: ignore[arg-type]
            passed=False, failures=["too_short", "language_not_arabic"]
        ),
        image_generator=None,
    )

    outcome = await processor.process(pending_raw_id)

    assert outcome.status == "rejected"
    assert outcome.quality_passed is False
    assert "too_short" in outcome.failures
    assert await _status_of(pending_raw_id) == "rejected"
    assert await _draft_for(pending_raw_id) is None


@pytest.mark.asyncio
async def test_localizer_transient_error_marks_failed(pending_raw_id: int) -> None:
    """A parse-shaped AIQualityError (not a model reject) stays `failed` so
    retry_failed can re-attempt it (the failure may be a transient model hiccup)."""
    processor = ArticleProcessor(
        localizer=_FailingLocalizer(),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(passed=True),  # type: ignore[arg-type]
        image_generator=None,
    )

    outcome = await processor.process(pending_raw_id)

    assert outcome.status == "failed"
    assert "localizer_failed" in outcome.failures
    assert await _status_of(pending_raw_id) == "failed"
    assert await _draft_for(pending_raw_id) is None


@pytest.mark.asyncio
async def test_model_reject_marks_rejected_terminal(pending_raw_id: int) -> None:
    """A model rejection lands in the TERMINAL `rejected` status (not `failed`),
    so retry_failed never re-localizes it — kills the deterministic-reject retry
    leak (~70% of spend on ~7.5 retries per unfit article)."""
    processor = ArticleProcessor(
        localizer=_RejectingLocalizer(),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(passed=True),  # type: ignore[arg-type]
        image_generator=None,
    )

    outcome = await processor.process(pending_raw_id)

    assert outcome.status == "rejected"
    assert "localizer_rejected" in outcome.failures
    assert await _status_of(pending_raw_id) == "rejected"
    assert await _draft_for(pending_raw_id) is None


@pytest.mark.asyncio
async def test_image_failure_marks_failed(pending_raw_id: int) -> None:
    processor = ArticleProcessor(
        localizer=_FakeLocalizer(_make_localized("img")),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(passed=True),  # type: ignore[arg-type]
        image_generator=_FailingImageGenerator(),  # type: ignore[arg-type]
    )

    outcome = await processor.process(pending_raw_id)

    assert outcome.status == "failed"
    assert outcome.quality_passed is True
    assert await _status_of(pending_raw_id) == "failed"
    assert await _draft_for(pending_raw_id) is None


@pytest.mark.asyncio
async def test_missing_raw_article_returns_failed() -> None:
    processor = ArticleProcessor(
        localizer=_FakeLocalizer(_make_localized("x")),  # type: ignore[arg-type]
        quality_gate=_FakeQualityGate(passed=True),  # type: ignore[arg-type]
        image_generator=None,
    )

    outcome = await processor.process(999_999_999)

    assert outcome.status == "failed"
    assert "raw_article_not_found" in outcome.failures
