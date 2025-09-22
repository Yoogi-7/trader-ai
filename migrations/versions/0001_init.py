
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('ohlcv',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('tf', sa.String(), primary_key=True),
        sa.Column('ts', sa.BigInteger(), primary_key=True),
        sa.Column('o', sa.Float(), nullable=False),
        sa.Column('h', sa.Float(), nullable=False),
        sa.Column('l', sa.Float(), nullable=False),
        sa.Column('c', sa.Float(), nullable=False),
        sa.Column('v', sa.Float(), nullable=False),
        sa.Column('source_hash', sa.String(), nullable=True),
    )
    op.create_table('features',
        sa.Column('symbol', sa.String(), primary_key=True),
        sa.Column('tf', sa.String(), primary_key=True),
        sa.Column('ts', sa.BigInteger(), primary_key=True),
        sa.Column('version', sa.String(), primary_key=True),
        sa.Column('f_vector', postgresql.JSONB(), nullable=False),
    )
    op.create_table('backfill_progress',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('tf', sa.String(), nullable=False),
        sa.Column('last_ts_completed', sa.BigInteger(), nullable=True),
        sa.Column('chunk_start_ts', sa.BigInteger(), nullable=True),
        sa.Column('chunk_end_ts', sa.BigInteger(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('gaps', postgresql.JSONB(), nullable=True),
    )
    op.create_table('signals',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('tf_base', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('dir', sa.String(), nullable=False),
        sa.Column('entry', sa.Float(), nullable=False),
        sa.Column('tp', postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column('sl', sa.Float(), nullable=False),
        sa.Column('lev', sa.Integer(), nullable=False),
        sa.Column('risk', sa.Float(), nullable=False),
        sa.Column('margin_mode', sa.String(), nullable=True),
        sa.Column('expected_net_pct', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('model_ver', sa.String(), nullable=False),
        sa.Column('reason_discard', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
    )
    op.create_table('executions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('signal_id', sa.String(), sa.ForeignKey('signals.id')),
        sa.Column('order_id', sa.String(), nullable=True),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('px', sa.Float(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('fee', sa.Float(), nullable=False),
        sa.Column('slippage', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('ts', sa.BigInteger(), nullable=False),
    )
    op.create_table('pnl',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('signal_id', sa.String(), sa.ForeignKey('signals.id')),
        sa.Column('realized', sa.Float(), nullable=True),
        sa.Column('unrealized', sa.Float(), nullable=True),
        sa.Column('max_dd', sa.Float(), nullable=True),
        sa.Column('rr', sa.Float(), nullable=True),
        sa.Column('holding_time', sa.Integer(), nullable=True),
        sa.Column('funding_paid', sa.Float(), nullable=True),
    )
    op.create_table('training_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('finished_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('params_json', postgresql.JSONB(), nullable=True),
        sa.Column('metrics_json', postgresql.JSONB(), nullable=True),
    )
    op.create_table('backtests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('params_json', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('finished_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('summary_json', postgresql.JSONB(), nullable=True),
    )
    op.create_table('backtest_trades',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('backtest_id', sa.Integer(), sa.ForeignKey('backtests.id')),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('entry_ts', sa.BigInteger(), nullable=False),
        sa.Column('exit_ts', sa.BigInteger(), nullable=False),
        sa.Column('entry', sa.Float(), nullable=False),
        sa.Column('exit', sa.Float(), nullable=False),
        sa.Column('fee', sa.Float(), nullable=False),
        sa.Column('pnl', sa.Float(), nullable=False),
    )
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('risk_profile', sa.String(), nullable=True),
        sa.Column('capital', sa.Float(), nullable=True),
        sa.Column('prefs', postgresql.JSONB(), nullable=True),
        sa.Column('api_connected', sa.Boolean(), nullable=True),
    )

def downgrade():
    for t in ['users','backtest_trades','backtests','training_runs','pnl','executions','signals','backfill_progress','features','ohlcv']:
        op.drop_table(t)
