from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from apps.api.db import get_db
from apps.api.db.models import ModelRegistry, TradeResult, Signal
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SystemStatusResponse(BaseModel):
    hit_rate_tp1: Optional[float] = None
    avg_net_profit_pct: Optional[float] = None
    active_models: int = 0
    total_signals: int = 0
    total_trades: int = 0
    win_rate: Optional[float] = None


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    """Get real-time system status metrics"""

    # Count active models
    active_models = db.query(ModelRegistry).filter(
        ModelRegistry.is_active == True
    ).count()

    # Get hit rate from active models (average)
    hit_rate_query = db.query(
        func.avg(ModelRegistry.hit_rate_tp1)
    ).filter(
        ModelRegistry.is_active == True,
        ModelRegistry.hit_rate_tp1.isnot(None)
    ).scalar()

    # Get average net profit from active models
    avg_profit_query = db.query(
        func.avg(ModelRegistry.avg_net_profit_pct)
    ).filter(
        ModelRegistry.is_active == True,
        ModelRegistry.avg_net_profit_pct.isnot(None)
    ).scalar()

    # Count total signals
    total_signals = db.query(Signal).count()

    # Count total trades with results
    total_trades = db.query(TradeResult).count()

    # Calculate win rate from actual trade results
    profitable_trades = db.query(TradeResult).filter(
        TradeResult.net_pnl_pct > 0
    ).count()

    win_rate = None
    if total_trades > 0:
        win_rate = profitable_trades / total_trades

    return SystemStatusResponse(
        hit_rate_tp1=hit_rate_query if hit_rate_query else None,
        avg_net_profit_pct=avg_profit_query if avg_profit_query else None,
        active_models=active_models,
        total_signals=total_signals,
        total_trades=total_trades,
        win_rate=win_rate
    )
