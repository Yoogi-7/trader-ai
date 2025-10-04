from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from apps.api.db import get_db
from celery.result import AsyncResult
from apps.ml.worker import celery_app

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
    elapsed_seconds: Optional[float] = None
    error_message: Optional[str] = None


@router.post("/start", response_model=TrainResponse)
async def start_training(request: TrainRequest, db: Session = Depends(get_db)):
    """Start model training (async via Celery)"""
    from apps.ml.worker import train_model_task

    # Trigger Celery task
    task = train_model_task.delay(
        symbol=request.symbol,
        timeframe=request.timeframe,
        lookback_days=1460  # ~4 years of data
    )

    return TrainResponse(
        job_id=task.id,
        status="queued",
        model_id=None
    )


@router.get("/status/{job_id}", response_model=TrainingStatus)
async def get_training_status(job_id: str):
    """Get training job status from Celery"""
    task_result = AsyncResult(job_id, app=celery_app)

    status_map = {
        'PENDING': 'queued',
        'STARTED': 'training',
        'SUCCESS': 'completed',
        'FAILURE': 'failed',
        'RETRY': 'training',
        'REVOKED': 'cancelled'
    }

    status = status_map.get(task_result.state, 'unknown')

    # Build response
    response = TrainingStatus(
        job_id=job_id,
        status=status
    )

    # If task has metadata (progress info), include it
    if task_result.info and isinstance(task_result.info, dict):
        response.progress_pct = task_result.info.get('progress_pct')
        response.current_fold = task_result.info.get('current_fold')
        response.total_folds = task_result.info.get('total_folds')
        response.accuracy = task_result.info.get('accuracy')
        response.hit_rate_tp1 = task_result.info.get('hit_rate_tp1')
        response.elapsed_seconds = task_result.info.get('elapsed_seconds')

    # If failed, include error
    if task_result.state == 'FAILURE':
        response.error_message = str(task_result.info)

    return response
