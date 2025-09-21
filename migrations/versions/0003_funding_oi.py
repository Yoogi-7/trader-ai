from alembic import op
import sqlalchemy as sa

revision = '0003_funding_oi'
down_revision = '0002_timescale_hypertables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('funding_rates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('rate_bps', sa.Float(), nullable=False),
    )
    op.create_unique_constraint("u_funding_idx", "funding_rates", ["symbol","ts"])

    op.create_table('open_interest',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('ts', sa.BigInteger(), nullable=False),
        sa.Column('oi', sa.Float(), nullable=False),
    )
    op.create_unique_constraint("u_oi_idx", "open_interest", ["symbol","ts"])

def downgrade():
    op.drop_constraint("u_oi_idx", "open_interest", type_="unique")
    op.drop_table("open_interest")
    op.drop_constraint("u_funding_idx", "funding_rates", type_="unique")
    op.drop_table("funding_rates")
