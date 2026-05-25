from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AILog(SQLModel, table=True):
    __tablename__ = "ai_logs"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    raw_article_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("raw_articles.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    provider: str = Field(sa_column=Column(String(20), nullable=False, index=True))
    model: str = Field(sa_column=Column(String(50), nullable=False))
    input_tokens: int | None = Field(default=None, nullable=True)
    output_tokens: int | None = Field(default=None, nullable=True)
    cost_usd: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(
            Numeric(10, 6),
            nullable=False,
            server_default=text("0"),
        ),
    )
    duration_ms: int | None = Field(default=None, nullable=True)
    success: bool = Field(sa_column=Column(Boolean, nullable=False, index=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
