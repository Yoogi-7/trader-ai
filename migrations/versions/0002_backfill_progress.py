"""add backfill_progress table

Revision ID: 0002_backfill_progress
Revises: 0001_init
Create Date: 2025-09-22 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_backfill_progress"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backfill_progress",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("tf", sa.String(length=8), nullable=False),
        sa.Column("last_ts", sa.TIMESTAMP(timezone=False), nullable=True),
        sa.PrimaryKeyConstraint("symbol", "tf", name="pk_backfill_symbol_tf"),
    )


def downgrade():
    op.drop_table("backfill_progress")
