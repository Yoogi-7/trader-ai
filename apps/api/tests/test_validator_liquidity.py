from apps.api.db import SessionLocal
from apps.api.models import OHLCV
from apps.ml.validators import basic_market_checks

def test_liquidity_check_passes_with_volume():
    db = SessionLocal()
    # wstaw kilka świec z sensowną wartością (cena*wolumen)
    import time as _t
    now = int(_t.time()*1000)
    sym = "BTCUSDT"
    for i in range(20):
        db.add(OHLCV(symbol=sym, tf="1m", ts=now - i*60000, o=100, h=101, l=99, c=100, v=1000))
    db.commit()
    ok, reason = basic_market_checks(db, sym)
    assert ok and reason is None
