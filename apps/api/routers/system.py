from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, case, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from apps.api import cache
from apps.api.db import get_db
from apps.api.db.models import (
    ModelRegistry,
    OHLCV,
    RiskProfile,
    Signal,
    SignalStatus,
    SignalRejection,
    TimeFrame,
    TradeResult,
)
from apps.api.config import settings


ANALYTICS_CACHE_TTL_SECONDS = 300

router = APIRouter()


class SystemStatusResponse(BaseModel):
    hit_rate_tp1: Optional[float] = None
    avg_net_profit_pct: Optional[float] = None
    active_models: int = 0
    total_signals: int = 0
    total_trades: int = 0
    win_rate: Optional[float] = None
    total_net_profit_usd: Optional[float] = None
    avg_trade_duration_minutes: Optional[float] = None
    metrics_source: str = "trade_results"
    metrics_sample_size: int = 0


class CandleInfo(BaseModel):
    symbol: str
    timeframe: str
    total_candles: int
    first_candle: Optional[str] = None
    last_candle: Optional[str] = None


class AggregatedPNLResponse(BaseModel):
    date: date
    risk_profile: RiskProfile
    net_pnl_usd: float
    avg_net_pnl_pct: Optional[float] = None
    trade_count: int


class AggregatedExposureResponse(BaseModel):
    date: date
    risk_profile: RiskProfile
    exposure_usd: float


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    """Get real-time system status metrics"""

    # Count active models
    active_models = db.query(ModelRegistry).filter(
        ModelRegistry.is_active == True
    ).count()

    # Count total signals
    total_signals = db.query(Signal).count()

    # Aggregate executed trade performance
    tp_statuses = [
        SignalStatus.TP1_HIT,
        SignalStatus.TP2_HIT,
        SignalStatus.TP3_HIT,
    ]

    trade_stats = db.query(
        func.count(TradeResult.id).label("total"),
        func.sum(case((TradeResult.net_pnl_pct > 0, 1), else_=0)).label("wins"),
        func.sum(case((TradeResult.final_status.in_(tp_statuses), 1), else_=0)).label("tp_hits"),
        func.avg(TradeResult.net_pnl_pct).label("avg_pct"),
        func.sum(TradeResult.net_pnl_usd).label("total_usd"),
        func.avg(TradeResult.duration_minutes).label("avg_duration"),
    ).one()

    total_trades = int(trade_stats.total or 0)
    wins = float(trade_stats.wins or 0)
    tp_hits = float(trade_stats.tp_hits or 0)
    avg_net_profit_pct = float(trade_stats.avg_pct) if trade_stats.avg_pct is not None else None
    total_net_profit_usd = float(trade_stats.total_usd) if trade_stats.total_usd is not None else None
    avg_duration = float(trade_stats.avg_duration) if trade_stats.avg_duration is not None else None

    win_rate = wins / total_trades if total_trades else None
    hit_rate_tp1 = tp_hits / total_trades if total_trades else None

    metrics_source = "trade_results"
    sample_size = total_trades

    if total_trades == 0:
        try:
            fallback_sql = text(
                """
                SELECT
                    COUNT(*) AS total_samples,
                    AVG(actual_net_pnl_pct) AS avg_pct,
                    SUM(actual_net_pnl_usd) AS total_usd,
                    AVG(duration_minutes) AS avg_duration,
                    SUM(CASE WHEN actual_net_pnl_usd > 0 THEN 1 ELSE 0 END) AS winning_samples,
                    SUM(CASE WHEN final_status IN ('tp1_hit','tp2_hit','tp3_hit') THEN 1 ELSE 0 END) AS tp_hits
                FROM (
                    SELECT actual_net_pnl_pct,
                           actual_net_pnl_usd,
                           duration_minutes,
                           final_status
                    FROM historical_signal_snapshots
                    WHERE actual_net_pnl_pct IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT :limit
                ) recent
                """
            )
            row = db.execute(
                fallback_sql,
                {"limit": settings.HISTORICAL_PERFORMANCE_SAMPLE},
            ).first()
        except ProgrammingError:
            row = None

        if row and row.total_samples:
            sample_size = int(row.total_samples)
            metrics_source = "historical_snapshots"

            if row.avg_pct is not None:
                avg_net_profit_pct = float(row.avg_pct)
            if row.total_usd is not None:
                total_net_profit_usd = float(row.total_usd)
            if row.avg_duration is not None:
                avg_duration = float(row.avg_duration)

            wins = float(row.winning_samples or 0)
            tp_hits = float(row.tp_hits or 0)
            win_rate = wins / sample_size if sample_size else None
            hit_rate_tp1 = tp_hits / sample_size if sample_size else None

    return SystemStatusResponse(
        hit_rate_tp1=hit_rate_tp1,
        avg_net_profit_pct=avg_net_profit_pct,
        active_models=active_models,
        total_signals=total_signals,
        total_trades=total_trades,
        win_rate=win_rate,
        total_net_profit_usd=total_net_profit_usd,
        avg_trade_duration_minutes=avg_duration,
        metrics_source=metrics_source,
        metrics_sample_size=sample_size,
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
@router.get("/pnl", response_model=List[AggregatedPNLResponse])
async def get_system_pnl(db: Session = Depends(get_db)) -> List[AggregatedPNLResponse]:
    cache_key = "system:pnl"
    cached = cache.get_cached_json(cache_key)
    if cached:
        return [AggregatedPNLResponse(**item) for item in cached]

    date_column = func.date(TradeResult.closed_at)
    query = (
        db.query(
            date_column.label("date"),
            Signal.risk_profile.label("risk_profile"),
            func.sum(TradeResult.net_pnl_usd).label("net_pnl_usd"),
            func.avg(TradeResult.net_pnl_pct).label("avg_net_pnl_pct"),
            func.count(TradeResult.id).label("trade_count"),
        )
        .join(Signal, Signal.signal_id == TradeResult.signal_id)
        .filter(TradeResult.closed_at.isnot(None))
        .group_by(date_column, Signal.risk_profile)
        .order_by(date_column.asc(), Signal.risk_profile.asc())
    )

    rows = query.all()

    response = [
        AggregatedPNLResponse(
            date=row.date,
            risk_profile=RiskProfile(row.risk_profile)
            if not isinstance(row.risk_profile, RiskProfile)
            else row.risk_profile,
            net_pnl_usd=float(row.net_pnl_usd or 0.0),
            avg_net_pnl_pct=float(row.avg_net_pnl_pct)
            if row.avg_net_pnl_pct is not None
            else None,
            trade_count=int(row.trade_count),
        )
        for row in rows
    ]

    cache.set_cached_json(
        cache_key,
        [record.model_dump(mode="json") for record in response],
        ANALYTICS_CACHE_TTL_SECONDS,
    )

    return response


@router.get("/exposure", response_model=List[AggregatedExposureResponse])
async def get_system_exposure(db: Session = Depends(get_db)) -> List[AggregatedExposureResponse]:
    cache_key = "system:exposure"
    cached = cache.get_cached_json(cache_key)
    if cached:
        return [AggregatedExposureResponse(**item) for item in cached]

    date_column = func.date(TradeResult.closed_at)
    query = (
        db.query(
            date_column.label("date"),
            Signal.risk_profile.label("risk_profile"),
            func.sum(Signal.position_size_usd).label("exposure_usd"),
        )
        .join(Signal, Signal.signal_id == TradeResult.signal_id)
        .filter(
            TradeResult.closed_at.isnot(None),
            Signal.position_size_usd.isnot(None),
        )
        .group_by(date_column, Signal.risk_profile)
        .order_by(date_column.asc(), Signal.risk_profile.asc())
    )

    rows = query.all()

    response = [
        AggregatedExposureResponse(
            date=row.date,
            risk_profile=RiskProfile(row.risk_profile)
            if not isinstance(row.risk_profile, RiskProfile)
            else row.risk_profile,
            exposure_usd=float(row.exposure_usd or 0.0),
        )
        for row in rows
    ]

    cache.set_cached_json(
        cache_key,
        [record.model_dump(mode="json") for record in response],
        ANALYTICS_CACHE_TTL_SECONDS,
    )

    return response


class RejectedSignalResponse(BaseModel):
    """Response model for rejected signal"""
    id: int
    symbol: str
    timeframe: str
    environment: str
    model_id: Optional[str] = None
    risk_profile: str
    failed_filters: List[str]
    rejection_reason: str
    created_at: str
    inference_metadata: Optional[dict] = None


@router.get("/rejected-signals", response_model=List[RejectedSignalResponse])
async def get_rejected_signals(
    hours: int = 24,
    db: Session = Depends(get_db)
) -> List[RejectedSignalResponse]:
    """
    Get list of signals rejected in the last N hours.

    This endpoint shows signals that were generated but rejected by risk filters,
    helping to understand why signals are being filtered out.

    Args:
        hours: Number of hours to look back (default: 24)
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = (
        db.query(SignalRejection)
        .filter(SignalRejection.created_at >= cutoff)
        .order_by(SignalRejection.created_at.desc())
        .limit(1000)  # Safety limit
    )

    rejections = query.all()

    return [
        RejectedSignalResponse(
            id=rej.id,
            symbol=rej.symbol,
            timeframe=rej.timeframe,
            environment=rej.environment or 'production',
            model_id=rej.model_id,
            risk_profile=rej.risk_profile.value if isinstance(rej.risk_profile, RiskProfile) else str(rej.risk_profile),
            failed_filters=rej.failed_filters or [],
            rejection_reason=rej.rejection_reason or 'Unknown',
            created_at=rej.created_at.isoformat() if rej.created_at else None,
            inference_metadata=rej.inference_metadata
        )
        for rej in rejections
    ]
