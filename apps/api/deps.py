# apps/api/deps.py
# PL: Zależności FastAPI (DB sesja, paginacja). EN: FastAPI dependencies.

from fastapi import Depends, Query
from apps.api.db.session import get_db
from sqlalchemy.orm import Session
from apps.api.config import settings

def db_dep() -> Session:
    # Generator z get_db
    from apps.api.db.session import get_db as _get_db
    return next(_get_db())

def get_pagination(
    limit: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    offset: int = Query(default=0, ge=0),
):
    return {"limit": limit, "offset": offset}
