"""timescale resampling: hypertable + continuous aggregates (TSDB 2.x-safe)

Revision ID: 0002_resampling_timescale
Revises: 0001_init
Create Date: 2025-09-22 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_resampling_timescale"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    # 0) Włącz rozszerzenie TimescaleDB (idempotentnie)
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    # 1) Kolumna ts_time (timestamptz) generowana z ts (ms) – potrzebna do hypertable i time_bucket
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='ohlcv' AND column_name='ts_time'
          ) THEN
            ALTER TABLE ohlcv
              ADD COLUMN ts_time timestamptz
              GENERATED ALWAYS AS (to_timestamp(ts/1000.0)) STORED;
          END IF;
        END$$;
        """
    )

    # 2) Utwórz hypertable na ohlcv(ts_time), jeśli jeszcze nie istnieje
    #    Wykrywamy przez timescaledb_information.hypertables (TSDB 2.x)
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'public' AND hypertable_name = 'ohlcv'
          ) THEN
            PERFORM create_hypertable('ohlcv', 'ts_time', if_not_exists => TRUE);
          END IF;
        END$$;
        """
    )

    # 3) Continuous Aggregates: 15m / 1h / 4h / 1d z bazowej tf='1m'
    #    Uwaga: otwarcie/zamknięcie liczone przez array_agg(... ORDER BY ...) – kompatybilne z czystym Postgres/TSDB.
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_15m
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '15m'::varchar AS tf,
          time_bucket('15 minutes', ts_time) AS ts_time,
          (array_agg(o ORDER BY ts_time ASC))[1]         AS o,
          max(h)                                         AS h,
          min(l)                                         AS l,
          (array_agg(c ORDER BY ts_time DESC))[1]        AS c,
          sum(v)                                         AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket('15 minutes', ts_time)
        WITH NO DATA;

        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '1h'::varchar AS tf,
          time_bucket('1 hour', ts_time) AS ts_time,
          (array_agg(o ORDER BY ts_time ASC))[1]         AS o,
          max(h)                                         AS h,
          min(l)                                         AS l,
          (array_agg(c ORDER BY ts_time DESC))[1]        AS c,
          sum(v)                                         AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket('1 hour', ts_time)
        WITH NO DATA;

        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_4h
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '4h'::varchar AS tf,
          time_bucket('4 hours', ts_time) AS ts_time,
          (array_agg(o ORDER BY ts_time ASC))[1]         AS o,
          max(h)                                         AS h,
          min(l)                                         AS l,
          (array_agg(c ORDER BY ts_time DESC))[1]        AS c,
          sum(v)                                         AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket('4 hours', ts_time)
        WITH NO DATA;

        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1d
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '1d'::varchar AS tf,
          time_bucket('1 day', ts_time) AS ts_time,
          (array_agg(o ORDER BY ts_time ASC))[1]         AS o,
          max(h)                                         AS h,
          min(l)                                         AS l,
          (array_agg(c ORDER BY ts_time DESC))[1]        AS c,
          sum(v)                                         AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket('1 day', ts_time)
        WITH NO DATA;
        """
    )

    # 4) Indeksy dla widoków (symbol + ts_time)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_15m_pk ON ohlcv_15m (symbol, ts_time);
        CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_1h_pk  ON ohlcv_1h  (symbol, ts_time);
        CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_4h_pk  ON ohlcv_4h  (symbol, ts_time);
        CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_1d_pk  ON ohlcv_1d  (symbol, ts_time);
        """
    )

    # 5) Polityki automatycznych odświeżeń
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('ohlcv_15m',
            start_offset => INTERVAL '30 days',
            end_offset   => INTERVAL '1 minute',
            schedule_interval => INTERVAL '5 minutes');

        SELECT add_continuous_aggregate_policy('ohlcv_1h',
            start_offset => INTERVAL '90 days',
            end_offset   => INTERVAL '5 minutes',
            schedule_interval => INTERVAL '10 minutes');

        SELECT add_continuous_aggregate_policy('ohlcv_4h',
            start_offset => INTERVAL '180 days',
            end_offset   => INTERVAL '10 minutes',
            schedule_interval => INTERVAL '20 minutes');

        SELECT add_continuous_aggregate_policy('ohlcv_1d',
            start_offset => INTERVAL '4 years',
            end_offset   => INTERVAL '30 minutes',
            schedule_interval => INTERVAL '60 minutes');
        """
    )

    # 6) Pierwszy refresh (bulk)
    op.execute(
        """
        CALL refresh_continuous_aggregate('ohlcv_15m', NULL, now());
        CALL refresh_continuous_aggregate('ohlcv_1h',  NULL, now());
        CALL refresh_continuous_aggregate('ohlcv_4h',  NULL, now());
        CALL refresh_continuous_aggregate('ohlcv_1d',  NULL, now());
        """
    )


def downgrade():
    # Usuń polityki i widoki
    op.execute(
        """
        SELECT remove_continuous_aggregate_policy('ohlcv_15m');
        SELECT remove_continuous_aggregate_policy('ohlcv_1h');
        SELECT remove_continuous_aggregate_policy('ohlcv_4h');
        SELECT remove_continuous_aggregate_policy('ohlcv_1d');

        DROP MATERIALIZED VIEW IF EXISTS ohlcv_15m;
        DROP MATERIALIZED VIEW IF EXISTS ohlcv_1h;
        DROP MATERIALIZED VIEW IF EXISTS ohlcv_4h;
        DROP MATERIALIZED VIEW IF EXISTS ohlcv_1d;
        """
    )
    # (Opcjonalnie) pozostawiamy ts_time i hypertable — są przydatne dalej
