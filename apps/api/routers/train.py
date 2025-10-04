from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class TrainRequest(BaseModel):
    symbol: str
    timeframe: str
    force_retrain: bool = False


class TrainResponse(BaseModel):
    model_id: str
    status: str
    accuracy: float
    hit_rate_tp1: float


@router.post("/start", response_model=TrainResponse)
async def start_training(request: TrainRequest):
    """Start model training (async via Celery in production)"""
    # Placeholder
    return TrainResponse(
        model_id="model_btc_15m_v1",
        status="training",
        accuracy=0.62,
        hit_rate_tp1=0.57
    )
