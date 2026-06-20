"""Read-only ERE observability dashboard endpoints (admin only).

All GET. No mutation, no ranking change, no publication/enforce action, no
SpendGuard control. Mirrors the ai_logs admin module conventions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.core.security import require_admin
from app.schemas.auth import AdminUser
from app.schemas.ere_dashboard import (
    EreArticleList,
    EreCategoryList,
    EreDistribution,
    EreOverview,
    EreSourceList,
    EreSpendGuard,
)
from app.services.editorial import dashboard_service as svc

router = APIRouter(prefix="/admin/ere", tags=["admin", "ere"])


@router.get("/overview", response_model=EreOverview)
async def get_overview(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> EreOverview:
    return await svc.ere_overview(session)


@router.get("/distribution", response_model=EreDistribution)
async def get_distribution(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> EreDistribution:
    return await svc.ere_distribution(session)


@router.get("/articles", response_model=EreArticleList)
async def get_articles(
    decision: str | None = Query(default=None, pattern="^(selected|deferred)$"),
    source: str | None = None,
    category: str | None = None,
    score_min: int = Query(default=0, ge=0, le=100),
    score_max: int = Query(default=100, ge=0, le=100),
    date_from: str | None = None,
    date_to: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> EreArticleList:
    items, next_cursor = await svc.ere_articles(
        session,
        decision=decision,
        source=source,
        category=category,
        score_min=score_min,
        score_max=score_max,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )
    return EreArticleList(data=items, next_cursor=next_cursor)


@router.get("/categories", response_model=EreCategoryList)
async def get_categories(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> EreCategoryList:
    return EreCategoryList(data=await svc.ere_categories(session))


@router.get("/sources", response_model=EreSourceList)
async def get_sources(
    session: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
) -> EreSourceList:
    return EreSourceList(data=await svc.ere_sources(session))


@router.get("/spendguard", response_model=EreSpendGuard)
async def get_spendguard(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: AdminUser = Depends(require_admin),
) -> EreSpendGuard:
    redis = get_redis_client()
    try:
        return await svc.ere_spendguard(
            session,
            redis=redis,
            daily_cap=settings.ai_spend_daily_hard_cap_usd,
            monthly_cap=settings.ai_monthly_cap_usd,
        )
    finally:
        await redis.aclose()
