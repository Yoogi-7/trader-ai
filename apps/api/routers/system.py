from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from apps.api.db import get_db
from apps.api.db.models import ModelRegistry, TradeResult, Signal, OHLCV, TimeFrame
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class SystemStatusResponse(BaseModel):
    hit_rate_tp1: Optional[float] = None
    avg_net_profit_pct: Optional[float] = None
    active_models: int = 0
    total_signals: int = 0
    total_trades: int = 0
    win_rate: Optional[float] = None


class CandleInfo(BaseModel):
    symbol: str
    timeframe: str
    total_candles: int
    first_candle: Optional[str] = None
    last_candle: Optional[str] = None


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


@router.get("/candles", response_model=List[CandleInfo])
async def get_candles_info(db: Session = Depends(get_db)):
    """Get candle database info for all tracked trading pairs"""

    # List of tracked pairs (same as in worker.py)
    TRACKED_PAIRS = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT',
        'ADA/USDT', 'SOL/USDT', 'DOGE/USDT', 'POL/USDT',
        'DOT/USDT', 'AVAX/USDT', 'LINK/USDT', 'UNI/USDT'
    ]

    result = []

    for symbol in TRACKED_PAIRS:
        # Get candle count
        count = db.query(OHLCV).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == TimeFrame.M15
            )
        ).count()

        # Get first and last candle timestamps
        first_candle = db.query(OHLCV.timestamp).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == TimeFrame.M15
            )
        ).order_by(OHLCV.timestamp.asc()).first()

        last_candle = db.query(OHLCV.timestamp).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == TimeFrame.M15
            )
        ).order_by(OHLCV.timestamp.desc()).first()

        result.append(CandleInfo(
            symbol=symbol,
            timeframe='15m',
            total_candles=count,
            first_candle=first_candle[0].isoformat() if first_candle else None,
            last_candle=last_candle[0].isoformat() if last_candle else None
        ))

    return result
