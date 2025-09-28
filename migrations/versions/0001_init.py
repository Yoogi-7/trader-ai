# migrations/versions/0001_init.py
# Initial migration – Timescale extensions, core tables, hypertables for heavy TS (ohlcv, features).
# IMPORTANT: 'signals' stays a regular table (NOT a hypertable) to allow FK references to it.

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin;")

    # --- Tables ---

    # OHLCV (time-series, will be hypertable)
    op.create_table(
        "ohlcv",
        sa.Column("symbol", sa.String(), primary_key=True),
        sa.Column("tf", sa.String(), primary_key=True),
        sa.Column("ts", sa.BigInteger(), primary_key=True),  # epoch ms
        sa.Column("o", sa.Float(), nullable=False),
        sa.Column("h", sa.Float(), nullable=False),
        sa.Column("l", sa.Float(), nullable=False),
        sa.Column("c", sa.Float(), nullable=False),
        sa.Column("v", sa.Float(), nullable=False),
        sa.Column("source_hash", sa.String(), nullable=True),
    )
    op.create_index("ix_ohlcv_ts", "ohlcv", ["ts"])
    op.create_index("ix_ohlcv_sym_tf_ts", "ohlcv", ["symbol", "tf", "ts"])

    # FEATURES (time-series, will be hypertable)
    op.create_table(
        "features",
        sa.Column("symbol", sa.String(), primary_key=True),
        sa.Column("tf", sa.String(), primary_key=True),
        sa.Column("ts", sa.BigInteger(), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("f_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_features_ts", "features", ["ts"])

    # BACKFILL PROGRESS (control/meta)
    op.create_table(
        "backfill_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("tf", sa.String(), nullable=False),
        sa.Column("last_ts_completed", sa.BigInteger(), nullable=True),
        sa.Column("chunk_start_ts", sa.BigInteger(), nullable=True),
        sa.Column("chunk_end_ts", sa.BigInteger(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="idle"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("symbol", "tf", name="uq_backfill_symbol_tf"),
    )
    op.create_index("ix_backfill_status", "backfill_progress", ["status"])

    # SIGNALS (regular table! NOT hypertable — to allow inbound FKs)
    op.create_table(
        "signals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("tf_base", sa.String(), nullable=False),
        sa.Column("ts", sa.BigInteger(), nullable=False),
        sa.Column("dir", sa.String(), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("tp", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("sl", sa.Float(), nullable=False),
        sa.Column("lev", sa.Float(), nullable=False),
        sa.Column("risk", sa.String(), nullable=False),
        sa.Column("margin_mode", sa.String(), nullable=False, server_default="ISOLATED"),
        sa.Column("expected_net_pct", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_ver", sa.String(), nullable=True),
        sa.Column("reason_discard", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
    )
    op.create_index("ix_signals_sym_tf_ts", "signals", ["symbol", "tf_base", "ts"])
    op.create_index("ix_signals_status", "signals", ["status"])

    # EXECUTIONS (FK -> signals.id)
    op.create_table(
        "executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(), sa.ForeignKey("signals.id", ondelete="SET NULL")),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("px", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("slippage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="filled"),
        sa.Column("ts", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_exec_signal_ts", "executions", ["signal_id", "ts"])

    # PNL (FK -> signals.id)
    op.create_table(
        "pnl",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.String(), sa.ForeignKey("signals.id", ondelete="SET NULL")),
        sa.Column("realized", sa.Float(), nullable=True),
        sa.Column("unrealized", sa.Float(), nullable=True),
        sa.Column("max_dd", sa.Float(), nullable=True),
        sa.Column("rr", sa.Float(), nullable=True),
        sa.Column("holding_time", sa.Integer(), nullable=True),
        sa.Column("funding_paid", sa.Float(), nullable=True),
    )
    op.create_index("ix_pnl_signal", "pnl", ["signal_id"])

    # TRAINING RUNS (meta)
    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("finished_at", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_train_status_start", "training_runs", ["status", "started_at"])

    # BACKTESTS
    op.create_table(
        "backtests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("finished_at", sa.BigInteger(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_backtests_start", "backtests", ["started_at"])

    # BACKTEST TRADES (FK -> backtests.id)
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("backtest_id", sa.Integer(), sa.ForeignKey("backtests.id", ondelete="CASCADE")),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("entry_ts", sa.BigInteger(), nullable=False),
        sa.Column("exit_ts", sa.BigInteger(), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("exit", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pnl", sa.Float(), nullable=False),
    )
    op.create_index("ix_bt_trades_bt", "backtest_trades", ["backtest_id"])
    op.create_index("ix_bt_trades_sym", "backtest_trades", ["symbol"])

    # USERS
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="user"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )

    # --- Hypertables for heavy time-series ---
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE, chunk_time_interval => 604800000);")   # 7d in ms
    op.execute("SELECT create_hypertable('features','ts', if_not_exists => TRUE, chunk_time_interval => 604800000);")
    # NO hypertable for 'signals' (keep it regular table!)

def downgrade():
    # Drop in reverse order
    op.drop_table("users")

    op.drop_index("ix_bt_trades_sym", table_name="backtest_trades")
    op.drop_index("ix_bt_trades_bt", table_name="backtest_trades")
    op.drop_table("backtest_trades")

    op.drop_index("ix_backtests_start", table_name="backtests")
    op.drop_table("backtests")

    op.drop_index("ix_train_status_start", table_name="training_runs")
    op.drop_table("training_runs")

    op.drop_index("ix_pnl_signal", table_name="pnl")
    op.drop_table("pnl")

    op.drop_index("ix_exec_signal_ts", table_name="executions")
    op.drop_table("executions")

    op.drop_index("ix_signals_status", table_name="signals")
    op.drop_index("ix_signals_sym_tf_ts", table_name="signals")
    op.drop_table("signals")

    op.drop_index("ix_backfill_status", table_name="backfill_progress")
    op.drop_table("backfill_progress")

    op.drop_index("ix_features_ts", table_name="features")
    op.drop_table("features")

    op.drop_index("ix_ohlcv_sym_tf_ts", table_name="ohlcv")
    op.drop_index("ix_ohlcv_ts", table_name="ohlcv")
    op.drop_table("ohlcv")
