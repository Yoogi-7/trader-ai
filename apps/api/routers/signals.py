from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, text
from sqlalchemy.exc import ProgrammingError
from typing import List, Optional
from datetime import datetime, timedelta
from apps.api.db import get_async_db, get_db
from apps.api.db.models import Signal, RiskProfile, SignalStatus, TradeResult
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
    ai_summary: Optional[str] = None

    class Config:
        from_attributes = True


class HistoricalSignalResponse(BaseModel):
    signal_id: str
    symbol: str
    side: str
    entry_price: float
    timeframe: Optional[str] = None
    tp1_price: float
    tp2_price: float
    tp3_price: float
    sl_price: float
    timestamp: datetime
    status: str
    confidence: float
    expected_net_profit_pct: float
    ai_summary: Optional[str] = None

    # Actual results
    actual_net_pnl_pct: Optional[float] = None
    actual_net_pnl_usd: Optional[float] = None
    final_status: Optional[str] = None
    duration_minutes: Optional[int] = None
    was_profitable: Optional[bool] = None

    class Config:
        from_attributes = True


class GenerateHistoricalSignalsRequest(BaseModel):
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: str = "15m"


class SignalGenerationStatus(BaseModel):
    job_id: str
    status: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    progress_pct: Optional[float] = None
    signals_generated: Optional[int] = None
    signals_backtested: Optional[int] = None
    win_rate: Optional[float] = None
    avg_profit_pct: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    error_message: Optional[str] = None


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
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE]),
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


