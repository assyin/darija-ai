"""add proofread columns to articles

Revision ID: 8a4b2e9c5f17
Revises: 7f3a9c2e1b8d
Create Date: 2026-06-04 13:00:00.000000

Auto-flag mode for the AI Proofreader: each article gets two scores (Darija
body + French body) and a boolean computed at pipeline time that says "this
draft cleared the configured threshold on every populated language". The
admin UI surfaces this as a green badge so the editor can publish in one
click instead of opening the article to re-run the manual proofreader.

Per CLAUDE.md §1 the boolean does NOT auto-publish — it is a hint only.
Publication remains `POST /admin/articles/{id}/publish`.

The composite index supports the hot admin-list query that filters on
`is_published=false AND proofread_ready_to_publish=true ORDER BY created_at`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a4b2e9c5f17"
down_revision: str | Sequence[str] | None = "7f3a9c2e1b8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "articles",
        sa.Column("proofread_score_darija", sa.Integer(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("proofread_score_fr", sa.Integer(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("proofread_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column(
            "proofread_ready_to_publish",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "idx_articles_ready_to_publish",
        "articles",
        ["proofread_ready_to_publish", "is_published", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_articles_ready_to_publish", table_name="articles")
    op.drop_column("articles", "proofread_ready_to_publish")
    op.drop_column("articles", "proofread_at")
    op.drop_column("articles", "proofread_score_fr")
    op.drop_column("articles", "proofread_score_darija")
