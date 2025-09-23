# apps/api/routes/train.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas, crud
from apps.api.ws import ws_manager
import asyncio

router = APIRouter(prefix="/train", tags=["train"])

@router.post("/run", response_model=schemas.TrainRunResp)
def train_run(req: schemas.TrainRunReq, db: Session = Depends(db_dep)):
    run_id = crud.train_run_create(db, req.params)
    try:
        asyncio.create_task(ws_manager.broadcast({"type": "train_started", "run_id": run_id}))
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