@router.post("/historical/generate")
async def generate_historical_signals(
    request: GenerateHistoricalSignalsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate historical signals and backtest them"""
    from apps.ml.worker import celery_app

    if request.end_date <= request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    task = celery_app.send_task(
        'signals.generate_historical',
        kwargs={
            'symbol': request.symbol,
            'start_date': request.start_date.isoformat(),
            'end_date': request.end_date.isoformat(),
            'timeframe': request.timeframe
        }
    )

    return {
        "job_id": task.id,
        "status": "queued",
        "message": f"Generating historical signals for {request.symbol} from {request.start_date} to {request.end_date}"
    }


@router.get("/historical/status/{job_id}", response_model=SignalGenerationStatus)
def get_signal_generation_status(job_id: str, db: Session = Depends(get_db)):
    """Get historical signal generation status"""
    from apps.api.db.models import SignalGenerationJob

    job = db.query(SignalGenerationJob).filter_by(job_id=job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Signal generation job not found")

    return SignalGenerationStatus(
        job_id=job.job_id,
        status=job.status,
        symbol=job.symbol,
        timeframe=job.timeframe.value if hasattr(job.timeframe, "value") else str(job.timeframe),
        start_date=job.start_date.isoformat(),
        end_date=job.end_date.isoformat(),
        progress_pct=job.progress_pct,
        signals_generated=job.signals_generated,
        signals_backtested=job.signals_backtested,
        win_rate=job.win_rate,
        avg_profit_pct=job.avg_profit_pct,
        elapsed_seconds=job.elapsed_seconds,
        error_message=job.error_message
    )


@router.post("/historical/cancel/{job_id}")
def cancel_signal_generation(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running signal generation job"""
    from apps.api.db.models import SignalGenerationJob
    from apps.ml.worker import celery_app

    job = db.query(SignalGenerationJob).filter_by(job_id=job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ['generating', 'pending']:
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


@router.get("/historical/jobs", response_model=List[SignalGenerationStatus])
def list_signal_generation_jobs(db: Session = Depends(get_db)):
    """List all recent signal generation jobs"""
    from apps.api.db.models import SignalGenerationJob
    from datetime import datetime, timedelta

    # Get jobs from last 24 hours
    cutoff = datetime.utcnow() - timedelta(hours=24)
    jobs = db.query(SignalGenerationJob).filter(
        SignalGenerationJob.created_at >= cutoff
    ).order_by(SignalGenerationJob.created_at.desc()).all()

    return [
        SignalGenerationStatus(
            job_id=job.job_id,
            status=job.status,
            symbol=job.symbol,
            timeframe=job.timeframe.value if hasattr(job.timeframe, "value") else str(job.timeframe),
            start_date=job.start_date.isoformat(),
            end_date=job.end_date.isoformat(),
            progress_pct=job.progress_pct,
            signals_generated=job.signals_generated,
            signals_backtested=job.signals_backtested,
            win_rate=job.win_rate,
            avg_profit_pct=job.avg_profit_pct,
            elapsed_seconds=job.elapsed_seconds,
            error_message=job.error_message
        )
        for job in jobs
    ]


@router.get("/historical/results", response_model=List[HistoricalSignalResponse])
def get_historical_signals(
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db)
):
    """Get historical signals with their actual results"""
    try:
        query = db.query(Signal).outerjoin(TradeResult, Signal.signal_id == TradeResult.signal_id)

        if symbol:
            if symbol.upper() != "ALL":
                query = query.filter(Signal.symbol == symbol)

        query = query.order_by(desc(Signal.timestamp)).limit(limit)
        signals = query.all()

        results = []
        for signal in signals:
            trade_result = signal.trade_results[0] if signal.trade_results else None

            results.append(HistoricalSignalResponse(
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                side=signal.side.value,
                entry_price=signal.entry_price,
                timeframe=signal.model.timeframe.value if signal.model and signal.model.timeframe else None,
                tp1_price=signal.tp1_price,
                tp2_price=signal.tp2_price,
                tp3_price=signal.tp3_price,
                sl_price=signal.sl_price,
                timestamp=signal.timestamp,
                status=signal.status.value,
                confidence=signal.confidence or 0.0,
                expected_net_profit_pct=signal.expected_net_profit_pct,
                ai_summary=signal.ai_summary,
                actual_net_pnl_pct=trade_result.net_pnl_pct if trade_result else None,
                actual_net_pnl_usd=trade_result.net_pnl_usd if trade_result else None,
                final_status=trade_result.final_status.value if trade_result and trade_result.final_status else None,
                duration_minutes=trade_result.duration_minutes if trade_result else None,
                was_profitable=trade_result.net_pnl_usd > 0 if trade_result and trade_result.net_pnl_usd is not None else None
            ))

        return results
    except ProgrammingError:
        db.rollback()

        base_query = """
            SELECT signal_id,
                   symbol,
                   timeframe,
                   side,
                   entry_price,
                   timestamp,
                   tp1_price,
                   tp2_price,
                   tp3_price,
                   sl_price,
                   expected_net_profit_pct,
                   expected_net_profit_usd,
                   confidence,
                   model_id,
                   risk_profile,
                   actual_net_pnl_pct,
                   actual_net_pnl_usd,
                   final_status,
                   duration_minutes
            FROM historical_signal_snapshots
            WHERE (:symbol IS NULL OR symbol = :symbol)
            ORDER BY created_at DESC, timestamp DESC
            LIMIT :limit
        """

        rows = db.execute(text(base_query), {
            'symbol': symbol,
            'limit': limit
        }).mappings().all()

        responses = []
        for row in rows:
            responses.append(HistoricalSignalResponse(
                signal_id=row['signal_id'],
                symbol=row['symbol'],
                side=row['side'],
                entry_price=row['entry_price'],
                timeframe=row['timeframe'],
                tp1_price=row['tp1_price'] or row['entry_price'],
                tp2_price=row['tp2_price'] or row['entry_price'],
                tp3_price=row['tp3_price'] or row['entry_price'],
                sl_price=row['sl_price'] or row['entry_price'],
                timestamp=row['timestamp'],
                status=row['final_status'] or 'time_stop',
                confidence=row['confidence'] or 0.0,
                expected_net_profit_pct=row['expected_net_profit_pct'] or 0.0,
                ai_summary=None,
                actual_net_pnl_pct=row['actual_net_pnl_pct'],
                actual_net_pnl_usd=row['actual_net_pnl_usd'],
                final_status=row['final_status'],
                duration_minutes=row['duration_minutes'],
                was_profitable=(row['actual_net_pnl_usd'] > 0) if row['actual_net_pnl_usd'] is not None else None,
            ))

        return responses
