from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from apps.api.db import get_db
from apps.api.db.models import BackfillJob, TimeFrame
from apps.ml.backfill import BackfillService

router = APIRouter()


class BackfillRequest(BaseModel):
    symbol: str
    timeframe: TimeFrame
    start_date: str
    end_date: str


class BackfillStatus(BaseModel):
    job_id: str
    symbol: str
    timeframe: str
    status: str
    progress_pct: float
    candles_fetched: int
    candles_per_minute: Optional[float]
    eta_minutes: Optional[float]

    class Config:
        from_attributes = True


@router.post("/start")
async def start_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a backfill job"""
    service = BackfillService(db)

    start_date = datetime.fromisoformat(request.start_date)
    end_date = datetime.fromisoformat(request.end_date)

    job = service.create_backfill_job(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_date=start_date,
        end_date=end_date
    )

    # In production, this would be a Celery task
    # background_tasks.add_task(service.execute_backfill, job)

    return {"job_id": job.job_id, "status": "started"}


@router.get("/status/{job_id}", response_model=BackfillStatus)
async def get_backfill_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get backfill job status"""
    service = BackfillService(db)
    status = service.get_job_status(job_id)

    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    return status
