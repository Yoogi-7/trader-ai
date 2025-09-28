#!/usr/bin/env bash
set -Eeuo pipefail

echo "[api] Boot: waiting for database…"

tries=0
until python - <<'PY'
import os, sys, time
import psycopg2
from urllib.parse import urlparse

url = os.getenv("DATABASE_URL")
if not url:
    sys.exit(1)

# Convert sqlalchemy url to psycopg (strip +driver)
url = url.replace("postgresql+psycopg2://", "postgresql://")
u = urlparse(url)
conn = psycopg2.connect(
    dbname=u.path.lstrip("/"),
    user=u.username,
    password=u.password,
    host=u.hostname,
    port=u.port or 5432,
)
conn.close()
PY
do
  tries=$((tries+1))
  if [ "$tries" -gt 30 ]; then
    echo "[api] DB not reachable after 30 attempts. Exiting."
    exit 1
  fi
  echo "[api] DB not ready, retry $tries/30…"
  sleep 2
done

echo "[api] DB is reachable."
echo "[api] Running alembic upgrade head…"
alembic upgrade head

echo "[api] Starting Uvicorn…"
exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
