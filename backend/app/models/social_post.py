from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SocialPost(SQLModel, table=True):
    __tablename__ = "social_posts"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('linkedin','twitter','facebook','instagram')",
            name="ck_social_posts_platform",
        ),
        CheckConstraint(
            "status IN ('pending','posted','failed')",
            name="ck_social_posts_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    article_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    platform: str = Field(sa_column=Column(String(20), nullable=False, index=True))
    post_text: str = Field(sa_column=Column(Text, nullable=False))
    external_post_id: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: str = Field(
        default="pending",
        sa_column=Column(
            String(20),
            nullable=False,
            index=True,
            server_default="pending",
        ),
    )
    posted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
