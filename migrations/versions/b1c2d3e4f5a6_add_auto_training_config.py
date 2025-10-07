"""add auto training config table

Revision ID: b1c2d3e4f5a6
Revises: a3b4c5d6e7f8
Create Date: 2025-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create auto_training_config table
    # Note: TimeFrame enum already exists, use create_type=False
    op.create_table(
        'auto_training_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True, index=True),
        sa.Column('symbols', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('timeframe', sa.Enum('M1', 'M5', 'M15', 'H1', 'H4', 'D1', name='timeframe', create_type=False), nullable=False),
        sa.Column('quick_mode', sa.Boolean(), nullable=True),
        sa.Column('current_generation', sa.Integer(), nullable=True),
        sa.Column('best_score', sa.Float(), nullable=True),
        sa.Column('evolution_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auto_training_config_enabled'), 'auto_training_config', ['enabled'], unique=False)
    op.create_index(op.f('ix_auto_training_config_id'), 'auto_training_config', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_auto_training_config_id'), table_name='auto_training_config')
    op.drop_index(op.f('ix_auto_training_config_enabled'), table_name='auto_training_config')
    op.drop_table('auto_training_config')
