# apps/api/routers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
import time, uuid

from apps.api.db.session import SessionLocal
from apps.api.schemas import StartBackfillRequest, StartBacktestRequest, StartTrainRequest
from apps.api.db import models
from apps.api.config import settings

# 🔁 Wspólna Celery app
from apps.common.celery_app import app as celery_app

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/backfill/start")
def backfill_start(req: StartBackfillRequest):
    # Wyślij asynchroniczne zadanie do Workera
    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(
            pairs=req.pairs,
            tf=req.tf,
            start_ts_ms=req.start_ts_ms,
            end_ts_ms=req.end_ts_ms,
            batch_limit=req.batch_limit,
            use_ccxt=True,
        ),
    )
    return {"status": "queued", "task_id": async_result.id, "params": req.model_dump()}

@router.get("/backfill/status")
def backfill_status(db: Session = Depends(get_db)):
    rows = db.execute(select(models.BackfillProgress)).scalars().all()
    out = []
    for r in rows:
        total = None
        pct = None
        done = None
        if r.chunk_start_ts and r.chunk_end_ts:
            total = ((r.chunk_end_ts - r.chunk_start_ts) // 60_000) + 1
            if r.last_ts_completed:
                done = ((r.last_ts_completed - r.chunk_start_ts) // 60_000) + 1
                pct = round(done / total * 100, 2) if total else None
        out.append({
            "symbol": r.symbol,
            "tf": r.tf,
            "status": r.status,
            "last_ts_completed": r.last_ts_completed,
            "chunk_start_ts": r.chunk_start_ts,
            "chunk_end_ts": r.chunk_end_ts,
            "retry_count": r.retry_count,
            "gaps": r.gaps or [],
            "progress_pct": pct,
            "done": done,
            "total": total,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return {"items": out}

@router.post("/backfill/pause")
def backfill_pause(symbol: str, tf: str = "1m", db: Session = Depends(get_db)):
    row = db.execute(
        select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)
    ).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="progress not found")
    row.status = "paused"
    db.add(row); db.commit()
    return {"ok": True}

@router.post("/backfill/resume")
def backfill_resume(symbol: str, tf: str = "1m"):
    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(pairs=[symbol], tf=tf),
    )
    return {"status": "queued", "task_id": async_result.id, "symbol": symbol, "tf": tf}

@router.post("/backfill/restart")
def backfill_restart(symbol: str, tf: str = "1m", db: Session = Depends(get_db)):
    row = db.execute(
        select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)
    ).scalars().first()
    if row:
        row.last_ts_completed = None
        row.chunk_start_ts = None
        row.chunk_end_ts = None
        row.retry_count = 0
        row.status = "idle"
        row.gaps = []
        db.add(row); db.commit()
    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(pairs=[symbol], tf=tf),
    )
    return {"status": "queued", "task_id": async_result.id, "symbol": symbol, "tf": tf}

@router.post("/train/run")
def train_run(req: StartTrainRequest):
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
