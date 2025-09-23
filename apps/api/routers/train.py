# apps/api/routes/train.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
from apps.ml.training import walkforward_tune_and_backtest, save_training_result
from apps.ml.registry import save_artifact
import asyncio, time, os

router = APIRouter(prefix="/train", tags=["train"])

@router.post("/run", response_model=schemas.TrainRunResp)
def train_run(req: schemas.TrainRunReq, db: Session = Depends(db_dep)):
    run_id = crud.train_run_create(db, req.params)
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "train_started", "run_id": run_id}))
    except RuntimeError:
        pass

    # Uruchom WF + tuning synchronicznie (na teraz) – P8 przeniesiemy do workerów.
    sym = req.params.get("symbol", "BTC/USDT")
    tf = req.params.get("tf", "15m")
    start_ts = int(req.params.get("start_ts", 0))
    end_ts = int(req.params.get("end_ts", time.time()*1000))
    n_folds = int(req.params.get("n_folds", 5))
    capital = float(req.params.get("capital", float(os.getenv("DEFAULT_CAPITAL","100"))))
    risk = req.params.get("risk", "LOW")

    summary = walkforward_tune_and_backtest(db, sym, tf, start_ts, end_ts, n_folds, capital, risk)
    save_training_result(db, run_id, summary)

    # Zapis do registry
    if summary.get("ok"):
        version = save_artifact("strategy", {"params": req.params, "summary": summary})
        try:
            asyncio.create_task(ws_manager.broadcast({"type": "train_finished", "run_id": run_id, "version": version, "ok": True}))
        except RuntimeError:
            pass
    else:
        try:
            asyncio.create_task(ws_manager.broadcast({"type": "train_finished", "run_id": run_id, "ok": False}))
        except RuntimeError:
            pass

    return schemas.TrainRunResp(created_id=run_id)

@router.get("/status", response_model=schemas.TrainStatusResp)
def train_status(p=Depends(get_pagination), db: Session = Depends(db_dep)):
    total, rows = crud.train_list(db, p["limit"], p["offset"])
    items = [
        schemas.TrainRunItem(
            id=r.id,
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            params_json=r.params_json,
            metrics_json=r.metrics_json,
        ) for r in rows
    ]
    return schemas.TrainStatusResp(total=total, items=items)
