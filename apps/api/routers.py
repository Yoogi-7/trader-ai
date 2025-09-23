from __future__ import annotations

import time
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.config import settings

from apps.common.celery_app import app as celery_app

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------- Backfill --------

@router.post("/backfill/start")
def backfill_start(payload: dict = Body(default={})):
    pairs: Optional[List[str]] = payload.get("pairs")
    tf: str = payload.get("tf", "1m")
    start_ts_ms: Optional[int] = payload.get("start_ts_ms")
    end_ts_ms: Optional[int] = payload.get("end_ts_ms")
    batch_limit: int = int(payload.get("batch_limit", 1000))

    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(
            pairs=pairs, tf=tf, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms,
            batch_limit=batch_limit, use_ccxt=True,
        ),
    )
    return {"status": "queued", "task_id": async_result.id, "params": {
        "pairs": pairs, "tf": tf, "start_ts_ms": start_ts_ms, "end_ts_ms": end_ts_ms, "batch_limit": batch_limit
    }}

@router.get("/backfill/status")
def backfill_status(db: Session = Depends(get_db)):
    rows = db.execute(select(models.BackfillProgress)).scalars().all()
    out = []
    for r in rows:
        total = pct = done = None
        if r.chunk_start_ts and r.chunk_end_ts:
            total = ((r.chunk_end_ts - r.chunk_start_ts) // 60_000) + 1
            if r.last_ts_completed:
                done = ((r.last_ts_completed - r.chunk_start_ts) // 60_000) + 1
                pct = round(done / total * 100, 2) if total else None
        out.append({
            "symbol": r.symbol, "tf": r.tf, "status": r.status,
            "last_ts_completed": r.last_ts_completed,
            "chunk_start_ts": r.chunk_start_ts, "chunk_end_ts": r.chunk_end_ts,
            "retry_count": r.retry_count, "gaps": r.gaps or [],
            "progress_pct": pct, "done": done, "total": total,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return {"items": out}

@router.post("/backfill/pause")
def backfill_pause(symbol: str, tf: str = "1m", db: Session = Depends(get_db)):
    row = db.execute(
        select(models.BackfillProgress).where(
            models.BackfillProgress.symbol == symbol,
            models.BackfillProgress.tf == tf
        )
    ).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="progress not found")
    row.status = "paused"
    db.add(row); db.commit()
    return {"ok": True}

@router.post("/backfill/resume")
def backfill_resume(payload: dict = Body(...)):
    symbol: str = payload.get("symbol")
    tf: str = payload.get("tf", "1m")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(pairs=[symbol], tf=tf),
    )
    return {"status": "queued", "task_id": async_result.id, "symbol": symbol, "tf": tf}

@router.post("/backfill/restart")
def backfill_restart(payload: dict = Body(...), db: Session = Depends(get_db)):
    symbol: str = payload.get("symbol")
    tf: str = payload.get("tf", "1m")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    row = db.execute(
        select(models.BackfillProgress).where(
            models.BackfillProgress.symbol == symbol,
            models.BackfillProgress.tf == tf
        )
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

# -------- Resampling --------

@router.get("/resample/info")
def resample_info(db: Session = Depends(get_db)):
    out = {}
    for view in ["ohlcv_15m","ohlcv_1h","ohlcv_4h","ohlcv_1d"]:
        row = db.execute(
            text(f"SELECT COUNT(*)::bigint AS cnt, max(ts_time) AS last_ts FROM {view};")
        ).mappings().first()
        out[view] = {
            "rows": int(row["cnt"]) if row and row["cnt"] is not None else 0,
            "last_ts": row["last_ts"].isoformat() if row and row["last_ts"] else None
        }
    return out

@router.post("/resample/refresh")
def resample_refresh(
    view: str = Body(..., embed=True),
    start_iso: Optional[str] = Body(None, embed=True),
    end_iso: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
):
    if view not in {"ohlcv_15m","ohlcv_1h","ohlcv_4h","ohlcv_1d"}:
        raise HTTPException(status_code=400, detail="invalid view")
    db.execute(
        text("CALL refresh_continuous_aggregate(:view, COALESCE(:start::timestamptz, NULL), COALESCE(:end::timestamptz, now()));"),
        {"view": view, "start": start_iso, "end": end_iso}
    )
    db.commit()
    return {"ok": True, "view": view, "start": start_iso, "end": end_iso or "now()"}

# -------- Feature Engineering --------

@router.post("/features/run")
def features_run(payload: dict = Body(default={})):
    symbols: Optional[List[str]] = payload.get("symbols")
    tf: str = payload.get("tf", "15m")
    start_iso: Optional[str] = payload.get("start_iso")
    end_iso: Optional[str] = payload.get("end_iso")
    version: Optional[str] = payload.get("version")

    async_result = celery_app.send_task(
        "apps.ml.jobs.features.run_features",
        kwargs=dict(symbols=symbols, tf=tf, start_iso=start_iso, end_iso=end_iso, version=version),
    )
    return {"status": "queued", "task_id": async_result.id, "params": {
        "symbols": symbols, "tf": tf, "start_iso": start_iso, "end_iso": end_iso, "version": version
    }}

@router.get("/features/status")
def features_status(
    tf: str = "15m",
    version: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if version:
        sql = """
        SELECT symbol, COUNT(*) AS rows, MAX(ts) AS last_ts
        FROM features
        WHERE tf=:tf AND version=:version
        GROUP BY symbol ORDER BY symbol
        """
        rows = db.execute(text(sql), {"tf": tf, "version": version}).mappings().all()
    else:
        sql = """
        SELECT symbol, version, COUNT(*) AS rows, MAX(ts) AS last_ts
        FROM features
        WHERE tf=:tf
        GROUP BY symbol, version
        ORDER BY symbol, version
        """
        rows = db.execute(text(sql), {"tf": tf}).mappings().all()
    out = [dict(r) for r in rows]
    for r in out:
        if "last_ts" in r and r["last_ts"] is not None:
            r["last_ts"] = int(r["last_ts"])
    return {"items": out}

# -------- Training / Backtest (stubs) --------

@router.post("/train/run")
def train_run(payload: dict = Body(default={})):
    return {"status": "queued", "params": payload.get("params", {})}

@router.get("/train/status")
def train_status():
    return {"status": "stub"}

@router.post("/backtest/run")
def backtest_run(payload: dict = Body(default={})):
    return {"status": "queued", "params": payload.get("params", {})}

@router.get("/backtest/results")
def backtest_results():
    return {"status": "stub"}

# -------- Signals --------

@router.post("/signals/generate")
def signals_generate(db: Session = Depends(get_db)):
    sig = models.Signal(
        id=str(uuid.uuid4()), symbol="BTCUSDT", tf_base=settings.base_tf,
        ts=int(time.time()*1000), dir="long",
        entry=65000.0, tp=[65500.0, 66000.0, 67000.0],
        sl=64000.0, lev=5, risk=0.01, margin_mode="isolated",
        expected_net_pct=0.025, confidence=0.62, model_ver="v0.1",
        reason_discard=None, status="published"
    )
    db.add(sig); db.commit()
    return {"inserted": sig.id}

@router.get("/signals/live")
def signals_live(db: Session = Depends(get_db)):
    q = db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(20).all()
    return {"signals": [_signal_to_dict(s) for s in q]}

@router.get("/signals/history")
def signals_history(limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 1000))
    q = db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(limit).all()
    return {"signals": [_signal_to_dict(s) for s in q]}

def _signal_to_dict(s: models.Signal) -> dict:
    return {
        "id": s.id, "symbol": s.symbol, "tf_base": s.tf_base, "ts": s.ts, "dir": s.dir,
        "entry": s.entry, "tp": s.tp, "sl": s.sl, "lev": s.lev, "risk": s.risk,
        "margin_mode": s.margin_mode, "expected_net_pct": s.expected_net_pct,
        "confidence": s.confidence, "model_ver": s.model_ver,
        "reason_discard": s.reason_discard, "status": s.status,
    }

# -------- Settings --------

@router.post("/settings/profile")
def settings_profile(profile: str = Body(..., embed=True)):
    profile = profile.upper()
    if profile not in {"LOW","MED","HIGH"}:
        raise HTTPException(status_code=400, detail="profile must be LOW/MED/HIGH")
    return {"ok": True, "profile": profile}

@router.post("/capital")
def capital_set(amount: float = Body(..., embed=True)):
    if amount < 0:
        raise HTTPException(status_code=400, detail="amount must be >= 0")
    return {"ok": True, "capital": amount}
