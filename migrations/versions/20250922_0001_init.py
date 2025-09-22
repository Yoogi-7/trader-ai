from alembic import op
import sqlalchemy as sa

revision = "20250922_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Timescale extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    # OHLCV
    op.create_table(
        "ohlcv",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), index=True, nullable=False),
        sa.Column("tf", sa.String(8), index=True, nullable=False),
        sa.Column("ts", sa.DateTime, index=True, nullable=False),
        sa.Column("o", sa.Float, nullable=False),
        sa.Column("h", sa.Float, nullable=False),
        sa.Column("l", sa.Float, nullable=False),
        sa.Column("c", sa.Float, nullable=False),
        sa.Column("v", sa.Float, nullable=False),
        sa.Column("source_hash", sa.String(64)),
        sa.UniqueConstraint("symbol", "tf", "ts", name="uq_ohlcv_symbol_tf_ts")
    )
    # Hypertable
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists=>TRUE);")

    # BackfillProgress
    op.create_table(
        "backfill_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("tf", sa.String(8), nullable=False),
        sa.Column("last_ts_completed", sa.DateTime),
        sa.Column("chunk_start_ts", sa.DateTime),
        sa.Column("chunk_end_ts", sa.DateTime),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint("symbol", "tf", name="uq_backfill_symbol_tf")
    )

    # Signals
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("tf_base", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("entry", sa.Float, nullable=False),
        sa.Column("tp1", sa.Float, nullable=False),
        sa.Column("tp2", sa.Float, nullable=False),
        sa.Column("tp3", sa.Float, nullable=False),
        sa.Column("sl", sa.Float, nullable=False),
        sa.Column("leverage", sa.Integer, nullable=False),
        sa.Column("risk_pct", sa.Float, nullable=False),
        sa.Column("margin_mode", sa.String(10), nullable=False),
        sa.Column("expected_net_pct", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("model_ver", sa.String(50), nullable=False),
        sa.Column("reason_discard", sa.String(120)),
        sa.Column("status", sa.String(16), server_default="published"),
        sa.Index("idx_signals_symbol_ts", "symbol", "ts")
    )

    # Executions
    op.create_table(
        "executions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE")),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("px", sa.Float, nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("fee", sa.Float, nullable=False),
        sa.Column("slippage", sa.Float, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False, index=True)
    )

    # PnL
    op.create_table(
        "pnl",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE")),
        sa.Column("realized", sa.Float, nullable=False),
        sa.Column("unrealized", sa.Float, nullable=False),
        sa.Column("max_dd", sa.Float, nullable=False),
        sa.Column("rr", sa.Float, nullable=False),
        sa.Column("holding_time_min", sa.Integer, nullable=False),
        sa.Column("funding_paid", sa.Float, server_default="0.0")
    )

def downgrade():
    op.drop_table("pnl")
    op.drop_table("executions")
    op.drop_table("signals")
    op.drop_table("backfill_progress")
    op.drop_table("ohlcv")
