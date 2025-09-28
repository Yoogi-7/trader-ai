
"""add user auth fields

Revision ID: 0003_user_auth
Revises: 0002_resampling_timescale
Create Date: 2024-09-28 00:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '0003_user_auth'
down_revision = '0002_resampling_timescale'
branch_labels = None
depends_on = None

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='USER'))
    op.add_column('users', sa.Column('created_at', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.BigInteger(), nullable=True))

    conn = op.get_bind()
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    default_hash = pwd_context.hash('changeme')
    conn.execute(sa.text(
        "UPDATE users SET email = CONCAT('legacy_user_', id, '@local'), "
        "password_hash = :hash, created_at = :now, updated_at = :now "
        "WHERE email IS NULL"
    ), {"hash": default_hash, "now": now_ms})

    op.alter_column('users', 'email', nullable=False)
    op.alter_column('users', 'password_hash', nullable=False)
    op.alter_column('users', 'created_at', nullable=False)
    op.alter_column('users', 'updated_at', nullable=False)
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
def downgrade() -> None:
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
