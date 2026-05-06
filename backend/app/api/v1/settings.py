from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import NotFoundError
from app.models.site_setting import SiteSetting
from app.schemas.site_setting import (
    BulkUpdateRequest,
    SiteSettingAdmin,
    SiteSettingUpdate,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public", response_model=dict[str, str])
async def get_public_settings(
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """All public settings as a key→value dict.

    The frontend fetches this once per page load (cached client-side).
    Public — no auth required.
    """
    result = await session.execute(
        select(SiteSetting).where(SiteSetting.is_public.is_(True))
    )
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}


# Admin routes — auth wiring deferred to Sprint 3.
admin_router = APIRouter(prefix="/admin/settings", tags=["admin", "settings"])


@admin_router.get("", response_model=list[SiteSettingAdmin])
async def list_all_settings(
    session: AsyncSession = Depends(get_db),
) -> list[SiteSetting]:
    """All settings (public + private) with metadata. Admin only."""
    result = await session.execute(
        select(SiteSetting).order_by(SiteSetting.category, SiteSetting.key)
    )
    return list(result.scalars().all())


@admin_router.get("/{key}", response_model=SiteSettingAdmin)
async def get_setting(
    key: str,
    session: AsyncSession = Depends(get_db),
) -> SiteSetting:
    setting = await session.get(SiteSetting, key)
    if setting is None:
        raise NotFoundError(
            f"Setting '{key}' not found",
            details={"key": key},
        )
    return setting


@admin_router.patch("/{key}", response_model=SiteSettingAdmin)
async def update_setting(
    key: str,
    update: SiteSettingUpdate,
    session: AsyncSession = Depends(get_db),
) -> SiteSetting:
    setting = await session.get(SiteSetting, key)
    if setting is None:
        raise NotFoundError(
            f"Setting '{key}' not found",
            details={"key": key},
        )
    setting.value = update.value
    await session.commit()
    await session.refresh(setting)
    return setting


@admin_router.post("/bulk", response_model=list[SiteSettingAdmin])
async def bulk_update_settings(
    payload: BulkUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> list[SiteSetting]:
    """Atomic multi-key update. Used by admin "Save all" button.

    Unknown keys are silently ignored — only existing settings are updated.
    """
    updated: list[SiteSetting] = []
    for item in payload.updates:
        setting = await session.get(SiteSetting, item.key)
        if setting is not None:
            setting.value = item.value
            updated.append(setting)
    await session.commit()
    for s in updated:
        await session.refresh(s)
    return updated
