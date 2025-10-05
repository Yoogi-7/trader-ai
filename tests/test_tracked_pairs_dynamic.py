from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db.base import Base
from apps.api.db import models
from apps.common.tracked_pairs import (
    bump_tracked_pairs_version,
    get_tracked_pairs,
    invalidate_tracked_pairs_cache,
)
from apps.ml import worker as worker_module


@pytest.fixture
def sqlite_sessionmaker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class DummyClient:
    def fetch_ohlcv_range(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame()

    def get_earliest_timestamp(self, *_: object) -> None:
        return None


def test_update_task_detects_new_tracked_pair(sqlite_sessionmaker, monkeypatch):
    Session = sqlite_sessionmaker

    invalidate_tracked_pairs_cache()

    created_jobs: list[tuple[str, str]] = []

    class DummyBackfillService:
        def __init__(self, db_session):
            self.db = db_session
            self.client = DummyClient()

        def _upsert_ohlcv(self, *_: object) -> None:  # pragma: no cover - not used in this test
            return None

        def create_backfill_job(self, symbol, timeframe, start_date, end_date):  # noqa: ANN001
            created_jobs.append((symbol, getattr(timeframe, "value", timeframe)))
            return SimpleNamespace(job_id=f"job-{symbol}-{getattr(timeframe, 'value', timeframe)}")

    class DummyExecute:
        @staticmethod
        def delay(_job_id: str) -> None:
            return None

    monkeypatch.setattr(worker_module, "SessionLocal", Session)
    monkeypatch.setattr(worker_module, "BackfillService", DummyBackfillService)
    monkeypatch.setattr(worker_module, "execute_backfill_task", DummyExecute)

    # Seed initial tracked pair
    with Session() as db:
        pair = models.TrackedPair(
            symbol="BTC/USDT",
            timeframe=models.TimeFrame.M15,
            is_active=True,
        )
        db.add(pair)
        bump_tracked_pairs_version(db)
        db.commit()

    first_result = worker_module.update_latest_candles_task()

    assert first_result["pairs_tracked"] == 1
    assert any(symbol == "BTC/USDT" for symbol, _ in created_jobs)

    created_jobs.clear()

    # Add a new tracked pair and verify it is picked up on subsequent runs
    with Session() as db:
        new_pair = models.TrackedPair(
            symbol="ETH/USDT",
            timeframe=models.TimeFrame.M15,
            is_active=True,
        )
        db.add(new_pair)
        bump_tracked_pairs_version(db)
        db.commit()

    second_result = worker_module.update_latest_candles_task()

    assert second_result["pairs_tracked"] == 2
    assert any(symbol == "ETH/USDT" for symbol, _ in created_jobs)

    # Ensure helper returns both tracked pairs without relying on cache
    with Session() as db:
        invalidate_tracked_pairs_cache()
        pairs = get_tracked_pairs(db, use_cache=False)

    symbols = {pair.symbol for pair in pairs}
    assert symbols == {"BTC/USDT", "ETH/USDT"}
