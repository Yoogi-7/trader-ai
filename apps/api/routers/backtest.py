# apps/api/routes/backtest.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
import asyncio

router = APIRRouter = APIRouter(prefix="/backtest", tags=["backtest"])

@router.post("/run", response_model=schemas.BacktestRunResp)
def backtest_run(req: schemas.BacktestRunReq, db: Session = Depends(db_dep)):
    bt_id = crud.backtest_run_create(db, req.params)
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "backtest_started", "backtest_id": bt_id}))
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
