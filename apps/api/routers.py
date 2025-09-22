
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any, Dict, List
from apps.api.db.session import get_db
from apps.api.schemas import UserSettingsIn, CapitalIn, UserOut, BackfillStartRequest, TrainRunRequest, BacktestRequest, SignalPublishRequest
from apps.api import crud
from apps.api.services.risk import map_profile
from apps.api.tools.signals import publish_signal_decision
from apps.api.tools.backtester import run_backtest_sync

router = APIRouter()

@router.get("/health", tags=["system"])
def health() -> Dict[str, Any]:
    return {"status": "ok"}

@router.post("/settings/profile", response_model=UserOut, tags=["settings"])
def set_profile(payload: UserSettingsIn, db: Session = Depends(get_db)) -> UserOut:
    params = map_profile(payload.risk_profile)
    prefs = {"pairs": payload.pairs or [], "max_parallel_positions": payload.max_parallel_positions, "margin_mode": payload.margin_mode}
    user = crud.update_user(db, {"risk_profile": payload.risk_profile, "prefs": prefs})
    return UserOut.model_validate(user.__dict__)

@router.post("/capital", response_model=UserOut, tags=["settings"])
def set_capital(payload: CapitalIn, db: Session = Depends(get_db)) -> UserOut:
    user = crud.update_user(db, {"capital": float(payload.capital)})
    return UserOut.model_validate(user.__dict__)

# ---- Backfill hooks (synchronous stub; real job in worker) ----
@router.post("/backfill/start", tags=["backfill"])
def backfill_start(req: BackfillStartRequest) -> Dict[str, Any]:
    return {"status": "queued", "symbols": req.symbols, "tf": req.tf, "years": req.years}

@router.get("/backfill/status", tags=["backfill"])
def backfill_status(job_id: str) -> Dict[str, Any]:
    return {"job_id": job_id, "status": "running", "progress": 42, "eta": "15m"}

# ---- Train ----
@router.post("/train/run", tags=["train"])
def train_run(req: TrainRunRequest) -> Dict[str, Any]:
    return {"status": "started", "job_id": "train-"+ "0001"}

@router.get("/train/status", tags=["train"])
def train_status(job_id: str) -> Dict[str, Any]:
    return {"job_id": job_id, "status": "running", "oos_hit_rate": 0.57}

# ---- Backtest ----
@router.post("/backtest/run", tags=["backtest"])
def backtest_run(req: BacktestRequest) -> Dict[str, Any]:
    summary = run_backtest_sync(req)
    return {"status": "done", "summary": summary}

# ---- Signals ----
@router.post("/signals/generate", tags=["signals"])
def signals_generate(req: SignalPublishRequest) -> Dict[str, Any]:
    ok, expected_net_pct, reason = publish_signal_decision(req.dict())
    return {"ok": ok, "expected_net_pct": expected_net_pct, "reason": reason}
