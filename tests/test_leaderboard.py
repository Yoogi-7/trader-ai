import time

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.security import get_password_hash


def _now_ms() -> int:
    return int(time.time() * 1000)


def setup_leaderboard_data():
    with SessionLocal() as db:
        db.query(models.PnL).delete()
        db.query(models.Signal).delete()
        db.query(models.User).delete()
        db.commit()

        admin = models.User(
            email="admin@test.com",
            password_hash=get_password_hash("secret"),
            role="ADMIN",
            risk_profile="LOW",
            capital=1000.0,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )
        user1 = models.User(
            email="user1@test.com",
            password_hash=get_password_hash("pass1"),
            role="USER",
            risk_profile="MED",
            capital=1500.0,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )
        user2 = models.User(
            email="user2@test.com",
            password_hash=get_password_hash("pass2"),
            role="USER",
            risk_profile="HIGH",
            capital=800.0,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )
        db.add_all([admin, user1, user2])
        db.commit()

        ts_recent = _now_ms() - (5 * 24 * 60 * 60 * 1000)

        sig_win = models.Signal(
            id="sig-win",
            symbol="BTCUSDT",
            tf_base="15m",
            ts=ts_recent,
            dir="LONG",
            entry=60000.0,
            tp=[60500.0],
            sl=59000.0,
            lev=2.0,
            risk="LOW",
            margin_mode="ISOLATED",
            expected_net_pct=0.03,
            confidence=0.7,
            model_ver="test",
            reason_discard=None,
            status="published",
            ai_summary="test summary win",
        )
        sig_loss = models.Signal(
            id="sig-loss",
            symbol="ETHUSDT",
            tf_base="15m",
            ts=ts_recent,
            dir="SHORT",
            entry=3000.0,
            tp=[2900.0],
            sl=3100.0,
            lev=2.0,
            risk="LOW",
            margin_mode="ISOLATED",
            expected_net_pct=0.02,
            confidence=0.6,
            model_ver="test",
            reason_discard=None,
            status="published",
            ai_summary="test summary loss",
        )
        db.add_all([sig_win, sig_loss])
        db.commit()

        pnl_win = models.PnL(signal_id="sig-win", realized=120.0)
        pnl_loss = models.PnL(signal_id="sig-loss", realized=-80.0)
        db.add_all([pnl_win, pnl_loss])
        db.commit()


def test_leaderboard_endpoint_returns_data():
    setup_leaderboard_data()
    client = TestClient(app)

    login_resp = client.post('/auth/login', json={'email': 'admin@test.com', 'password': 'secret'})
    assert login_resp.status_code == 200
    token = login_resp.json()['access_token']

    resp = client.get('/leaderboard', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()

    assert data['overall']['total_trades'] == 2
    assert data['overall']['wins'] == 1
    assert abs(data['overall']['win_rate'] - 0.5) < 1e-6

    users = data['users']
    assert len(users) >= 3
    # Users sorted by capital desc
    assert users[0]['email'] == 'user1@test.com'
    assert users[1]['email'] == 'admin@test.com'
