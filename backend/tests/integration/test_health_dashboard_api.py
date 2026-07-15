"""Integration tests for the read-only Production Health dashboard API.

Real Postgres. Seeds a uniquely-sourced batch of raw articles in every
processing status plus a draft and a published article, hits the single admin
endpoint, and asserts the aggregate shape, the queue counters, and that the
endpoint performs NO writes. Assertions use ``>=`` on counters so the test is
robust to other rows already in the database.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, text
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.models.source import Source

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

# One raw article per queue status we surface (pending/processing/failed/rejected).
_RAW_STATUSES = ["pending", "processing", "failed", "rejected"]


@pytest_asyncio.fixture
async def health_data() -> AsyncIterator[str]:
    token = uuid.uuid4().hex[:8]
    name = f"_test_health_{token}"
    async with AsyncSessionLocal() as session:
        src = Source(name=name, rss_url=f"http://t/{token}.xml")
        session.add(src)
        await session.commit()
        await session.refresh(src)
        sid = int(src.id)  # type: ignore[arg-type]

        raw_ids: list[int] = []
        for i, status in enumerate(_RAW_STATUSES):
            raw = RawArticle(
                source_id=sid,
                external_url=f"http://t/{token}/{i}",
                url_hash=f"{token}{i}".ljust(64, "0"),
                original_title=f"health test {i}",
                original_content="ai content",
                processing_status=status,
                fetched_at=_NOW,
            )
            session.add(raw)
            await session.commit()
            await session.refresh(raw)
            raw_ids.append(int(raw.id))  # type: ignore[arg-type]

        # One draft + one published article linked to the first two raw rows.
        session.add(
            Article(
                raw_article_id=raw_ids[0],
                slug=f"health-draft-{token}",
                title_darija="مسودة",
                excerpt_darija="x",
                content_darija="y",
                is_published=False,
            )
        )
        session.add(
            Article(
                raw_article_id=raw_ids[1],
                slug=f"health-pub-{token}",
                title_darija="منشور",
                excerpt_darija="x",
                content_darija="y",
                is_published=True,
                published_at=_NOW,
            )
        )
        await session.commit()

    yield name

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Article).where(col(Article.raw_article_id).in_(raw_ids)))
        await session.execute(delete(RawArticle).where(col(RawArticle.source_id) == sid))
        await session.execute(delete(Source).where(col(Source.id) == sid))
        await session.commit()


# --- auth ---


@pytest.mark.asyncio
async def test_health_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/health")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# --- shape ---


@pytest.mark.asyncio
async def test_health_shape(
    client: AsyncClient, health_data: str, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/health", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    # Top-level blocks present.
    assert set(body) >= {"generated_at", "pipeline", "activity", "spendguard", "queues"}

    # Section 1 — 7 pipeline stages incl. SpendGuard, each with a valid state.
    keys = [s["key"] for s in body["pipeline"]]
    assert keys == [
        "rss_fetch",
        "ai_processing",
        "translation",
        "editorial_ranking",
        "human_audit",
        "publication",
        "spendguard",
    ]
    valid = {"healthy", "warning", "critical"}
    assert all(s["state"] in valid for s in body["pipeline"])

    # Section 2 — 6 activity items (no SpendGuard row), each with a valid state.
    assert [a["key"] for a in body["activity"]] == [
        "rss_fetch",
        "ai_processing",
        "translation",
        "editorial_ranking",
        "human_audit",
        "publication",
    ]
    assert all(a["state"] in valid for a in body["activity"])

    # Section 3 — SpendGuard read-only block reused from the ERE dashboard schema.
    sg = body["spendguard"]
    assert set(sg) >= {
        "today_spend_usd",
        "month_spend_usd",
        "daily_cap_usd",
        "monthly_cap_usd",
        "budget_pause",
        "emergency_pause",
    }

    # Section 4 — queue counters include our seeded rows.
    q = body["queues"]
    assert set(q) == {"pending", "processing", "failed", "rejected", "draft", "published"}
    assert q["pending"] >= 1
    assert q["processing"] >= 1
    assert q["failed"] >= 1
    assert q["rejected"] >= 1
    assert q["draft"] >= 1
    assert q["published"] >= 1


# --- read-only guarantee ---


@pytest.mark.asyncio
async def test_health_is_read_only(
    client: AsyncClient, health_data: str, auth_headers: dict[str, str]
) -> None:
    """Calling the endpoint must not change any row counts."""
    async with AsyncSessionLocal() as session:
        before_raw = (await session.execute(text("SELECT count(*) FROM raw_articles"))).scalar()
        before_art = (await session.execute(text("SELECT count(*) FROM articles"))).scalar()

    resp = await client.get("/api/v1/admin/health", headers=auth_headers)
    assert resp.status_code == 200

    async with AsyncSessionLocal() as session:
        after_raw = (await session.execute(text("SELECT count(*) FROM raw_articles"))).scalar()
        after_art = (await session.execute(text("SELECT count(*) FROM articles"))).scalar()

    assert before_raw == after_raw
    assert before_art == after_art
