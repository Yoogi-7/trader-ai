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


def insert_correlated_ohlcv_pair(
    session,
    primary_symbol="BTC/USDT",
    secondary_symbol="ETH/USDT",
    rows=120
):
    base_ts = datetime.utcnow() - timedelta(minutes=rows * 15)

    for idx in range(rows):
        ts = base_ts + timedelta(minutes=15 * idx)
        primary_close = 50000 + idx + 120
        secondary_close = 2500 + idx * 5

        session.add(
            OHLCV(
                symbol=primary_symbol,
                timeframe=TimeFrame.M15,
                timestamp=ts,
                open=primary_close - 100,
                high=primary_close + 800,
                low=primary_close - 800,
                close=primary_close,
                volume=200 + idx
            )
        )

        session.add(
            OHLCV(
                symbol=secondary_symbol,
                timeframe=TimeFrame.M15,
                timestamp=ts,
                open=secondary_close - 25,
                high=secondary_close + 40,
                low=secondary_close - 45,
                close=secondary_close,
                volume=180 + idx
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


def test_signal_engine_pipeline_respects_position_limit():
    SessionLocal, engine = create_sqlite_session()
    session = SessionLocal()
    insert_mock_ohlcv(session)

    for idx in range(settings.MED_MAX_POSITIONS):
        session.add(
            Signal(
                signal_id=f"existing_{idx}",
                symbol="BTC/USDT",
                side=Side.LONG,
                entry_price=52000.0,
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                tp1_price=53000.0,
                tp1_pct=30.0,
                tp2_price=54000.0,
                tp2_pct=40.0,
                tp3_price=55000.0,
                tp3_pct=30.0,
                sl_price=51000.0,
                leverage=5.0,
                margin_mode="ISOLATED",
                position_size_usd=100.0,
                quantity=0.01,
                risk_reward_ratio=2.0,
                estimated_liquidation=45000.0,
                max_loss_usd=50.0,
                model_id=None,
                confidence=0.7,
                expected_net_profit_pct=3.0,
                expected_net_profit_usd=30.0,
                valid_until=datetime.utcnow() + timedelta(hours=1),
                status=SignalStatus.ACTIVE,
                risk_profile=RiskProfile.MEDIUM
            )
        )

    session.commit()

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
    assert result.accepted is False
    assert result.signal is None
    assert result.risk_filters['position_limit'] is False

    session.close()
    engine.dispose()


def test_signal_engine_blocks_highly_correlated_signal():
    SessionLocal, engine = create_sqlite_session()
    session = SessionLocal()

    insert_correlated_ohlcv_pair(session)

    deployment = {
        'model_id': 'model123',
        'version': 'v1',
        'path': 'unused',
        'symbol': 'BTC/USDT',
        'timeframe': '15m'
    }

    class AnySymbolRegistry(DummyRegistry):
        def get_deployed_model(self, symbol, timeframe, environment='production'):
            return {
                'model_id': 'model123',
                'version': 'v1',
                'path': 'unused',
                'symbol': symbol,
                'timeframe': timeframe
            }

    engine_service = SignalEngine(
        db=session,
        registry=AnySymbolRegistry(deployment),
        model_factory=lambda: DummyModel(0.8),
        lookback_bars=90
    )

    original_threshold = settings.CORRELATION_THRESHOLD
    settings.CORRELATION_THRESHOLD = 0.6

    try:
        first_result = engine_service.generate_for_deployment(
            symbol='BTC/USDT',
            timeframe='15m',
            risk_profile=RiskProfile.MEDIUM,
            capital_usd=1000.0
        )

        assert first_result is not None
        assert first_result.accepted is True
        assert engine_service.correlation_state.current_exposures['BTC/USDT'] == Side.LONG

        session.add(
            Signal(
                signal_id=first_result.signal['signal_id'],
                symbol=first_result.signal['symbol'],
                side=first_result.signal['side'],
                entry_price=first_result.signal['entry_price'],
                timestamp=first_result.signal['timestamp'],
                tp1_price=first_result.signal['tp1_price'],
                tp1_pct=first_result.signal['tp1_pct'],
                tp2_price=first_result.signal['tp2_price'],
                tp2_pct=first_result.signal['tp2_pct'],
                tp3_price=first_result.signal['tp3_price'],
                tp3_pct=first_result.signal['tp3_pct'],
                sl_price=first_result.signal['sl_price'],
                leverage=first_result.signal['leverage'],
                margin_mode=first_result.signal['margin_mode'],
                position_size_usd=first_result.signal['position_size_usd'],
                quantity=first_result.signal['quantity'],
                risk_reward_ratio=first_result.signal['risk_reward_ratio'],
                estimated_liquidation=first_result.signal['estimated_liquidation'],
                max_loss_usd=first_result.signal['max_loss_usd'],
                model_id=first_result.signal['model_id'],
                confidence=first_result.signal['confidence'],
                expected_net_profit_pct=first_result.signal['expected_net_profit_pct'],
                expected_net_profit_usd=first_result.signal['expected_net_profit_usd'],
                valid_until=first_result.signal['valid_until'],
                status=SignalStatus.ACTIVE,
                risk_profile=first_result.signal['risk_profile'],
                passed_spread_check=True,
                passed_liquidity_check=True,
                passed_profit_filter=True,
                passed_correlation_check=True
            )
        )
        session.commit()

        second_result = engine_service.generate_for_deployment(
            symbol='ETH/USDT',
            timeframe='15m',
            risk_profile=RiskProfile.MEDIUM,
            capital_usd=1000.0
        )

        assert second_result is not None
        assert second_result.accepted is False
        assert second_result.signal is None
        assert second_result.risk_filters['correlation'] is False
    finally:
        settings.CORRELATION_THRESHOLD = original_threshold
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
                risk_filters={
                    'spread': True,
                    'liquidity': True,
                    'profit': True,
                    'correlation': True,
                    'confidence': True,
                    'position_limit': True
                },
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


def test_generate_signals_task_skips_when_position_limit_reached(monkeypatch):
    SessionLocal, engine = create_sqlite_session()
    session = SessionLocal()
    insert_mock_ohlcv(session)

    for idx in range(settings.MED_MAX_POSITIONS):
        session.add(
            Signal(
                signal_id=f"active_{idx}",
                symbol="BTC/USDT",
                side=Side.LONG,
                entry_price=52000.0,
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                tp1_price=53000.0,
                tp1_pct=30.0,
                tp2_price=54000.0,
                tp2_pct=40.0,
                tp3_price=55000.0,
                tp3_pct=30.0,
                sl_price=51000.0,
                leverage=5.0,
                margin_mode="ISOLATED",
                position_size_usd=100.0,
                quantity=0.01,
                risk_reward_ratio=2.0,
                estimated_liquidation=45000.0,
                max_loss_usd=50.0,
                model_id=None,
                confidence=0.7,
                expected_net_profit_pct=3.0,
                expected_net_profit_usd=30.0,
                valid_until=datetime.utcnow() + timedelta(hours=1),
                status=SignalStatus.ACTIVE,
                risk_profile=RiskProfile.MEDIUM
            )
        )

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

    def signal_engine_factory(db, registry=None, **kwargs):
        return SignalEngine(
            db=db,
            registry=registry,
            model_factory=lambda: DummyModel(0.8),
            lookback_bars=90
        )

    monkeypatch.setattr('apps.ml.worker.ModelRegistry', lambda: StubRegistry())
    monkeypatch.setattr('apps.ml.worker.SignalEngine', signal_engine_factory)

    result = generate_signals_task.run()

    assert result['signals_generated'] == 0
    assert result['skipped'] == 1
    assert result['metrics']['skipped_due_to_filters'] == 1

    session = SessionLocal()
    assert session.query(Signal).count() == settings.MED_MAX_POSITIONS
    session.close()
    engine.dispose()
