from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DarijaGlossary(SQLModel, table=True):
    __tablename__ = "darija_glossary"

    id: int | None = Field(default=None, primary_key=True)
    english_term: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    darija_translation: str = Field(sa_column=Column(String(255), nullable=False))
    context: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    category: str | None = Field(
        default=None, sa_column=Column(String(50), nullable=True, index=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
