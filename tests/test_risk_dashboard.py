import time

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.security import get_password_hash


def _now_ms() -> int:
    return int(time.time() * 1000)


def setup_risk_data():
    with SessionLocal() as db:
        db.query(models.PnL).delete()
        db.query(models.BacktestTrade).delete()
        db.query(models.Backtest).delete()
        db.query(models.Signal).delete()
        db.query(models.User).delete()
        db.commit()

        now = _now_ms()
        admin = models.User(
            email="risk@test.com",
            password_hash=get_password_hash("secret"),
            role="ADMIN",
            risk_profile="LOW",
            capital=1000.0,
            created_at=now,
            updated_at=now,
        )
        db.add(admin)
        db.commit()

        backtest = models.Backtest(
            params_json={"capital": 1000.0},
            started_at=now - 10_000,
            finished_at=now - 5_000,
            summary_json={
                "params": {"capital": 1000.0},
                "metrics": {
                    "max_dd": 120.0,
                    "max_dd_pct": 0.12,
                    "pnl_total": 200.0,
                    "trades": 10,
                    "hit_rate_tp1": 0.6,
                },
            },
        )
        db.add(backtest)

        sig_win = models.Signal(
            id="sig-win-risk",
            symbol="BTCUSDT",
            tf_base="15m",
            ts=now - 4_000,
            dir="LONG",
            entry=60_000.0,
            tp=[60_500.0],
            sl=59_000.0,
            lev=3.0,
            risk="LOW",
            margin_mode="ISOLATED",
            expected_net_pct=0.03,
            confidence=0.7,
            model_ver="test",
            reason_discard=None,
            status="published",
            ai_summary="win",
        )
        sig_loss = models.Signal(
            id="sig-loss-risk",
            symbol="ETHUSDT",
            tf_base="15m",
            ts=now - 2_000,
            dir="SHORT",
            entry=3_000.0,
            tp=[2_900.0],
            sl=3_100.0,
            lev=3.0,
            risk="LOW",
            margin_mode="ISOLATED",
            expected_net_pct=0.02,
            confidence=0.6,
            model_ver="test",
            reason_discard=None,
            status="published",
            ai_summary="loss",
        )
        db.add_all([sig_win, sig_loss])
        db.commit()

        pnl_win = models.PnL(signal_id="sig-win-risk", realized=120.0)
        pnl_loss = models.PnL(signal_id="sig-loss-risk", realized=-80.0)
        db.add_all([pnl_win, pnl_loss])
        db.commit()


def test_risk_dashboard_endpoint():
    setup_risk_data()
    client = TestClient(app)

    login_resp = client.post("/auth/login", json={"email": "risk@test.com", "password": "secret"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    resp = client.get("/risk/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    data = resp.json()
    backtest = data["backtest"]
    live = data["live"]

    assert backtest["source"] == "backtest"
    assert backtest["trades"] == 10
    assert abs(backtest["max_drawdown"] - 120.0) < 1e-6
    assert abs(backtest["avg_profit_per_trade"] - 20.0) < 1e-6
    assert abs(backtest["win_rate"] - 0.6) < 1e-6

    assert live["source"] == "live"
    assert live["trades"] == 2
    assert abs(live["avg_profit_per_trade"] - 20.0) < 1e-6
    assert abs(live["win_rate"] - 0.5) < 1e-6
    assert abs(live["max_drawdown"] - 80.0) < 1e-6
    assert live["max_drawdown_pct"] is not None
    assert live["last_updated_ms"] is not None
