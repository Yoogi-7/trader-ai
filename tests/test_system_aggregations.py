import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api import cache
from apps.api.db.models import Base, RiskProfile, Side, Signal, TradeResult
from apps.api.routers import system
from apps.api.routers.system import ANALYTICS_CACHE_TTL_SECONDS


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _create_signal_with_result(
    session: Session,
    *,
    signal_id: str,
    risk_profile: RiskProfile,
    closed_at: datetime,
    net_pnl_usd: float,
    net_pnl_pct: float,
    position_size_usd: float,
) -> None:
    timestamp = closed_at - timedelta(hours=1)
    signal = Signal(
        signal_id=signal_id,
        symbol="BTC/USDT",
        side=Side.LONG,
        entry_price=100.0,
        timestamp=timestamp,
        tp1_price=110.0,
        tp2_price=120.0,
        tp3_price=130.0,
        sl_price=90.0,
        leverage=2.0,
        position_size_usd=position_size_usd,
        quantity=1.0,
        expected_net_profit_pct=5.0,
        expected_net_profit_usd=5.0,
        valid_until=timestamp + timedelta(hours=4),
        risk_profile=risk_profile,
    )
    session.add(signal)

    trade_result = TradeResult(
        signal_id=signal_id,
        net_pnl_usd=net_pnl_usd,
        net_pnl_pct=net_pnl_pct,
        closed_at=closed_at,
    )
    session.add(trade_result)

    session.commit()


@pytest.mark.asyncio
async def test_get_system_pnl_aggregation_groups_by_day_and_profile(monkeypatch, db_session: Session):
    monkeypatch.setattr(cache, "get_cached_json", lambda key: None)
    stored_cache = {}

    def _fake_set(key: str, value, ttl: int) -> None:
        stored_cache[key] = {"value": value, "ttl": ttl}

    monkeypatch.setattr(cache, "set_cached_json", _fake_set)

    base_date = datetime(2024, 1, 1, 12, 0, 0)
    _create_signal_with_result(
        db_session,
        signal_id="sig-low-1",
        risk_profile=RiskProfile.LOW,
        closed_at=base_date,
        net_pnl_usd=150.0,
        net_pnl_pct=3.0,
        position_size_usd=1000.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-low-2",
        risk_profile=RiskProfile.LOW,
        closed_at=base_date + timedelta(hours=2),
        net_pnl_usd=50.0,
        net_pnl_pct=1.0,
        position_size_usd=800.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-med-1",
        risk_profile=RiskProfile.MEDIUM,
        closed_at=base_date,
        net_pnl_usd=-20.0,
        net_pnl_pct=-0.5,
        position_size_usd=1200.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-high-1",
        risk_profile=RiskProfile.HIGH,
        closed_at=base_date + timedelta(days=1),
        net_pnl_usd=200.0,
        net_pnl_pct=4.0,
        position_size_usd=1500.0,
    )

    response = await system.get_system_pnl(db=db_session)

    assert [r.risk_profile for r in response] == [
        RiskProfile.LOW,
        RiskProfile.MEDIUM,
        RiskProfile.HIGH,
    ]
    assert response[0].date.isoformat() == "2024-01-01"
    assert response[0].net_pnl_usd == pytest.approx(200.0)
    assert response[0].trade_count == 2
    assert response[1].net_pnl_usd == pytest.approx(-20.0)
    assert response[2].date.isoformat() == "2024-01-02"
    assert stored_cache["system:pnl"]["ttl"] == ANALYTICS_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_system_exposure_aggregation_and_cache(monkeypatch, db_session: Session):
    monkeypatch.setattr(cache, "get_cached_json", lambda key: None)
    stored_cache = {}

    def _fake_set(key: str, value, ttl: int) -> None:
        stored_cache[key] = {"value": value, "ttl": ttl}

    monkeypatch.setattr(cache, "set_cached_json", _fake_set)

    base_date = datetime(2024, 1, 1, 12, 0, 0)
    _create_signal_with_result(
        db_session,
        signal_id="sig-low-1",
        risk_profile=RiskProfile.LOW,
        closed_at=base_date,
        net_pnl_usd=150.0,
        net_pnl_pct=3.0,
        position_size_usd=1000.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-low-2",
        risk_profile=RiskProfile.LOW,
        closed_at=base_date + timedelta(hours=2),
        net_pnl_usd=50.0,
        net_pnl_pct=1.0,
        position_size_usd=800.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-med-1",
        risk_profile=RiskProfile.MEDIUM,
        closed_at=base_date,
        net_pnl_usd=-20.0,
        net_pnl_pct=-0.5,
        position_size_usd=1200.0,
    )
    _create_signal_with_result(
        db_session,
        signal_id="sig-high-1",
        risk_profile=RiskProfile.HIGH,
        closed_at=base_date + timedelta(days=1),
        net_pnl_usd=200.0,
        net_pnl_pct=4.0,
        position_size_usd=1500.0,
    )

    # Query exposures and assert aggregation on the inserted dataset.
    response = await system.get_system_exposure(db=db_session)

    assert response[0].exposure_usd == pytest.approx(1800.0)
    assert response[1].exposure_usd == pytest.approx(1200.0)
    assert response[2].exposure_usd == pytest.approx(1500.0)
    assert stored_cache["system:exposure"]["ttl"] == ANALYTICS_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_system_exposure_returns_cached(monkeypatch, db_session: Session):
    cached_payload = [
        {"date": "2024-02-01", "risk_profile": "low", "exposure_usd": 999.0}
    ]

    monkeypatch.setattr(cache, "get_cached_json", lambda key: cached_payload)

    set_called = False

    def _fake_set(*args, **kwargs):
        nonlocal set_called
        set_called = True

    monkeypatch.setattr(cache, "set_cached_json", _fake_set)

    response = await system.get_system_exposure(db=db_session)

    assert len(response) == 1
    assert response[0].risk_profile == RiskProfile.LOW
    assert response[0].exposure_usd == pytest.approx(999.0)
    assert set_called is False
