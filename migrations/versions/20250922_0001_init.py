from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20250922_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("risk_profile", sa.String(10), nullable=False),
        sa.Column("capital", sa.Numeric(18, 4), nullable=False, server_default="100"),
        sa.Column("prefs", postgresql.JSONB, nullable=True),
        sa.Column("api_connected", sa.Boolean, server_default=sa.text("false")),
    )

    # OHLCV (Timescale-friendly)
    op.execute("CREATE TABLE ohlcv (symbol text, tf text, ts timestamptz, o numeric, h numeric, l numeric, c numeric, v numeric, source_hash text, PRIMARY KEY(symbol, tf, ts));")
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE);")

    # Features
    op.execute("CREATE TABLE features (symbol text, tf text, ts timestamptz, f_vector jsonb, version text, PRIMARY KEY(symbol, tf, ts, version));")
    op.execute("SELECT create_hypertable('features','ts', if_not_exists => TRUE);")

    # Backfill progress
    op.create_table(
        "backfill_progress",
        sa.Column("symbol", sa.Text, primary_key=True),
        sa.Column("tf", sa.Text, primary_key=True),
        sa.Column("last_ts_completed", sa.DateTime(timezone=True)),
        sa.Column("chunk_start_ts", sa.DateTime(timezone=True)),
        sa.Column("chunk_end_ts", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Signals
    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("tf_base", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dir", sa.String(4), nullable=False),  # LONG/SHORT
        sa.Column("entry", sa.Numeric(18,8), nullable=False),
        sa.Column("tp1", sa.Numeric(18,8)),
        sa.Column("tp2", sa.Numeric(18,8)),
        sa.Column("tp3", sa.Numeric(18,8)),
        sa.Column("sl", sa.Numeric(18,8), nullable=False),
        sa.Column("lev", sa.Numeric(10,2), nullable=False),
        sa.Column("risk", sa.Numeric(6,3), nullable=False),
        sa.Column("margin_mode", sa.String(10), nullable=False),
        sa.Column("expected_net_pct", sa.Numeric(6,3), nullable=False),
        sa.Column("confidence", sa.Numeric(6,3)),
        sa.Column("model_ver", sa.String(50)),
        sa.Column("reason_discard", sa.Text),
        sa.Column("status", sa.String(20), server_default="published"),  # or discarded, executed
    )

    # Executions
    op.create_table(
        "executions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("signal_id", sa.BigInteger, sa.ForeignKey("signals.id")),
        sa.Column("order_id", sa.String(64)),
        sa.Column("side", sa.String(5)),
        sa.Column("px", sa.Numeric(18,8)),
        sa.Column("qty", sa.Numeric(28,12)),
        sa.Column("fee", sa.Numeric(18,8)),
        sa.Column("slippage", sa.Numeric(18,8)),
        sa.Column("status", sa.String(20)),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # PnL
    op.create_table(
        "pnl",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("signal_id", sa.BigInteger, sa.ForeignKey("signals.id")),
        sa.Column("realized", sa.Numeric(18,8)),
        sa.Column("unrealized", sa.Numeric(18,8)),
        sa.Column("max_dd", sa.Numeric(18,8)),
        sa.Column("rr", sa.Numeric(10,4)),
        sa.Column("holding_time", sa.Integer),
        sa.Column("funding_paid", sa.Numeric(18,8)),
    )

    # Training / Backtests / Trades
    op.create_table(
        "training_runs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("params_json", postgresql.JSONB),
        sa.Column("metrics_json", postgresql.JSONB),
    )

    op.create_table(
        "backtests",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("params_json", postgresql.JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("summary_json", postgresql.JSONB),
    )

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("backtest_id", sa.BigInteger, sa.ForeignKey("backtests.id")),
        sa.Column("symbol", sa.Text),
        sa.Column("side", sa.String(5)),
        sa.Column("entry_ts", sa.DateTime(timezone=True)),
        sa.Column("exit_ts", sa.DateTime(timezone=True)),
        sa.Column("entry_px", sa.Numeric(18,8)),
        sa.Column("exit_px", sa.Numeric(18,8)),
        sa.Column("fee", sa.Numeric(18,8)),
        sa.Column("pnl", sa.Numeric(18,8)),
        sa.Column("rr", sa.Numeric(10,4)),
        sa.Column("tp_hit", sa.Integer),  # 0/1/2/3
    )

def downgrade():
    for t in ["backtest_trades","backtests","training_runs","pnl","executions","signals","backfill_progress","features","ohlcv","users"]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
