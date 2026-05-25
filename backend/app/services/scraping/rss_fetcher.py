from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any

import feedparser
import httpx
from selectolax.parser import HTMLParser

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

USER_AGENT = "DarijaAI-Scraper/0.1 (+https://darija-ai.com)"
EXCERPT_MAX_CHARS = 280

logger = get_logger("services.scraping.rss_fetcher")


@dataclass
class FetchedItem:
    title: str
    content: str
    excerpt: str | None
    url: str
    image_url: str | None
    published_at: datetime | None


def _strip_html(html: str) -> str:
    if not html:
        return ""
    parser = HTMLParser(html)
    text = parser.text(separator=" ", strip=True) or ""
    return " ".join(text.split())


def _struct_time_to_utc(t: struct_time | None) -> datetime | None:
    if t is None:
        return None
    try:
        return datetime(
            t.tm_year,
            t.tm_mon,
            t.tm_mday,
            t.tm_hour,
            t.tm_min,
            t.tm_sec,
            tzinfo=UTC,
        )
    except (ValueError, TypeError):
        return None


def _extract_image_url(entry: dict[str, Any]) -> str | None:
    media_content = entry.get("media_content")
    if media_content:
        first = media_content[0] if isinstance(media_content, list) else media_content
        if isinstance(first, dict):
            url = first.get("url")
            if url:
                return str(url)

    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        first = media_thumbnail[0] if isinstance(media_thumbnail, list) else media_thumbnail
        if isinstance(first, dict):
            url = first.get("url")
            if url:
                return str(url)
        elif isinstance(first, str):
            return first

    return None


def _extract_content(entry: dict[str, Any]) -> str:
    content_list = entry.get("content")
    if content_list and isinstance(content_list, list) and content_list:
        first = content_list[0]
        if isinstance(first, dict) and first.get("value"):
            return _strip_html(str(first["value"]))

    summary = entry.get("summary")
    if summary:
        return _strip_html(str(summary))

    return ""


class RSSFetcher:
    def __init__(self, timeout_seconds: int = 20):
        self._timeout_seconds = timeout_seconds

    async def fetch(self, rss_url: str) -> list[FetchedItem]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(rss_url)
                response.raise_for_status()
                body = response.content
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                f"RSS fetch failed for {rss_url}: {exc.__class__.__name__}",
                details={"rss_url": rss_url, "error": str(exc)},
            ) from exc

        try:
            parsed = feedparser.parse(body)
        except Exception as exc:
            raise ExternalServiceError(
                f"RSS parse failed for {rss_url}",
                details={"rss_url": rss_url, "error": str(exc)},
            ) from exc

        if parsed.bozo:
            bozo_exc = parsed.get("bozo_exception")
            if not parsed.entries:
                # Malformed feed with nothing recoverable: remote site's fault,
                # skip gracefully rather than treating as a service failure.
                logger.warning(
                    "rss.malformed_feed",
                    rss_url=rss_url,
                    error=str(bozo_exc),
                )
                return []
            # Lenient parse recovered entries — proceed but flag.
            logger.warning(
                "rss.feed_parse_warning",
                rss_url=rss_url,
                error=str(bozo_exc),
                entries_recovered=len(parsed.entries),
            )

        items: list[FetchedItem] = []
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            url = (entry.get("link") or "").strip()

            if not title or not url:
                logger.warning(
                    "rss.entry.skipped_missing_field",
                    rss_url=rss_url,
                    has_title=bool(title),
                    has_url=bool(url),
                )
                continue

            content = _extract_content(entry)
            excerpt = content[:EXCERPT_MAX_CHARS] if content else None
            image_url = _extract_image_url(entry)

            published_at = _struct_time_to_utc(
                entry.get("published_parsed") or entry.get("updated_parsed")
            )

            items.append(
                FetchedItem(
                    title=title,
                    content=content,
                    excerpt=excerpt,
                    url=url,
                    image_url=image_url,
                    published_at=published_at,
                )
            )

        return items
