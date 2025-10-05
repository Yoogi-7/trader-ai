from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.config import settings
from apps.api.db.base import Base
from apps.api.db.models import (
    OHLCV,
    ModelRegistry as ModelRegistryRecord,
    RiskProfile,
    Side,
    Signal,
    SignalStatus,
    TimeFrame
)
from apps.ml.signal_engine import SignalEngine
from apps.ml.signal_engine import SignalGenerator
from apps.ml.worker import generate_signals_task


class DummyRegistry:
    def __init__(self, deployment):
        self._deployment = deployment

    def get_deployed_model(self, symbol, timeframe, environment='production'):
        return self._deployment


class DummyModel:
    def __init__(self, probability=0.8):
        self.probability = probability
        self.feature_names = ['ema_21', 'rsi_14', 'atr_14', 'volume']

    def load(self, path):
        return self

    def predict_proba(self, X):
        return [self.probability for _ in range(len(X))]


def create_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


def insert_mock_ohlcv(session, symbol="BTC/USDT", rows=120):
    base_ts = datetime.utcnow() - timedelta(minutes=rows * 15)

    for idx in range(rows):
        ts = base_ts + timedelta(minutes=15 * idx)
        session.add(
            OHLCV(
                symbol=symbol,
                timeframe=TimeFrame.M15,
                timestamp=ts,
                open=50000 + idx,
                high=50000 + idx + 800,
                low=50000 + idx - 800,
                close=50000 + idx + 120,
                volume=150 + idx
            )
        )

    session.commit()


def test_signal_engine_pipeline_generates_profitable_signal():
    SessionLocal, engine = create_sqlite_session()
    session = SessionLocal()
    insert_mock_ohlcv(session)

    deployment = {
        'model_id': 'model123',
        'version': 'v1',
        'path': 'unused',
        'symbol': 'BTC/USDT',
        'timeframe': '15m'
    }

    engine_service = SignalEngine(
        db=session,
        registry=DummyRegistry(deployment),
        model_factory=lambda: DummyModel(0.8),
        lookback_bars=90
    )

    result = engine_service.generate_for_deployment(
        symbol='BTC/USDT',
        timeframe='15m',
        risk_profile=RiskProfile.MEDIUM,
        capital_usd=1000.0
    )

    assert result is not None
    assert result.accepted is True
    assert result.signal['expected_net_profit_pct'] >= settings.MIN_NET_PROFIT_PCT
    assert result.inference_metadata['confidence'] == pytest.approx(0.8)

    session.close()
    engine.dispose()


def test_generate_signals_task_returns_statistics(monkeypatch):
    SessionLocal, engine = create_sqlite_session()
    session = SessionLocal()
    insert_mock_ohlcv(session)

    # Seed registry table to satisfy FK constraints if enabled
    registry_record = ModelRegistryRecord(
        model_id='model123',
        symbol='BTC/USDT',
        timeframe=TimeFrame.M15,
        model_type='ensemble',
        version='v1',
        train_start=datetime.utcnow() - timedelta(days=200),
        train_end=datetime.utcnow() - timedelta(days=60),
        oos_start=datetime.utcnow() - timedelta(days=60),
        oos_end=datetime.utcnow() - timedelta(days=1),
        hyperparameters={}
    )
    session.add(registry_record)
    session.commit()
    session.close()

    def session_factory():
        return SessionLocal()

    monkeypatch.setattr('apps.ml.worker.SessionLocal', session_factory)

    class StubRegistry:
        def __init__(self):
            self.index = {
                'deployments': {
                    'BTC_USDT_15m_production': {
                        'symbol': 'BTC/USDT',
                        'timeframe': '15m',
                        'environment': 'production',
                        'model_id': 'model123',
                        'version': 'v1',
                        'path': 'unused'
                    }
                }
            }

        def get_deployed_model(self, symbol, timeframe, environment='production'):
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'environment': environment,
                'model_id': 'model123',
                'version': 'v1',
                'path': 'unused'
            }

    generator = SignalGenerator()

    class StubSignalEngine:
        def __init__(self, db, registry=None, **kwargs):
            self.db = db
            self.registry = registry

        def generate_for_deployment(self, symbol, timeframe, environment='production', **kwargs):
            timestamp = datetime.utcnow()
            signal = generator.generate_signal(
                symbol=symbol,
                side=Side.LONG,
                entry_price=52000.0,
                atr=1500.0,
                risk_profile=RiskProfile.MEDIUM,
                capital_usd=1000.0,
                confidence=0.7,
                timestamp=timestamp
            )

            if not signal:
                return None

            signal['model_id'] = 'model123'
            signal['model_version'] = 'v1'

            return SimpleNamespace(
                signal=signal,
                model_info={
                    'model_id': 'model123',
                    'version': 'v1',
                    'path': 'unused'
                },
                risk_filters={'spread': True, 'liquidity': True, 'profit': True, 'correlation': True, 'confidence': True},
                inference_metadata={'probability': 0.7, 'confidence': 0.7, 'side': 'long', 'timestamp': timestamp},
                accepted=True
            )

    monkeypatch.setattr('apps.ml.worker.ModelRegistry', lambda: StubRegistry())
    monkeypatch.setattr('apps.ml.worker.SignalEngine', StubSignalEngine)

    broadcasts = []

    async def fake_broadcast(message):
        broadcasts.append(message)

    monkeypatch.setattr('apps.api.main.manager.broadcast', fake_broadcast)

    result = generate_signals_task.run()

    assert result['signals_generated'] == 1
    assert result['broadcasts'] == 1
    assert result['metrics']['average_confidence'] == pytest.approx(0.7)

    session = SessionLocal()
    stored_signals = session.query(Signal).all()
    assert len(stored_signals) == 1
    assert stored_signals[0].status == SignalStatus.ACTIVE

    assert len(broadcasts) == 1
    assert broadcasts[0]['type'] == 'signal.created'

    session.close()
    engine.dispose()
