from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlmodel import col

from app.core.db import AsyncSessionLocal
from app.models.article import Article
from app.models.raw_article import RawArticle
from app.models.source import Source


async def _existing_article_id() -> int | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Article.id).order_by(Article.id).limit(1))


async def test_admin_route_returns_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/articles")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_admin_list_articles_returns_existing(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        resp = await client.get("/api/v1/admin/articles", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        # Empty DB: every count bucket must be zero.
        assert body["counts"] == {"all": 0, "drafts": 0, "ready": 0, "published": 0}
        return

    resp = await client.get("/api/v1/admin/articles?is_published=false", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    ids = {item["id"] for item in items}
    assert article_id in ids
    sample = next(it for it in items if it["id"] == article_id)
    assert sample["is_published"] is False
    # Counts come back with all four buckets even when the page is filtered
    # to drafts only — that's the whole point of this PR.
    counts = body["counts"]
    assert set(counts) == {"all", "drafts", "ready", "published"}
    # And counts must not be limited to the filtered slice — the live total
    # is always >= the number of drafts shown.
    assert counts["all"] >= counts["drafts"]


async def test_admin_get_article_unknown_id_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/v1/admin/articles/99999999", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_admin_publish_then_unpublish_cycle(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        return  # nothing seeded; skip silently

    # Snapshot original state to restore at the end.
    original = (
        await client.get(f"/api/v1/admin/articles/{article_id}", headers=auth_headers)
    ).json()
    try:
        pub = await client.post(
            f"/api/v1/admin/articles/{article_id}/publish", headers=auth_headers
        )
        assert pub.status_code == 200
        assert pub.json()["is_published"] is True
        assert pub.json()["published_at"] is not None

        unpub = await client.post(
            f"/api/v1/admin/articles/{article_id}/unpublish", headers=auth_headers
        )
        assert unpub.status_code == 200
        assert unpub.json()["is_published"] is False
    finally:
        if original.get("is_published"):
            await client.post(
                f"/api/v1/admin/articles/{article_id}/publish", headers=auth_headers
            )


async def test_admin_patch_recomputes_word_count(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        return

    original = (
        await client.get(f"/api/v1/admin/articles/{article_id}", headers=auth_headers)
    ).json()
    try:
        new_content = "هاد المقال قصير. " * 60  # 120 short Arabic tokens
        resp = await client.patch(
            f"/api/v1/admin/articles/{article_id}",
            json={"content_darija": new_content},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["word_count"] is not None and body["word_count"] >= 100
        assert body["reading_time_minutes"] is not None
    finally:
        await client.patch(
            f"/api/v1/admin/articles/{article_id}",
            json={"content_darija": original["content_darija"]},
            headers=auth_headers,
        )


# --- Phase 2: search (q) / sort / ERE score column on GET /admin/articles ---

_NOW = datetime(2026, 6, 21, 0, 0, tzinfo=UTC)

# (label, editorial_score, original_title, title_darija)
_HUB_ROWS = [
    ("HI", 80, "Anthropic raises a big round", "أنثروبيك جمعات فلوس"),
    ("LO", 40, "A quiet unrelated update", "شي خبر آخر عادي"),
]


@pytest_asyncio.fixture
async def hub_data() -> AsyncIterator[dict[str, object]]:
    token = uuid.uuid4().hex[:8]
    name = f"_test_hub_{token}"
    ids: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        src = Source(name=name, rss_url=f"http://t/{token}.xml")
        session.add(src)
        await session.commit()
        await session.refresh(src)
        sid = int(src.id)  # type: ignore[arg-type]
        for i, (label, score, otitle, _da) in enumerate(_HUB_ROWS):
            raw = RawArticle(
                source_id=sid,
                external_url=f"http://t/{token}/{i}",
                url_hash=f"{token}{i}".ljust(64, "0"),
                original_title=otitle,
                original_content="ai content",
                processing_status="translated",
                published_at=_NOW,
                fetched_at=_NOW,
                editorial_score=score,
                editorial_decision="selected" if score >= 55 else "deferred",
            )
            session.add(raw)
            await session.commit()
            await session.refresh(raw)
            ids[label] = int(raw.id)  # type: ignore[arg-type]
            session.add(
                Article(
                    raw_article_id=ids[label],
                    slug=f"hub-{token}-{label.lower()}",
                    title_darija=_HUB_ROWS[i][3],
                    excerpt_darija="ملخص",
                    content_darija="المحتوى " * 20,
                    is_published=False,
                )
            )
            await session.commit()

    yield {"token": token, "source": name, "ids": ids, "sid": sid}

    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Article).where(col(Article.raw_article_id).in_(list(ids.values())))
        )
        await session.execute(delete(RawArticle).where(col(RawArticle.source_id) == sid))
        await session.execute(delete(Source).where(col(Source.id) == sid))
        await session.commit()


async def test_admin_list_includes_editorial_score(
    client: AsyncClient, hub_data: dict[str, object], auth_headers: dict[str, str]
) -> None:
    token = hub_data["token"]
    resp = await client.get(
        f"/api/v1/admin/articles?q={token}&limit=200", headers=auth_headers
    )
    assert resp.status_code == 200
    by_slug = {it["slug"]: it for it in resp.json()["items"]}
    assert by_slug[f"hub-{token}-hi"]["editorial_score"] == 80
    assert by_slug[f"hub-{token}-lo"]["editorial_score"] == 40


async def test_admin_list_search_by_title(
    client: AsyncClient, hub_data: dict[str, object], auth_headers: dict[str, str]
) -> None:
    # Search by original_title — only the HI row matches "Anthropic".
    resp = await client.get(
        "/api/v1/admin/articles?q=Anthropic&limit=200", headers=auth_headers
    )
    assert resp.status_code == 200
    slugs = {it["slug"] for it in resp.json()["items"]}
    token = hub_data["token"]
    assert f"hub-{token}-hi" in slugs
    assert f"hub-{token}-lo" not in slugs


async def test_admin_list_search_by_source_name(
    client: AsyncClient, hub_data: dict[str, object], auth_headers: dict[str, str]
) -> None:
    # Searching the (unique) source name returns BOTH seeded articles.
    resp = await client.get(
        f"/api/v1/admin/articles?q={hub_data['source']}&limit=200", headers=auth_headers
    )
    assert resp.status_code == 200
    token = hub_data["token"]
    slugs = {it["slug"] for it in resp.json()["items"]}
    assert {f"hub-{token}-hi", f"hub-{token}-lo"} <= slugs


async def test_admin_list_sort_by_score_desc(
    client: AsyncClient, hub_data: dict[str, object], auth_headers: dict[str, str]
) -> None:
    token = hub_data["token"]
    resp = await client.get(
        f"/api/v1/admin/articles?q={token}&sort=score&limit=200", headers=auth_headers
    )
    assert resp.status_code == 200
    ours = [it for it in resp.json()["items"] if str(token) in it["slug"]]
    # HI (80) must come before LO (40).
    assert [it["editorial_score"] for it in ours] == [80, 40]
