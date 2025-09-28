
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
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at BIGINT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at BIGINT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS risk_profile VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS capital DOUBLE PRECISION")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS prefs JSONB")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS api_connected BOOLEAN")

    conn = op.get_bind()
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    default_hash = pwd_context.hash('changeme')
    conn.execute(sa.text(
        "UPDATE users SET email = CONCAT('legacy_user_', id, '@local'), "
        "password_hash = COALESCE(password_hash, :hash), created_at = COALESCE(created_at, :now), "
        "updated_at = COALESCE(updated_at, :now), risk_profile = COALESCE(risk_profile, 'LOW'), "
        "capital = COALESCE(capital, 100.0), prefs = COALESCE(prefs, '{}'::jsonb), "
        "api_connected = COALESCE(api_connected, FALSE), role = COALESCE(role, 'USER') "
        "WHERE email IS NULL"
    ), {"hash": default_hash, "now": now_ms})

    conn.execute(sa.text(
        "UPDATE users SET risk_profile = COALESCE(risk_profile, 'LOW'), "
        "capital = COALESCE(capital, 100.0), prefs = COALESCE(prefs, '{}'::jsonb), "
        "api_connected = COALESCE(api_connected, FALSE), role = COALESCE(role, 'USER')"
    ))

    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'USER'")
    op.execute("ALTER TABLE users ALTER COLUMN risk_profile SET DEFAULT 'LOW'")
    op.execute("ALTER TABLE users ALTER COLUMN capital SET DEFAULT 100.0")
    op.execute("ALTER TABLE users ALTER COLUMN api_connected SET DEFAULT FALSE")

    op.alter_column('users', 'email', nullable=False)
    op.alter_column('users', 'password_hash', nullable=False)
    op.alter_column('users', 'created_at', nullable=False)
    op.alter_column('users', 'updated_at', nullable=False)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'users'::regclass AND conname = 'uq_users_email'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);
            END IF;
        END
        $$;
        """
    )
def downgrade() -> None:
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.drop_column('users', 'api_connected')
    op.drop_column('users', 'prefs')
    op.drop_column('users', 'capital')
    op.drop_column('users', 'risk_profile')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'role')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
