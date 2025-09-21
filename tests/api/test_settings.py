# tests/api/test_settings.py
import os
import pytest
from fastapi.testclient import TestClient

os.environ["POSTGRES_HOST"] = "db"  # w CI i lokalnie podmień jeśli potrzeba

from apps.api.main import app  # zakładam, że masz main.py, który include_router(routers.router)

client = TestClient(app)

def test_set_profile_rejects_too_many_parallel_positions(monkeypatch):
    # nadpisz map_profile, żeby nie dotykać DB przy teście logiki
    from apps.api.services import risk as risk_mod
    base = risk_mod.RISK_PRESETS["LOW"]
    monkeypatch.setattr(risk_mod, "map_profile", lambda _: base)
    resp = client.post("/settings/profile", json={
        "risk_profile": "LOW",
        "pairs": ["BTCUSDT"],
        "max_parallel_positions": base.max_parallel_positions + 1,
        "margin_mode": "isolated"
    })
    assert resp.status_code == 400

def test_set_capital_payload_validation():
    resp = client.post("/capital", json={"capital": -10})
    assert resp.status_code in (400, 422)
