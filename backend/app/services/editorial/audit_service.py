"""ERE Human Audit V1 — read queue / metrics + the single write (upsert verdict).

The ONLY write here is into ``editorial_audits``. ``raw_articles`` (and therefore
``editorial_score`` / ``editorial_decision`` / ``processing_status``) is never
modified — the ERE score/decision are snapshotted into the audit row.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.exceptions import NotFoundError
from app.models.editorial_audit import EditorialAudit
from app.schemas.ere_audit import AuditMetrics, AuditQueueItem, AuditRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Scored, NOT-yet-audited articles, ordered borderline-first (closest to the 55
# threshold). Keyset cursor on (distance, id). Category derived inline. Preview
# data is LEFT-JOINed from the localized `articles` row (may be absent). Content
# is truncated server-side. Read-only: nothing here writes.
_QUEUE_SQL = text(
    """
    SELECT r.id::int AS id, r.original_title AS title,
           a.title_darija AS title_darija, a.title_fr AS title_fr,
           s.name AS source, r.external_url AS original_url,
           COALESCE(a.hero_image_url, r.original_image_url) AS image_url,
           COALESCE(a.excerpt_darija, r.original_excerpt) AS excerpt,
           left(a.content_darija, 1500) AS content_darija,
           left(a.content_fr, 1500) AS content_fr,
           a.is_published AS is_published,
           a.id::int AS article_id,
           r.editorial_score::int AS score, r.editorial_decision AS decision,
           CASE
             WHEN (r.score_breakdown->'importance_detail'->>'strategic_label') <> 'none'
                  THEN (r.score_breakdown->'importance_detail'->>'strategic_label')
             WHEN COALESCE((r.score_breakdown->'importance_detail'->>'actors')::int, 0) > 0
                  THEN 'actors_only'
             ELSE 'none'
           END AS category,
           r.score_breakdown AS breakdown,
           ABS(r.editorial_score - 55)::int AS dist
    FROM raw_articles r
    JOIN sources s ON s.id = r.source_id
    LEFT JOIN articles a ON a.raw_article_id = r.id AND a.deleted_at IS NULL
    LEFT JOIN editorial_audits au ON au.article_id = r.id
    WHERE r.editorial_score IS NOT NULL
      AND au.id IS NULL
      AND (
        CAST(:cur_dist AS int) IS NULL
        OR (ABS(r.editorial_score - 55), r.id) > (:cur_dist, :cur_id)
      )
    ORDER BY ABS(r.editorial_score - 55) ASC, r.id ASC
    LIMIT :limit
    """
)


def _parse_cursor(cursor: str | None) -> tuple[int, int] | None:
    if not cursor:
        return None
    try:
        d, i = cursor.split(":", 1)
        return int(d), int(i)
    except (ValueError, AttributeError):
        return None


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


async def audit_queue(
    session: AsyncSession, *, cursor: str | None = None, limit: int = 20
) -> tuple[list[AuditQueueItem], str | None]:
    cur = _parse_cursor(cursor)
    rows = (
        await session.execute(
            _QUEUE_SQL,
            {
                "cur_dist": cur[0] if cur else None,
                "cur_id": cur[1] if cur else None,
                "limit": limit,
            },
        )
    ).all()
    items = [
        AuditQueueItem(
            id=int(r.id),
            title=r.title,
            title_darija=r.title_darija,
            title_fr=r.title_fr,
            source=r.source,
            original_url=r.original_url,
            image_url=r.image_url,
            excerpt=r.excerpt,
            content_darija=r.content_darija,
            content_fr=r.content_fr,
            is_published=bool(r.is_published) if r.is_published is not None else None,
            article_id=int(r.article_id) if r.article_id is not None else None,
            score=int(r.score),
            decision=r.decision,
            category=r.category,
            breakdown=_as_dict(r.breakdown),
        )
        for r in rows
    ]
    next_cursor = (
        f"{int(rows[-1].dist)}:{int(rows[-1].id)}" if len(rows) == limit and rows else None
    )
    return items, next_cursor


async def record_verdict(
    session: AsyncSession,
    *,
    article_id: int,
    human_verdict: str,
    notes: str | None,
    reviewer: str,
) -> AuditRecord:
    """Upsert one human verdict, snapshotting the current ERE score/decision.

    Reads raw_articles ONLY to snapshot; never writes back to it.
    """
    snap = (
        await session.execute(
            text(
                "SELECT editorial_score::int AS score, editorial_decision AS decision "
                "FROM raw_articles WHERE id = :id AND editorial_score IS NOT NULL"
            ),
            {"id": article_id},
        )
    ).first()
    if snap is None:
        raise NotFoundError(f"Scored article {article_id} not found")

    ins = pg_insert(EditorialAudit).values(
        article_id=article_id,
        ere_score=int(snap.score),
        ere_decision=str(snap.decision),
        human_verdict=human_verdict,
        reviewer=reviewer,
        notes=notes,
    )
    upsert = ins.on_conflict_do_update(
        index_elements=["article_id"],
        set_={
            "human_verdict": ins.excluded.human_verdict,
            "notes": ins.excluded.notes,
            "reviewer": ins.excluded.reviewer,
            "ere_score": ins.excluded.ere_score,
            "ere_decision": ins.excluded.ere_decision,
            "updated_at": func.now(),
        },
    )
    await session.execute(upsert)
    await session.commit()
    # Read the row back (avoids a 9-column RETURNING; values are stable post-commit).
    row = (
        await session.execute(
            text(
                "SELECT id, article_id, ere_score, ere_decision, human_verdict, "
                "reviewer, notes, created_at, updated_at "
                "FROM editorial_audits WHERE article_id = :id"
            ),
            {"id": article_id},
        )
    ).one()
    return AuditRecord(
        id=int(row.id),
        article_id=int(row.article_id),
        ere_score=int(row.ere_score),
        ere_decision=str(row.ere_decision),
        human_verdict=str(row.human_verdict),
        reviewer=str(row.reviewer),
        notes=row.notes,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


_METRICS_SQL = text(
    """
    SELECT count(*)::int AS audited,
           count(*) FILTER (WHERE ere_decision='selected' AND human_verdict='KEEP')::int AS tp,
           count(*) FILTER (WHERE ere_decision='selected' AND human_verdict='REJECT')::int AS fp,
           count(*) FILTER (WHERE ere_decision='deferred' AND human_verdict='KEEP')::int AS fn,
           count(*) FILTER (WHERE ere_decision='deferred' AND human_verdict='REJECT')::int AS tn
    FROM editorial_audits
    """
)


async def audit_metrics(session: AsyncSession) -> AuditMetrics:
    row = (await session.execute(_METRICS_SQL)).one()
    tp, fp, fn, tn = int(row.tp), int(row.fp), int(row.fn), int(row.tn)
    return AuditMetrics(
        audited=int(row.audited),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=round(tp / (tp + fp), 3) if (tp + fp) else 0.0,
        recall=round(tp / (tp + fn), 3) if (tp + fn) else 0.0,
    )
