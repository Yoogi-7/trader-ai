from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('ohlcv',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('tf', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('o', sa.Float()), sa.Column('h', sa.Float()), sa.Column('l', sa.Float()), sa.Column('c', sa.Float()), sa.Column('v', sa.Float()),
        sa.Column('source_hash', sa.String()),
    )
    op.create_unique_constraint("u_ohlcv_idx","ohlcv",["symbol","tf","ts"])

    op.create_table('features',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('tf', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('f_vector', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('version', sa.String(), default="v1"),
    )
    op.create_unique_constraint("u_features_idx","features",["symbol","tf","ts","version"])

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

    op.create_table('executions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('order_id', sa.String()),
        sa.Column('side', sa.String()),
        sa.Column('px', sa.Float()), sa.Column('qty', sa.Float()),
        sa.Column('fee', sa.Float()), sa.Column('slippage', sa.Float()),
        sa.Column('status', sa.String()), sa.Column('ts', sa.BigInteger()),
    )

    op.create_table('pnl',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('realized', sa.Float()), sa.Column('unrealized', sa.Float()),
        sa.Column('max_dd', sa.Float()), sa.Column('rr', sa.Float()),
        sa.Column('holding_time', sa.Integer()),
        sa.Column('funding_paid', sa.Float(), default=0.0),
    )

    op.create_table('training_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('status', sa.String(), default="running"),
        sa.Column('params_json', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('metrics_json', postgresql.JSON(astext_type=sa.Text())),
    )

    op.create_table('backtests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('params_json', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('summary_json', postgresql.JSON(astext_type=sa.Text())),
    )

    op.create_table('backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('signal_id', sa.Integer()),
        sa.Column('entry', sa.Float()), sa.Column('exit', sa.Float()),
        sa.Column('fee', sa.Float()), sa.Column('pnl', sa.Float()),
        sa.Column('hit_tp_level', sa.Integer(), default=0),
        sa.Column('opened_at', sa.BigInteger()), sa.Column('closed_at', sa.BigInteger()),
    )

    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('risk_profile', sa.String(), default="LOW"),
        sa.Column('capital', sa.Float(), default=100.0),
        sa.Column('prefs', postgresql.JSON(astext_type=sa.Text())),
        sa.Column('api_connected', sa.Boolean(), default=False),
    )

def downgrade():
    for t in ["users","backtest_trades","backtests","training_runs","pnl","executions","signals","backfill_progress","features","ohlcv"]:
        op.drop_table(t)