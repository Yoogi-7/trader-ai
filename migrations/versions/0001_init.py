from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    # Timescale musi istnieć przed tworzeniem hypertables
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))

    # =========================
    # OHLCV (hypertable na 'tstz')
    # =========================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol      TEXT NOT NULL,
            tf          TEXT NOT NULL,
            tstz        TIMESTAMPTZ NOT NULL,
            ts          BIGINT NOT NULL,
            o           DOUBLE PRECISION,
            h           DOUBLE PRECISION,
            l           DOUBLE PRECISION,
            c           DOUBLE PRECISION,
            v           DOUBLE PRECISION,
            source_hash TEXT
        );
    """))
    conn.execute(sa.text("SELECT create_hypertable('ohlcv', 'tstz', if_not_exists => TRUE);"))
    conn.execute(sa.text("ALTER TABLE ohlcv ADD CONSTRAINT pk_ohlcv PRIMARY KEY(symbol, tf, tstz);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_tstz ON ohlcv(symbol, tf, tstz DESC);"))

    # =========================
    # FEATURES (hypertable na 'tstz')
    # =========================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS features (
            symbol   TEXT NOT NULL,
            tf       TEXT NOT NULL,
            tstz     TIMESTAMPTZ NOT NULL,
            ts       BIGINT NOT NULL,
            f_vector JSONB NOT NULL,
            version  TEXT NOT NULL DEFAULT 'v1'
        );
    """))
    conn.execute(sa.text("SELECT create_hypertable('features', 'tstz', if_not_exists => TRUE);"))
    conn.execute(sa.text("ALTER TABLE features ADD CONSTRAINT pk_features PRIMARY KEY(symbol, tf, tstz, version);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_features_symbol_tf_tstz ON features(symbol, tf, tstz DESC);"))

    # =========================
    # backfill_progress
    # =========================
    op.create_table('backfill_progress',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String()),
        sa.Column('tf', sa.String()),
        sa.Column('last_ts_completed', sa.BigInteger(), default=0),
        sa.Column('chunk_start_ts', sa.BigInteger(), default=0),
        sa.Column('chunk_end_ts', sa.BigInteger(), default=0),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('status', sa.String(), default="idle"),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True)),
    )
    op.create_unique_constraint("u_backfill_idx","backfill_progress",["symbol","tf"])

    # =========================
    # signals
    # =========================
    op.create_table('signals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String()),
        sa.Column('tf_base', sa.String(), default="15m"),
        sa.Column('ts', sa.BigInteger()),
        sa.Column('dir', sa.String()),
        sa.Column('entry', sa.Float()), sa.Column('sl', sa.Float()),
        sa.Column('tp', postgresql.ARRAY(sa.Float())),
        sa.Column('lev', sa.Integer()), sa.Column('risk', sa.Float()),
        sa.Column('margin_mode', sa.String(), default="isolated"),
        sa.Column('expected_net_pct', sa.Float()),
        sa.Column('confidence', sa.Float()),
        sa.Column('model_ver', sa.String()),
        sa.Column('reason_discard', sa.String()),
        sa.Column('status', sa.String(), default="published"),
    )

    # =========================
    # executions
    # =========================
    op.create_table('executions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('order_id', sa.String()),
        sa.Column('side', sa.String()),
        sa.Column('px', sa.Float()), sa.Column('qty', sa.Float()),
        sa.Column('fee', sa.Float()), sa.Column('slippage', sa.Float()),
        sa.Column('status', sa.String()), sa.Column('ts', sa.BigInteger()),
    )

    # =========================
    # pnl
    # =========================
    op.create_table('pnl',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('realized', sa.Float()), sa.Column('unrealized', sa.Float()),
        sa.Column('max_dd', sa.Float()), sa.Column('rr', sa.Float()),
        sa.Column('holding_time', sa.Integer()),
        sa.Column('funding_paid', sa.Float(), default=0.0),
    )

    # =========================
    # training_runs
    # =========================
    op.create_table('training_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('status', sa.String(), default="running"),
        sa.Column('params_json', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('metrics_json', postgresql.JSON(astext_type=sa.Text())),
    )

    # =========================
    # backtests
    # =========================
    op.create_table('backtests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('params_json', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('summary_json', postgresql.JSON(astext_type=sa.Text())),
    )

    # =========================
    # backtest_trades
    # =========================
    op.create_table('backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('entry', sa.Float()), sa.Column('exit', sa.Float()),
        sa.Column('fee', sa.Float()), sa.Column('pnl', sa.Float()),
        sa.Column('hit_tp_level', sa.Integer(), default=0),
        sa.Column('opened_at', sa.BigInteger()), sa.Column('closed_at', sa.BigInteger()),
    )

    # =========================
    # users
    # =========================
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('risk_profile', sa.String(), default="LOW"),
        sa.Column('capital', sa.Float(), default=100.0),
        sa.Column('prefs', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('api_connected', sa.Boolean(), default=False),
    )

def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_features_symbol_tf_tstz;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_ohlcv_symbol_tf_tstz;"))
    for t in ["users","backtest_trades","backtests","training_runs","pnl","executions","signals","backfill_progress","features","ohlcv"]:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {t} CASCADE;"))
