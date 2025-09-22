from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.config import get_settings

settings = get_settings()

# Używamy złożonego DSN z configu (obsługuje DATABASE_URL albo parametry host/port/user/db)
ENGINE = create_engine(
    settings.sqlalchemy_dsn,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(
    bind=ENGINE,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
