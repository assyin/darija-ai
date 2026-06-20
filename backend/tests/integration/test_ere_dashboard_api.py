"""Integration tests for the read-only ERE dashboard API.

Real Postgres. Inserts a small, uniquely-sourced batch of SHADOW-scored
raw_articles, exercises every admin endpoint, and tears the rows down. Robust to
other data by asserting on the per-source aggregate and source-filtered lists.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.models.raw_article import RawArticle
from app.models.source import Source

_PUB = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)

# (score, decision, strategic_label, actors) → derived category:
#   frontier_move(70) · actors_only(58) · market_structure(50) · none(40) · none(20)
_ROWS = [
    (70, "selected", "frontier_move", 8),
    (58, "selected", "none", 5),
    (50, "deferred", "market_structure", 8),
    (40, "deferred", "none", 0),
    (20, "deferred", "none", 0),
]


def _breakdown(score: int, label: str, actors: int) -> dict[str, object]:
    return {
        "total": score,
        "importance": 35,
        "relevance": 12,
        "mena": 0,
        "source": 15,
        "freshness": 0,
        "importance_detail": {
            "event_type": 15,
            "magnitude": 12,
            "strategic_category": 0 if label == "none" else 10,
            "strategic_label": label,
            "actors": actors,
            "combine": 12,
            "model": "v1_1",
        },
        "source_tier": "A",
        "computed_at": "2026-06-20T00:08:00+00:00",
    }


@pytest_asyncio.fixture
async def ere_data() -> AsyncIterator[str]:
    token = uuid.uuid4().hex[:8]
    name = f"_test_ere_{token}"
    async with AsyncSessionLocal() as session:
        src = Source(name=name, rss_url=f"http://t/{token}.xml")
        session.add(src)
        await session.commit()
        await session.refresh(src)
        sid = int(src.id)  # type: ignore[arg-type]
        for i, (score, decision, label, actors) in enumerate(_ROWS):
            session.add(
                RawArticle(
                    source_id=sid,
                    external_url=f"http://t/{token}/{i}",
                    url_hash=f"{token}{i}".ljust(64, "0"),
                    original_title=f"ERE test article {i} ({label})",
                    original_content="ai content",
                    processing_status="translated",
                    published_at=_PUB,
                    fetched_at=_PUB,
                    editorial_score=score,
                    editorial_decision=decision,
                    score_breakdown=_breakdown(score, label, actors),
                )
            )
        await session.commit()

    yield name

    async with AsyncSessionLocal() as session:
        await session.execute(delete(RawArticle).where(col(RawArticle.source_id) == sid))
        await session.execute(delete(Source).where(col(Source.id) == sid))
        await session.commit()


# --- auth ---


@pytest.mark.asyncio
async def test_endpoints_require_auth(client: AsyncClient) -> None:
    for path in ("overview", "distribution", "articles", "categories", "sources", "spendguard"):
        resp = await client.get(f"/api/v1/admin/ere/{path}")
        assert resp.status_code == 401, path
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# --- overview ---


@pytest.mark.asyncio
async def test_overview_aggregates(
    client: AsyncClient, ere_data: str, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/ere/overview", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "v1_1"
    assert body["total"] >= 5
    assert body["selected"] + body["deferred"] == body["total"]
    assert body["max_score"] >= 70


# --- articles filtering ---


@pytest.mark.asyncio
async def test_articles_filtering(
    client: AsyncClient, ere_data: str, auth_headers: dict[str, str]
) -> None:
    base = "/api/v1/admin/ere/articles"
    # All 5 of this source, sorted by score desc.
    r_all = await client.get(f"{base}?source={ere_data}", headers=auth_headers)
    assert r_all.status_code == 200
    rows = r_all.json()["data"]
    assert len(rows) == 5
    assert [x["score"] for x in rows] == [70, 58, 50, 40, 20]

    # decision filter
    r_sel = await client.get(f"{base}?source={ere_data}&decision=selected", headers=auth_headers)
    assert [x["score"] for x in r_sel.json()["data"]] == [70, 58]

    # borderline score window (§8)
    r_bord = await client.get(
        f"{base}?source={ere_data}&score_min=50&score_max=60", headers=auth_headers
    )
    assert [x["score"] for x in r_bord.json()["data"]] == [58, 50]

    # derived category surfaces correctly
    cats = {x["score"]: x["category"] for x in rows}
    assert cats[70] == "frontier_move"
    assert cats[58] == "actors_only"
    assert cats[40] == "none"


# --- categories ---


@pytest.mark.asyncio
async def test_categories_aggregation(
    client: AsyncClient, ere_data: str, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/ere/categories", headers=auth_headers)
    assert resp.status_code == 200
    cats = {c["category"] for c in resp.json()["data"]}
    assert {"frontier_move", "actors_only", "market_structure", "none"} <= cats


# --- sources ---


@pytest.mark.asyncio
async def test_sources_aggregation(
    client: AsyncClient, ere_data: str, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/ere/sources", headers=auth_headers)
    assert resp.status_code == 200
    mine = next(s for s in resp.json()["data"] if s["source"] == ere_data)
    assert mine["total"] == 5
    assert mine["selected"] == 2
    assert mine["deferred"] == 3
    assert abs(mine["avg_score"] - 47.6) < 0.05


# --- distribution + spendguard (read-only smoke) ---


@pytest.mark.asyncio
async def test_distribution_shape(
    client: AsyncClient, ere_data: str, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/ere/distribution", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["threshold"] == 55
    assert len(body["histogram"]) == 20
    assert {b["bucket"] for b in body["buckets"]} == {
        "0-20",
        "21-40",
        "41-54",
        "55-69",
        "70-84",
        "85-100",
    }


@pytest.mark.asyncio
async def test_spendguard_readonly_status(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/ere/spendguard", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["daily_cap_usd"]) == 2.0
    assert float(body["monthly_cap_usd"]) == 50.0
    assert "active" in body["budget_pause"]
    assert "active" in body["emergency_pause"]
