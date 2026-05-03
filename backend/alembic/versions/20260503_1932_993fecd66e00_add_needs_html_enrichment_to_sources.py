"""add needs_html_enrichment to sources

Revision ID: 993fecd66e00
Revises: a40f4ff284f0
Create Date: 2026-05-03 19:32:13.857309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '993fecd66e00'
down_revision: Union[str, Sequence[str], None] = 'a40f4ff284f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'sources',
        sa.Column(
            'needs_html_enrichment',
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sources', 'needs_html_enrichment')
