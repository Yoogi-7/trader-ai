"""
Celery signal handlers for tracking training jobs
"""
from celery.signals import task_prerun, task_postrun, task_failure, task_success
from apps.api.db.session import SessionLocal
from apps.api.db.models import TrainingJob
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@task_prerun.connect(sender='training.train_model')
def training_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Called before training task starts"""
    db = SessionLocal()
    try:
        symbol = kwargs.get('symbol') or (args[0] if len(args) > 0 else None)
        timeframe = kwargs.get('timeframe') or (args[1] if len(args) > 1 else None)

        if not symbol or not timeframe:
            logger.warning(f"Cannot create TrainingJob record: missing symbol or timeframe")
            return

        # Create or update training job record
        training_job = db.query(TrainingJob).filter_by(job_id=task_id).first()

        if not training_job:
            training_job = TrainingJob(
                job_id=task_id,
                symbol=symbol,
                timeframe=timeframe,
                test_period_days=kwargs.get('test_period_days', 30),
                min_train_days=kwargs.get('min_train_days', 180),
                use_expanding_window=kwargs.get('use_expanding_window', True),
                status='training',
                started_at=datetime.utcnow()
            )
            db.add(training_job)
        else:
            training_job.status = 'training'
            training_job.started_at = datetime.utcnow()

        db.commit()
        logger.info(f"Training job {task_id} started for {symbol} {timeframe}")

    except Exception as e:
        logger.error(f"Error in training_task_prerun: {e}")
        db.rollback()
    finally:
        db.close()


@task_success.connect(sender='training.train_model')
def training_task_success(sender=None, result=None, **kwargs):
    """Called when training task succeeds"""
    db = SessionLocal()
    try:
        task_id = kwargs.get('task_id')
        if not task_id:
            return

        training_job = db.query(TrainingJob).filter_by(job_id=task_id).first()

        if training_job:
            training_job.status = 'completed'
            training_job.completed_at = datetime.utcnow()

            if training_job.started_at:
                elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                training_job.elapsed_seconds = elapsed

            # Update metrics from result
            if isinstance(result, dict):
                training_job.model_id = result.get('model_id')
                training_job.version = result.get('version')

                avg_metrics = result.get('avg_metrics', {})
                training_job.accuracy = avg_metrics.get('avg_accuracy')
                training_job.avg_roc_auc = avg_metrics.get('avg_roc_auc')

            training_job.progress_pct = 100.0
            db.commit()
            logger.info(f"Training job {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Error in training_task_success: {e}")
        db.rollback()
    finally:
        db.close()


@task_failure.connect(sender='training.train_model')
def training_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Called when training task fails"""
    db = SessionLocal()
    try:
        training_job = db.query(TrainingJob).filter_by(job_id=task_id).first()

        if training_job:
            training_job.status = 'failed'
            training_job.completed_at = datetime.utcnow()
            training_job.error_message = str(exception)

            if training_job.started_at:
                elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                training_job.elapsed_seconds = elapsed

            db.commit()
            logger.error(f"Training job {task_id} failed: {exception}")

    except Exception as e:
        logger.error(f"Error in training_task_failure: {e}")
        db.rollback()
    finally:
        db.close()
