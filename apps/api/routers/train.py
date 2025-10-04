from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class TrainRequest(BaseModel):
    symbol: str
    timeframe: str
    force_retrain: bool = False


class TrainResponse(BaseModel):
    job_id: str
    status: str
    model_id: Optional[str] = None


class TrainingStatus(BaseModel):
    job_id: str
    status: str
    progress_pct: Optional[float] = None
    current_fold: Optional[int] = None
    total_folds: Optional[int] = None
    accuracy: Optional[float] = None
    hit_rate_tp1: Optional[float] = None


@router.post("/start", response_model=TrainResponse)
async def start_training(request: TrainRequest):
    """Start model training (async via Celery in production)"""
    job_id = f"train_{request.symbol.replace('/', '_')}_{request.timeframe}"

    # In production, this would trigger a Celery task
    # For now, return a job_id that can be used to query status
    return TrainResponse(
        job_id=job_id,
        status="queued",
        model_id=None
    )


@router.get("/status/{job_id}", response_model=TrainingStatus)
async def get_training_status(job_id: str):
    """Get training job status"""
    # Placeholder - in production, this would query Celery task status
    # or database for the actual training job status

    # Simulating a training job in progress
    return TrainingStatus(
        job_id=job_id,
        status="training",
        progress_pct=45.0,
        current_fold=3,
        total_folds=5,
        accuracy=0.62,
        hit_rate_tp1=0.57
    )
