from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from apps.api.db import get_db
from apps.api.db.models import BackfillJob, TimeFrame
from apps.ml.backfill import BackfillService
import logging

logger = logging.getLogger(__name__)
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
    total_candles_estimate: Optional[int] = None
    candles_per_minute: Optional[float]
    eta_minutes: Optional[float]
    detected_gaps: Optional[list[dict[str, str]]] = None
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

    # Parse dates and remove timezone info to make them naive (UTC assumed)
    start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))

    # Convert to naive datetime (remove timezone)
    if start_date.tzinfo is not None:
        start_date = start_date.replace(tzinfo=None)
    if end_date.tzinfo is not None:
        end_date = end_date.replace(tzinfo=None)

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


@router.post("/cancel/{job_id}")
async def cancel_backfill(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Cancel a running backfill job"""
    from apps.api.db.models import BackfillJob
    from datetime import datetime

    job = db.query(BackfillJob).filter(BackfillJob.job_id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ['running', 'pending']:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job.status}")

    # Mark job as failed/cancelled
    job.status = 'failed'
    job.error_message = 'Cancelled by user'
    job.completed_at = datetime.utcnow()
    db.commit()

    # Try to revoke Celery task if still running
    try:
        from apps.ml.worker import celery_app
        celery_app.control.revoke(job_id, terminate=True)
    except Exception as e:
        logger.warning(f"Could not revoke Celery task {job_id}: {e}")

    return {"job_id": job_id, "status": "cancelled"}


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


@router.post("/start-all")
async def start_all_backfills(
    db: Session = Depends(get_db)
):
    """Start backfill jobs for all tracked trading pairs"""
    from apps.api.db.models import TimeFrame, OHLCV
    from sqlalchemy import and_
    from datetime import datetime

    # List of trading pairs to track
    TRACKED_PAIRS = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT',
        'ADA/USDT', 'SOL/USDT', 'DOGE/USDT', 'POL/USDT',
        'DOT/USDT', 'AVAX/USDT', 'LINK/USDT', 'UNI/USDT'
    ]

    service = BackfillService(db)
    jobs_created = []
    jobs_skipped = []

    for symbol in TRACKED_PAIRS:
        try:
            # Check if pair already has data
            existing_count = db.query(OHLCV).filter(
                and_(
                    OHLCV.symbol == symbol,
                    OHLCV.timeframe == TimeFrame.M15
                )
            ).count()

            if existing_count > 0:
                jobs_skipped.append({
                    "symbol": symbol,
                    "reason": f"Already has {existing_count} candles"
                })
                continue

            # Get earliest available date from exchange
            earliest_dt = service.client.get_earliest_timestamp(symbol, '15m')
            if not earliest_dt:
                earliest_dt = datetime(2020, 1, 1)  # Fallback to 2020

            end_date = datetime.utcnow()

            # Create backfill job
            job = service.create_backfill_job(
                symbol=symbol,
                timeframe=TimeFrame.M15,
                start_date=earliest_dt,
                end_date=end_date
            )

            # Trigger async backfill
            from apps.ml.worker import execute_backfill_task
            execute_backfill_task.delay(job.job_id)

            jobs_created.append({
                "symbol": symbol,
                "job_id": job.job_id,
                "start_date": earliest_dt.isoformat(),
                "end_date": end_date.isoformat()
            })

        except Exception as e:
            jobs_skipped.append({
                "symbol": symbol,
                "reason": f"Error: {str(e)}"
            })

    return {
        "jobs_created": len(jobs_created),
        "jobs_skipped": len(jobs_skipped),
        "created": jobs_created,
        "skipped": jobs_skipped
    }
