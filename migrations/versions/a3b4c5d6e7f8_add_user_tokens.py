"""add user tokens table

Revision ID: a3b4c5d6e7f8
Revises: 93d8353d4348
Create Date: 2025-10-05 07:19:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "93d8353d4348"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tokens_user_id_name"),
    )
    op.create_index(op.f("ix_user_tokens_id"), "user_tokens", ["id"], unique=False)
    op.create_index(
        op.f("ix_user_tokens_token_hash"),
        "user_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(op.f("ix_user_tokens_user_id"), "user_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_tokens_revoked"), "user_tokens", ["revoked"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_tokens_revoked"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_user_id"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_token_hash"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_id"), table_name="user_tokens")
    op.drop_table("user_tokens")
