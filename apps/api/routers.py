from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import select, text, desc
from sqlalchemy.orm import Session

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.config import settings
from apps.api import schemas, crud
from apps.api.services.signals_service import generate_ai_summary
from apps.api.security import (create_access_token, get_current_user, get_password_hash, require_admin, verify_password)

from apps.common.celery_app import app as celery_app

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------- Auth --------

@router.post("/auth/login", response_model=schemas.AuthResponse)
def auth_login(payload: schemas.AuthLoginReq, db: Session = Depends(get_db)):
    user = crud.user_get_by_email(db, payload.email.strip().lower())
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role})
    return schemas.AuthResponse(access_token=token, user=schemas.UserInfo.model_validate(user))

@router.get("/auth/me", response_model=schemas.UserInfo)
def auth_me(current_user: models.User = Depends(get_current_user)):
    return schemas.UserInfo.model_validate(current_user)

@router.get("/users", response_model=List[schemas.UserInfo])
def users_list(_admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    users = crud.user_list(db)
    return [schemas.UserInfo.model_validate(u) for u in users]

@router.post("/users", response_model=schemas.UserInfo)
def users_create(payload: schemas.UserCreateReq, _admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    if crud.user_get_by_email(db, payload.email.strip().lower()):
        raise HTTPException(status_code=400, detail="User already exists")
    password_hash = get_password_hash(payload.password)
    user = crud.user_create(db, payload.email.strip().lower(), password_hash, role=payload.role, risk_profile=payload.risk_profile, capital=payload.capital, prefs=payload.prefs)
    return schemas.UserInfo.model_validate(user)

@router.patch("/users/{user_id}", response_model=schemas.UserInfo)
def users_update(user_id: int, payload: schemas.UserUpdateReq, _admin: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    fields = {}
    if payload.role is not None:
        fields['role'] = payload.role
    if payload.password:
        fields['password_hash'] = get_password_hash(payload.password)
    if payload.risk_profile is not None:
        fields['risk_profile'] = payload.risk_profile
    if payload.capital is not None:
        fields['capital'] = payload.capital
    if payload.prefs is not None:
        fields['prefs'] = payload.prefs
    user = crud.user_update(db, user, **fields)
    return schemas.UserInfo.model_validate(user)

# -------- Backfill --------

@router.post("/backfill/start")
def backfill_start(payload: dict = Body(default={}), _admin: models.User = Depends(require_admin)):
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

def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return str(value)


@router.get("/backfill/status")
def backfill_status(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
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
            "retry_count": r.retry_count, "gaps": getattr(r, "gaps", []) or [],
            "progress_pct": pct, "done": done, "total": total,
            "updated_at": _to_iso(r.updated_at),
        })
    return {"items": out}

@router.post("/backfill/pause")
def backfill_pause(symbol: str, tf: str = "1m", db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
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
def backfill_resume(payload: dict = Body(...), _admin: models.User = Depends(require_admin)):
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
def backfill_restart(payload: dict = Body(...), db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
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
        if hasattr(row, "gaps"):
            row.gaps = []
        db.add(row); db.commit()
    async_result = celery_app.send_task(
        "apps.ml.jobs.backfill.run_backfill",
        kwargs=dict(pairs=[symbol], tf=tf),
    )
    return {"status": "queued", "task_id": async_result.id, "symbol": symbol, "tf": tf}

@router.get("/admin/summary")
def admin_summary(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    backfills = db.execute(
        select(models.BackfillProgress)
        .order_by(desc(models.BackfillProgress.updated_at))
        .limit(10)
    ).scalars().all()
    trainings = db.execute(
        select(models.TrainingRun)
        .order_by(desc(models.TrainingRun.started_at))
        .limit(10)
    ).scalars().all()
    signals = db.execute(
        select(models.Signal)
        .order_by(desc(models.Signal.ts))
        .limit(10)
    ).scalars().all()

    backfill_payload = [
        {
            "symbol": row.symbol,
            "tf": row.tf,
            "status": row.status,
            "chunk_start_ts": row.chunk_start_ts,
            "chunk_end_ts": row.chunk_end_ts,
            "last_ts_completed": row.last_ts_completed,
            "updated_at": _to_iso(row.updated_at),
        }
        for row in backfills
    ]

    training_payload = [
        {
            "id": row.id,
            "params": row.params_json,
            "started_at": _to_iso(row.started_at),
            "finished_at": _to_iso(row.finished_at),
            "status": row.status,
            "metrics": row.metrics_json,
        }
        for row in trainings
    ]

    signal_payload = [
        {
            "id": row.id,
            "symbol": row.symbol,
            "tf": row.tf_base,
            "dir": row.dir,
            "ts": row.ts,
            "expected_net_pct": row.expected_net_pct,
            "confidence": row.confidence,
            "status": row.status,
        }
        for row in signals
    ]

    resample_views = {}
    for view in ("ohlcv_15m", "ohlcv_1h", "ohlcv_4h", "ohlcv_1d"):
        row = db.execute(
            text(f"SELECT COUNT(*)::bigint AS cnt, max(ts) AS last_ts FROM {view};")
        ).mappings().first()
        resample_views[view] = {
            "rows": int(row["cnt"]) if row and row["cnt"] is not None else 0,
            "last_ts": _to_iso(row["last_ts"]) if row and row["last_ts"] is not None else None,
        }

    features_rows = db.execute(
        text("""
            SELECT symbol, tf, version, COUNT(*)::bigint AS rows, max(ts) AS last_ts
            FROM features
            GROUP BY symbol, tf, version
            ORDER BY last_ts DESC
            LIMIT 10
        """)
    ).mappings().all()

    features_payload = [
        {
            "symbol": row["symbol"],
            "tf": row["tf"],
            "version": row["version"],
            "rows": int(row["rows"]) if row["rows"] is not None else 0,
            "last_ts": _to_iso(row["last_ts"]) if row["last_ts"] is not None else None,
        }
        for row in features_rows
    ]

    return {
        "backfill": backfill_payload,
        "training": training_payload,
        "signals": signal_payload,
        "resample": resample_views,
        "features": features_payload,
    }


# -------- Resampling --------

@router.get("/resample/info")
def resample_info(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    out = {}
    for view in ["ohlcv_15m","ohlcv_1h","ohlcv_4h","ohlcv_1d"]:
        row = db.execute(
            text(f"SELECT COUNT(*)::bigint AS cnt, max(ts) AS last_ts FROM {view};")
        ).mappings().first()
        out[view] = {
            "rows": int(row["cnt"]) if row and row["cnt"] is not None else 0,
            "last_ts": _to_iso(row["last_ts"]) if row and row["last_ts"] is not None else None
        }
    return out

@router.post("/resample/refresh")
def resample_refresh(
    view: str = Body(..., embed=True),
    start_iso: Optional[str] = Body(None, embed=True),
    end_iso: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
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
def features_run(payload: dict = Body(default={}), _admin: models.User = Depends(require_admin)):
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
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin)
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
def train_run(payload: dict = Body(default={}), _admin: models.User = Depends(require_admin)):
    return {"status": "queued", "params": payload.get("params", {})}

@router.get("/train/status")
def train_status(_admin: models.User = Depends(require_admin)):
    return {"status": "stub"}

@router.post("/backtest/run")
def backtest_run(payload: dict = Body(default={}), _admin: models.User = Depends(require_admin)):
    return {"status": "queued", "params": payload.get("params", {})}

@router.get("/backtest/results")
def backtest_results(_admin: models.User = Depends(require_admin)):
    return {"status": "stub"}

# -------- Signals --------

@router.post("/signals/generate")
def signals_generate(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    sig = models.Signal(
        id=str(uuid.uuid4()), symbol="BTCUSDT", tf_base=settings.base_tf,
        ts=int(time.time()*1000), dir="long",
        entry=65000.0, tp=[65500.0, 66000.0, 67000.0],
        sl=64000.0, lev=5, risk=0.01, margin_mode="isolated",
        expected_net_pct=0.025, confidence=0.62, model_ver="v0.1",
        reason_discard=None, status="published",
        ai_summary=generate_ai_summary(
            symbol="BTCUSDT",
            tf_base=settings.base_tf,
            direction="LONG",
            entry=65000.0,
            tp=[65500.0, 66000.0, 67000.0],
            sl=64000.0,
            expected_net_pct=0.025,
            confidence=0.62,
        )
    )
    db.add(sig); db.commit()
    return {"inserted": sig.id}

@router.get("/signals/live")
def signals_live(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    q = db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(20).all()
    return {"signals": [_signal_to_dict(s) for s in q]}

@router.get("/signals/history")
def signals_history(limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
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
        "ai_summary": s.ai_summary,
    }

# -------- Settings --------

@router.post("/settings/profile")
def settings_profile(payload: schemas.UserSettingsReq, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    target_user = current_user
    if payload.user_id and payload.user_id != current_user.id:
        if current_user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Forbidden")
        target_user = db.get(models.User, payload.user_id)
        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")
    crud.user_update_settings(db, target_user, payload.risk_profile, payload.capital, payload.prefs)
    return {"ok": True}

@router.post("/capital")
def capital_set(amount: float = Body(..., embed=True), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if amount < 0:
        raise HTTPException(status_code=400, detail="amount must be >= 0")
    crud.user_update_settings(db, current_user, current_user.risk_profile, amount, current_user.prefs or {})
    return {"ok": True, "capital": amount}
