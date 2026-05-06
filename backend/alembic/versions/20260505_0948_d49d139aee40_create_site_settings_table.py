"""create site_settings table

Revision ID: d49d139aee40
Revises: 993fecd66e00
Create Date: 2026-05-05 09:48:20.741143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd49d139aee40'
down_revision: Union[str, Sequence[str], None] = '993fecd66e00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'site_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=2000), server_default='', nullable=False),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('label_fr', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('contact', 'branding', 'cta', 'social', 'seo', 'admin')",
            name='check_category',
        ),
        sa.CheckConstraint(
            "value_type IN ('string', 'url', 'phone', 'email', 'html', 'markdown', 'boolean', 'integer')",
            name='check_value_type',
        ),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('site_settings')
