
from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session
from apps.api.db.session import SessionLocal
from apps.api.schemas import StartBackfillRequest, StartBacktestRequest, StartTrainRequest
from apps.api.db import models
from apps.api.config import settings
import uuid, time
from confluent_kafka import Producer

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/backfill/start")
def backfill_start(req: StartBackfillRequest):
    p = Producer({"bootstrap.servers": settings.kafka_brokers})
    payload = {"pairs": req.pairs, "tf": req.tf, "ts": int(time.time()*1000)}
    p.produce(settings.kafka_backfill_topic, value=str(payload).encode())
    p.flush(2)
    return {"status": "queued", "payload": payload}

@router.get("/backfill/status")
def backfill_status(job_id: str | None = None):
    return {"status": "stub", "job_id": job_id}

@router.post("/train/run")
def train_run(req: StartTrainRequest):
    # In real system send to Kafka or Celery
    return {"status": "queued", "params": req.params}

@router.get("/train/status")
def train_status():
    return {"status": "stub"}

@router.post("/backtest/run")
def backtest_run(req: StartBacktestRequest):
    return {"status": "queued", "params": req.params}

@router.get("/backtest/results")
def backtest_results():
    return {"status": "stub"}

@router.post("/signals/generate")
def signals_generate(db: Session = Depends(get_db)):
    # Demo: generate a single signal to prove path end-to-end
    sig = models.Signal(
        id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        tf_base=settings.base_tf,
        ts=int(time.time()*1000),
        dir="long",
        entry=65000.0, tp=[65500.0, 66000.0, 67000.0],
        sl=64000.0, lev=5, risk=0.01,
        margin_mode="isolated", expected_net_pct=0.025,
        confidence=0.62, model_ver="v0.1", reason_discard=None, status="published"
    )
    db.add(sig); db.commit()
    return {"inserted": sig.id}

@router.get("/signals/live")
def signals_live(db: Session = Depends(get_db)):
    return {"signals": [s.__dict__ for s in db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(20)]}

@router.get("/signals/history")
def signals_history(limit: int = 100, db: Session = Depends(get_db)):
    return {"signals": [s.__dict__ for s in db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(limit)]}

@router.post("/settings/profile")
def settings_profile(profile: str):
    return {"ok": True, "profile": profile}

@router.post("/capital")
def capital_set(amount: float):
    return {"ok": True, "capital": amount}
