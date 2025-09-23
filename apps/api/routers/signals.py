# apps/api/routes/signals.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
import asyncio

router = APIRouter(prefix="/signals", tags=["signals"])

@router.post("/generate", response_model=schemas.SignalItem)
def signals_generate(req: schemas.SignalCreateReq, db: Session = Depends(db_dep)):
    # P5 wprowadzi twardy filtr >= 2% po kosztach i funding.
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
