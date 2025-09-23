# apps/api/routes/signals.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Literal
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
from apps.api.services.signals_service import evaluate_and_publish
from apps.api.db import models
from sqlalchemy import select, desc
import asyncio
import os
import time

router = APIRouter(prefix="/signals", tags=["signals"])

# --- 1) Ręczna publikacja (zachowane) ---

@router.post("/generate", response_model=schemas.SignalItem)
def signals_generate(req: schemas.SignalCreateReq, db: Session = Depends(db_dep)):
    # Twardy filtr ≥ 2% będzie wymuszony w auto-generacji; tu zakładamy, że payload jest po filtrze.
    obj = crud.signal_create(db, req.dict())
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "signal_published", "signal_id": obj.id, "symbol": obj.symbol, "dir": obj.dir}))
    except RuntimeError:
        pass
    return schemas.SignalItem(
        id=obj.id, symbol=obj.symbol, tf_base=obj.tf_base, ts=obj.ts, dir=obj.dir, entry=obj.entry,
        tp=obj.tp, sl=obj.sl, lev=obj.lev, risk=obj.risk, margin_mode=obj.margin_mode,
        expected_net_pct=obj.expected_net_pct, confidence=obj.confidence, model_ver=obj.model_ver,
        reason_discard=obj.reason_discard, status=obj.status
    )

# --- 2) Historia ---

@router.get("/history", response_model=schemas.SignalsListResp)
def signals_history(
    symbol: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    p=Depends(get_pagination),
    db: Session = Depends(db_dep),
):
    total, rows = crud.signals_list(db, symbol, status, p["limit"], p["offset"])
    items = [
        schemas.SignalItem(
            id=o.id, symbol=o.symbol, tf_base=o.tf_base, ts=o.ts, dir=o.dir, entry=o.entry,
            tp=o.tp, sl=o.sl, lev=o.lev, risk=o.risk, margin_mode=o.margin_mode,
            expected_net_pct=o.expected_net_pct, confidence=o.confidence, model_ver=o.model_ver,
            reason_discard=o.reason_discard, status=o.status
        ) for o in rows
    ]
    return schemas.SignalsListResp(total=total, items=items)

# --- 3) AUTO – generacja i publikacja wg silnika + polityk ryzyka ---

from pydantic import BaseModel, Field

class AutoSignalReq(BaseModel):
    symbol: str
    tf_base: Literal["15m","1h","4h"] = "15m"
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
    direction: Literal["LONG","SHORT"]
    close: float
    atr: float
    fibo: Optional[dict] = None                # np. {"fibo_382": 64000.0, "fibo_618": 63500.0}
    desired_leverage: float = 3.0
    risk: Literal["LOW","MED","HIGH"] = "LOW"
    capital: Optional[float] = None
    confidence: Optional[float] = None
    margin_mode: Literal["ISOLATED","CROSS"] = "ISOLATED"

@router.post("/auto", response_model=schemas.SignalItem)
def signals_auto(req: AutoSignalReq, db: Session = Depends(db_dep)):
    capital = req.capital if req.capital and req.capital > 0 else float(os.getenv("DEFAULT_CAPITAL", "100"))
    sig, reason = evaluate_and_publish(
        db=db,
        symbol=req.symbol,
        tf_base=req.tf_base,
        ts=req.ts,
        direction=req.direction,
        close=req.close,
        atr_val=req.atr,
        fib_levels=req.fibo,
        desired_leverage=req.desired_leverage,
        risk=req.risk,
        capital=capital,
        confidence=req.confidence,
        margin_mode=req.margin_mode,
    )
    if sig is None:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": reason})
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "signal_published", "signal_id": sig.id, "symbol": sig.symbol, "dir": sig.dir}))
    except RuntimeError:
        pass
    return schemas.SignalItem(
        id=sig.id, symbol=sig.symbol, tf_base=sig.tf_base, ts=sig.ts, dir=sig.dir, entry=sig.entry,
        tp=sig.tp, sl=sig.sl, lev=sig.lev, risk=sig.risk, margin_mode=sig.margin_mode,
        expected_net_pct=sig.expected_net_pct, confidence=sig.confidence, model_ver=sig.model_ver,
        reason_discard=sig.reason_discard, status=sig.status
    )
