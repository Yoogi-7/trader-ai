
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.create_table(
        "ohlcv",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("tf", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("o", sa.Float, nullable=False),
        sa.Column("h", sa.Float, nullable=False),
        sa.Column("l", sa.Float, nullable=False),
        sa.Column("c", sa.Float, nullable=False),
        sa.Column("v", sa.Float, nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=True),
    )
    op.create_unique_constraint("uq_ohlcv_symbol_tf_ts", "ohlcv", ["symbol", "tf", "ts"])
    op.create_index("idx_ohlcv_symbol_tf_ts", "ohlcv", ["symbol", "tf", "ts"])

    # Business tables
    op.create_table("backfill_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("tf", sa.String(8), nullable=False),
        sa.Column("last_ts_completed", sa.DateTime, nullable=True),
        sa.Column("chunk_start_ts", sa.DateTime, nullable=True),
        sa.Column("chunk_end_ts", sa.DateTime, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="idle"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()"))
    )
    op.create_unique_constraint("uq_backfill_symbol_tf", "backfill_progress", ["symbol","tf"])

    op.create_table("signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("tf_base", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
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
        sa.Column("reason_discard", sa.String(200), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
    )

    op.create_table("executions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE")),
        sa.Column("order_id", sa.String(40), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("px", sa.Float, nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("fee", sa.Float, nullable=False, server_default="0"),
        sa.Column("slippage_bps", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
    )

    op.create_table("pnl",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE")),
        sa.Column("realized", sa.Float, nullable=False),
        sa.Column("unrealized", sa.Float, nullable=False),
        sa.Column("max_dd", sa.Float, nullable=False),
        sa.Column("rr", sa.Float, nullable=False),
        sa.Column("holding_time_min", sa.Integer, nullable=False),
        sa.Column("funding_paid", sa.Float, nullable=False, server_default="0"),
    )

    op.create_table("training_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("started_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("params_json", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("metrics_json", sa.JSON, nullable=False, server_default=sa.text("'{}'::json"))
    )

    op.create_table("backtests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("params_json", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("started_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("summary_json", sa.JSON, nullable=True)
    )

    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("risk_profile", sa.String(8), nullable=False, server_default="LOW"),
        sa.Column("capital", sa.Float, nullable=False, server_default="100"),
        sa.Column("prefs", sa.JSON, nullable=True),
        sa.Column("api_connected", sa.Boolean, nullable=False, server_default="false")
    )

    # hypertable for OHLCV
    op.execute("SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE)")

def downgrade():
    for t in ["users","backtests","training_runs","pnl","executions","signals","backfill_progress","ohlcv"]:
        op.drop_table(t, if_exists=True)
