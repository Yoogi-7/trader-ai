"""add_ai_summary_to_signals

Revision ID: 158784867c46
Revises: 0001
Create Date: 2025-10-04 18:17:57.600679

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '158784867c46'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'signals'
                  AND column_name = 'ai_summary'
            ) THEN
                ALTER TABLE signals ADD COLUMN ai_summary TEXT;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_column('signals', 'ai_summary')
