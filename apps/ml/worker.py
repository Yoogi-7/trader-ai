# apps/ml/worker.py
from __future__ import annotations
from apps.common.celery_app import app  # <- wspólna instancja Celery

# Opcjonalnie: trasy zadań / kolejki
# app.conf.task_routes = {
#     "apps.ml.jobs.backfill.run_backfill": {"queue": "backfill"},
# }

if __name__ == "__main__":
    app.start()
