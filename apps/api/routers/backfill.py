# apps/api/routes/backfill.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.api.deps import db_dep, get_pagination
from apps.api import schemas
from apps.api import crud
from apps.api.ws import ws_manager

router = APIRouter(prefix="/backfill", tags=["backfill"])

@router.post("/start", response_model=schemas.BackfillStartResp)
def backfill_start(req: schemas.BackfillStartReq, db: Session = Depends(db_dep)):
    items = crud.backfill_start(db, req.symbols, req.tf, req.from_ts, req.to_ts)
    # Broadcast info
    try:
        import asyncio
        asyncio.create_task(ws_manager.broadcast({"type": "backfill_started", "tf": req.tf, "symbols": req.symbols}))
    except RuntimeError:
        # When no loop (sync path), ignore
        pass
    return schemas.BackfillStartResp(
        created=len(items),
        items=[
            schemas.BackfillItem(
                id=i.id,
                symbol=i.symbol,
                tf=i.tf,
                last_ts_completed=i.last_ts_completed,
                chunk_start_ts=i.chunk_start_ts,
                chunk_end_ts=i.chunk_end_ts,
                retry_count=i.retry_count,
                status=i.status,
                updated_at=i.updated_at,
            ) for i in items
        ]
    )

@router.get("/status", response_model=schemas.BackfillStatusResp)
def backfill_status(p=Depends(get_pagination), db: Session = Depends(db_dep)):
    total, rows = crud.backfill_list(db, p["limit"], p["offset"])
    items = [
        schemas.BackfillItem(
            id=i.id,
            symbol=i.symbol,
            tf=i.tf,
            last_ts_completed=i.last_ts_completed,
            chunk_start_ts=i.chunk_start_ts,
            chunk_end_ts=i.chunk_end_ts,
            retry_count=i.retry_count,
            status=i.status,
            updated_at=i.updated_at,
        ) for i in rows
    ]
    return schemas.BackfillStatusResp(total=total, items=items)
