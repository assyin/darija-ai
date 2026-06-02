"""add french columns to articles

Revision ID: 7f3a9c2e1b8d
Revises: d49d139aee40
Create Date: 2026-06-02 15:05:00.000000

Adds the French translation columns: title_fr / excerpt_fr / content_fr /
meta_title_fr / meta_description_fr. All nullable so existing rows stay
valid; the admin UI fills them on demand via the French tab.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3a9c2e1b8d"
down_revision: str | Sequence[str] | None = "d49d139aee40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("articles", sa.Column("title_fr", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("excerpt_fr", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("content_fr", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("meta_title_fr", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("meta_description_fr", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("articles", "meta_description_fr")
    op.drop_column("articles", "meta_title_fr")
    op.drop_column("articles", "content_fr")
    op.drop_column("articles", "excerpt_fr")
    op.drop_column("articles", "title_fr")
