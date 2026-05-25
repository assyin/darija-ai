from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, String, func
from sqlmodel import Field, SQLModel


class SiteSetting(SQLModel, table=True):
    """Key-value store for editable business configuration.

    All values stored as ``str``. Frontend casts based on ``value_type``.
    Fields with ``is_public=True`` are exposed via ``/api/v1/settings/public``.
    Sensitive/admin-only fields (e.g. CTA template internals) stay private.
    """

    __tablename__ = "site_settings"
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'url', 'phone', 'email', 'html', 'markdown', 'boolean', 'integer')",  # noqa: E501
            name="check_value_type",
        ),
        CheckConstraint(
            "category IN ('contact', 'branding', 'cta', 'social', 'seo', 'admin')",
            name="check_category",
        ),
    )

    key: str = Field(
        sa_column=Column(String(100), primary_key=True),
    )
    value: str = Field(
        default="",
        sa_column=Column(String(2000), nullable=False, server_default=""),
    )
    value_type: str = Field(default="string", max_length=20)
    category: str = Field(default="branding", max_length=20)
    label_fr: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_public: bool = Field(default=False, nullable=False)
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )
