# apps/api/routes/backtest.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
from apps.api.db import models
from apps.ml.backtest import backtest_signals, BTParams, load_bars
from sqlalchemy import select
import asyncio, time, os
from typing import Dict, Any

router = APIRouter(prefix="/backtest", tags=["backtest"])

@router.post("/run", response_model=schemas.BacktestRunResp)
def backtest_run(req: schemas.BacktestRunReq, db: Session = Depends(db_dep)):
    bt_id = crud.backtest_run_create(db, req.params)
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "backtest_started", "backtest_id": bt_id}))
    except RuntimeError:
        pass

    # Parametry
    sym = req.params.get("symbol", "BTC/USDT")
    tf = req.params.get("tf", "15m")
    start_ts = int(req.params.get("start_ts", 0))
    end_ts = int(req.params.get("end_ts", time.time()*1000))
    capital = float(req.params.get("capital", float(os.getenv("DEFAULT_CAPITAL","100"))))
    risk = req.params.get("risk", "LOW")
    funding_rate_hourly = float(req.params.get("funding_rate_hourly", 0.0))
    slippage_bps = float(req.params.get("slippage_bps", float(os.getenv("SLIPPAGE_BPS","10"))))
    time_stop_min = int(req.params.get("time_stop_min", 240))
    taker_only = bool(req.params.get("taker_only", True))
    trailing_offset_pct = float(req.params.get("trailing_offset_pct", 0.002))

    # Dane
    bars = load_bars(db, sym, tf, start_ts, end_ts)
    if not bars:
        raise HTTPException(status_code=400, detail="no_bars_in_range")

    q = select(models.Signal).where(
        models.Signal.symbol == sym,
        models.Signal.tf_base == tf,
        models.Signal.ts >= start_ts,
        models.Signal.ts <= end_ts,
        models.Signal.status == "published",
    ).order_by(models.Signal.ts.asc())
    signals = list(db.execute(q).scalars().all())
    if not signals:
        raise HTTPException(status_code=400, detail="no_signals_in_range")

    bt_params = BTParams(
        capital=capital,
        risk=risk,
        taker_only=taker_only,
        funding_rate_hourly=funding_rate_hourly,
        slippage_bps=slippage_bps,
        time_stop_min=time_stop_min,
        trailing_offset_pct=trailing_offset_pct,
    )

    trades, metrics = backtest_signals(db, sym, tf, signals, bt_params, bars)

    # Zapis do DB (summary)
    summary: Dict[str, Any] = {
        "symbol": sym, "tf": tf, "params": req.params, "metrics": metrics
    }
    bt = db.get(models.Backtest, bt_id)
    if bt:
        bt.finished_at = int(time.time()*1000)
        bt.summary_json = summary
        db.commit()

    try:
        asyncio.create_task(ws_manager.broadcast({"type": "backtest_finished", "backtest_id": bt_id, "ok": True}))
    except RuntimeError:
        pass

    return schemas.BacktestRunResp(created_id=bt_id)

@router.get("/results", response_model=schemas.BacktestResultsResp)
def backtest_results(p=Depends(get_pagination), db: Session = Depends(db_dep)):
    total, rows = crud.backtest_list(db, p["limit"], p["offset"])
    items = [
        schemas.BacktestItem(
            id=b.id, started_at=b.started_at, finished_at=b.finished_at, summary_json=b.summary_json
        ) for b in rows
    ]
    return schemas.BacktestResultsResp(total=total, items=items)
