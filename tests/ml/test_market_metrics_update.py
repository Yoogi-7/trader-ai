import pandas as pd
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

from apps.api.db.base import Base
from apps.api.db.models import OHLCV, MarketMetrics, TimeFrame
from apps.ml import backfill
from apps.ml import worker


def test_update_latest_candles_task_records_market_metrics(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    initial_session = TestSessionLocal()
    base_timestamp = datetime.utcnow() - timedelta(minutes=30)
    initial_session.add(
        OHLCV(
            symbol="BTC/USDT",
            timeframe=TimeFrame.M15,
            timestamp=base_timestamp,
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=10.0,
        )
    )
    initial_session.commit()
    initial_session.close()

    mock_client = Mock()
    next_timestamp = base_timestamp + timedelta(minutes=15)
    df = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp(next_timestamp),
                "open": 101.0,
                "high": 101.5,
                "low": 100.5,
                "close": 101.2,
                "volume": 12.0,
            }
        ]
    )
    mock_client.fetch_ohlcv_range.return_value = df
    mock_client.fetch_order_book.return_value = {
        "bids": [[100.0, 1.0]],
        "asks": [[100.5, 1.2]],
    }
    mock_client.fetch_open_interest.return_value = 12345.6
    mock_client.fetch_funding_rate.return_value = 0.0001

    class TestBackfillService(backfill.BackfillService):
        def __init__(self, db, exchange_id=None):
            super().__init__(db, exchange_id=exchange_id, client=mock_client)

    monkeypatch.setattr(worker, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(backfill, "BackfillService", TestBackfillService)
    monkeypatch.setattr(backfill.BackfillService, "_upsert_ohlcv", lambda self, symbol, timeframe, data: None)

    result = worker.update_latest_candles_task()

    assert result["status"] == "completed"
    assert result["candles_updated"] == 1

    check_session = TestSessionLocal()
    metrics_records = check_session.query(MarketMetrics).all()
    assert len(metrics_records) == 1

    metrics = metrics_records[0]
    expected_spread_bps = ((100.5 - 100.0) / ((100.5 + 100.0) / 2)) * 10_000

    assert metrics.symbol == "BTC/USDT"
    assert metrics.timestamp == next_timestamp
    assert metrics.open_interest == 12345.6
    assert metrics.spread_bps == pytest.approx(expected_spread_bps, rel=1e-6)
    assert metrics.funding_rate == 0.0001

    check_session.close()
    engine.dispose()
