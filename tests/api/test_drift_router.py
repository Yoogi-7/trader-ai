import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.db.base import Base
from apps.api.db import models  # noqa: F401 - register models
from apps.api.db.models import DriftMetrics, ModelRegistry, TimeFrame
from apps.api.db.session import get_async_db
from apps.api.main import app


@pytest.fixture()
def drift_test_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def init_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_models())

    async def override_get_async_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db

    with TestClient(app) as client:
        yield client, session_maker

    app.dependency_overrides.clear()

    async def drop_models():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(drop_models())
    asyncio.run(engine.dispose())


async def _create_model(session, model_id: str):
    now = datetime.utcnow()
    model = ModelRegistry(
        model_id=model_id,
        symbol="BTC/USDT",
        timeframe=TimeFrame.M15,
        model_type="lgbm",
        version="v1",
        train_start=now - timedelta(days=30),
        train_end=now - timedelta(days=20),
        oos_start=now - timedelta(days=19),
        oos_end=now - timedelta(days=1),
        hyperparameters={},
        hit_rate_tp1=0.55,
        avg_net_profit_pct=1.2,
        is_active=True,
        is_production=True,
        artifact_path="/tmp/model",
    )
    session.add(model)
    await session.flush()
    return model


async def _insert_metrics(session_maker, model_id: str, metric_values):
    async with session_maker() as session:
        await _create_model(session, model_id)
        records = []
        for entry in metric_values:
            timestamp, psi, drift_flag = entry
            records.append(
                DriftMetrics(
                    model_id=model_id,
                    timestamp=timestamp,
                    psi_score=psi,
                    ks_statistic=psi * 0.5,
                    prediction_drift=psi * 0.25,
                    data_freshness_hours=4.0,
                    drift_detected=drift_flag,
                )
            )
        session.add_all(records)
        await session.commit()


def test_list_drift_metrics_pagination(drift_test_client):
    client, session_maker = drift_test_client
    base_time = datetime.utcnow()
    metric_values = [
        (base_time - timedelta(minutes=30), 0.05, False),
        (base_time - timedelta(minutes=20), 0.12, False),
        (base_time - timedelta(minutes=10), 0.25, True),
    ]

    asyncio.run(_insert_metrics(session_maker, "model-alpha", metric_values))

    response = client.get(
        "/api/v1/drift",
        params={
            "model_id": "model-alpha",
            "page": 1,
            "page_size": 2,
            "sort_by": "timestamp",
            "sort_order": "asc",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert payload["items"][0]["timestamp"] < payload["items"][1]["timestamp"]

    response_page_2 = client.get(
        "/api/v1/drift",
        params={
            "model_id": "model-alpha",
            "page": 2,
            "page_size": 2,
            "sort_by": "timestamp",
            "sort_order": "asc",
        },
    )
    assert response_page_2.status_code == 200
    payload_page_2 = response_page_2.json()

    assert len(payload_page_2["items"]) == 1
    assert payload_page_2["items"][0]["timestamp"] > payload["items"][1]["timestamp"]


def test_list_drift_metrics_sorting(drift_test_client):
    client, session_maker = drift_test_client
    base_time = datetime.utcnow()
    metric_values = [
        (base_time - timedelta(minutes=15), 0.05, False),
        (base_time - timedelta(minutes=10), 0.15, True),
        (base_time - timedelta(minutes=5), 0.25, True),
    ]

    asyncio.run(_insert_metrics(session_maker, "model-beta", metric_values))

    response = client.get(
        "/api/v1/drift",
        params={
            "sort_by": "psi_score",
            "sort_order": "desc",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    psi_scores = [item["psi_score"] for item in payload["items"]]
    assert psi_scores == sorted(psi_scores, reverse=True)
