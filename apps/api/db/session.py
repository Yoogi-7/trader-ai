# apps/api/db/session.py
# PL: Konfiguracja silnika i sesji DB z env DATABASE_URL.
# EN: Engine & session factory configured via DATABASE_URL env variable.

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")

# Pool parametry rozsądne dla API/workerów
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
