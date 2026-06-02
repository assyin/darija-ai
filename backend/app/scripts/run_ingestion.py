from __future__ import annotations

import asyncio
import sys

from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging, get_logger
from app.services.scraping.html_enricher import HTMLEnricher
from app.services.scraping.ingestion import IngestionResult, IngestionService
from app.services.scraping.rss_fetcher import RSSFetcher


def _print_summary(results: list[IngestionResult]) -> None:
    header = f"{'Source':<24} {'Fetched':>8} {'Inserted':>9} {'Enriched':>9} {'Skipped':>8} {'Rejected':>9} {'Duration':>10}"  # noqa: E501
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        print(
            f"{r.source_name[:24]:<24} {r.fetched:>8} {r.inserted:>9} "
            f"{r.enriched:>9} {r.skipped:>8} {r.rejected:>9} {r.duration_ms:>8} ms"
        )
    print(sep)
    totals = {
        "fetched": sum(r.fetched for r in results),
        "inserted": sum(r.inserted for r in results),
        "enriched": sum(r.enriched for r in results),
        "skipped": sum(r.skipped for r in results),
        "rejected": sum(r.rejected for r in results),
    }
    print(
        f"{'TOTAL':<24} {totals['fetched']:>8} {totals['inserted']:>9} "
        f"{totals['enriched']:>9} {totals['skipped']:>8} {totals['rejected']:>9}"
    )
    print(sep)


async def main() -> int:
    configure_logging()
    log = get_logger("scripts.run_ingestion")

    fetcher = RSSFetcher()
    enricher = HTMLEnricher()
    service = IngestionService(rss_fetcher=fetcher, enricher=enricher)

    try:
        async with AsyncSessionLocal() as session:
            results = await service.ingest_all_active(session)

        for r in results:
            log.info(
                "source.ingested",
                source_id=r.source_id,
                source_name=r.source_name,
                fetched=r.fetched,
                inserted=r.inserted,
                enriched=r.enriched,
                skipped=r.skipped,
                rejected=r.rejected,
                errors=r.errors,
                duration_ms=r.duration_ms,
            )

        _print_summary(results)

        any_errors = any(r.errors for r in results)
        return 1 if any_errors else 0
    except Exception:
        log.exception("ingestion.run_failed")
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
