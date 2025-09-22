# apps/common/celery_app.py
from __future__ import annotations
import os
from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Wspólna aplikacja Celery dla API i Workera
app = Celery(
    "trader_ai",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        # Rejestrujemy moduły z zadaniami Celery
        "apps.ml.jobs.backfill",
    ],
)

# Sensowne ustawienia do pracy z zadaniami długimi / idempotentnymi
app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=60 * 60,        # 60 minut
    task_soft_time_limit=60 * 60,   # miękki limit
    result_expires=60 * 60,         # 1h
    timezone="UTC",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)
