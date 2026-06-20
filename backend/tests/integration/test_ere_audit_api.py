"""Integration tests for ERE Human Audit V1.

Real Postgres. The single write target is ``editorial_audits``; these tests pin
that raw_articles is never modified, that the queue excludes audited rows and is
borderline-first, that POST upserts + snapshots, and that metrics are correct.
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

_PUB = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)

# (label, score, decision, strategic_label, actors) — distances from 55:
#   A=15, B=3, C=5, D=15 → borderline order: B, C, A, D (A/D tie broken by id asc)
_ROWS = [
    ("A", 70, "selected", "frontier_move", 8),
    ("B", 58, "selected", "none", 5),
    ("C", 50, "deferred", "market_structure", 8),
    ("D", 40, "deferred", "none", 0),
]


def _breakdown(label: str, actors: int) -> dict[str, object]:
    return {
        "importance_detail": {"strategic_label": label, "actors": actors, "model": "v1_1"},
        "computed_at": "2026-06-20T00:08:00+00:00",
    }


@pytest_asyncio.fixture
async def audit_data() -> AsyncIterator[dict[str, int]]:
    token = uuid.uuid4().hex[:8]
    name = f"_test_audit_{token}"
    ids: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        src = Source(name=name, rss_url=f"http://t/{token}.xml")
        session.add(src)
        await session.commit()
        await session.refresh(src)
        sid = int(src.id)  # type: ignore[arg-type]
        for i, (label, score, decision, slabel, actors) in enumerate(_ROWS):
            raw = RawArticle(
                source_id=sid,
                external_url=f"http://t/{token}/{i}",
                url_hash=f"{token}{i}".ljust(64, "0"),
                original_title=f"Audit {label}",
                original_content="ai content",
                processing_status="translated",
                published_at=_PUB,
                fetched_at=_PUB,
                editorial_score=score,
                editorial_decision=decision,
                score_breakdown=_breakdown(slabel, actors),
            )
            session.add(raw)
            await session.commit()
            await session.refresh(raw)
            ids[label] = int(raw.id)  # type: ignore[arg-type]
        # Article "A" has a localized row (preview data); the others do not.
        session.add(
            Article(
                raw_article_id=ids["A"],
                slug=f"audit-{token}-a",
                title_darija="عنوان بالدارجة",
                excerpt_darija="ملخص بالدارجة",
                content_darija="المحتوى بالدارجة " * 30,
                title_fr="Titre FR",
                content_fr="Contenu en français. " * 30,
                hero_image_url="https://img.example/hero.jpg",
                is_published=True,
            )
        )
        await session.commit()

    yield ids

    async with AsyncSessionLocal() as session:
        # articles FK is ON DELETE RESTRICT → delete articles first, then raws.
        await session.execute(
            delete(Article).where(col(Article.raw_article_id).in_(list(ids.values())))
        )
        await session.execute(delete(RawArticle).where(col(RawArticle.source_id) == sid))
        await session.execute(delete(Source).where(col(Source.id) == sid))
        await session.commit()


async def _verdict(
    client: AsyncClient,
    headers: dict[str, str],
    article_id: int,
    verdict: str,
    notes: str | None = None,
) -> dict[str, object]:
    resp = await client.post(
        "/api/v1/admin/ere/audit/verdict",
        headers=headers,
        json={"article_id": article_id, "human_verdict": verdict, "notes": notes},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- auth ---


@pytest.mark.asyncio
async def test_audit_endpoints_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/ere/audit/queue")).status_code == 401
    assert (await client.get("/api/v1/admin/ere/audit/metrics")).status_code == 401
    r = await client.post(
        "/api/v1/admin/ere/audit/verdict", json={"article_id": 1, "human_verdict": "KEEP"}
    )
    assert r.status_code == 401


# --- queue ---


@pytest.mark.asyncio
async def test_queue_borderline_first_and_excludes_audited(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    q = (await client.get("/api/v1/admin/ere/audit/queue", headers=auth_headers)).json()["data"]
    ours = [x for x in q if x["id"] in audit_data.values()]
    # borderline-first: B(58,d3), C(50,d5) are the two closest to 55.
    assert [ours[0]["score"], ours[1]["score"]] == [58, 50]
    assert "importance_detail" in ours[0]["breakdown"]

    # Audit B → it leaves the queue.
    await _verdict(client, auth_headers, audit_data["B"], "KEEP")
    q2 = (await client.get("/api/v1/admin/ere/audit/queue", headers=auth_headers)).json()["data"]
    assert audit_data["B"] not in {x["id"] for x in q2}


@pytest.mark.asyncio
async def test_queue_includes_preview_fields(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    q = (await client.get("/api/v1/admin/ere/audit/queue", headers=auth_headers)).json()["data"]
    by_id = {x["id"]: x for x in q}
    # A has a localized article → preview populated.
    a = by_id[audit_data["A"]]
    assert a["title_darija"] and a["content_darija"]
    assert a["title_fr"] and a["content_fr"]
    assert a["image_url"] == "https://img.example/hero.jpg"
    assert a["is_published"] is True
    assert a["article_id"] is not None
    assert a["original_url"]  # external_url
    # B has no localized article → preview fields null (graceful).
    b = by_id[audit_data["B"]]
    assert b["title_darija"] is None
    assert b["article_id"] is None


# --- POST create / snapshot / no raw mutation ---


@pytest.mark.asyncio
async def test_post_creates_and_snapshots_without_touching_raw(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    rec = await _verdict(client, auth_headers, audit_data["A"], "KEEP", notes="good")
    assert rec["human_verdict"] == "KEEP"
    assert rec["ere_score"] == 70  # snapshot
    assert rec["ere_decision"] == "selected"  # snapshot
    assert rec["reviewer"] == "test-admin@darija-ai.ma"  # from JWT
    assert rec["notes"] == "good"

    # raw_articles untouched.
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                text(
                    "SELECT editorial_score, editorial_decision, processing_status "
                    "FROM raw_articles WHERE id = :id"
                ),
                {"id": audit_data["A"]},
            )
        ).one()
    assert row.editorial_score == 70
    assert row.editorial_decision == "selected"
    assert row.processing_status == "translated"


@pytest.mark.asyncio
async def test_post_upsert_overwrites_keeps_single_row(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    first = await _verdict(client, auth_headers, audit_data["A"], "KEEP")
    second = await _verdict(client, auth_headers, audit_data["A"], "REJECT", notes="changed")
    assert first["id"] == second["id"]  # same row (upsert)
    assert second["human_verdict"] == "REJECT"
    assert second["notes"] == "changed"

    async with AsyncSessionLocal() as session:
        n = (
            await session.execute(
                text("SELECT count(*)::int AS n FROM editorial_audits WHERE article_id = :id"),
                {"id": audit_data["A"]},
            )
        ).one()
    assert n.n == 1


@pytest.mark.asyncio
async def test_post_unknown_article_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/admin/ere/audit/verdict",
        headers=auth_headers,
        json={"article_id": 999_999_999, "human_verdict": "KEEP"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_invalid_verdict_422(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/admin/ere/audit/verdict",
        headers=auth_headers,
        json={"article_id": audit_data["A"], "human_verdict": "MAYBE"},
    )
    assert r.status_code == 422


# --- metrics ---


@pytest.mark.asyncio
async def test_metrics_confusion_and_rates(
    client: AsyncClient, audit_data: dict[str, int], auth_headers: dict[str, str]
) -> None:
    # A selected+KEEP=TP · B selected+REJECT=FP · C deferred+KEEP=FN · D deferred+REJECT=TN
    await _verdict(client, auth_headers, audit_data["A"], "KEEP")
    await _verdict(client, auth_headers, audit_data["B"], "REJECT")
    await _verdict(client, auth_headers, audit_data["C"], "KEEP")
    await _verdict(client, auth_headers, audit_data["D"], "REJECT")

    m = (await client.get("/api/v1/admin/ere/audit/metrics", headers=auth_headers)).json()
    assert m["audited"] == 4
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == 0.5
    assert m["recall"] == 0.5
