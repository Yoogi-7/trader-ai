"""
Auto-Training API Endpoints

Provides API control for the continuous auto-training system:
- Start/stop auto-training
- Get status
- Configure parameters
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from apps.api.db.session import get_db
from apps.api.db.models import AutoTrainingConfig, TimeFrame
from apps.ml.auto_trainer import AutoTrainer
from apps.ml.worker import auto_train_task

router = APIRouter(prefix="/auto-train", tags=["auto-training"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AutoTrainStartRequest(BaseModel):
    """Request to start auto-training"""
    symbols: Optional[List[str]] = None
    timeframe: str = "15m"
    quick_start: bool = True


class AutoTrainConfigResponse(BaseModel):
    """Auto-training configuration response"""
    enabled: bool
    symbols: List[str]
    timeframe: str
    quick_mode: bool
    current_generation: Optional[int] = None
    best_score: Optional[float] = None


class AutoTrainStatusResponse(BaseModel):
    """Auto-training status response"""
    enabled: bool
    symbols: List[str]
    timeframe: str
    quick_mode: bool
    last_updated: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/start", response_model=dict)
def start_auto_training(
    request: AutoTrainStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start continuous auto-training system.

    This will:
    1. Perform quick initial training for immediate signal generation
    2. Continue with full training cycles every 12 hours
    3. Evolve parameters to optimize for 1% min return and 60% accuracy
    """
    trainer = AutoTrainer(db)

    result = trainer.start_auto_training(
        symbols=request.symbols,
        timeframe=request.timeframe,
        quick_start=request.quick_start
    )

    # Trigger immediate training cycle
    auto_train_task.delay()

    return {
        **result,
        "message": "Auto-training started successfully. Initial training triggered."
    }


@router.post("/stop", response_model=dict)
def stop_auto_training(db: Session = Depends(get_db)):
    """
    Stop continuous auto-training system.

    Current training jobs will complete, but no new ones will be started.
    """
    trainer = AutoTrainer(db)
    result = trainer.stop_auto_training()

    return {
        **result,
        "message": "Auto-training stopped successfully"
    }


@router.get("/status", response_model=AutoTrainStatusResponse)
def get_auto_training_status(db: Session = Depends(get_db)):
    """
    Get current auto-training status and configuration.
    """
    config = db.query(AutoTrainingConfig).first()

    if not config:
        return AutoTrainStatusResponse(
            enabled=False,
            symbols=[],
            timeframe="15m",
            quick_mode=False,
            last_updated=None
        )

    timeframe_value = config.timeframe.value if hasattr(config.timeframe, 'value') else str(config.timeframe)

    return AutoTrainStatusResponse(
        enabled=config.enabled,
        symbols=config.symbols or [],
        timeframe=timeframe_value,
        quick_mode=config.quick_mode,
        last_updated=config.last_updated.isoformat() if config.last_updated else None
    )


@router.get("/config", response_model=AutoTrainConfigResponse)
def get_auto_training_config(db: Session = Depends(get_db)):
    """
    Get detailed auto-training configuration including evolution stats.
    """
    config = db.query(AutoTrainingConfig).first()

    if not config:
        raise HTTPException(status_code=404, detail="Auto-training not configured")

    timeframe_value = config.timeframe.value if hasattr(config.timeframe, 'value') else str(config.timeframe)

    return AutoTrainConfigResponse(
        enabled=config.enabled,
        symbols=config.symbols or [],
        timeframe=timeframe_value,
        quick_mode=config.quick_mode,
        current_generation=config.current_generation,
        best_score=config.best_score
    )


@router.post("/trigger", response_model=dict)
def trigger_training_cycle(db: Session = Depends(get_db)):
    """
    Manually trigger an auto-training cycle immediately.

    Useful for testing or forcing a retrain.
    """
    trainer = AutoTrainer(db)

    if not trainer.is_training_enabled():
        raise HTTPException(
            status_code=400,
            detail="Auto-training is disabled. Enable it first with POST /auto-train/start"
        )

    # Trigger task
    result = auto_train_task.delay()

    return {
        "status": "triggered",
        "task_id": result.id,
        "message": "Training cycle triggered successfully"
    }


@router.put("/config", response_model=AutoTrainConfigResponse)
def update_auto_training_config(
    request: AutoTrainStartRequest,
    db: Session = Depends(get_db)
):
    """
    Update auto-training configuration without stopping/starting.
    """
    config = db.query(AutoTrainingConfig).first()

    if not config:
        raise HTTPException(status_code=404, detail="Auto-training not configured. Use POST /start first.")

    # Update configuration
    if request.symbols is not None:
        config.symbols = request.symbols

    if request.timeframe:
        config.timeframe = TimeFrame(request.timeframe)

    if request.quick_start is not None:
        config.quick_mode = request.quick_start

    from datetime import datetime
    config.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(config)

    timeframe_value = config.timeframe.value if hasattr(config.timeframe, 'value') else str(config.timeframe)

    return AutoTrainConfigResponse(
        enabled=config.enabled,
        symbols=config.symbols or [],
        timeframe=timeframe_value,
        quick_mode=config.quick_mode,
        current_generation=config.current_generation,
        best_score=config.best_score
    )
