# apps/api/db/session.py
# PL: Konfiguracja silnika i sesji DB z env DATABASE_URL.
# EN: Engine & session factory configured via DATABASE_URL env variable.

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

if "DATABASE_URL" in os.environ:
    DATABASE_URL = os.environ["DATABASE_URL"]
else:
    if os.getenv("SQLITE_FALLBACK", "1") == "1" or os.getenv("PYTEST_CURRENT_TEST"):
        DATABASE_URL = "sqlite:///./trader_ai_test.db"
    else:
        DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"

if DATABASE_URL.startswith("sqlite:///./"):
    path = DATABASE_URL.replace("sqlite:///./", "")
    reset_flag = os.getenv("RESET_SQLITE_DB", "0")
    should_reset = bool(os.getenv("PYTEST_CURRENT_TEST")) or str(reset_flag).strip().lower() in {"1", "true", "yes", "on"}
    if should_reset and os.path.exists(path):
        os.remove(path)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        future=True,
    )
    # Auto-create schema for lightweight tests/demos when using sqlite fallback.
    from apps.api.db.base import Base  # noqa: WPS433 - local import to avoid circular
    from apps.api.db import models  # noqa: F401  # ensures model metadata is registered

    Base.metadata.create_all(bind=engine)
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_db() -> Generator:
    """PL: Dependency dla FastAPI; EN: FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
