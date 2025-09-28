import time

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.security import get_password_hash


def _now_ms():
    return int(time.time() * 1000)


def setup_journal_data():
    with SessionLocal() as db:
        db.query(models.PnL).delete()
        db.query(models.Signal).delete()
        db.query(models.User).delete()
        db.commit()

        user = models.User(
            email='journal@test.com',
            password_hash=get_password_hash('secret'),
            role='USER',
            risk_profile='LOW',
            capital=1000.0,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )
        db.add(user)
        db.commit()

        ts_base = _now_ms() - 10_000
        sig_win = models.Signal(
            id='sig-win-journal',
            symbol='BTCUSDT',
            tf_base='15m',
            ts=ts_base,
            dir='LONG',
            entry=60000.0,
            tp=[60500.0],
            sl=59000.0,
            lev=3.0,
            risk='LOW',
            margin_mode='ISOLATED',
            expected_net_pct=0.03,
            confidence=0.8,
            status='published',
            market_regime='trend_wzrostowy',
            ai_summary='test win',
            model_ver='test',
        )
        sig_loss = models.Signal(
            id='sig-loss-journal',
            symbol='ETHUSDT',
            tf_base='15m',
            ts=ts_base + 5000,
            dir='SHORT',
            entry=3000.0,
            tp=[2900.0],
            sl=3100.0,
            lev=3.0,
            risk='LOW',
            margin_mode='ISOLATED',
            expected_net_pct=0.02,
            confidence=0.4,
            status='published',
            market_regime='boczniak',
            ai_summary='test loss',
            model_ver='test',
        )
        db.add_all([sig_win, sig_loss])
        db.commit()

        pnl_win = models.PnL(signal_id='sig-win-journal', realized=150.0)
        pnl_loss = models.PnL(signal_id='sig-loss-journal', realized=-80.0)
        db.add_all([pnl_win, pnl_loss])
        db.commit()


def test_journal_endpoint():
    setup_journal_data()
    client = TestClient(app)

    login_resp = client.post('/auth/login', json={'email': 'journal@test.com', 'password': 'secret'})
    assert login_resp.status_code == 200
    token = login_resp.json()['access_token']

    resp = client.get('/journal', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data['equity_curve']) == 2
    assert data['metrics']['total_trades'] == 2
    assert data['metrics']['cumulative_pnl'] == 70.0
    assert data['metrics']['best_trade']['symbol'] == 'BTCUSDT'
    assert data['recent_mistakes'][0]['symbol'] == 'ETHUSDT'
