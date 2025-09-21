#!/usr/bin/env bash
set -e

HOST="${1:-db}"
PORT="${2:-5432}"
USER="${3:-trader}"
DB="${4:-trader_ai}"
RETRIES="${5:-60}"

for i in $(seq 1 "${RETRIES}"); do
  if PGPASSWORD=trader psql -h "${HOST}" -U "${USER}" -d "${DB}" -c "SELECT 1" >/dev/null 2>&1; then
    echo "DB is ready."
    exit 0
  fi
  echo "Waiting for DB... (${i}/${RETRIES})"
  sleep 1
done

echo "DB was not ready in time."
exit 1
