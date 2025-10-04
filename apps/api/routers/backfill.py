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
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None

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

    # Trigger Celery task to execute backfill
    from apps.ml.worker import execute_backfill_task
    execute_backfill_task.delay(job.job_id)

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


@router.get("/jobs", response_model=list[BackfillStatus])
async def list_backfill_jobs(
    db: Session = Depends(get_db),
    limit: int = 10
):
    """List recent backfill jobs"""
    from apps.api.db.models import BackfillJob

    jobs = db.query(BackfillJob).order_by(BackfillJob.created_at.desc()).limit(limit).all()

    service = BackfillService(db)
    return [service.get_job_status(job.job_id) for job in jobs if service.get_job_status(job.job_id)]


@router.get("/earliest")
async def get_earliest_available_date(
    symbol: str,
    timeframe: str,
    db: Session = Depends(get_db)
):
    """Get earliest available date for a symbol and timeframe from the exchange"""
    service = BackfillService(db)

    earliest_dt = service.client.get_earliest_timestamp(symbol, timeframe)

    if earliest_dt:
        return {"earliest_date": earliest_dt.isoformat(), "symbol": symbol, "timeframe": timeframe}
    else:
        # Fallback to a reasonable default if unable to fetch
        return {"earliest_date": "2017-01-01T00:00:00", "symbol": symbol, "timeframe": timeframe}
