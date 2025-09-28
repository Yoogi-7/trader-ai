"""add ai summary to signals

Revision ID: 0004_signal_ai_summary
Revises: 0003_user_auth
Create Date: 2025-09-28 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_signal_ai_summary'
down_revision = '0003_user_auth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('signals', sa.Column('ai_summary', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('signals', 'ai_summary')
