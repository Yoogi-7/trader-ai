# migrations/versions/0002_timescale_hypertables.py
from alembic import op
import sqlalchemy as sa

revision = '0002_timescale_hypertables'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()

    # 1) Upewnij się, że rozszerzenie jest dostępne
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))

    # 2) Dodaj kolumny pomocnicze TIMESTAMPTZ (Timescale wymaga time column z typem time/timestamptz)
    #    Trzymamy oryginalne 'ts' (epoch ms), a tworzymy 'tstz' jako pochodną.
    #    Dla features też.
    with op.batch_alter_table("ohlcv") as b:
        b.add_column(sa.Column("tstz", sa.TIMESTAMP(timezone=True)))
    with op.batch_alter_table("features") as b:
        b.add_column(sa.Column("tstz", sa.TIMESTAMP(timezone=True)))

    # 3) Przelanie wartości
    conn.execute(sa.text("""
        UPDATE ohlcv SET tstz = to_timestamp(ts/1000.0)
    """))
    conn.execute(sa.text("""
        UPDATE features SET tstz = to_timestamp(ts/1000.0)
    """))

    # 4) Stwórz hypertables (jeśli jeszcze nie są)
    #    Uwaga: create_hypertable ignoruje jeśli już istnieje.
    conn.execute(sa.text("""
        SELECT create_hypertable('ohlcv', 'tstz', if_not_exists => TRUE);
    """))
    conn.execute(sa.text("""
        SELECT create_hypertable('features', 'tstz', if_not_exists => TRUE);
    """))

    # 5) Indeksy po (symbol, tf, ts/tstz)
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_tstz ON ohlcv (symbol, tf, tstz DESC);
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_features_symbol_tf_tstz ON features (symbol, tf, tstz DESC);
    """))

def downgrade():
    conn = op.get_bind()
    # usuwamy indeksy i kolumny tstz (zostawiamy EXTENSION)
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_ohlcv_symbol_tf_tstz;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_features_symbol_tf_tstz;"))

    with op.batch_alter_table("features") as b:
        b.drop_column("tstz")
    with op.batch_alter_table("ohlcv") as b:
        b.drop_column("tstz")
