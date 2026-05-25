from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteSettingPublic(BaseModel):
    """Returned by ``/api/v1/settings/public`` — only public settings."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    value_type: str


class SiteSettingAdmin(BaseModel):
    """Admin views — full setting with metadata."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    value_type: str
    category: str
    label_fr: str
    description: str | None
    is_public: bool
    updated_at: datetime


class SiteSettingUpdate(BaseModel):
    """PATCH body. Only ``value`` is editable; key/type/category are immutable."""

    value: str


class BulkUpdateItem(BaseModel):
    key: str
    value: str


class BulkUpdateRequest(BaseModel):
    """Body for bulk PATCH (admin "Save all" button)."""

    updates: list[BulkUpdateItem]
