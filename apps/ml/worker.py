from celery import Celery
from apps.api.config import settings
from apps.api.db.session import SessionLocal
from apps.api.db.models import OHLCV
from apps.ml.backfill import BackfillService
from apps.ml.training import train_model_pipeline
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)

# Import celery signals to register them
import apps.ml.celery_signals  # noqa: F401

celery_app = Celery(
    "traderai",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND)
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery_app.task(name="backfill.execute")
def execute_backfill_task(job_id: str):
    """Execute backfill job"""
    db = SessionLocal()
    try:
        service = BackfillService(db)
        job = service.resume_backfill_job(job_id)
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        logger.error(f"Backfill task failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="training.train_model", bind=True)
def train_model_task(
    self,
    symbol: str,
    timeframe: str,
    test_period_days: int = 30,
    min_train_days: int = 180,
    use_expanding_window: bool = True
):
    """Train ML model with walk-forward validation using expanding windows"""
    from apps.api.db.models import TrainingJob, TimeFrame
    from datetime import datetime

    db = SessionLocal()
    training_job = None

    try:
        # Create training job record
        training_job = TrainingJob(
            job_id=self.request.id,
            symbol=symbol,
            timeframe=TimeFrame(timeframe),
            test_period_days=test_period_days,
            min_train_days=min_train_days,
            use_expanding_window=use_expanding_window,
            status='training',
            started_at=datetime.utcnow()
        )
        db.add(training_job)
        db.commit()

        logger.info(
            f"Starting training task: {symbol} {timeframe}, "
            f"test_period={test_period_days}, min_train={min_train_days}, "
            f"expanding={use_expanding_window}"
        )

        # Define progress callbacks to update DB
        def update_training_progress(progress_pct, current_fold, total_folds):
            """Update training job progress in database"""
            try:
                db.refresh(training_job)
                training_job.progress_pct = progress_pct
                training_job.current_fold = current_fold
                training_job.total_folds = total_folds

                if training_job.started_at:
                    elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                    training_job.elapsed_seconds = elapsed

                db.commit()
                logger.info(f"Training Progress: {progress_pct:.1f}% - Fold {current_fold}/{total_folds}")
            except Exception as e:
                logger.error(f"Failed to update training progress: {e}")
                db.rollback()

        def update_labeling_progress(progress_pct):
            """Update labeling progress in database"""
            try:
                db.refresh(training_job)
                training_job.labeling_progress_pct = progress_pct

                if training_job.started_at:
                    elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                    training_job.elapsed_seconds = elapsed

                db.commit()
                logger.info(f"Labeling Progress: {progress_pct:.1f}%")
            except Exception as e:
                logger.error(f"Failed to update labeling progress: {e}")
                db.rollback()

        results = train_model_pipeline(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            test_period_days=test_period_days,
            min_train_days=min_train_days,
            use_expanding_window=use_expanding_window,
            progress_callback={
                'training': update_training_progress,
                'labeling': update_labeling_progress
            }
        )

        # Update job as completed
        training_job.status = 'completed'
        training_job.completed_at = datetime.utcnow()
        training_job.model_id = results.get('model_id')
        training_job.version = results.get('registry_version')

        avg_metrics = results.get('avg_metrics', {})
        training_job.accuracy = avg_metrics.get('avg_accuracy')
        training_job.avg_roc_auc = avg_metrics.get('avg_roc_auc')
        training_job.progress_pct = 100.0

        if training_job.started_at:
            elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
            training_job.elapsed_seconds = elapsed

        db.commit()

        return {
            "status": "completed",
            "model_id": results['model_id'],
            "version": results.get('registry_version'),
            "avg_metrics": avg_metrics
        }
    except Exception as e:
        logger.error(f"Training task failed: {e}", exc_info=True)

        # Update job as failed
        if training_job:
            training_job.status = 'failed'
            training_job.completed_at = datetime.utcnow()
            training_job.error_message = str(e)

            if training_job.started_at:
                elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                training_job.elapsed_seconds = elapsed

            db.commit()

        # Re-raise exception so Celery marks task as FAILURE
        raise
    finally:
        db.close()


@celery_app.task(name="signals.generate")
def generate_signals_task():
    """Generate trading signals (runs every 5 minutes)"""
    # Placeholder for signal generation logic
    logger.info("Generating trading signals...")
    return {"status": "completed", "signals_generated": 0}


@celery_app.task(name="backfill.update_latest")
def update_latest_candles_task():
    """Update latest candles for all active symbols (runs every 15 minutes)"""
    db = SessionLocal()
    try:
        from apps.ml.backfill import BackfillService
        from apps.api.db.models import TimeFrame
        from datetime import datetime, timedelta

        # List of trading pairs to track
        TRACKED_PAIRS = [
            'BTC/USDT',
            'ETH/USDT',
            'BNB/USDT',
            'XRP/USDT',
            'ADA/USDT',
            'SOL/USDT',
            'DOGE/USDT',
            'MATIC/USDT',
            'DOT/USDT',
            'AVAX/USDT',
            'LINK/USDT',
            'UNI/USDT'
        ]

        service = BackfillService(db)
        total_updated = 0

        for symbol in TRACKED_PAIRS:
            try:
                # Get latest timestamp from database for this symbol
                latest_candle = db.query(OHLCV).filter(
                    and_(
                        OHLCV.symbol == symbol,
                        OHLCV.timeframe == TimeFrame.M15
                    )
                ).order_by(OHLCV.timestamp.desc()).first()

                if latest_candle:
                    # Fetch candles from latest timestamp to now
                    start_date = latest_candle.timestamp
                    end_date = datetime.utcnow()

                    logger.info(f"Updating {symbol} candles from {start_date} to {end_date}")

                    df = service.client.fetch_ohlcv_range(
                        symbol=symbol,
                        timeframe='15m',
                        start_date=start_date,
                        end_date=end_date,
                        limit=100
                    )

                    if not df.empty:
                        service._upsert_ohlcv(symbol, TimeFrame.M15, df)
                        logger.info(f"Updated {len(df)} latest candles for {symbol} 15m")
                        total_updated += len(df)
                else:
                    logger.info(f"No existing candles for {symbol}, skipping update (use backfill first)")

            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                continue

        return {"status": "completed", "candles_updated": total_updated, "pairs_tracked": len(TRACKED_PAIRS)}

    except Exception as e:
        logger.error(f"Update latest candles task failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="drift.monitor")
def monitor_drift_task():
    """Monitor model drift (runs daily)"""
    logger.info("Monitoring model drift...")
    return {"status": "completed"}


@celery_app.task(name="signals.generate_historical", bind=True)
def generate_historical_signals_task(self, symbol: str, start_date: str, end_date: str, timeframe: str = "15m"):
    """Generate historical signals and validate them against actual market data"""
    from apps.api.db.models import SignalGenerationJob, TimeFrame
    from datetime import datetime as dt

    db = SessionLocal()
    signal_job = None

    try:
        from apps.ml.signal_engine import SignalEngine
        from apps.ml.backtest import backtest_signals

        # Parse dates
        start = dt.fromisoformat(start_date)
        end = dt.fromisoformat(end_date)

        # Create job record
        signal_job = SignalGenerationJob(
            job_id=self.request.id,
            symbol=symbol,
            timeframe=TimeFrame(timeframe),
            start_date=start,
            end_date=end,
            status='generating',
            started_at=dt.utcnow()
        )
        db.add(signal_job)
        db.commit()

        logger.info(f"Generating historical signals for {symbol} from {start_date} to {end_date}")

        # Initialize signal engine
        engine = SignalEngine(db)

        # Generate signals for historical period
        signals = engine.generate_signals_for_period(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end
        )

        # Update progress
        signal_job.signals_generated = len(signals)
        signal_job.progress_pct = 50.0
        db.commit()

        # Backtest the generated signals
        backtest_results = backtest_signals(db, signals)

        # Update job as completed
        signal_job.status = 'completed'
        signal_job.completed_at = dt.utcnow()
        signal_job.signals_backtested = len(backtest_results) if isinstance(backtest_results, list) else 0
        signal_job.win_rate = backtest_results.get('win_rate', 0) if isinstance(backtest_results, dict) else 0
        signal_job.avg_profit_pct = backtest_results.get('avg_profit_pct', 0) if isinstance(backtest_results, dict) else 0
        signal_job.total_pnl_usd = backtest_results.get('total_pnl_usd', 0) if isinstance(backtest_results, dict) else 0
        signal_job.progress_pct = 100.0

        if signal_job.started_at:
            elapsed = (dt.utcnow() - signal_job.started_at).total_seconds()
            signal_job.elapsed_seconds = elapsed

        db.commit()

        logger.info(f"Generated {len(signals)} historical signals, {signal_job.signals_backtested} backtested")

        return {
            "status": "completed",
            "signals_generated": len(signals),
            "signals_backtested": signal_job.signals_backtested,
            "win_rate": signal_job.win_rate
        }
    except Exception as e:
        logger.error(f"Historical signal generation failed: {e}", exc_info=True)

        # Update job as failed
        if signal_job:
            signal_job.status = 'failed'
            signal_job.completed_at = dt.utcnow()
            signal_job.error_message = str(e)

            if signal_job.started_at:
                elapsed = (dt.utcnow() - signal_job.started_at).total_seconds()
                signal_job.elapsed_seconds = elapsed

            db.commit()

        # Re-raise exception
        raise
    finally:
        db.close()


# Celery beat schedule (for periodic tasks)
celery_app.conf.beat_schedule = {
    'update-latest-candles-every-15-minutes': {
        'task': 'backfill.update_latest',
        'schedule': 900.0,  # 15 minutes
    },
    'generate-signals-every-5-minutes': {
        'task': 'signals.generate',
        'schedule': 300.0,  # 5 minutes
    },
    'monitor-drift-daily': {
        'task': 'drift.monitor',
        'schedule': 86400.0,  # 1 day
    },
}
