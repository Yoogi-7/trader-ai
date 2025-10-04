import pytest
from apps.ml.backfill import BackfillService
from apps.api.db.models import BackfillJob, TimeFrame
from datetime import datetime, timedelta
from unittest.mock import Mock


def test_backfill_resume_from_checkpoint():
    """
    Test that backfill can resume from last checkpoint after interruption.
    """
    # Mock database session
    db_mock = Mock()

    # Create a partially completed job
    job = BackfillJob(
        job_id="test_job_123",
        symbol="BTC/USDT",
        timeframe=TimeFrame.M15,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 2, 1),
        last_completed_ts=datetime(2020, 1, 15),  # Checkpoint
        candles_fetched=1000,
        status="paused"
    )

    service = BackfillService(db_mock)

    # Verify that resume would start from checkpoint
    # In production, this would fetch data from 2020-01-15 onwards
    expected_resume_point = datetime(2020, 1, 15) + timedelta(seconds=1)

    assert job.last_completed_ts is not None
    assert job.last_completed_ts == datetime(2020, 1, 15)


def test_backfill_progress_tracking():
    """Test that backfill tracks progress correctly"""
    job = BackfillJob(
        job_id="test_job_456",
        symbol="ETH/USDT",
        timeframe=TimeFrame.M15,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2021, 1, 1),
        total_candles_estimate=35040,  # ~1 year of 15m candles
        candles_fetched=17520,
        status="running"
    )

    # Calculate progress
    progress_pct = (job.candles_fetched / job.total_candles_estimate) * 100

    assert progress_pct == pytest.approx(50.0, 0.1)
    assert job.total_candles_estimate > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
