from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db.base import Base
from apps.api.db.models import RiskProfile, Side, Signal, SignalStatus
from apps.ml.worker import expire_signals_task


def create_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), engine


@pytest.mark.parametrize("initial_status", [SignalStatus.ACTIVE, SignalStatus.PENDING])
def test_expire_signals_task_updates_expired_records(monkeypatch, initial_status):
    SessionLocal, engine = create_sqlite_session()

    session = SessionLocal()

    expired_signal = Signal(
        signal_id=f"expired-{initial_status.value}",
        symbol="BTC/USDT",
        side=Side.LONG,
        entry_price=52000.0,
        timestamp=datetime.utcnow() - timedelta(hours=2),
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
        valid_until=datetime.utcnow() - timedelta(minutes=5),
        status=initial_status,
        risk_profile=RiskProfile.MEDIUM,
    )

    active_signal = Signal(
        signal_id="active-signal",
        symbol="ETH/USDT",
        side=Side.SHORT,
        entry_price=3500.0,
        timestamp=datetime.utcnow() - timedelta(minutes=30),
        tp1_price=3400.0,
        tp1_pct=30.0,
        tp2_price=3300.0,
        tp2_pct=40.0,
        tp3_price=3200.0,
        tp3_pct=30.0,
        sl_price=3600.0,
        leverage=3.0,
        margin_mode="ISOLATED",
        position_size_usd=150.0,
        quantity=0.05,
        risk_reward_ratio=1.8,
        estimated_liquidation=3900.0,
        max_loss_usd=60.0,
        model_id=None,
        confidence=0.6,
        expected_net_profit_pct=2.5,
        expected_net_profit_usd=37.5,
        valid_until=datetime.utcnow() + timedelta(hours=1),
        status=SignalStatus.ACTIVE,
        risk_profile=RiskProfile.MEDIUM,
    )

    session.add_all([expired_signal, active_signal])
    session.commit()

    expired_id = expired_signal.signal_id
    active_id = active_signal.signal_id

    session.close()

    def session_factory():
        return SessionLocal()

    monkeypatch.setattr("apps.ml.worker.SessionLocal", session_factory)

    result = expire_signals_task.run()

    assert result == {"expired": 1}

    session = SessionLocal()
    updated = session.query(Signal).filter_by(signal_id=expired_id).one()
    still_active = session.query(Signal).filter_by(signal_id=active_id).one()

    assert updated.status == SignalStatus.TIME_STOP
    assert updated.expired_at is not None
    assert updated.closed_at is not None
    assert updated.expired_at == updated.closed_at

    assert still_active.status == SignalStatus.ACTIVE
    assert still_active.expired_at is None
    assert still_active.closed_at is None

    session.close()
    engine.dispose()
