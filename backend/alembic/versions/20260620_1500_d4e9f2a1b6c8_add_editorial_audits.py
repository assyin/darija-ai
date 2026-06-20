"""add editorial_audits table (ERE Human Audit V1)

Revision ID: d4e9f2a1b6c8
Revises: c3f8a1e6b4d9
Create Date: 2026-06-20 15:00:00.000000

ERE Human Audit V1 — a separate, additive table recording an admin's human
verdict (KEEP / REJECT) on a shadow-scored article, to measure precision/recall.
Fully decoupled from raw_articles/ERE: it snapshots ere_score/ere_decision and
NEVER modifies them. One verdict per article (UNIQUE), upserted on re-audit.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9f2a1b6c8"
down_revision: str | Sequence[str] | None = "c3f8a1e6b4d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema — additive, new isolated table."""
    op.create_table(
        "editorial_audits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("raw_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ere_score", sa.SmallInteger(), nullable=False),
        sa.Column("ere_decision", sa.String(length=12), nullable=False),
        sa.Column("human_verdict", sa.String(length=8), nullable=False),
        sa.Column("reviewer", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "human_verdict IN ('KEEP', 'REJECT')",
            name="ck_editorial_audits_verdict",
        ),
        sa.UniqueConstraint("article_id", name="uq_editorial_audits_article"),
    )
    op.create_index("idx_editorial_audits_verdict", "editorial_audits", ["human_verdict"])
    op.create_index("idx_editorial_audits_decision", "editorial_audits", ["ere_decision"])


def downgrade() -> None:
    """Downgrade schema — drop the whole table."""
    op.drop_index("idx_editorial_audits_decision", table_name="editorial_audits")
    op.drop_index("idx_editorial_audits_verdict", table_name="editorial_audits")
    op.drop_table("editorial_audits")
