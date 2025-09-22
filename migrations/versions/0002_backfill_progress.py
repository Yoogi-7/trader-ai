"""add backfill_progress table

Revision ID: 0002_backfill_progress
Revises: 0001_init
Create Date: 2025-09-22
"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = "0002_backfill_progress"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Stwórz tabelę tylko jeśli jej nie ma (idempotentnie)
    if not insp.has_table("backfill_progress"):
        op.create_table(
            "backfill_progress",
            sa.Column("symbol", sa.String(20), nullable=False),
            sa.Column("tf", sa.String(8), nullable=False),
            sa.Column("last_ts", sa.DateTime(timezone=False), nullable=True),
            sa.PrimaryKeyConstraint("symbol", "tf", name="pk_backfill_symbol_tf"),
        )
    else:
        # Tabela już istnieje – nic nie rób (pozwól Alembicowi oznaczyć migrację jako zastosowaną)
        pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Usuń tabelę tylko jeśli istnieje (też idempotentnie)
    if insp.has_table("backfill_progress"):
        op.drop_table("backfill_progress")
