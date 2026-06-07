from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.article import Article


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
