"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension (for time-series optimization)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # Create all tables (SQLAlchemy will handle this via Base.metadata.create_all)
    # But we'll add TimescaleDB hypertable conversion for OHLCV

    # Convert ohlcv to hypertable
    op.execute("""
        SELECT create_hypertable('ohlcv', 'timestamp',
                                 chunk_time_interval => INTERVAL '7 days',
                                 if_not_exists => TRUE);
    """)

    # Add compression policy (optional, for older data)
    op.execute("""
        ALTER TABLE ohlcv SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol,timeframe'
        );
    """)

    op.execute("""
        SELECT add_compression_policy('ohlcv', INTERVAL '30 days', if_not_exists => TRUE);
    """)


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")
