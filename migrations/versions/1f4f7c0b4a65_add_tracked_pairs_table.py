"""Add tracked pairs table

Revision ID: 1f4f7c0b4a65
Revises: 93d8353d4348
Create Date: 2024-04-22 00:00:00.000000

"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1f4f7c0b4a65"
down_revision: Union[str, None] = "93d8353d4348"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRACKED_PAIR_DEFAULTS = [
    ("BTC/USDT", "15m"),
    ("ETH/USDT", "15m"),
    ("BNB/USDT", "15m"),
    ("XRP/USDT", "15m"),
    ("ADA/USDT", "15m"),
    ("SOL/USDT", "15m"),
    ("DOGE/USDT", "15m"),
    ("POL/USDT", "15m"),
    ("DOT/USDT", "15m"),
    ("AVAX/USDT", "15m"),
    ("LINK/USDT", "15m"),
    ("UNI/USDT", "15m"),
]


def upgrade() -> None:
    timeframe_enum = sa.Enum(
        "M1", "M5", "M15", "H1", "H4", "D1",
        name="timeframe",
        create_type=False,
    )

    op.create_table(
        "tracked_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("timeframe", timeframe_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", name="uq_tracked_pairs_symbol_timeframe"),
    )
    op.create_index(op.f("ix_tracked_pairs_id"), "tracked_pairs", ["id"], unique=False)
    op.create_index("idx_tracked_pairs_symbol", "tracked_pairs", ["symbol"], unique=False)
    op.create_index("idx_tracked_pairs_active", "tracked_pairs", ["is_active"], unique=False)

    tracked_pairs_table = sa.table(
        "tracked_pairs",
        sa.column("symbol", sa.String(length=20)),
        sa.column("timeframe", timeframe_enum),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    now = datetime.utcnow()
    op.bulk_insert(
        tracked_pairs_table,
        [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for symbol, timeframe in TRACKED_PAIR_DEFAULTS
        ],
    )

    system_config_table = sa.table(
        "system_config",
        sa.column("key", sa.String(length=100)),
        sa.column("value", sa.JSON()),
        sa.column("description", sa.Text()),
        sa.column("updated_at", sa.DateTime()),
    )

    conn = op.get_bind()
    version_payload = {"version": datetime.utcnow().isoformat()}

    insert_stmt = postgresql.insert(system_config_table).values(
        key="tracked_pairs_version",
        value=version_payload,
        description="Version marker for tracked pairs configuration",
        updated_at=datetime.utcnow(),
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[system_config_table.c.key],
        set_={
            "value": insert_stmt.excluded.value,
            "updated_at": insert_stmt.excluded.updated_at,
            "description": insert_stmt.excluded.description,
        },
    )
    conn.execute(upsert_stmt)


def downgrade() -> None:
    op.execute("DELETE FROM system_config WHERE key = 'tracked_pairs_version'")
    op.drop_index("idx_tracked_pairs_active", table_name="tracked_pairs")
    op.drop_index("idx_tracked_pairs_symbol", table_name="tracked_pairs")
    op.drop_index(op.f("ix_tracked_pairs_id"), table_name="tracked_pairs")
    op.drop_table("tracked_pairs")
