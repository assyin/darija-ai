from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EditorialAudit(SQLModel, table=True):
    """A human KEEP/REJECT verdict on a shadow-scored article (ERE Human Audit V1).

    Decoupled from the ERE pipeline: ``ere_score`` / ``ere_decision`` are a
    snapshot taken at audit time and are NEVER written back to ``raw_articles``.
    One verdict per article (``UNIQUE(article_id)``), upserted on re-audit.
    """

    __tablename__ = "editorial_audits"
    __table_args__ = (
        CheckConstraint(
            "human_verdict IN ('KEEP', 'REJECT')",
            name="ck_editorial_audits_verdict",
        ),
        UniqueConstraint("article_id", name="uq_editorial_audits_article"),
        Index("idx_editorial_audits_verdict", "human_verdict"),
        Index("idx_editorial_audits_decision", "ere_decision"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    article_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("raw_articles.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    ere_score: int = Field(sa_column=Column(SmallInteger, nullable=False))
    ere_decision: str = Field(sa_column=Column(String(12), nullable=False))
    human_verdict: str = Field(sa_column=Column(String(8), nullable=False))
    reviewer: str = Field(sa_column=Column(String(255), nullable=False))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
