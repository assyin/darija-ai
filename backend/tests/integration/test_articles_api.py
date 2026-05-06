from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.article import Article
from app.models.raw_article import RawArticle


async def _existing_article_id() -> int | None:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(Article.id).order_by(Article.id).limit(1))


async def test_admin_list_articles_returns_existing(client: AsyncClient) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        # No data yet — endpoint should still answer cleanly with an empty list.
        resp = await client.get("/api/v1/admin/articles")
        assert resp.status_code == 200
        assert resp.json() == []
        return

    resp = await client.get("/api/v1/admin/articles?is_published=false")
    assert resp.status_code == 200
    items = resp.json()
    ids = {item["id"] for item in items}
    assert article_id in ids
    sample = next(it for it in items if it["id"] == article_id)
    assert sample["is_published"] is False


async def test_admin_get_article_unknown_id_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/articles/99999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_admin_publish_then_unpublish_cycle(client: AsyncClient) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        return  # nothing seeded; skip silently

    # Snapshot original state to restore at the end.
    original = (await client.get(f"/api/v1/admin/articles/{article_id}")).json()
    try:
        pub = await client.post(f"/api/v1/admin/articles/{article_id}/publish")
        assert pub.status_code == 200
        assert pub.json()["is_published"] is True
        assert pub.json()["published_at"] is not None

        unpub = await client.post(f"/api/v1/admin/articles/{article_id}/unpublish")
        assert unpub.status_code == 200
        assert unpub.json()["is_published"] is False
    finally:
        # Restore: if it was originally published, re-publish; otherwise unpublish (already done).
        if original.get("is_published"):
            await client.post(f"/api/v1/admin/articles/{article_id}/publish")


async def test_admin_patch_recomputes_word_count(client: AsyncClient) -> None:
    article_id = await _existing_article_id()
    if article_id is None:
        return

    original = (await client.get(f"/api/v1/admin/articles/{article_id}")).json()
    try:
        new_content = "هاد المقال قصير. " * 60  # 120 short Arabic tokens
        resp = await client.patch(
            f"/api/v1/admin/articles/{article_id}",
            json={"content_darija": new_content},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["word_count"] is not None and body["word_count"] >= 100
        assert body["reading_time_minutes"] is not None
    finally:
        await client.patch(
            f"/api/v1/admin/articles/{article_id}",
            json={"content_darija": original["content_darija"]},
        )
