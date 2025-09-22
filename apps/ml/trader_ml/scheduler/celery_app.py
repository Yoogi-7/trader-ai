import os
from celery import Celery

broker = os.getenv("REDIS_URL","redis://redis:6379/0")  # prosto, broker=Redis
app = Celery("trader_ml", broker=broker, backend=broker)
app.conf.worker_hijack_root_logger = False
