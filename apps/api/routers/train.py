from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from apps.api.db import get_db
from celery.result import AsyncResult
from apps.ml.worker import celery_app
from apps.ml.model_registry import ModelRegistry
from apps.ml.performance_tracker import PerformanceTracker
from datetime import datetime, timedelta

router = APIRouter()


class TrainRequest(BaseModel):
    symbol: str
    timeframe: str
    test_period_days: int = 30
    min_train_days: int = 180
    use_expanding_window: bool = True
    force_retrain: bool = False


class TrainResponse(BaseModel):
    job_id: str
    status: str
    model_id: Optional[str] = None


class TrainingStatus(BaseModel):
    job_id: str
    status: str
    progress_pct: Optional[float] = None
    labeling_progress_pct: Optional[float] = None
    current_fold: Optional[int] = None
    total_folds: Optional[int] = None
    accuracy: Optional[float] = None
    hit_rate_tp1: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    error_message: Optional[str] = None


class ModelInfo(BaseModel):
    model_id: str
    version: str
    symbol: str
    timeframe: str
    metrics: Dict[str, Any]
    registered_at: str
    status: str


class DeploymentRequest(BaseModel):
    symbol: str
    timeframe: str
    version: str
    environment: str = "production"


@router.post("/start", response_model=TrainResponse)
async def start_training(request: TrainRequest, db: Session = Depends(get_db)):
    """
    Start model training with walk-forward validation using expanding windows.

    Trains on ALL available historical data by default (expanding window mode).
    """
    from apps.ml.worker import train_model_task

    # Trigger Celery task
    task = train_model_task.delay(
        symbol=request.symbol,
        timeframe=request.timeframe,
        test_period_days=request.test_period_days,
        min_train_days=request.min_train_days,
        use_expanding_window=request.use_expanding_window
    )

    return TrainResponse(
        job_id=task.id,
        status="queued",
        model_id=None
    )


@router.get("/status/{job_id}", response_model=TrainingStatus)
async def get_training_status(job_id: str, db: Session = Depends(get_db)):
    """Get training job status from database and Celery"""
    from apps.api.db.models import TrainingJob

    # Try to get from database first
    training_job = db.query(TrainingJob).filter_by(job_id=job_id).first()

    if training_job:
        # Return data from database (most reliable)
        response = TrainingStatus(
            job_id=job_id,
            status=training_job.status,
            progress_pct=training_job.progress_pct,
            labeling_progress_pct=training_job.labeling_progress_pct,
            current_fold=training_job.current_fold,
            total_folds=training_job.total_folds,
            accuracy=training_job.accuracy,
            hit_rate_tp1=training_job.hit_rate_tp1,
            elapsed_seconds=training_job.elapsed_seconds,
            error_message=training_job.error_message
        )
        return response

    # Fallback to Celery if not in database yet
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


