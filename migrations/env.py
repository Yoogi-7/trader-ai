import os
import time
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from apps.api.db import Base  # noqa: E402
target_metadata = Base.metadata

# DATABASE_URL z env (fallback do alembic.ini jeśli ustawione tam)
DB_URL = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

def _connect_with_retry(cfg, url: str, retries: int = 30, interval: float = 1.0) -> Engine:
    cfg.set_main_option("sqlalchemy.url", url)
    for i in range(retries):
        try:
            engine = engine_from_config(
                cfg.get_section(cfg.config_ini_section),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
                pool_pre_ping=True,
            )
            # szybki ping
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return engine
        except OperationalError as e:
            print(f"[alembic] DB not ready yet (try {i+1}/{retries}): {e}")
            time.sleep(interval)
    # ostatnia próba (poza pętlą) – nie łapiemy wyjątku, niech poleci na wierzch
    engine = engine_from_config(
        cfg.get_section(cfg.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    return engine

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode' with retry until DB is ready."""
    connectable = _connect_with_retry(config, DB_URL, retries=60, interval=1.0)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
