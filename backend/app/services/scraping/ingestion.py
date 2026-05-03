from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.models.raw_article import RawArticle
from app.models.source import Source
from app.services.scraping.relevance_filter import is_relevant, normalize_url, url_hash
from app.services.scraping.rss_fetcher import FetchedItem, RSSFetcher

logger = get_logger("services.scraping.ingestion")


@dataclass
class IngestionResult:
    source_id: int
    source_name: str
    fetched: int = 0
    inserted: int = 0
    skipped: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


class IngestionService:
    def __init__(
        self,
        rss_fetcher: RSSFetcher,
        max_items_per_source: int = 20,
    ):
        self._rss_fetcher = rss_fetcher
        self._max_items_per_source = max_items_per_source

    async def ingest_source(
        self, source: Source, session: AsyncSession
    ) -> IngestionResult:
        # Capture as locals up front: rollbacks expire ORM attributes, which would
        # cause MissingGreenlet on later access in this async context.
        assert source.id is not None
        source_id: int = source.id
        source_name: str = source.name
        rss_url: str | None = source.rss_url

        result = IngestionResult(source_id=source_id, source_name=source_name)
        start = time.perf_counter()

        if not rss_url:
            logger.info(
                "source.skipped_no_rss",
                source_id=source_id,
                source_name=source_name,
            )
            await self._mark_fetched(source_id, session)
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            return result

        items: list[FetchedItem] = []
        try:
            items = await self._rss_fetcher.fetch(rss_url)
        except ExternalServiceError as exc:
            logger.error(
                "source.fetch_failed",
                source_id=source_id,
                source_name=source_name,
                rss_url=rss_url,
                error=exc.message,
                details=exc.details,
            )
            result.errors.append(exc.message)
            await self._mark_fetched(source_id, session)
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            return result
        except Exception as exc:
            logger.exception(
                "source.fetch_unexpected_error",
                source_id=source_id,
                source_name=source_name,
            )
            result.errors.append(f"{exc.__class__.__name__}: {exc}")
            await self._mark_fetched(source_id, session)
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            return result

        capped = items[: self._max_items_per_source]
        result.fetched = len(capped)

        for item in capped:
            try:
                await self._process_item(item, source_id, session, result)
            except Exception as exc:
                logger.exception(
                    "source.item_failed",
                    source_id=source_id,
                    url=item.url,
                )
                result.errors.append(f"{exc.__class__.__name__}: {exc}")
                await session.rollback()

        await self._mark_fetched(source_id, session)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        return result

    async def _process_item(
        self,
        item: FetchedItem,
        source_id: int,
        session: AsyncSession,
        result: IngestionResult,
    ) -> None:
        normalized = normalize_url(item.url)
        h = url_hash(normalized)

        existing = await session.scalar(
            select(RawArticle.id).where(RawArticle.url_hash == h).limit(1)
        )
        if existing is not None:
            result.skipped += 1
            return

        relevant, reason = is_relevant(item.title, item.content)
        if not relevant:
            logger.info(
                "source.item_rejected",
                source_id=source_id,
                url=normalized,
                reason=reason,
                title=item.title[:120],
            )
            result.rejected += 1
            return

        raw = RawArticle(
            source_id=source_id,
            external_url=normalized,
            url_hash=h,
            original_title=item.title,
            original_content=item.content,
            original_excerpt=item.excerpt,
            original_image_url=item.image_url,
            published_at=item.published_at,
            processing_status="pending",
        )
        session.add(raw)
        await session.commit()
        result.inserted += 1
        logger.info(
            "source.item_inserted",
            source_id=source_id,
            raw_article_id=raw.id,
            url=normalized,
            title=item.title[:120],
        )

    async def _mark_fetched(self, source_id: int, session: AsyncSession) -> None:
        # Use UPDATE rather than ORM mutation so a prior rollback (which expires
        # ORM attributes) doesn't trigger a sync lazy-load in this async context.
        await session.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(last_fetched_at=datetime.now(timezone.utc))
        )
        await session.commit()

    async def ingest_all_active(
        self, session: AsyncSession
    ) -> list[IngestionResult]:
        sources = (
            await session.scalars(
                select(Source).where(Source.is_active.is_(True)).order_by(Source.id)
            )
        ).all()

        results: list[IngestionResult] = []
        for source in sources:
            result = await self.ingest_source(source, session)
            results.append(result)
        return results
