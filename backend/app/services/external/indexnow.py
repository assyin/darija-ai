"""IndexNow notifier — push freshly-published URLs to Bing/Yandex/etc.

IndexNow (https://www.indexnow.org/) is a free protocol that lets us notify
participating search engines the moment an article is published, instead of
waiting for them to crawl us. Bing routes incoming pings to Yandex, Naver,
Seznam and a few others, so a single POST covers most of the non-Google search
market.

Design notes:

  - **Fail-soft, always.** A 4xx/5xx response, timeout, or network blip must
    NEVER prevent an article from publishing. We log a structured warning and
    persist a row in ``ai_logs`` (so /admin/costs surfaces failures without
    hiding them).
  - **Disabled silently** when ``settings.indexnow_api_key`` is None — useful
    for dev/staging where we don't want to ping production search engines.
  - **One batch call per publish** containing every locale URL (ar-MA + fr).
    IndexNow allows up to 10000 URLs/call, so we're far from any limit.
  - **No retries**. IndexNow is best-effort by design; if Bing missed the
    notification, the regular crawl will catch the new article within a day
    or two via the sitemap.
  - **Key location**: per protocol convention, the key file is hosted at
    ``{public_site_url}/{key}.txt``. We pass that URL explicitly in the
    request body so receivers don't have to guess.
"""

from __future__ import annotations

import time
from decimal import Decimal

import httpx

from app.core.logging import get_logger
from app.services.ai.ai_logging import persist_ai_log

logger = get_logger("services.external.indexnow")

# IndexNow generic endpoint — fans out to every search engine that participates
# in the protocol (Bing, Yandex, Naver, Seznam, IndexNow.io discovery, …).
# Using bing.com/indexnow would also work, but routes only to Bing.
INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"

# Bound the request so we can't block a publish indefinitely if IndexNow is
# slow. 10 s is generous — a normal call returns in <500 ms.
HTTP_TIMEOUT_SECONDS = 10.0


def _host_of(url: str) -> str:
    """Strip the scheme and any path to extract the bare hostname."""
    if "://" in url:
        url = url.split("://", 1)[1]
    return url.split("/", 1)[0]


async def notify(
    *,
    urls: list[str],
    api_key: str | None,
    site_url: str,
) -> bool:
    """Notify IndexNow about ``urls``. Returns True on 200/202, False otherwise.

    Never raises — caller can fire-and-forget.

    ``api_key`` is the IndexNow key (also published at ``site_url/<key>.txt``).
    When None, the function is a no-op and returns False — useful for dev.
    """
    if not api_key:
        logger.debug("indexnow.skipped", reason="no_api_key", url_count=len(urls))
        return False

    if not urls:
        logger.debug("indexnow.skipped", reason="empty_url_list")
        return False

    host = _host_of(site_url)
    payload = {
        "host": host,
        "key": api_key,
        "keyLocation": f"{site_url.rstrip('/')}/{api_key}.txt",
        "urlList": urls,
    }

    start = time.perf_counter()
    success = False
    status_code: int | None = None
    error: str | None = None

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                INDEXNOW_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        status_code = response.status_code
        # IndexNow returns 200 or 202 (queued) for successful submissions.
        # 422 means the API key/key file failed verification — worth surfacing.
        success = status_code in (200, 202)
        if not success:
            error = f"http_{status_code}"
            logger.warning(
                "indexnow.non_2xx",
                status_code=status_code,
                response_preview=response.text[:200],
                host=host,
                url_count=len(urls),
            )
    except (httpx.HTTPError, OSError) as exc:
        error = f"{exc.__class__.__name__}: {exc}"
        logger.warning(
            "indexnow.failed_soft",
            error=str(exc),
            error_type=exc.__class__.__name__,
            host=host,
            url_count=len(urls),
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    # Log to ai_logs so the cost dashboard sees IndexNow activity (it's free,
    # but we still want a count of pings + failure visibility).
    await persist_ai_log(
        provider="indexnow",
        model="api",
        success=success,
        cost_usd=Decimal("0"),
        duration_ms=duration_ms,
        error=error,
    )

    if success:
        logger.info(
            "indexnow.notified",
            host=host,
            url_count=len(urls),
            duration_ms=duration_ms,
            status_code=status_code,
        )
    return success
