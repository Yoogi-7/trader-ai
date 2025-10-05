import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers import backfill as backfill_router


@pytest.fixture
def backfill_client(monkeypatch):
    base_status = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "status": "running",
        "progress_pct": 42.5,
        "candles_fetched": 4200,
        "total_candles_estimate": 10000,
        "candles_per_minute": 120.5,
        "eta_minutes": 48.0,
        "detected_gaps": [
            {"start": "2024-01-01T00:00:00", "end": "2024-01-01T01:00:00"}
        ],
        "started_at": "2024-01-01T00:00:00",
        "completed_at": None,
        "created_at": "2024-01-01T00:00:00",
    }

    class DummyBackfillService:
        def __init__(self, db):
            self.db = db

        def get_job_status(self, job_id: str):
            return {"job_id": job_id, **base_status}

    class DummyJob:
        def __init__(self, job_id: str):
            self.job_id = job_id
            self.created_at = None

    class DummyQuery:
        def __init__(self, jobs):
            self.jobs = jobs

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, limit):
            return self

        def all(self):
            return self.jobs

    class DummyDB:
        def __init__(self, jobs):
            self._jobs = jobs

        def query(self, model):
            return DummyQuery(self._jobs)

    dummy_jobs = [DummyJob("job-1")]

    def override_get_db():
        yield DummyDB(dummy_jobs)

    app.dependency_overrides[backfill_router.get_db] = override_get_db
    monkeypatch.setattr(backfill_router, "BackfillService", DummyBackfillService)

    try:
        with TestClient(app) as client:
            yield client, base_status, dummy_jobs
    finally:
        app.dependency_overrides.pop(backfill_router.get_db, None)


def test_backfill_status_includes_new_fields(backfill_client):
    client, base_status, _ = backfill_client

    response = client.get("/api/v1/backfill/status/test-job")
    assert response.status_code == 200

    data = response.json()
    assert data["total_candles_estimate"] == base_status["total_candles_estimate"]
    assert data["detected_gaps"] == base_status["detected_gaps"]


def test_backfill_jobs_include_new_fields(backfill_client):
    client, base_status, dummy_jobs = backfill_client

    response = client.get("/api/v1/backfill/jobs")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == len(dummy_jobs)
    assert data[0]["total_candles_estimate"] == base_status["total_candles_estimate"]
    assert data[0]["detected_gaps"] == base_status["detected_gaps"]
