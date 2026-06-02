"""Conditional HTML enrichment for RSS items that ship without full content.

Many modern RSS feeds (TechCrunch, HuggingFace blog, etc.) carry only a short
excerpt — sometimes nothing at all — in the feed body. The full article lives
on the source website. This service fetches the URL and extracts the main
article text using trafilatura, so the relevance filter has real content to
work with.

Used by `IngestionService` *only* when `is_relevant` returns
``(False, "too_short")``. Items with a sufficient body skip enrichment
entirely (no extra latency for VentureBeat etc.).
"""

from __future__ import annotations

import httpx
import trafilatura

from app.core.logging import get_logger

logger = get_logger("services.scraping.html_enricher")

# A real desktop browser UA — the scraper UA gets blocked by some hosts.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class HTMLEnricher:
    """Async URL → main article text extractor.

    `enrich(url)` returns the extracted text on success, or ``None`` on any
    failure (network error, empty extraction, parse error). All paths log
    structured events for observability — never raises to the caller.
    """

    def __init__(self, timeout_seconds: int = 8):
        self._timeout_seconds = timeout_seconds

    async def enrich(self, url: str) -> str | None:
        # 1) fetch HTML
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                headers={"User-Agent": _BROWSER_UA, "Accept": "text/html,*/*"},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError as exc:
            logger.warning(
                "enrichment.fetch_failed",
                url=url,
                error=f"{exc.__class__.__name__}: {exc}",
            )
            return None
        except Exception as exc:
            logger.exception(
                "enrichment.fetch_unexpected_error",
                url=url,
                error=str(exc),
            )
            return None

        if not html or not html.strip():
            logger.info("enrichment.failed", url=url, reason="empty_html")
            return None

        # 2) extract main content
        try:
            extracted: str | None = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_precision=True,
            )
        except Exception as exc:
            logger.exception("enrichment.extract_error", url=url, error=str(exc))
            return None

        if not extracted or not extracted.strip():
            logger.info("enrichment.failed", url=url, reason="empty_extract")
            return None

        return extracted.strip()
