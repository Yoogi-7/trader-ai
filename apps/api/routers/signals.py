from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, text, or_
from sqlalchemy.exc import ProgrammingError
from typing import List, Optional
from datetime import datetime, timedelta, timezone
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
    limit: int = Query(5, le=500),
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
    from apps.api.db.models import SignalGenerationJob, TimeFrame

    if request.end_date <= request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    try:
        timeframe_enum = TimeFrame(request.timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {request.timeframe}") from exc

    def _normalize_dt(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    start_dt = _normalize_dt(request.start_date)
    end_dt = _normalize_dt(request.end_date)

    task = celery_app.send_task(
        'signals.generate_historical',
        kwargs={
            'symbol': request.symbol,
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'timeframe': request.timeframe
        }
    )

    job = db.query(SignalGenerationJob).filter_by(job_id=task.id).first()
    if job:
        job.symbol = request.symbol
        job.timeframe = timeframe_enum
        job.start_date = start_dt
        job.end_date = end_dt
        job.status = 'pending'
        job.progress_pct = 0.0
        job.signals_generated = 0
        job.signals_backtested = 0
        job.error_message = None
        job.elapsed_seconds = None
        job.started_at = None
        job.completed_at = None
    else:
        job = SignalGenerationJob(
            job_id=task.id,
            symbol=request.symbol,
            timeframe=timeframe_enum,
            start_date=start_dt,
            end_date=end_dt,
            status='pending',
        )
        db.add(job)

    db.commit()

    return {
        "job_id": task.id,
        "status": "queued",
        "message": f"Generating historical signals for {request.symbol} from {start_dt} to {end_dt}"
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

    cutoff = datetime.utcnow() - timedelta(hours=3)
    active_statuses = ['generating', 'pending']

    active_jobs = (
        db.query(SignalGenerationJob)
        .filter(SignalGenerationJob.status.in_(active_statuses))
        .order_by(SignalGenerationJob.created_at.desc())
        .all()
    )

    recent_jobs = (
        db.query(SignalGenerationJob)
        .filter(
            ~SignalGenerationJob.status.in_(active_statuses),
            or_(
                SignalGenerationJob.completed_at >= cutoff,
                SignalGenerationJob.created_at >= cutoff
            )
        )
        .order_by(SignalGenerationJob.created_at.desc())
        .all()
    )

    jobs = []
    seen: set[str] = set()

    for job in active_jobs + recent_jobs:
        if job.job_id in seen:
            continue
        jobs.append(job)
        seen.add(job.job_id)

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


def _fetch_snapshot_results(
    db: Session,
    symbol: Optional[str],
    timeframe: Optional[str],
    limit: int,
    job_id: Optional[str] = None,
    cursor: Optional[str] = None,
    sort_order: str = "desc",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    filters = []
    params: dict[str, object] = {"page_size": limit}

    if job_id:
        filters.append("job_id = :job_id")
        params["job_id"] = job_id

    if symbol and symbol.upper() != "ALL":
        filters.append("symbol = :symbol")
        params["symbol"] = symbol

    if timeframe:
        filters.append("timeframe = :timeframe")
        params["timeframe"] = timeframe

    if start_date:
        filters.append("timestamp >= :start_date")
        params["start_date"] = start_date

    if end_date:
        filters.append("timestamp <= :end_date")
        params["end_date"] = end_date

    filters.append("actual_net_pnl_pct IS NOT NULL")

    if cursor:
        try:
            cursor_ts = datetime.fromisoformat(cursor)
            if sort_order.lower() == "asc":
                filters.append("timestamp > :cursor_ts")
            else:
                filters.append("timestamp < :cursor_ts")
            params["cursor_ts"] = cursor_ts
        except ValueError:
            pass

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    order_clause = "timestamp DESC" if sort_order.lower() != "asc" else "timestamp ASC"

    snapshot_query = f"""
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
        {where_clause}
        ORDER BY {order_clause}, created_at {'DESC' if sort_order.lower() != 'asc' else 'ASC'}
        LIMIT :page_size
    """

    rows = db.execute(text(snapshot_query), params).mappings().all()

    responses = []
    for row in rows:
        side_value = row['side'].upper() if isinstance(row['side'], str) else row['side']
        responses.append(HistoricalSignalResponse(
            signal_id=row['signal_id'],
            symbol=row['symbol'],
            side=side_value,
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
            final_status=row['final_status'] or 'no_data',
            duration_minutes=row['duration_minutes'],
            was_profitable=(row['actual_net_pnl_usd'] > 0) if row['actual_net_pnl_usd'] is not None else None,
        ))

    next_cursor = None
    if rows:
        last_ts = rows[-1]['timestamp']
        if isinstance(last_ts, datetime):
            next_cursor = last_ts.isoformat()

    return responses, next_cursor


class HistoricalSignalPage(BaseModel):
    data: List[HistoricalSignalResponse]
    next_cursor: Optional[str] = None


@router.get("/historical/results", response_model=HistoricalSignalPage)
def get_historical_signals(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    job_id: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    sort_order: str = Query("desc", pattern="^(?i)(asc|desc)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Get historical signals with their actual results"""
    try:
        signals: List[Signal] = []
        next_cursor: Optional[str] = None

        if timeframe is None:
            query = db.query(Signal).outerjoin(TradeResult, Signal.signal_id == TradeResult.signal_id)

            if symbol and symbol.upper() != "ALL":
                query = query.filter(Signal.symbol == symbol)

            query = query.order_by(desc(Signal.timestamp)).limit(limit)
            signals = query.all()

        results: List[HistoricalSignalResponse] = []
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

        if results:
            return {'data': results, 'next_cursor': None}

        snapshot_results, next_cursor = _fetch_snapshot_results(
            db,
            symbol,
            timeframe,
            limit,
            job_id=job_id,
            cursor=cursor,
            sort_order=sort_order,
            start_date=start_date,
            end_date=end_date,
        )
        return {'data': snapshot_results, 'next_cursor': next_cursor}
    except ProgrammingError:
        db.rollback()
        snapshot_results, next_cursor = _fetch_snapshot_results(
            db,
            symbol,
            timeframe,
            limit,
            job_id=job_id,
            cursor=cursor,
            sort_order=sort_order,
            start_date=start_date,
            end_date=end_date,
        )
        return {'data': snapshot_results, 'next_cursor': next_cursor}
