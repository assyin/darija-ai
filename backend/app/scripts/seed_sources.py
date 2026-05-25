from __future__ import annotations

import asyncio
import sys
from typing import TypedDict

from sqlalchemy import select

from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.models.source import Source


class SourceSeed(TypedDict):
    name: str
    rss_url: str | None
    scraping_url: str | None
    needs_html_enrichment: bool


SEED_SOURCES: list[SourceSeed] = [
    {
        "name": "Unite.AI",
        "rss_url": "https://www.unite.ai/feed/",
        "scraping_url": None,
        "needs_html_enrichment": False,
    },
    {
        "name": "VentureBeat AI",
        "rss_url": "https://venturebeat.com/category/ai/feed/",
        "scraping_url": None,
        "needs_html_enrichment": False,
    },
    {
        "name": "TechCrunch AI",
        "rss_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Hugging Face Blog",
        "rss_url": "https://huggingface.co/blog/feed.xml",
        "scraping_url": None,
        "needs_html_enrichment": True,
    },
    {
        "name": "Anthropic News",
        "rss_url": None,
        "scraping_url": "https://www.anthropic.com/news",
        "needs_html_enrichment": False,
    },
]


async def main() -> int:
    configure_logging()
    logger = get_logger("scripts.seed_sources")

    created = 0
    updated = 0
    unchanged = 0

    try:
        async with AsyncSessionLocal() as session:
            for seed in SEED_SOURCES:
                existing = await session.scalar(select(Source).where(Source.name == seed["name"]))
                if existing is None:
                    source = Source(
                        name=seed["name"],
                        rss_url=seed["rss_url"],
                        scraping_url=seed["scraping_url"],
                        is_active=True,
                        needs_html_enrichment=seed["needs_html_enrichment"],
                    )
                    session.add(source)
                    await session.flush()
                    logger.info(
                        "source.created",
                        name=source.name,
                        source_id=source.id,
                        rss_url=source.rss_url,
                        scraping_url=source.scraping_url,
                        needs_html_enrichment=source.needs_html_enrichment,
                    )
                    created += 1
                    continue

                changes: dict[str, object] = {}
                if existing.rss_url != seed["rss_url"]:
                    changes["rss_url"] = seed["rss_url"]
                if existing.scraping_url != seed["scraping_url"]:
                    changes["scraping_url"] = seed["scraping_url"]
                if existing.needs_html_enrichment != seed["needs_html_enrichment"]:
                    changes["needs_html_enrichment"] = seed["needs_html_enrichment"]

                if not changes:
                    logger.info(
                        "source.skipped_already_exists",
                        name=seed["name"],
                        source_id=existing.id,
                    )
                    unchanged += 1
                    continue

                for field_name, value in changes.items():
                    setattr(existing, field_name, value)
                session.add(existing)
                logger.info(
                    "source.updated",
                    name=existing.name,
                    source_id=existing.id,
                    changes=changes,
                )
                updated += 1

            await session.commit()

        logger.info(
            "seed.complete",
            created=created,
            updated=updated,
            unchanged=unchanged,
            total=len(SEED_SOURCES),
        )
        return 0
    except Exception:
        logger.exception(
            "seed.failed",
            created=created,
            updated=updated,
            unchanged=unchanged,
        )
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
