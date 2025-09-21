from apps.api.routers import signals_generate
from apps.api.schemas import SignalRequest
from apps.api.db import SessionLocal

def test_filter_2pct_net():
    db = SessionLocal()
    req = SignalRequest(pairs=["BTCUSDT"], risk_profile="LOW", capital=100.0)
    out = signals_generate(req, db)
    # All published signals must be >= 2% net (in our demo logic, exactly meets if net >= 0.02)
    for s in out:
        assert s.expected_net_pct >= 2.0