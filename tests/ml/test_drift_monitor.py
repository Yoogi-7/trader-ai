from datetime import datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db.base import Base
from apps.api.db.models import DriftMetrics, FeatureSet, ModelRegistry, TimeFrame
from apps.ml import worker


class _StubRegistry:
    """Simple registry stub exposing deployed model metadata."""

    def __init__(self, model_entry, environment="production"):
        self._model_entry = model_entry
        self._environment = environment
        deployment_key = f"{model_entry['symbol']}_{model_entry['timeframe']}_{environment}"
        self.index = {
            'deployments': {
                deployment_key: {
                    'symbol': model_entry['symbol'],
                    'timeframe': model_entry['timeframe'],
                    'version': model_entry['version'],
                    'model_id': model_entry['model_id'],
                    'environment': environment
                }
            }
        }

    def get_deployed_model(self, symbol, timeframe, environment="production"):
        if (
            symbol == self._model_entry['symbol']
            and timeframe == self._model_entry['timeframe']
            and environment == self._environment
        ):
            return self._model_entry
        return None


@pytest.fixture()
def sqlite_session(monkeypatch):
    """Provide isolated in-memory database and patch Celery worker session."""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr(worker, "SessionLocal", TestSession)

    yield TestSession

    Base.metadata.drop_all(engine)


def _insert_feature_rows(session, symbol, timeframe, timestamps, values):
    for ts, value in zip(timestamps, values):
        session.add(
            FeatureSet(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                ema_9=float(value),
                ema_21=float(value) * 1.01,
                atr_14=1.0
            )
        )


def _prepare_model(session, *, model_id="model-1", is_active=True):
    now = datetime.utcnow()
    train_start = now - timedelta(days=30)
    train_end = now - timedelta(days=15)
    oos_start = train_end + timedelta(minutes=15)
    oos_end = now - timedelta(days=1)

    model = ModelRegistry(
        model_id=model_id,
        symbol="BTC/USDT",
        timeframe=TimeFrame.M15,
        model_type="lgbm",
        version="v1",
        train_start=train_start,
        train_end=train_end,
        oos_start=oos_start,
        oos_end=oos_end,
        is_active=is_active,
        is_production=True,
        artifact_path="/tmp/model"
    )

    session.add(model)
    session.flush()

    return model, train_start, train_end, oos_start


def _patch_registry(monkeypatch, model_entry):
    stub = _StubRegistry(model_entry)
    monkeypatch.setattr(worker, "ModelRegistry", lambda: stub)
    return stub


def test_monitor_drift_no_drift(sqlite_session, monkeypatch):
    session = sqlite_session()
    model, train_start, train_end, oos_start = _prepare_model(session)

    baseline_times = [train_start + timedelta(minutes=15 * i) for i in range(60)]
    current_times = [oos_start + timedelta(minutes=15 * (i + 1)) for i in range(60)]

    rng = np.random.default_rng(42)
    baseline_values = rng.normal(0.0, 0.5, size=len(baseline_times))
    current_values = baseline_values + rng.normal(0.0, 0.05, size=len(current_times))

    _insert_feature_rows(session, model.symbol, model.timeframe, baseline_times, baseline_values)
    _insert_feature_rows(session, model.symbol, model.timeframe, current_times, current_values)

    session.commit()

    deployed_model = {
        'model_id': model.model_id,
        'symbol': model.symbol,
        'timeframe': model.timeframe.value,
        'version': model.version,
        'path': '/tmp/model',
        'metrics': {}
    }

    _patch_registry(monkeypatch, deployed_model)

    result = worker.monitor_drift_task()

    assert result['status'] == 'completed'
    assert result['models_checked'] == 1
    assert result['results'][0]['drift_detected'] is False

    session.close()
    session = sqlite_session()

    metrics = session.query(DriftMetrics).filter_by(model_id=model.model_id).all()
    assert len(metrics) == 1
    assert metrics[0].drift_detected is False
    assert metrics[0].psi_score is None or metrics[0].psi_score < 0.15 + 1e-2

    refreshed_model = session.query(ModelRegistry).filter_by(model_id=model.model_id).one()
    assert refreshed_model.is_active is True


def test_monitor_drift_detects_drift(sqlite_session, monkeypatch):
    session = sqlite_session()
    model, train_start, train_end, oos_start = _prepare_model(session)

    baseline_times = [train_start + timedelta(minutes=15 * i) for i in range(60)]
    current_times = [oos_start + timedelta(minutes=15 * (i + 1)) for i in range(60)]

    baseline_values = np.linspace(0.0, 1.0, num=len(baseline_times))
    current_values = baseline_values + 5.0  # large shift to trigger PSI/KS

    _insert_feature_rows(session, model.symbol, model.timeframe, baseline_times, baseline_values)
    _insert_feature_rows(session, model.symbol, model.timeframe, current_times, current_values)

    session.commit()

    deployed_model = {
        'model_id': model.model_id,
        'symbol': model.symbol,
        'timeframe': model.timeframe.value,
        'version': model.version,
        'path': '/tmp/model',
        'metrics': {}
    }

    _patch_registry(monkeypatch, deployed_model)

    result = worker.monitor_drift_task()

    assert result['status'] == 'completed'
    assert result['models_checked'] == 1
    assert result['results'][0]['drift_detected'] is True

    session.close()
    session = sqlite_session()

    metrics = session.query(DriftMetrics).filter_by(model_id=model.model_id).all()
    assert len(metrics) == 1
    assert metrics[0].drift_detected is True
    assert metrics[0].psi_score > 0.15

    refreshed_model = session.query(ModelRegistry).filter_by(model_id=model.model_id).one()
    assert refreshed_model.is_active is False
