from datetime import datetime, timedelta, timezone
import pandas as pd

from apps.api.db.session import SessionLocal
from apps.api.db.models import OHLCV, Feature
from apps.ml.jobs.features import run_features

UTC = timezone.utc

def test_features_insert_and_version():
    db = SessionLocal()
    try:
        # Wstrzykujemy kilka świec 15m do widoku bazowego (tabela ohlcv_15m jest materialized view,
        # więc do testu skorzystamy z 1m i założymy, że resampling istnieje – tutaj symulujemy 1m).
        now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        base_ts = int((now - timedelta(minutes=60)).timestamp() * 1000)

        # Insert minimalnych danych do 1m
        for i in range(60):
            ts = base_ts + i * 60_000
            row = OHLCV(symbol="TESTUSDT", tf="1m", ts=ts, o=100+i*0.01, h=101+i*0.01, l=99, c=100+i*0.01, v=1.0, source_hash=None)
            db.merge(row)
        db.commit()

        # Odpal features na 1m (żeby nie zależeć od CAGG w teście)
        res = run_features(symbols=["TESTUSDT"], tf="1m", start_iso=None, end_iso=None, version="vtest_1m")
        assert res["ok"]
        # Sprawdź, że coś się wstawiło
        cnt = db.query(Feature).filter_by(symbol="TESTUSDT", tf="1m", version="vtest_1m").count()
        assert cnt > 0
    finally:
        db.close()
