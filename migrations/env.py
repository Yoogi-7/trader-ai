import os
import sys

# Dodaj katalog repo (…/migrations/..) do sys.path, aby import "apps" zawsze działał.
# Dzięki temu Alembic uruchamiany jako osobny proces widzi pakiety projektu.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Importy modeli MUSZĄ być po ustawieniu sys.path:
from apps.api.db.base import Base  # noqa: E402
from apps.api.db import models      # noqa: F401, E402

# Ten obiekt Alembica konfigurujemy na podstawie pliku alembic.ini
config = context.config

# Konfiguracja logowania z pliku alembic.ini (opcjonalna)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# metadata dla autogeneracji migracji
target_metadata = Base.metadata


def run_migrations_offline():
    """Uruchamia migracje w trybie offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Uruchamia migracje w trybie online."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
