"""Admin Production Health dashboard — READ-ONLY observability API.

A single GET that returns a whole-platform health snapshot: pipeline-stage
traffic-lights, last-activity ages, the SpendGuard state, and queue counters.
It mirrors the ai_logs / ERE admin-dashboard conventions: admin-gated, session +
settings via Depends, Redis opened per request and closed in ``finally``.

No write endpoint exists here by design — this module can only observe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.core.security import require_admin
from app.schemas.auth import AdminUser
from app.schemas.health_dashboard import ProductionHealth
from app.services.monitoring import health_service as svc

router = APIRouter(prefix="/admin/health", tags=["admin", "health"])


@router.get("", response_model=ProductionHealth)
async def get_production_health(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: AdminUser = Depends(require_admin),
) -> ProductionHealth:
    """Whole-platform health snapshot (read-only)."""
    redis = get_redis_client()
    try:
        return await svc.production_health(
            session,
            redis=redis,
            daily_cap=settings.ai_spend_daily_hard_cap_usd,
            monthly_cap=settings.ai_monthly_cap_usd,
        )
    finally:
        await redis.aclose()
