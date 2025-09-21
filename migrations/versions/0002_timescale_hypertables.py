from alembic import op
import sqlalchemy as sa

revision = '0002_timescale_hypertables'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()

    # 1) Timescale extension
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))

    # 2) Dodaj kolumny timestamptz
    with op.batch_alter_table("ohlcv") as b:
        b.add_column(sa.Column("tstz", sa.TIMESTAMP(timezone=True)))
    with op.batch_alter_table("features") as b:
        b.add_column(sa.Column("tstz", sa.TIMESTAMP(timezone=True)))

    # 3) Przelej wartości
    conn.execute(sa.text("UPDATE ohlcv   SET tstz = to_timestamp(ts/1000.0)"))
    conn.execute(sa.text("UPDATE features SET tstz = to_timestamp(ts/1000.0)"))

    # 4) Zrzuć stare UNIQUE (nie zawierają kolumny partycjonującej)
    conn.execute(sa.text("ALTER TABLE ohlcv    DROP CONSTRAINT IF EXISTS u_ohlcv_idx"))
    conn.execute(sa.text("ALTER TABLE features DROP CONSTRAINT IF EXISTS u_features_idx"))

    # 5) Utwórz hypertables
    conn.execute(sa.text("SELECT create_hypertable('ohlcv', 'tstz', if_not_exists => TRUE);"))
    conn.execute(sa.text("SELECT create_hypertable('features', 'tstz', if_not_exists => TRUE);"))

    # 6) Nowe UNIQUE zgodne z wymaganiem Timescale
    conn.execute(sa.text("ALTER TABLE ohlcv    ADD CONSTRAINT u_ohlcv_idx_ht UNIQUE(symbol, tf, tstz)"))
    conn.execute(sa.text("ALTER TABLE features ADD CONSTRAINT u_features_idx_ht UNIQUE(symbol, tf, tstz, version)"))

    # 7) Indeksy wydajnościowe
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_tstz    ON ohlcv(symbol, tf, tstz DESC)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_features_symbol_tf_tstz ON features(symbol, tf, tstz DESC)"))

def downgrade():
    conn = op.get_bind()
    # Zrzuć indeksy/unique hypertable
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_ohlcv_symbol_tf_tstz"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_features_symbol_tf_tstz"))
    conn.execute(sa.text("ALTER TABLE features DROP CONSTRAINT IF EXISTS u_features_idx_ht"))
    conn.execute(sa.text("ALTER TABLE ohlcv    DROP CONSTRAINT IF EXISTS u_ohlcv_idx_ht"))

    # Nie usuwamy hypertable (brak potrzeby), ale usuwamy kolumny tstz dla czystości
    with op.batch_alter_table("features") as b:
        b.drop_column("tstz")
    with op.batch_alter_table("ohlcv") as b:
        b.drop_column("tstz")
