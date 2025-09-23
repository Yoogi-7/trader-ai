# migrations/env.py
# PL: Standardowy plik Alembica z target_metadata i wsparciem dla env DATABASE_URL.
# EN: Standard Alembic env with target_metadata and env DATABASE_URL support.

import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Umożliw import "apps.*" gdy alembic uruchamiany spoza repo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apps.api.db.base import Base  # noqa: E402
from apps.api.db import models     # noqa: F401,E402

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Pozwalaj na nadpisanie URL przez env var (np. w CI/CD)
def get_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section)
    url = get_url()
    if url:
        cfg["sqlalchemy.url"] = url

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
