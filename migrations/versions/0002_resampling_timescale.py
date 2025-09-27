"""timescale resampling: hypertable + continuous aggregates (TSDB 2.x-safe, integer time)

Revision ID: 0002_resampling_timescale
Revises: 0001_init
Create Date: 2025-09-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_resampling_timescale"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Opcjonalna kolumna TIMESTAMPTZ (pomocnicza do zapytań; CAGG używa integer 'ts')
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='ohlcv' AND column_name='ts_time'
            ) THEN
                ALTER TABLE ohlcv
                ADD COLUMN ts_time TIMESTAMPTZ
                GENERATED ALWAYS AS (to_timestamp(ts/1000.0)) STORED;
            END IF;
        END $$;
    """)

    # 2) Funkcja "now" w milisekundach + przypięcie do hypertablicy ohlcv
    op.execute("""
        CREATE OR REPLACE FUNCTION ms_now() RETURNS BIGINT
        LANGUAGE SQL STABLE AS
        $$
            SELECT (EXTRACT(EPOCH FROM now()) * 1000)::BIGINT;
        $$;
    """)
    op.execute("SELECT set_integer_now_func('ohlcv', 'ms_now');")

    # 3) Continuous Aggregates na integerowej kolumnie 'ts'
    #    15m = 900000 ms, 1h = 3600000 ms, 4h = 14400000 ms, 1d = 86400000 ms

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_15m
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '15m'::varchar AS tf,
          time_bucket(900000::BIGINT, ts) AS ts,
          (array_agg(o ORDER BY ts ASC))[1]   AS o,
          max(h)                              AS h,
          min(l)                              AS l,
          (array_agg(c ORDER BY ts DESC))[1]  AS c,
          sum(v)                              AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket(900000::BIGINT, ts)
        WITH NO DATA;
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '1h'::varchar AS tf,
          time_bucket(3600000::BIGINT, ts) AS ts,
          (array_agg(o ORDER BY ts ASC))[1]   AS o,
          max(h)                              AS h,
          min(l)                              AS l,
          (array_agg(c ORDER BY ts DESC))[1]  AS c,
          sum(v)                              AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket(3600000::BIGINT, ts)
        WITH NO DATA;
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_4h
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '4h'::varchar AS tf,
          time_bucket(14400000::BIGINT, ts) AS ts,
          (array_agg(o ORDER BY ts ASC))[1]   AS o,
          max(h)                              AS h,
          min(l)                              AS l,
          (array_agg(c ORDER BY ts DESC))[1]  AS c,
          sum(v)                              AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket(14400000::BIGINT, ts)
        WITH NO DATA;
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1d
        WITH (timescaledb.continuous) AS
        SELECT
          symbol,
          '1d'::varchar AS tf,
          time_bucket(86400000::BIGINT, ts) AS ts,
          (array_agg(o ORDER BY ts ASC))[1]   AS o,
          max(h)                              AS h,
          min(l)                              AS l,
          (array_agg(c ORDER BY ts DESC))[1]  AS c,
          sum(v)                              AS v
        FROM ohlcv
        WHERE tf = '1m'
        GROUP BY symbol, time_bucket(86400000::BIGINT, ts)
        WITH NO DATA;
    """)

    # 4) Indeksy na CAGGach (symbol, ts)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ohlcv_15m_sym_ts ON ohlcv_15m (symbol, ts);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ohlcv_1h_sym_ts  ON ohlcv_1h  (symbol, ts);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ohlcv_4h_sym_ts  ON ohlcv_4h  (symbol, ts);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ohlcv_1d_sym_ts  ON ohlcv_1d  (symbol, ts);")

    # 5) Polityki odświeżania CAGG dla integerowego czasu:
    #    start_offset / end_offset MUSZĄ być BIGINT w jednostkach 'ts' (ms).
    #    Harmonogram (schedule_interval) może pozostać INTERVAL.
    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_15m',
            start_offset => 172800000,     -- 2 dni w ms
            end_offset   => 300000,        -- 5 min w ms
            schedule_interval => INTERVAL '5 minutes');
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_1h',
            start_offset => 1209600000,    -- 14 dni w ms
            end_offset   => 600000,        -- 10 min w ms
            schedule_interval => INTERVAL '15 minutes');
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_4h',
            start_offset => 4838400000,    -- 56 dni w ms
            end_offset   => 1200000,       -- 20 min w ms
            schedule_interval => INTERVAL '30 minutes');
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('ohlcv_1d',
            start_offset => 15552000000,   -- 180 dni w ms
            end_offset   => 1800000,       -- 30 min w ms
            schedule_interval => INTERVAL '1 hour');
    """)


def downgrade():
    # Usuń polityki (jeśli istnieją)
    for view in ("ohlcv_15m", "ohlcv_1h", "ohlcv_4h", "ohlcv_1d"):
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM timescaledb_information.continuous_aggregates
                    WHERE view_name = '{view}'
                ) THEN
                    PERFORM remove_continuous_aggregate_policy('{view}');
                END IF;
            END $$;
        """)

    # Drop CAGGs
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_1d;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_4h;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_1h;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ohlcv_15m;")

    # Reset integer now func i drop funkcji ms_now()
    op.execute("""
        DO $$
        BEGIN
            PERFORM reset_integer_now_func('ohlcv');
        EXCEPTION WHEN undefined_function THEN
            -- ignore
            NULL;
        END $$;
    """)
    op.execute("DROP FUNCTION IF EXISTS ms_now();")

    # (opcjonalnie) usuń kolumnę generowaną ts_time
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='ohlcv' AND column_name='ts_time'
            ) THEN
                ALTER TABLE ohlcv DROP COLUMN ts_time;
            END IF;
        END $$;
    """)
