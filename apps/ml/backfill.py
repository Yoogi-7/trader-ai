import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from apps.api.db.models import OHLCV, BackfillJob, TimeFrame
from apps.ml.ccxt_client import CCXTClient
import time
import uuid

logger = logging.getLogger(__name__)


class BackfillService:
    """
    Resumable backfill service with checkpoint support.
    """

    def __init__(self, db: Session, exchange_id: str = None):
        self.db = db
        self.client = CCXTClient(exchange_id=exchange_id)

    def create_backfill_job(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_date: datetime,
        end_date: datetime
    ) -> BackfillJob:
        """Create a new backfill job"""
        job_id = f"backfill_{symbol.replace('/', '_')}_{timeframe.value}_{uuid.uuid4().hex[:8]}"

        # Estimate total candles
        delta = end_date - start_date
        tf_delta = self.client._timeframe_to_timedelta(timeframe.value)
        total_candles = int(delta / tf_delta)

        job = BackfillJob(
            job_id=job_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_candles_estimate=total_candles,
            status="pending"
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(f"Created backfill job {job_id} for {symbol} {timeframe.value} ({total_candles} candles)")
        return job

    def resume_backfill_job(self, job_id: str) -> Optional[BackfillJob]:
        """Resume a backfill job from checkpoint"""
        job = self.db.query(BackfillJob).filter(BackfillJob.job_id == job_id).first()

        if not job:
            logger.error(f"Job {job_id} not found")
            return None

        if job.status == "completed":
            logger.info(f"Job {job_id} already completed")
            return job

        logger.info(f"Resuming job {job_id} from {job.last_completed_ts or job.start_date}")
        return self.execute_backfill(job)

    def execute_backfill(self, job: BackfillJob) -> BackfillJob:
        """
        Execute backfill with checkpointing and progress tracking.
        """
        job.status = "running"
        job.started_at = datetime.utcnow()
        self.db.commit()

        # Determine start point (resume from checkpoint or start fresh)
        if job.last_completed_ts:
            current_start = job.last_completed_ts + timedelta(seconds=1)
        else:
            current_start = job.start_date

        chunk_size = 1000  # Candles per request
        start_time = time.time()

        try:
            while current_start < job.end_date:
                chunk_end = min(
                    current_start + timedelta(hours=chunk_size * self._tf_to_hours(job.timeframe.value)),
                    job.end_date
                )

                # Fetch chunk
                df = self.client.fetch_ohlcv_range(
                    symbol=job.symbol,
                    timeframe=job.timeframe.value,
                    start_date=current_start,
                    end_date=chunk_end,
                    limit=chunk_size
                )

                if df.empty:
                    logger.warning(f"No data returned for {job.symbol} {job.timeframe.value} from {current_start} to {chunk_end}")
                    current_start = chunk_end
                    continue

                # Upsert to database
                self._upsert_ohlcv(job.symbol, job.timeframe, df)

                # Update checkpoint
                job.last_completed_ts = df['timestamp'].max()
                job.candles_fetched += len(df)
                job.progress_pct = min(
                    100.0,
                    (job.candles_fetched / job.total_candles_estimate * 100) if job.total_candles_estimate > 0 else 0.0
                )

                # Calculate performance metrics
                elapsed = time.time() - start_time
                if elapsed > 0:
                    job.candles_per_minute = (job.candles_fetched / elapsed) * 60
                    remaining_candles = job.total_candles_estimate - job.candles_fetched
                    if job.candles_per_minute > 0:
                        job.eta_minutes = remaining_candles / job.candles_per_minute

                self.db.commit()

                logger.info(
                    f"Job {job.job_id}: Fetched {len(df)} candles, "
                    f"total={job.candles_fetched}, progress={job.progress_pct:.1f}%, "
                    f"rate={job.candles_per_minute:.0f} candles/min, eta={job.eta_minutes:.1f}min"
                )

                current_start = chunk_end

            # Detect and log gaps
            gaps = self._detect_gaps(job)
            if gaps:
                job.detected_gaps = [
                    {"start": gap[0].isoformat(), "end": gap[1].isoformat()}
                    for gap in gaps
                ]
                logger.warning(f"Detected {len(gaps)} gaps in {job.job_id}")

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.progress_pct = 100.0
            self.db.commit()

            logger.info(f"Backfill job {job.job_id} completed successfully")
            return job

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            self.db.commit()
            logger.error(f"Backfill job {job.job_id} failed: {e}")
            raise

    def _upsert_ohlcv(self, symbol: str, timeframe: TimeFrame, df):
        """Upsert OHLCV data (insert or update on conflict) using bulk operations"""
        from sqlalchemy.dialects.postgresql import insert

        # Prepare data for bulk insert
        records = []
        for _, row in df.iterrows():
            records.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': row['timestamp'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
                'created_at': datetime.utcnow()
            })

        if not records:
            return

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(OHLCV).values(records)
        stmt = stmt.on_conflict_do_update(
            constraint='uq_ohlcv_symbol_tf_ts',
            set_={
                'open': stmt.excluded.open,
                'high': stmt.excluded.high,
                'low': stmt.excluded.low,
                'close': stmt.excluded.close,
                'volume': stmt.excluded.volume
            }
        )

        try:
            self.db.execute(stmt)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error upserting OHLCV data: {e}")
            raise

    def _detect_gaps(self, job: BackfillJob):
        """Detect gaps in stored OHLCV data"""
        ohlcv_data = self.db.query(OHLCV).filter(
            and_(
                OHLCV.symbol == job.symbol,
                OHLCV.timeframe == job.timeframe,
                OHLCV.timestamp >= job.start_date,
                OHLCV.timestamp <= job.end_date
            )
        ).order_by(OHLCV.timestamp).all()

        if not ohlcv_data:
            return []

        import pandas as pd
        df = pd.DataFrame([{
            'timestamp': row.timestamp
        } for row in ohlcv_data])

        return self.client.detect_gaps(df, job.timeframe.value)

    @staticmethod
    def _tf_to_hours(timeframe: str) -> float:
        """Convert timeframe to hours"""
        units = {'m': 1/60, 'h': 1, 'd': 24, 'w': 168}
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        return value * units[unit]

    def pause_job(self, job_id: str):
        """Pause a running job"""
        job = self.db.query(BackfillJob).filter(BackfillJob.job_id == job_id).first()
        if job and job.status == "running":
            job.status = "paused"
            self.db.commit()
            logger.info(f"Job {job_id} paused")

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status summary"""
        job = self.db.query(BackfillJob).filter(BackfillJob.job_id == job_id).first()
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "symbol": job.symbol,
            "timeframe": job.timeframe.value,
            "status": job.status,
            "progress_pct": job.progress_pct,
            "candles_fetched": job.candles_fetched,
            "total_candles_estimate": job.total_candles_estimate,
            "candles_per_minute": job.candles_per_minute,
            "eta_minutes": job.eta_minutes,
            "detected_gaps": job.detected_gaps,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