@router.post("/cancel/{job_id}")
async def cancel_training(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running training job"""
    from apps.api.db.models import TrainingJob
    from datetime import datetime

    # Get job from database
    job = db.query(TrainingJob).filter_by(job_id=job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ['training', 'pending', 'queued']:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status: {job.status}")

    # Mark job as failed/cancelled
    job.status = 'failed'
    job.error_message = 'Cancelled by user'
    job.completed_at = datetime.utcnow()
    db.commit()

    # Try to revoke Celery task
    try:
        celery_app.control.revoke(job_id, terminate=True, signal='SIGKILL')
    except Exception as e:
        print(f"Could not revoke Celery task {job_id}: {e}")

    return {"job_id": job_id, "status": "cancelled"}


@router.get("/jobs", response_model=List[TrainingStatus])
async def list_training_jobs(db: Session = Depends(get_db)):
    """List all recent training jobs from database"""
    from apps.api.db.models import TrainingJob
    from datetime import datetime, timedelta

    # Get jobs from last 3 hours
    cutoff = datetime.utcnow() - timedelta(hours=3)
    jobs = db.query(TrainingJob).filter(
        TrainingJob.created_at >= cutoff
    ).order_by(TrainingJob.created_at.desc()).all()

    return [
        TrainingStatus(
            job_id=job.job_id,
            status=job.status,
            progress_pct=job.progress_pct,
            labeling_progress_pct=job.labeling_progress_pct,
            current_fold=job.current_fold,
            total_folds=job.total_folds,
            accuracy=job.accuracy,
            hit_rate_tp1=job.hit_rate_tp1,
            elapsed_seconds=job.elapsed_seconds,
            error_message=job.error_message
        )
        for job in jobs
    ]


@router.get("/models", response_model=List[ModelInfo])
async def list_models(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None)
):
    """List all registered models"""
    registry = ModelRegistry()
    models = registry.list_models(symbol=symbol, timeframe=timeframe)

    return [
        ModelInfo(
            model_id=m['model_id'],
            version=m['version'],
            symbol=m['symbol'],
            timeframe=m['timeframe'],
            metrics=m['metrics'],
            registered_at=m['registered_at'],
            status=m['status']
        )
        for m in models
    ]


@router.get("/models/{symbol}/{timeframe}/best")
async def get_best_model(
    symbol: str,
    timeframe: str,
    metric: str = Query("avg_roc_auc")
):
    """Get best model by metric"""
    registry = ModelRegistry()
    best = registry.get_best_model(symbol, timeframe, metric=metric)

    if not best:
        raise HTTPException(status_code=404, detail="No models found")

    return best


@router.get("/models/{symbol}/{timeframe}/deployed")
async def get_deployed_model(
    symbol: str,
    timeframe: str,
    environment: str = Query("production")
):
    """Get currently deployed model"""
    registry = ModelRegistry()
    deployed = registry.get_deployed_model(symbol, timeframe, environment=environment)

    if not deployed:
        raise HTTPException(status_code=404, detail="No deployed model found")

    return deployed


@router.post("/models/deploy")
async def deploy_model(request: DeploymentRequest):
    """Deploy a model version to an environment"""
    registry = ModelRegistry()

    success = registry.deploy_model(
        symbol=request.symbol,
        timeframe=request.timeframe,
        version=request.version,
        environment=request.environment
    )

    if not success:
        raise HTTPException(status_code=400, detail="Deployment failed")

    return {"status": "deployed", "version": request.version, "environment": request.environment}


@router.post("/models/{symbol}/{timeframe}/rollback")
async def rollback_deployment(
    symbol: str,
    timeframe: str,
    environment: str = Query("production")
):
    """Rollback deployment to previous version"""
    registry = ModelRegistry()

    success = registry.rollback_deployment(symbol, timeframe, environment=environment)

    if not success:
        raise HTTPException(status_code=400, detail="Rollback failed")

    return {"status": "rolled_back", "environment": environment}


@router.get("/models/{symbol}/{timeframe}/compare")
async def compare_models(
    symbol: str,
    timeframe: str,
    version1: str = Query(...),
    version2: str = Query(...)
):
    """Compare two model versions"""
    registry = ModelRegistry()
    comparison = registry.compare_models(symbol, timeframe, version1, version2)

    if 'error' in comparison:
        raise HTTPException(status_code=404, detail=comparison['error'])

    return comparison


@router.get("/models/{model_id}/performance")
async def get_model_performance(
    model_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """Get performance summary for a model"""
    tracker = PerformanceTracker()

    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    summary = tracker.get_performance_summary(model_id, start_date=start, end_date=end)

    if 'error' in summary:
        raise HTTPException(status_code=404, detail=summary['error'])

    return summary


@router.get("/models/{model_id}/degradation")
async def check_degradation(
    model_id: str,
    metric: str = Query("roc_auc"),
    window_days: int = Query(7),
    threshold_pct: float = Query(10.0)
):
    """Check for performance degradation"""
    tracker = PerformanceTracker()

    degradation = tracker.detect_performance_degradation(
        model_id=model_id,
        metric=metric,
        window_days=window_days,
        threshold_pct=threshold_pct
    )

    return degradation


@router.post("/models/{model_id}/report")
async def generate_performance_report(model_id: str):
    """Generate comprehensive performance report"""
    tracker = PerformanceTracker()

    report_path = tracker.generate_performance_report(model_id)

    if not report_path:
        raise HTTPException(status_code=500, detail="Report generation failed")

    return {"report_path": report_path}
