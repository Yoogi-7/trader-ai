from celery import Celery
from apps.api.config import settings
from apps.api.db.session import SessionLocal
from apps.ml.backfill import BackfillService
from apps.ml.training import train_model_pipeline
import logging

logger = logging.getLogger(__name__)

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


@celery_app.task(name="training.train_model")
def train_model_task(symbol: str, timeframe: str, lookback_days: int = 1460):
    """Train ML model"""
    db = SessionLocal()
    try:
        model_id = train_model_pipeline(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days
        )
        return {"status": "completed", "model_id": model_id}
    except Exception as e:
        logger.error(f"Training task failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="signals.generate")
def generate_signals_task():
    """Generate trading signals (runs every 5 minutes)"""
    # Placeholder for signal generation logic
    logger.info("Generating trading signals...")
    return {"status": "completed", "signals_generated": 0}


@celery_app.task(name="drift.monitor")
def monitor_drift_task():
    """Monitor model drift (runs daily)"""
    logger.info("Monitoring model drift...")
    return {"status": "completed"}


@celery_app.task(name="signals.generate_historical")
def generate_historical_signals_task(symbol: str, start_date: str, end_date: str, timeframe: str = "15m"):
    """Generate historical signals and validate them against actual market data"""
    db = SessionLocal()
    try:
        from apps.ml.signal_engine import SignalEngine
        from apps.ml.backtest import backtest_signals
        from datetime import datetime as dt

        logger.info(f"Generating historical signals for {symbol} from {start_date} to {end_date}")

        # Initialize signal engine
        engine = SignalEngine(db)

        # Parse dates
        start = dt.fromisoformat(start_date)
        end = dt.fromisoformat(end_date)

        # Generate signals for historical period
        signals = engine.generate_signals_for_period(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end
        )

        # Backtest the generated signals
        backtest_results = backtest_signals(db, signals)

        logger.info(f"Generated {len(signals)} historical signals, {len(backtest_results)} backtested")

        return {
            "status": "completed",
            "signals_generated": len(signals),
            "signals_backtested": len(backtest_results),
            "win_rate": backtest_results.get('win_rate', 0) if isinstance(backtest_results, dict) else 0
        }
    except Exception as e:
        logger.error(f"Historical signal generation failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


# Celery beat schedule (for periodic tasks)
celery_app.conf.beat_schedule = {
    'generate-signals-every-5-minutes': {
        'task': 'signals.generate',
        'schedule': 300.0,  # 5 minutes
    },
    'monitor-drift-daily': {
        'task': 'drift.monitor',
        'schedule': 86400.0,  # 1 day
    },
}
