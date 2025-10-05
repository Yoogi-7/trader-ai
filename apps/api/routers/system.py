from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from apps.api.db import get_db
from apps.api.db.models import ModelRegistry, TradeResult, Signal, OHLCV, TimeFrame, TrackedPair
from apps.common.tracked_pairs import (
    bump_tracked_pairs_version,
    get_tracked_pairs,
    invalidate_tracked_pairs_cache,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class TrackedPairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    timeframe: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TrackedPairCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., description="Trading pair symbol (e.g. BTC/USDT)")
    timeframe: TimeFrame = Field(TimeFrame.M15)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if "/" not in normalized:
            raise ValueError("Symbol must include '/' separator")
        return normalized


class TrackedPairUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Optional[str] = Field(None, description="Updated trading pair symbol")
    timeframe: Optional[TimeFrame] = Field(None, description="Updated timeframe")
    is_active: Optional[bool] = Field(None, description="Toggle whether the pair is active")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if "/" not in normalized:
            raise ValueError("Symbol must include '/' separator")
        return normalized


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

    result = []

    for tracked_pair in get_tracked_pairs(db, use_cache=False):
        symbol = tracked_pair.symbol
        timeframe_enum = tracked_pair.timeframe
        # Get candle count
        count = db.query(OHLCV).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe_enum
            )
        ).count()

        # Get first and last candle timestamps
        first_candle = db.query(OHLCV.timestamp).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe_enum
            )
        ).order_by(OHLCV.timestamp.asc()).first()

        last_candle = db.query(OHLCV.timestamp).filter(
            and_(
                OHLCV.symbol == symbol,
                OHLCV.timeframe == timeframe_enum
            )
        ).order_by(OHLCV.timestamp.desc()).first()

        result.append(CandleInfo(
            symbol=symbol,
            timeframe=timeframe_enum.value,
            total_candles=count,
            first_candle=first_candle[0].isoformat() if first_candle else None,
            last_candle=last_candle[0].isoformat() if last_candle else None
        ))

    return result


@router.get("/tracked-pairs", response_model=List[TrackedPairResponse])
async def list_tracked_pairs(db: Session = Depends(get_db)):
    pairs = (
        db.query(TrackedPair)
        .order_by(TrackedPair.symbol.asc(), TrackedPair.timeframe.asc())
        .all()
    )
    return pairs


@router.post(
    "/tracked-pairs",
    response_model=TrackedPairResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tracked_pair(
    payload: TrackedPairCreateRequest,
    db: Session = Depends(get_db),
):
    normalized_symbol = payload.symbol
    timeframe = payload.timeframe

    existing = (
        db.query(TrackedPair)
        .filter(
            TrackedPair.symbol == normalized_symbol,
            TrackedPair.timeframe == timeframe,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tracked pair already exists",
        )

    pair = TrackedPair(
        symbol=normalized_symbol,
        timeframe=timeframe,
        is_active=True,
    )
    db.add(pair)
    bump_tracked_pairs_version(db)
    db.commit()
    db.refresh(pair)
    invalidate_tracked_pairs_cache()
    return pair


@router.put("/tracked-pairs/{pair_id}", response_model=TrackedPairResponse)
async def update_tracked_pair(
    pair_id: int,
    payload: TrackedPairUpdateRequest,
    db: Session = Depends(get_db),
):
    pair = db.query(TrackedPair).filter(TrackedPair.id == pair_id).first()

    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked pair not found")

    new_symbol = payload.symbol or pair.symbol
    new_timeframe = payload.timeframe or pair.timeframe

    duplicate = (
        db.query(TrackedPair)
        .filter(
            TrackedPair.id != pair_id,
            TrackedPair.symbol == new_symbol,
            TrackedPair.timeframe == new_timeframe,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Another tracked pair already uses this symbol/timeframe",
        )

    updated = False

    if payload.symbol is not None and payload.symbol != pair.symbol:
        pair.symbol = payload.symbol
        updated = True

    if payload.timeframe is not None and payload.timeframe != pair.timeframe:
        pair.timeframe = payload.timeframe
        updated = True

    if payload.is_active is not None and payload.is_active != pair.is_active:
        pair.is_active = payload.is_active
        updated = True

    if not updated:
        return pair

    bump_tracked_pairs_version(db)
    db.commit()
    db.refresh(pair)
    invalidate_tracked_pairs_cache()
    return pair
