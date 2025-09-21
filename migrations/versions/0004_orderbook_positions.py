from alembic import op
import sqlalchemy as sa

revision = '0004_orderbook_positions'
down_revision = '0003_funding_oi'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('orderbook_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('bid_px', sa.Float(), nullable=False),
        sa.Column('bid_qty', sa.Float(), nullable=False),
        sa.Column('ask_px', sa.Float(), nullable=False),
        sa.Column('ask_qty', sa.Float(), nullable=False),
        sa.Column('mid_px', sa.Float(), nullable=False),
        sa.Column('spread_bps', sa.Float(), nullable=False),
        sa.Column('depth_usd_1pct', sa.Float(), nullable=False),
    )
    op.create_unique_constraint("u_ob_idx", "orderbook_snapshots", ["symbol","ts"])

    op.create_table('positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('entry_px', sa.Float(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('lev', sa.Integer(), nullable=False),
        sa.Column('margin_mode', sa.String(), nullable=True),
        sa.Column('exposure_usd', sa.Float(), nullable=False),
        sa.Column('opened_ts', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('pnl', sa.Float(), nullable=False, server_default='0'),
    )

def downgrade():
    op.drop_table("positions")
    op.drop_constraint("u_ob_idx", "orderbook_snapshots", type_="unique")
    op.drop_table("orderbook_snapshots")
