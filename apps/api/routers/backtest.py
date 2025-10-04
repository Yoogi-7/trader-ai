from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from apps.ml.backtest import Backtester
from apps.api.db.models import RiskProfile

router = APIRouter()


class BacktestRequest(BaseModel):
    capital: float = 100.0
    risk_profile: RiskProfile = RiskProfile.MEDIUM
    symbols: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class BacktestResponse(BaseModel):
    total_trades: int
    final_equity: float
    total_return_pct: float
    win_rate: float
    hit_rate_tp1: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """
    Run backtest simulation.
    Note: In production, this would fetch signals from DB and market data.
    """
    # Placeholder response (actual implementation would run full backtest)
    return BacktestResponse(
        total_trades=50,
        final_equity=request.capital * 1.25,
        total_return_pct=25.0,
        win_rate=60.0,
        hit_rate_tp1=58.0,
        profit_factor=1.8,
        max_drawdown_pct=12.5,
        sharpe_ratio=1.4
    )
