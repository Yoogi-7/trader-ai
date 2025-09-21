from alembic import op
import sqlalchemy as sa

revision = '0005_timescale_policies_cagg'
down_revision = '0004_orderbook_positions'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    # Upewnij się, że extension istnieje
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))

    # 1) Włącz kompresję na hypertable
    conn.execute(sa.text("ALTER TABLE ohlcv SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol,tf');"))
    conn.execute(sa.text("ALTER TABLE features SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol,tf,version');"))

    # 2) Polityka kompresji: starsze niż 7 dni
    conn.execute(sa.text("""
      SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);
    """))
    conn.execute(sa.text("""
      SELECT add_compression_policy('features', INTERVAL '7 days', if_not_exists => TRUE);
    """))

    # 3) Polityka retencji na surowych 1m (utrzymujemy 180 dni)
    #    UWAGA: ohlcv zawiera wszystkie TF w jednej tabeli — retencję stosujemy po czasie.
    conn.execute(sa.text("""
      SELECT add_retention_policy('ohlcv', INTERVAL '180 days', if_not_exists => TRUE);
    """))

    # 4) Continuous Aggregates dla OHLCV
    #    W widokach trzymamy: symbol, tf, bucket, o,h,l,c,v
    for tf, bucket in [("15m","15 minutes"), ("1h","1 hour"), ("4h","4 hours"), ("1d","1 day")]:
        view = f"ohlcv_cagg_{tf}"
        conn.execute(sa.text(f"""
            CREATE MATERIALIZED VIEW IF NOT EXISTS {view}
            WITH (timescaledb.continuous) AS
            SELECT
              symbol,
              '{tf}'::text as tf,
              time_bucket('{bucket}', tstz) as bucket,
              first(o, tstz) as o,
              max(h) as h,
              min(l) as l,
              last(c, tstz) as c,
              sum(v) as v
            FROM ohlcv
            GROUP BY symbol, tf, bucket;
        """))
        # polityka odświeżania: 3 dni wstecz co 15 min
        conn.execute(sa.text(f"""
            SELECT add_continuous_aggregate_policy('{view}',
              start_offset => INTERVAL '3 days',
              end_offset   => INTERVAL '1 minute',
              schedule_interval => INTERVAL '15 minutes',
              if_not_exists => TRUE);
        """))

def downgrade():
    conn = op.get_bind()
    for tf in ["15m","1h","4h","1d"]:
        view = f"ohlcv_cagg_{tf}"
        conn.execute(sa.text(f"DROP MATERIALIZED VIEW IF EXISTS {view}"))
    conn.execute(sa.text("SELECT remove_compression_policy('features');"))
    conn.execute(sa.text("SELECT remove_compression_policy('ohlcv');"))
    conn.execute(sa.text("SELECT remove_retention_policy('ohlcv');"))
