
from celery import shared_task
from apps.api.db.session import SessionLocal
from apps.api.db.models import TrainingRun
from datetime import datetime
import time, random, json

@shared_task
def run_training(params: dict | None = None):
    db = SessionLocal()
    tr = TrainingRun(started_at=datetime.utcnow(), status="running", params_json=params or {})
    db.add(tr); db.commit(); db.refresh(tr)
    # Demo: sleep to simulate training + produce metrics
    time.sleep(2)
    metrics = {"oos_hit_rate_tp1": round(random.uniform(0.55, 0.65), 3), "pf": round(random.uniform(1.2,2.0),2)}
    tr.metrics_json = metrics
    tr.status = "done"; tr.finished_at = datetime.utcnow()
    db.commit()
    return {"id": tr.id, "metrics": metrics}
