#!/usr/bin/env bash
set -euo pipefail

echo "[api] Boot: waiting for database…"
python - <<'PY'
import os, time, sys
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL")
if not url:
    print("[api] ERROR: DATABASE_URL not set", file=sys.stderr)
    sys.exit(1)

# timescaledb/psycopg2 DSN ex: postgresql+psycopg2://user:pass@db:5432/name
for i in range(60):
    try:
        eng = create_engine(url, pool_pre_ping=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        print("[api] DB is reachable.")
        break
    except Exception as e:
        print(f"[api] DB not ready yet ({i+1}/60): {e}")
        time.sleep(2)
else:
    print("[api] FATAL: DB never became ready.")
    sys.exit(2)
PY

echo "[api] Running alembic upgrade head…"
alembic upgrade head

echo "[api] Starting uvicorn…"
exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
