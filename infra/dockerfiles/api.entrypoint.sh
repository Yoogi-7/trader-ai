#!/bin/bash

set -euo pipefail

function log() {
  echo "[entrypoint] $*"
}

log "Waiting for database availability..."

database_url="${DATABASE_URL:-postgresql://traderai:traderai@db:5432/traderai}"
timeout=60
until python - <<PY
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ.get("DATABASE_URL", "postgresql://traderai:traderai@db:5432/traderai"))
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
PY
do
  sleep 1
  timeout=$((timeout - 1))
  if [ "$timeout" -le 0 ]; then
    echo "Database is not ready after waiting" >&2
    exit 1
  fi
done

log "Ensuring database schema exists via metadata create_all"

DATABASE_URL="${DATABASE_URL:-postgresql://traderai:traderai@db:5432/traderai}" \
ASYNC_DATABASE_URL="${ASYNC_DATABASE_URL:-postgresql+asyncpg://traderai:traderai@db:5432/traderai}" \
python - <<'PY'
from apps.api.db.session import engine
# Import models so metadata is populated
import apps.api.db.models  # noqa: F401
from apps.api.db.base import Base

try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    import sys
    print(f"Failed to create tables: {exc}", file=sys.stderr)
    raise
PY

log "Stamping Alembic revision to head"

DATABASE_URL="${DATABASE_URL:-postgresql://traderai:traderai@db:5432/traderai}" \
ASYNC_DATABASE_URL="${ASYNC_DATABASE_URL:-postgresql+asyncpg://traderai:traderai@db:5432/traderai}" \
alembic stamp head

log "Starting application"

exec "$@"
