
from celery import Celery
import os

broker = os.getenv("REDIS_URL", "redis://redis:6379/0")
backend = broker
app = Celery("trader_ai", broker=broker, backend=backend, include=["apps.ml.jobs.backfill", "apps.ml.jobs.train", "apps.ml.jobs.backtest"])
app.conf.task_routes = {"apps.ml.jobs.*": {"queue": "ml"}}
