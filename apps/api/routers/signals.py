from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime, timedelta
from apps.api.db import get_async_db
from apps.api.db.models import Signal, RiskProfile, SignalStatus
from pydantic import BaseModel

router = APIRouter()


class SignalResponse(BaseModel):
    signal_id: str
    symbol: str
    side: str
    entry_price: float
    tp1_price: float
    tp2_price: float
    tp3_price: float
    sl_price: float
    leverage: float
    position_size_usd: float
    confidence: float
    expected_net_profit_pct: float
    risk_profile: str
    timestamp: datetime
    valid_until: datetime

    class Config:
        from_attributes = True


@router.get("/live", response_model=List[SignalResponse])
async def get_live_signals(
    risk_profile: Optional[RiskProfile] = Query(None),
    symbols: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get active signals filtered by risk profile and symbols.
    """
    query = select(Signal).where(
        and_(
            Signal.status == SignalStatus.PENDING,
            Signal.valid_until > datetime.utcnow(),
            Signal.passed_profit_filter == True
        )
    )

    if risk_profile:
        query = query.where(Signal.risk_profile == risk_profile)

    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",")]
        query = query.where(Signal.symbol.in_(symbol_list))

    query = query.order_by(Signal.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()

    return signals


@router.get("/history", response_model=List[SignalResponse])
async def get_signal_history(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_async_db)
):
    """Get historical signals"""
    query = select(Signal).order_by(Signal.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    signals = result.scalars().all()

    return signals


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get a specific signal by ID"""
    query = select(Signal).where(Signal.signal_id == signal_id)
    result = await db.execute(query)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return signal
