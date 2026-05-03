from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Subscriber(SQLModel, table=True):
    __tablename__ = "subscribers"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True)
    )
    is_active: bool = Field(default=True, nullable=False)
    subscribed_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    unsubscribed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
