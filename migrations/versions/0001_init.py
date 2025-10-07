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

    # Attempt to convert ohlcv to hypertable, but skip if schema constraints block it
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'ohlcv'
            ) THEN
                BEGIN
                    PERFORM create_hypertable(
                        'ohlcv',
                        'timestamp',
                        chunk_time_interval => INTERVAL '7 days',
                        if_not_exists => TRUE
                    );
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Skipping hypertable conversion for ohlcv: %', SQLERRM;
                        RETURN;
                END;
            END IF;

            BEGIN
                ALTER TABLE ohlcv SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'symbol,timeframe'
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Skipping compression settings for ohlcv: %', SQLERRM;
            END;

            BEGIN
                PERFORM add_compression_policy(
                    'ohlcv',
                    INTERVAL '30 days',
                    if_not_exists => TRUE
                );
            EXCEPTION
                WHEN OTHERS THEN
                    RAISE NOTICE 'Skipping compression policy for ohlcv: %', SQLERRM;
            END;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")
