import time

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.api.security import get_password_hash


def _now_ms() -> int:
    return int(time.time() * 1000)


def setup_signals(min_conf_rating=None):
    with SessionLocal() as db:
        db.query(models.Signal).delete()
        db.query(models.User).delete()
        db.commit()

        prefs = {}
        if min_conf_rating is not None:
            prefs['min_confidence_rating'] = min_conf_rating

        user = models.User(
            email='conf@test.com',
            password_hash=get_password_hash('secret'),
            role='USER',
            risk_profile='LOW',
            capital=1000.0,
            prefs=prefs,
            created_at=_now_ms(),
            updated_at=_now_ms(),
        )
        db.add(user)

        high = models.Signal(
            id='sig-high',
            symbol='BTCUSDT',
            tf_base='15m',
            ts=_now_ms(),
            dir='LONG',
            entry=50000.0,
            tp=[51000.0],
            sl=49000.0,
            lev=3.0,
            risk='LOW',
            margin_mode='ISOLATED',
            expected_net_pct=0.03,
            confidence=0.85,
            model_ver='test',
            status='published',
        )
        low = models.Signal(
            id='sig-low',
            symbol='ETHUSDT',
            tf_base='15m',
            ts=_now_ms() - 1000,
            dir='SHORT',
            entry=3000.0,
            tp=[2900.0],
            sl=3100.0,
            lev=3.0,
            risk='LOW',
            margin_mode='ISOLATED',
            expected_net_pct=0.02,
            confidence=0.55,
            model_ver='test',
            status='published',
        )
        db.add_all([high, low])
        db.commit()


def _login(client: TestClient):
    resp = client.post('/auth/login', json={'email': 'conf@test.com', 'password': 'secret'})
    assert resp.status_code == 200
    token = resp.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def test_signals_live_respects_min_confidence():
    setup_signals(min_conf_rating=70)
    client = TestClient(app)
    headers = _login(client)

    resp = client.get('/signals/live', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [item['id'] for item in data['signals']]
    assert 'sig-high' in ids
    assert 'sig-low' not in ids
    for item in data['signals']:
        assert 'market_regime' in item


def test_signals_history_without_filter_returns_all():
    setup_signals(min_conf_rating=None)
    client = TestClient(app)
    headers = _login(client)

    resp = client.get('/signals/history?limit=10', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [item['id'] for item in data['signals']]
    assert 'sig-high' in ids
    assert 'sig-low' in ids


def test_signals_history_filter_applied():
    setup_signals(min_conf_rating=80)
    client = TestClient(app)
    headers = _login(client)

    resp = client.get('/signals/history?limit=10', headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [item['id'] for item in data['signals']]
    assert ids == ['sig-high']
    assert data['signals'][0]['confidence_rating'] >= 80
    assert 'market_regime' in data['signals'][0]
