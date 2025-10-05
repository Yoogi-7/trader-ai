from typing import Optional

from celery import Celery
from apps.api.config import settings
from apps.api.db.session import SessionLocal
from apps.api.db.models import (
    OHLCV,
    Signal,
    SignalStatus,
    RiskProfile,
    Side,
    SignalRejection,
    ModelRegistry as ModelRecord,
)
from apps.ml.backfill import BackfillService
from apps.ml.training import train_model_pipeline
from apps.ml.model_registry import ModelRegistry
from apps.ml.signal_engine import SignalEngine
from apps.ml.summaries import generate_signal_summary
from apps.ml.drift import DriftDetector
from sqlalchemy import and_, text
from datetime import datetime, timezone
from sqlalchemy.exc import ProgrammingError
import pandas as pd
import numpy as np
import asyncio
import logging
import math

_HISTORICAL_TABLE_INITIALIZED = False


def _ensure_historical_table(db):
    global _HISTORICAL_TABLE_INITIALIZED
    if _HISTORICAL_TABLE_INITIALIZED:
        return

    create_sql = text(
        """
        CREATE TABLE IF NOT EXISTS historical_signal_snapshots (
            signal_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price DOUBLE PRECISION NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            tp1_price DOUBLE PRECISION,
            tp2_price DOUBLE PRECISION,
            tp3_price DOUBLE PRECISION,
            sl_price DOUBLE PRECISION,
            expected_net_profit_pct DOUBLE PRECISION,
            expected_net_profit_usd DOUBLE PRECISION,
            confidence DOUBLE PRECISION,
            model_id TEXT,
            risk_profile TEXT,
            actual_net_pnl_pct DOUBLE PRECISION,
            actual_net_pnl_usd DOUBLE PRECISION,
            final_status TEXT,
            duration_minutes INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    db.execute(create_sql)

    alter_statements = [
        "ALTER TABLE historical_signal_snapshots ADD COLUMN IF NOT EXISTS actual_net_pnl_pct DOUBLE PRECISION",
        "ALTER TABLE historical_signal_snapshots ADD COLUMN IF NOT EXISTS actual_net_pnl_usd DOUBLE PRECISION",
        "ALTER TABLE historical_signal_snapshots ADD COLUMN IF NOT EXISTS final_status TEXT",
        "ALTER TABLE historical_signal_snapshots ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
    ]
    for stmt in alter_statements:
        db.execute(text(stmt))
    _HISTORICAL_TABLE_INITIALIZED = True

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
    from apps.api.db.models import TrainingJob, TimeFrame, ModelRegistry as ModelRecord
    from datetime import datetime

    db = SessionLocal()
    training_job = None

    try:
        # Create or reuse training job record (signals may pre-create it)
        training_job = db.query(TrainingJob).filter_by(job_id=self.request.id).first()

        if training_job is None:
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
        else:
            training_job.symbol = symbol
            training_job.timeframe = TimeFrame(timeframe)
            training_job.test_period_days = test_period_days
            training_job.min_train_days = min_train_days
            training_job.use_expanding_window = use_expanding_window
            training_job.status = 'training'
            training_job.started_at = datetime.utcnow()

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

        def ensure_model_registry_record(results_dict: dict):
            """Create or update relational model registry entry so FKs stay valid."""

            model_id = results_dict.get('model_id')
            if not model_id:
                return None

            try:
                timeframe_enum = TimeFrame(timeframe)
            except ValueError:
                logger.error("Invalid timeframe %s for model registry entry", timeframe)
                return None

            avg_metrics = results_dict.get('avg_metrics') or {}
            split_results = results_dict.get('split_results') or []
            validation_period = results_dict.get('validation_period') or {}

            train_starts = [split.get('train_start') for split in split_results if split.get('train_start')]
            train_ends = [split.get('train_end') for split in split_results if split.get('train_end')]
            test_starts = [split.get('test_start') for split in split_results if split.get('test_start')]
            test_ends = [split.get('test_end') for split in split_results if split.get('test_end')]

            def _parse_iso(value):
                if not value:
                    return None
                try:
                    return datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    return None

            train_start = min(train_starts) if train_starts else _parse_iso(validation_period.get('start'))
            train_end = max(train_ends) if train_ends else _parse_iso(validation_period.get('end'))
            oos_start = min(test_starts) if test_starts else train_start
            oos_end = max(test_ends) if test_ends else train_end

            registry = ModelRegistry()
            registry_version = results_dict.get('registry_version')
            registry_entry = registry.get_model(symbol, timeframe, registry_version)
            artifact_path = registry_entry.get('path') if registry_entry else None

            def _to_serializable(value):
                if isinstance(value, np.generic):
                    return value.item()
                if isinstance(value, dict):
                    return {k: _to_serializable(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [_to_serializable(v) for v in value]
                return value

            feature_importance = results_dict.get('feature_importance')
            if feature_importance:
                feature_importance = _to_serializable(feature_importance)

            db_model = db.query(ModelRecord).filter_by(model_id=model_id).first()

            if not db_model:
                if not (train_start and train_end and oos_start and oos_end):
                    logger.warning("Skipping model registry insert for %s due to missing timeline metadata", model_id)
                    return None

                db_model = ModelRecord(
                    model_id=model_id,
                    symbol=symbol,
                    timeframe=timeframe_enum,
                    model_type='ensemble',
                    version=registry_version or 'v1',
                    train_start=train_start,
                    train_end=train_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                    hyperparameters=None,
                    accuracy=avg_metrics.get('avg_accuracy'),
                    precision=avg_metrics.get('avg_precision'),
                    recall=avg_metrics.get('avg_recall'),
                    f1_score=avg_metrics.get('avg_f1_score'),
                    roc_auc=avg_metrics.get('avg_roc_auc'),
                    hit_rate_tp1=avg_metrics.get('avg_hit_rate_tp1'),
                    artifact_path=artifact_path,
                    feature_importance=feature_importance
                )
                db.add(db_model)
            else:
                db_model.symbol = symbol
                db_model.timeframe = timeframe_enum
                if registry_version:
                    db_model.version = registry_version
                if train_start:
                    db_model.train_start = train_start
                if train_end:
                    db_model.train_end = train_end
                if oos_start:
                    db_model.oos_start = oos_start
                if oos_end:
                    db_model.oos_end = oos_end
                db_model.accuracy = avg_metrics.get('avg_accuracy')
                db_model.precision = avg_metrics.get('avg_precision')
                db_model.recall = avg_metrics.get('avg_recall')
                db_model.f1_score = avg_metrics.get('avg_f1_score')
                db_model.roc_auc = avg_metrics.get('avg_roc_auc')
                db_model.hit_rate_tp1 = avg_metrics.get('avg_hit_rate_tp1')
                if artifact_path:
                    db_model.artifact_path = artifact_path
                if feature_importance:
                    db_model.feature_importance = feature_importance

            if db_model:
                # Promote the latest model to production and retire older ones for this pair
                siblings = db.query(ModelRecord).filter(
                    ModelRecord.symbol == symbol,
                    ModelRecord.timeframe == timeframe_enum,
                    ModelRecord.model_id != db_model.model_id,
                ).all()
                for sibling in siblings:
                    sibling.is_active = False
                    sibling.is_production = False

                db_model.is_active = True
                db_model.is_production = True
                db_model.deployed_at = datetime.utcnow()

                if registry_version:
                    try:
                        registry.deploy_model(symbol, timeframe, registry_version)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.error(
                            "Failed to auto-deploy model %s %s %s: %s",
                            symbol,
                            timeframe,
                            registry_version,
                            exc,
                        )

            return db_model

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
        model_record = ensure_model_registry_record(results)

        training_job.status = 'completed'
        training_job.completed_at = datetime.utcnow()
        if model_record:
            training_job.model_id = model_record.model_id
            training_job.version = model_record.version
        else:
            logger.warning(
                "No relational registry entry for model %s; leaving training job detached",
                results.get('model_id')
            )
            training_job.model_id = None
            training_job.version = results.get('registry_version')

        avg_metrics = results.get('avg_metrics', {})
        training_job.accuracy = avg_metrics.get('avg_accuracy')
        training_job.avg_roc_auc = avg_metrics.get('avg_roc_auc')
        training_job.hit_rate_tp1 = avg_metrics.get('avg_hit_rate_tp1')
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
        db.rollback()

        if training_job:
            try:
                training_job = db.query(TrainingJob).filter_by(job_id=self.request.id).first()
                if training_job:
                    training_job.status = 'failed'
                    training_job.completed_at = datetime.utcnow()
                    training_job.error_message = str(e)
                    training_job.model_id = None
                    training_job.version = None

                    if training_job.started_at:
                        elapsed = (datetime.utcnow() - training_job.started_at).total_seconds()
                        training_job.elapsed_seconds = elapsed

                    db.commit()
            except Exception as update_error:
                logger.error(f"Failed to persist training failure status: {update_error}")
                db.rollback()

        # Re-raise exception so Celery marks task as FAILURE
        raise
    finally:
        db.close()


@celery_app.task(name="signals.generate")
def generate_signals_task():
    """Generate trading signals (runs every 5 minutes)"""

    from apps.api.main import manager as ws_manager

    db = SessionLocal()
    registry = ModelRegistry()
    engine = SignalEngine(db, registry=registry)

    summary = {
        "status": "completed",
        "signals_generated": 0,
        "skipped": 0,
        "errors": 0,
        "broadcasts": 0,
        "details": [],
        "metrics": {}
    }

    confidences = []
    processed_deployments = 0
    skipped_filters = 0
    skipped_low_performance = 0
    performance_cache: dict[tuple[str, str], Optional[dict]] = {}
    min_performance_samples = max(30, settings.HISTORICAL_PERFORMANCE_SAMPLE // 5)

    try:
        deployments = registry.index.get('deployments', {}) if hasattr(registry, 'index') else {}

        if not deployments:
            logger.info(
                "No active model deployments found for signal generation; attempting to bootstrap from registry table"
            )

            candidates = db.query(ModelRecord).filter(ModelRecord.is_active == True).all()
            updated_candidates = False

            if not candidates:
                all_models = db.query(ModelRecord).order_by(ModelRecord.created_at.desc()).all()
                best_by_pair: dict[tuple[str, str], ModelRecord] = {}
                for model in all_models:
                    timeframe_value = (
                        model.timeframe.value if hasattr(model.timeframe, "value") else str(model.timeframe)
                    )
                    key = (model.symbol, timeframe_value)
                    score = model.hit_rate_tp1 or 0.0
                    existing = best_by_pair.get(key)
                    if not existing:
                        best_by_pair[key] = model
                        continue

                    existing_score = existing.hit_rate_tp1 or 0.0
                    if score > existing_score:
                        best_by_pair[key] = model
                        continue
                    if score == existing_score:
                        if model.created_at and (not existing.created_at or model.created_at > existing.created_at):
                            best_by_pair[key] = model

                candidates = list(best_by_pair.values())

            for candidate in candidates:
                timeframe_value = (
                    candidate.timeframe.value if hasattr(candidate.timeframe, "value") else str(candidate.timeframe)
                )
                try:
                    registry.deploy_model(candidate.symbol, timeframe_value, candidate.version)
                except Exception as exc:
                    logger.error(
                        "Failed to bootstrap deployment for %s %s: %s",
                        candidate.symbol,
                        timeframe_value,
                        exc,
                    )
                    continue

                if not candidate.is_active:
                    candidate.is_active = True
                    updated_candidates = True
                if not candidate.is_production:
                    candidate.is_production = True
                    updated_candidates = True

            if updated_candidates:
                try:
                    db.commit()
                except Exception:
                    db.rollback()

            deployments = registry.index.get('deployments', {}) if hasattr(registry, 'index') else {}

            if not deployments:
                summary["metrics"]["deployments_processed"] = 0
                summary["details"].append({"reason": "no_deployments_available"})
                return summary

        for _, deployment in deployments.items():
            symbol = deployment.get('symbol')
            timeframe = deployment.get('timeframe')
            environment = deployment.get('environment', 'production')

            if not symbol or not timeframe:
                logger.warning("Deployment missing symbol or timeframe: %s", deployment)
                summary['skipped'] += 1
                continue

            timeframe_value = timeframe.value if hasattr(timeframe, 'value') else str(timeframe)

            perf_key = (symbol, timeframe_value)
            if perf_key not in performance_cache:
                stats = None
                try:
                    perf_sql = text(
                        """
                        SELECT
                            COUNT(*) AS total_samples,
                            SUM(CASE WHEN actual_net_pnl_usd > 0 THEN 1 ELSE 0 END) AS winning_samples,
                            AVG(actual_net_pnl_pct) AS avg_pct
                        FROM (
                            SELECT actual_net_pnl_pct,
                                   actual_net_pnl_usd
                            FROM historical_signal_snapshots
                            WHERE symbol = :symbol
                              AND timeframe = :timeframe
                              AND actual_net_pnl_pct IS NOT NULL
                            ORDER BY created_at DESC
                            LIMIT :limit
                        ) recent
                        """
                    )
                    row = db.execute(
                        perf_sql,
                        {
                            'symbol': symbol,
                            'timeframe': timeframe_value,
                            'limit': settings.HISTORICAL_PERFORMANCE_SAMPLE,
                        },
                    ).first()
                except ProgrammingError:
                    db.rollback()
                    row = None

                if row and row.total_samples:
                    total_samples = int(row.total_samples)
                    win_rate_recent = (
                        float(row.winning_samples or 0) / total_samples if total_samples else None
                    )
                    stats = {
                        'total': total_samples,
                        'win_rate': win_rate_recent,
                        'avg_net_pnl_pct': float(row.avg_pct) if row.avg_pct is not None else None,
                    }
                performance_cache[perf_key] = stats

            stats = performance_cache.get(perf_key)
            if (
                stats
                and stats.get('total', 0) >= min_performance_samples
                and stats.get('win_rate') is not None
                and stats['win_rate'] < settings.MIN_HISTORICAL_WIN_RATE
            ):
                skipped_low_performance += 1
                summary['skipped'] += 1
                summary['details'].append({
                    'symbol': symbol,
                    'timeframe': timeframe_value,
                    'reason': 'low_recent_win_rate',
                    'recent_win_rate': stats['win_rate'],
                    'sample_size': stats['total'],
                })
                continue

            processed_deployments += 1

            selected_risk_profile = RiskProfile.MEDIUM

            try:
                result = engine.generate_for_deployment(
                    symbol=symbol,
                    timeframe=timeframe,
                    environment=environment,
                    risk_profile=selected_risk_profile,
                    capital_usd=1000.0
                )
            except Exception as exc:
                logger.error("Failed to generate signal for %s %s: %s", symbol, timeframe, exc)
                summary['errors'] += 1
                db.rollback()
                continue

            if not result or not result.accepted or not result.signal:
                summary['skipped'] += 1
                if result and not result.accepted:
                    skipped_filters += 1
                    rejection_reasons = result.rejection_reasons or []
                    reason_text = (
                        "Failed risk filters: " + ", ".join(rejection_reasons)
                        if rejection_reasons
                        else "Signal rejected by risk filters"
                    )
                    metadata = dict(result.inference_metadata or {})
                    timestamp = metadata.get('timestamp')
                    if timestamp is not None:
                        if hasattr(timestamp, 'isoformat'):
                            metadata['timestamp'] = timestamp.isoformat()
                        else:
                            metadata['timestamp'] = str(timestamp)
                    timeframe_value = timeframe.value if hasattr(timeframe, 'value') else str(timeframe)
                    rejection_record = SignalRejection(
                        symbol=symbol,
                        timeframe=timeframe_value,
                        environment=environment,
                        model_id=(result.model_info or {}).get('model_id') if result.model_info else None,
                        risk_profile=selected_risk_profile,
                        failed_filters=rejection_reasons,
                        rejection_reason=reason_text,
                        inference_metadata=metadata
                    )
                    try:
                        db.add(rejection_record)
                        db.commit()
                    except Exception as exc:
                        logger.error(
                            "Failed to persist rejection for %s %s: %s",
                            symbol,
                            timeframe_value,
                            exc
                        )
                        db.rollback()
                continue

            signal_data = result.signal
            risk_filters = result.risk_filters
            inference_metadata = result.inference_metadata
            model_info = result.model_info

            try:
                signal_data['ai_summary'] = generate_signal_summary(
                    signal_data,
                    model_info=model_info,
                    inference_metadata=inference_metadata
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "Failed to create AI summary for signal %s: %s",
                    signal_data.get('signal_id'),
                    exc,
                )
                signal_data['ai_summary'] = None

            signal_record = Signal(
                signal_id=signal_data['signal_id'],
                symbol=signal_data['symbol'],
                side=signal_data['side'] if isinstance(signal_data['side'], Side) else Side(signal_data['side']),
                entry_price=signal_data['entry_price'],
                timestamp=signal_data['timestamp'],
                tp1_price=signal_data['tp1_price'],
                tp1_pct=signal_data['tp1_pct'],
                tp2_price=signal_data['tp2_price'],
                tp2_pct=signal_data['tp2_pct'],
                tp3_price=signal_data['tp3_price'],
                tp3_pct=signal_data['tp3_pct'],
                sl_price=signal_data['sl_price'],
                leverage=signal_data['leverage'],
                margin_mode=signal_data['margin_mode'],
                position_size_usd=signal_data['position_size_usd'],
                quantity=signal_data['quantity'],
                risk_reward_ratio=signal_data['risk_reward_ratio'],
                estimated_liquidation=signal_data['estimated_liquidation'],
                max_loss_usd=signal_data['max_loss_usd'],
                model_id=model_info.get('model_id'),
                confidence=signal_data['confidence'],
                expected_net_profit_pct=signal_data['expected_net_profit_pct'],
                expected_net_profit_usd=signal_data['expected_net_profit_usd'],
                valid_until=signal_data['valid_until'],
                status=SignalStatus.ACTIVE,
                passed_spread_check=risk_filters.get('spread', True),
                passed_liquidity_check=risk_filters.get('liquidity', True),
                passed_profit_filter=risk_filters.get('profit', True),
                passed_correlation_check=risk_filters.get('correlation', True),
                risk_profile=signal_data['risk_profile'] if isinstance(signal_data['risk_profile'], RiskProfile) else RiskProfile(signal_data['risk_profile']),
                ai_summary=signal_data.get('ai_summary'),
                published_at=datetime.utcnow()
            )

            try:
                db.add(signal_record)
                db.commit()
                db.refresh(signal_record)
            except Exception as exc:
                logger.error("Failed to persist signal %s: %s", signal_data['signal_id'], exc)
                summary['errors'] += 1
                db.rollback()
                continue

            confidences.append(signal_record.confidence or 0.0)

            summary['signals_generated'] += 1
            summary['details'].append({
                'signal_id': signal_record.signal_id,
                'symbol': signal_record.symbol,
                'side': signal_record.side.value,
                'confidence': signal_record.confidence,
                'expected_net_profit_pct': signal_record.expected_net_profit_pct
            })

            broadcast_payload = _build_signal_broadcast_payload(
                signal_record,
                signal_data,
                model_info,
                inference_metadata,
                risk_filters
            )

            try:
                asyncio.run(ws_manager.broadcast(broadcast_payload))
                summary['broadcasts'] += 1
            except RuntimeError:
                # Fallback for already running event loops (common in tests)
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(ws_manager.broadcast(broadcast_payload))
                    summary['broadcasts'] += 1
                finally:
                    loop.close()
            except Exception as exc:
                logger.error("Failed to broadcast signal %s: %s", signal_record.signal_id, exc)

        if confidences:
            summary['metrics']['average_confidence'] = float(sum(confidences) / len(confidences))
            summary['metrics']['max_confidence'] = float(max(confidences))

        summary['metrics']['deployments_processed'] = processed_deployments
        summary['metrics']['skipped_due_to_filters'] = skipped_filters
        summary['metrics']['skipped_low_performance'] = skipped_low_performance

        return summary
    except Exception as exc:
        logger.error("Signal generation task failed: %s", exc, exc_info=True)
        db.rollback()
        summary['status'] = 'failed'
        summary['error'] = str(exc)
        return summary
    finally:
        db.close()


@celery_app.task(name="signals.expire")
def expire_signals_task():
    """Expire signals that are past their validity window."""

    db = SessionLocal()

    try:
        now = datetime.utcnow()

        try:
            expirable_signals = db.query(Signal).filter(
                Signal.valid_until < now,
                Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
            ).all()
        except ProgrammingError as exc:
            db.rollback()
            logger.warning(
                "Skipping signal expiration because required columns are missing: %s",
                exc,
            )
            return {"expired": 0, "skipped": True}

        if not expirable_signals:
            return {"expired": 0}

        expired_count = 0
        for signal in expirable_signals:
            signal.status = SignalStatus.TIME_STOP
            if signal.closed_at is None:
                signal.closed_at = now

            expired_count += 1

        db.commit()

        return {"expired": expired_count}
    except Exception as exc:
        db.rollback()
        logger.error("Failed to expire signals: %s", exc, exc_info=True)
        raise
    finally:
        db.close()


def _build_signal_broadcast_payload(signal_record, signal_data, model_info, inference_metadata, risk_filters):
    """Build websocket payload for a generated signal."""

    metadata = dict(inference_metadata or {})
    ts = metadata.get('timestamp')
    if isinstance(ts, datetime):
        metadata['timestamp'] = ts.isoformat()

    payload_data = {
        'signal_id': signal_record.signal_id,
        'symbol': signal_record.symbol,
        'side': signal_record.side.value,
        'entry_price': signal_record.entry_price,
        'timestamp': signal_record.timestamp.isoformat(),
        'tp1_price': signal_record.tp1_price,
        'tp1_pct': signal_record.tp1_pct,
        'tp2_price': signal_record.tp2_price,
        'tp2_pct': signal_record.tp2_pct,
        'tp3_price': signal_record.tp3_price,
        'tp3_pct': signal_record.tp3_pct,
        'sl_price': signal_record.sl_price,
        'leverage': signal_record.leverage,
        'margin_mode': signal_record.margin_mode,
        'position_size_usd': signal_record.position_size_usd,
        'quantity': signal_record.quantity,
        'risk_reward_ratio': signal_record.risk_reward_ratio,
        'estimated_liquidation': signal_record.estimated_liquidation,
        'max_loss_usd': signal_record.max_loss_usd,
        'model_id': model_info.get('model_id'),
        'model_version': model_info.get('version'),
        'confidence': signal_record.confidence,
        'expected_net_profit_pct': signal_record.expected_net_profit_pct,
        'expected_net_profit_usd': signal_record.expected_net_profit_usd,
        'valid_until': signal_record.valid_until.isoformat(),
        'status': signal_record.status.value,
        'risk_profile': signal_record.risk_profile.value,
        'ai_summary': signal_record.ai_summary,
        'risk_filters': risk_filters,
        'inference': metadata
    }

    return {
        'type': 'signal.created',
        'data': payload_data
    }


@celery_app.task(name="backfill.update_latest")
def update_latest_candles_task():
    """Update latest candles for all active symbols (runs every 15 minutes)"""
    db = SessionLocal()
    try:
        from apps.ml.backfill import BackfillService
        from apps.api.db.models import TimeFrame
        from datetime import datetime, timedelta

        # List of trading pairs to track (updated with current Binance symbols)
        TRACKED_PAIRS = [
            'BTC/USDT',
            'ETH/USDT',
            'BNB/USDT',
            'XRP/USDT',
            'ADA/USDT',
            'SOL/USDT',
            'DOGE/USDT',
            'POL/USDT',  # Previously MATIC
            'DOT/USDT',
            'AVAX/USDT',
            'LINK/USDT',
            'UNI/USDT'
        ]

        service = BackfillService(db)
        total_updated = 0
        backfills_triggered = 0

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

                        metrics_timestamp = df['timestamp'].max()
                        if hasattr(metrics_timestamp, 'to_pydatetime'):
                            metrics_timestamp = metrics_timestamp.to_pydatetime()

                        market_metrics = service.collect_market_metrics(symbol)
                        service.upsert_market_metrics(symbol, metrics_timestamp, market_metrics)

                        logger.info(f"Updated {len(df)} latest candles for {symbol} 15m")
                        total_updated += len(df)
                else:
                    # No candles exist - trigger initial backfill
                    logger.info(f"No candles for {symbol}, triggering initial backfill")

                    # Get earliest available date from exchange
                    earliest_dt = service.client.get_earliest_timestamp(symbol, '15m')
                    if not earliest_dt:
                        earliest_dt = datetime(2020, 1, 1)  # Fallback to 2020

                    end_date = datetime.utcnow()

                    # Create and execute backfill job
                    job = service.create_backfill_job(
                        symbol=symbol,
                        timeframe=TimeFrame.M15,
                        start_date=earliest_dt,
                        end_date=end_date
                    )

                    # Trigger async backfill
                    execute_backfill_task.delay(job.job_id)
                    backfills_triggered += 1
                    logger.info(f"Triggered backfill job {job.job_id} for {symbol}")

            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                continue

        return {
            "status": "completed",
            "candles_updated": total_updated,
            "backfills_triggered": backfills_triggered,
            "pairs_tracked": len(TRACKED_PAIRS)
        }

    except Exception as e:
        logger.error(f"Update latest candles task failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="drift.monitor")
def monitor_drift_task():
    """Monitor model drift (runs daily)"""
    from apps.api.db.models import (
        ModelRegistry as ModelRecord,
        DriftMetrics,
        FeatureSet,
        TimeFrame
    )

    logger.info("Monitoring model drift...")

    registry = ModelRegistry()
    deployments = getattr(registry, 'index', {}).get('deployments', {})

    if not deployments:
        logger.info("No deployments found for drift monitoring")
        return {"status": "completed", "models_checked": 0, "results": []}

    detector = DriftDetector(
        psi_threshold=settings.DRIFT_PSI_THRESHOLD,
        ks_threshold=settings.DRIFT_KS_THRESHOLD
    )

    db = SessionLocal()
    results = []

    def _load_feature_frame(symbol, timeframe_enum, start=None, end=None, exclusive_start=False):
        query = db.query(FeatureSet).filter(
            FeatureSet.symbol == symbol,
            FeatureSet.timeframe == timeframe_enum
        )

        if start is not None:
            if exclusive_start:
                query = query.filter(FeatureSet.timestamp > start)
            else:
                query = query.filter(FeatureSet.timestamp >= start)

        if end is not None:
            query = query.filter(FeatureSet.timestamp <= end)

        rows = query.order_by(FeatureSet.timestamp.asc()).all()

        if not rows:
            return pd.DataFrame(), []

        records = []
        timestamps = []

        feature_columns = [col.name for col in FeatureSet.__table__.columns]
        exclude_cols = {'id', 'created_at'}

        for row in rows:
            row_dict = {}
            for col in feature_columns:
                if col in exclude_cols:
                    continue
                value = getattr(row, col)
                row_dict[col] = value

            timestamps.append(row.timestamp)
            records.append(row_dict)

        df = pd.DataFrame(records)

        # Keep only numeric feature columns for drift detection
        feature_df = df.drop(columns=['symbol', 'timeframe', 'timestamp'], errors='ignore')
        feature_df = feature_df.select_dtypes(include=[np.number]).fillna(0)

        return feature_df, timestamps

    def _load_prediction_array(model_id, start=None, end=None, exclusive_start=False):
        query = db.query(Signal).filter(Signal.model_id == model_id)

        if start is not None:
            if exclusive_start:
                query = query.filter(Signal.timestamp > start)
            else:
                query = query.filter(Signal.timestamp >= start)

        if end is not None:
            query = query.filter(Signal.timestamp <= end)

        rows = query.order_by(Signal.timestamp.asc()).all()

        if not rows:
            return np.array([])

        predictions = []

        for row in rows:
            if row.confidence is None:
                continue
            try:
                predictions.append(float(row.confidence))
            except (TypeError, ValueError):
                continue

        return np.array(predictions)

    try:
        for deployment in deployments.values():
            symbol = deployment.get('symbol')
            timeframe_value = deployment.get('timeframe')
            environment = deployment.get('environment', 'production')

            if not symbol or not timeframe_value:
                continue

            model_entry = registry.get_deployed_model(symbol, timeframe_value, environment)

            if not model_entry:
                logger.warning(
                    "No model entry found for deployment %s %s (%s)",
                    symbol,
                    timeframe_value,
                    environment
                )
                continue

            model_id = model_entry.get('model_id')

            if not model_id:
                logger.warning("Deployment for %s %s missing model_id", symbol, timeframe_value)
                continue

            db_model = db.query(ModelRecord).filter(ModelRecord.model_id == model_id).first()

            if not db_model:
                logger.warning("Model %s not found in database", model_id)
                continue

            try:
                timeframe_enum = TimeFrame(timeframe_value)
            except ValueError:
                logger.error("Invalid timeframe %s for model %s", timeframe_value, model_id)
                continue

            baseline_start = getattr(db_model, 'train_start', None)
            baseline_end = getattr(db_model, 'train_end', None)
            current_start = getattr(db_model, 'oos_start', None) or baseline_end

            if baseline_start is None or baseline_end is None or current_start is None:
                logger.warning("Insufficient training metadata for model %s", model_id)
                continue

            baseline_features, _ = _load_feature_frame(
                symbol,
                timeframe_enum,
                start=baseline_start,
                end=baseline_end,
                exclusive_start=False
            )

            current_features, current_timestamps = _load_feature_frame(
                symbol,
                timeframe_enum,
                start=current_start,
                end=None,
                exclusive_start=True
            )

            if baseline_features.empty or current_features.empty:
                logger.warning("Insufficient feature data for drift detection on %s", model_id)
                continue

            shared_columns = baseline_features.columns.intersection(current_features.columns)

            if shared_columns.empty:
                logger.warning("No shared numeric features for model %s", model_id)
                continue

            baseline_features = baseline_features[shared_columns]
            current_features = current_features[shared_columns]

            baseline_predictions = _load_prediction_array(
                model_id,
                start=baseline_start,
                end=baseline_end,
                exclusive_start=False
            )

            current_predictions = _load_prediction_array(
                model_id,
                start=current_start,
                end=None,
                exclusive_start=True
            )

            if baseline_predictions.size == 0 or current_predictions.size == 0:
                baseline_predictions = None
                current_predictions = None

            drift_result = detector.check_drift(
                baseline_features,
                current_features,
                baseline_predictions,
                current_predictions
            )

            feature_drift_scores = {
                feature: {
                    'psi': float(values['psi']),
                    'ks_statistic': float(values['ks_statistic']),
                    'ks_pvalue': float(values['ks_pvalue']),
                    'drift_detected': bool(values['drift_detected'])
                }
                for feature, values in drift_result['feature_drift'].items()
            }

            if drift_result['prediction_drift']:
                prediction_drift_value = float(drift_result['prediction_drift']['psi'])
            else:
                prediction_drift_value = None

            if feature_drift_scores:
                psi_score = max(v['psi'] for v in feature_drift_scores.values())
                ks_statistic = max(v['ks_statistic'] for v in feature_drift_scores.values())
            else:
                psi_score = None
                ks_statistic = None

            if current_timestamps:
                latest_ts = max(current_timestamps)
                data_freshness_hours = (datetime.utcnow() - latest_ts).total_seconds() / 3600.0
            else:
                data_freshness_hours = None

            drift_record = DriftMetrics(
                model_id=model_id,
                timestamp=datetime.utcnow(),
                psi_score=psi_score,
                ks_statistic=ks_statistic,
                feature_drift_scores=feature_drift_scores,
                prediction_drift=prediction_drift_value,
                data_freshness_hours=data_freshness_hours,
                drift_detected=bool(drift_result['overall_drift_detected'])
            )

            db.add(drift_record)

            if drift_result['overall_drift_detected']:
                db_model.is_active = False
            else:
                db_model.is_active = True

            db.commit()

            results.append({
                'model_id': model_id,
                'drift_detected': drift_result['overall_drift_detected'],
                'num_features_with_drift': drift_result['num_features_with_drift'],
                'total_features': drift_result['total_features']
            })

    except Exception as exc:
        db.rollback()
        logger.error("Drift monitoring task failed: %s", exc, exc_info=True)
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()

    return {
        "status": "completed",
        "models_checked": len(results),
        "results": results
    }


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

        # Parse dates (handle Z suffix and timezone-aware strings)
        def _parse_dt(value):
            if isinstance(value, dt):
                parsed = value
            elif isinstance(value, str):
                cleaned = value.strip()
                if cleaned.endswith('Z'):
                    cleaned = cleaned[:-1] + '+00:00'
                try:
                    parsed = dt.fromisoformat(cleaned)
                except ValueError as exc:
                    raise ValueError(f"Invalid datetime format: {value}") from exc
            else:
                raise TypeError(f"Unsupported datetime value: {value!r}")

            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)

            return parsed

        start = _parse_dt(start_date)
        end = _parse_dt(end_date)

        if end <= start:
            raise ValueError("end_date must be after start_date")

        timeframe_enum = TimeFrame(timeframe)

        # Create or reuse job record (API may have pre-created it)
        signal_job = db.query(SignalGenerationJob).filter_by(job_id=self.request.id).first()

        if signal_job is None:
            signal_job = SignalGenerationJob(
                job_id=self.request.id,
                symbol=symbol,
                timeframe=timeframe_enum,
                start_date=start,
                end_date=end,
                status='generating',
                started_at=dt.utcnow()
            )
            db.add(signal_job)
        else:
            signal_job.symbol = symbol
            signal_job.timeframe = timeframe_enum
            signal_job.start_date = start
            signal_job.end_date = end
            signal_job.status = 'generating'
            signal_job.started_at = dt.utcnow()
            signal_job.progress_pct = 0.0
            signal_job.signals_generated = 0
            signal_job.signals_backtested = 0
            signal_job.error_message = None
            signal_job.elapsed_seconds = None
            signal_job.completed_at = None

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

        # Persist a manageable subset of generated signals for inspection
        max_records_to_store = 1000
        if len(signals) > max_records_to_store:
            signals_to_store = signals[-max_records_to_store:]
        else:
            signals_to_store = signals

        _ensure_historical_table(db)
        rows_to_insert = []
        for payload in signals_to_store:
            try:
                required_numeric_fields = [
                    'entry_price', 'tp1_price', 'tp2_price', 'tp3_price', 'sl_price',
                    'leverage', 'position_size_usd', 'quantity',
                    'expected_net_profit_pct', 'expected_net_profit_usd'
                ]
                if any(
                    payload.get(field) is None or
                    (isinstance(payload.get(field), float) and math.isnan(payload.get(field)))
                    for field in required_numeric_fields
                ):
                    continue
                rows_to_insert.append({
                    'signal_id': payload['signal_id'],
                    'job_id': signal_job.job_id,
                    'symbol': payload['symbol'],
                    'timeframe': timeframe,
                    'side': (payload['side'].value if isinstance(payload['side'], Side) else str(payload['side'])).lower(),
                    'entry_price': payload['entry_price'],
                    'timestamp': payload['timestamp'],
                    'tp1_price': payload['tp1_price'],
                    'tp2_price': payload['tp2_price'],
                    'tp3_price': payload['tp3_price'],
                    'sl_price': payload['sl_price'],
                    'expected_net_profit_pct': payload.get('expected_net_profit_pct'),
                    'expected_net_profit_usd': payload.get('expected_net_profit_usd'),
                    'confidence': payload.get('confidence'),
                    'model_id': payload.get('model_id'),
                    'risk_profile': (payload['risk_profile'].value if isinstance(payload['risk_profile'], RiskProfile) else str(payload['risk_profile'])).lower(),
                })
            except Exception as exc:
                logger.error("Failed to prepare historical signal %s for persistence: %s", payload.get('signal_id'), exc)
        if rows_to_insert:
            try:
                insert_stmt = text(
                    """
                    INSERT INTO historical_signal_snapshots (
                        signal_id,
                        job_id,
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
                        risk_profile
                    ) VALUES (
                        :signal_id,
                        :job_id,
                        :symbol,
                        :timeframe,
                        :side,
                        :entry_price,
                        :timestamp,
                        :tp1_price,
                        :tp2_price,
                        :tp3_price,
                        :sl_price,
                        :expected_net_profit_pct,
                        :expected_net_profit_usd,
                        :confidence,
                        :model_id,
                        :risk_profile
                    )
                    ON CONFLICT (signal_id) DO NOTHING
                    """
                )
                with db.no_autoflush:
                    db.execute(insert_stmt, rows_to_insert)
                db.commit()
            except Exception as exc:
                logger.error("Failed to persist %s historical signals: %s", len(rows_to_insert), exc)
                db.rollback()
            else:
                logger.info("Persisted %s historical signals for inspection", len(rows_to_insert))

        # Update progress
        signal_job.signals_generated = len(signals)
        signal_job.progress_pct = 50.0
        db.commit()

        # Backtest the generated signals
        backtest_results = backtest_signals(db, signals)
        trade_results = backtest_results.get('trades', []) if isinstance(backtest_results, dict) else []

        # Update job as completed
        signal_job.status = 'completed'
        signal_job.completed_at = dt.utcnow()
        if isinstance(backtest_results, dict):
            signal_job.signals_backtested = backtest_results.get('total_trades', 0)
            signal_job.win_rate = backtest_results.get('win_rate', 0)
            signal_job.avg_profit_pct = backtest_results.get('avg_profit_pct', 0)
            signal_job.total_pnl_usd = backtest_results.get('total_pnl_usd', 0)
        else:
            signal_job.signals_backtested = len(backtest_results)
            signal_job.win_rate = 0
            signal_job.avg_profit_pct = 0
            signal_job.total_pnl_usd = 0
        signal_job.progress_pct = 100.0

        if signal_job.started_at:
            elapsed = (dt.utcnow() - signal_job.started_at).total_seconds()
            signal_job.elapsed_seconds = elapsed

        db.commit()

        if trade_results:
            logger.info("Historical job %s has %s trade results", signal_job.job_id, len(trade_results))
            update_stmt = text(
                """
                UPDATE historical_signal_snapshots
                SET actual_net_pnl_pct = :actual_net_pnl_pct,
                    actual_net_pnl_usd = :actual_net_pnl_usd,
                    final_status = :final_status,
                    duration_minutes = :duration_minutes
                WHERE signal_id = :signal_id
                """
            )
            for trade in trade_results:
                minutes = trade.get('duration_minutes')
                if minutes is None:
                    duration_hours = trade.get('duration_hours')
                    if duration_hours is not None:
                        minutes = int(duration_hours * 60)

                actual_pct = trade.get('event_net_pnl_pct')
                if actual_pct is None:
                    actual_pct = trade.get('net_pnl_pct')

                actual_usd = trade.get('event_net_pnl_usd')
                if actual_usd is None:
                    actual_usd = trade.get('net_pnl')

                final_status = trade.get('status')
                if isinstance(final_status, SignalStatus):
                    final_status = final_status.value

                params = {
                    'signal_id': trade.get('signal_id'),
                    'actual_net_pnl_pct': actual_pct,
                    'actual_net_pnl_usd': actual_usd,
                    'final_status': final_status,
                    'duration_minutes': minutes,
                }
                logger.info(
                    "Updating historical snapshot %s: pct=%s usd=%s status=%s duration=%s",
                    params['signal_id'],
                    params['actual_net_pnl_pct'],
                    params['actual_net_pnl_usd'],
                    params['final_status'],
                    params['duration_minutes'],
                )
                try:
                    result = db.execute(update_stmt, params)
                    if result.rowcount == 0:
                        logger.debug(
                            "No snapshot row updated for historical signal %s",
                            params['signal_id'],
                        )
                except Exception as exc:
                    logger.error("Failed to update historical snapshot %s: %s", params['signal_id'], exc)
            db.commit()
            logger.info(
                "Updated actual results for %s historical signals",
                len(trade_results),
            )

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
    'expire-signals-every-5-minutes': {
        'task': 'signals.expire',
        'schedule': 300.0,  # 5 minutes
    },
    'monitor-drift-daily': {
        'task': 'drift.monitor',
        'schedule': 86400.0,  # 1 day
    },
}
