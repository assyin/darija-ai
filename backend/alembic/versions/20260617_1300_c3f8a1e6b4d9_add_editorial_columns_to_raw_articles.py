"""add editorial ranking columns to raw_articles

Revision ID: c3f8a1e6b4d9
Revises: 8a4b2e9c5f17
Create Date: 2026-06-17 13:00:00.000000

Editorial Ranking Engine (ERE) MVP — Step 1: schema only, NO behaviour change.

Adds the per-article editorial-decision fields the future (not-yet-built)
deterministic ranker will write to. All additive: existing rows take
``editorial_decision = 'unranked'`` via server_default. Fully decoupled from
``processing_status`` (the localization lifecycle is untouched). Nothing reads
or writes these columns yet — they sit dormant until the ranker job and the
``EDITORIAL_RANKING_ENABLED`` flag are introduced in later steps.

The index on ``editorial_decision`` supports the future ENFORCE query in
``process_pending`` (``WHERE editorial_decision = 'selected'``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a1e6b4d9"
down_revision: str | Sequence[str] | None = "8a4b2e9c5f17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema — additive, no data backfill needed."""
    op.add_column(
        "raw_articles",
        sa.Column("editorial_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "raw_articles",
        sa.Column(
            "editorial_decision",
            sa.String(length=12),
            nullable=False,
            server_default=sa.text("'unranked'"),
        ),
    )
    op.add_column(
        "raw_articles",
        sa.Column(
            "score_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_raw_articles_editorial_decision",
        "raw_articles",
        "editorial_decision IN ('unranked', 'selected', 'deferred')",
    )
    op.create_index(
        "idx_raw_articles_editorial_decision",
        "raw_articles",
        ["editorial_decision"],
    )


def downgrade() -> None:
    """Downgrade schema — drop everything this revision added."""
    op.drop_index("idx_raw_articles_editorial_decision", table_name="raw_articles")
    op.drop_constraint("ck_raw_articles_editorial_decision", "raw_articles", type_="check")
    op.drop_column("raw_articles", "score_breakdown")
    op.drop_column("raw_articles", "editorial_decision")
    op.drop_column("raw_articles", "editorial_score")
