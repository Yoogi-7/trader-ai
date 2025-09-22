from apps.ml.jobs.backfill import run_local
from apps.api.db.session import SessionLocal
from apps.api.db.models import OHLCV, BackfillProgress
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

def fake_fetcher_factory(step_ms: int, total_points: int):
    """
    Wytwarza sztuczne dane OHLCV w równych odstępach, niezależnie od symbolu.
    """
    def fetch(symbol: str, tf: str, since_ms: int, limit: int):
        out = []
        # generujemy do total_points świec, start od since_ms, maksymalnie limit
        count = min(limit, total_points)
        ts = since_ms
        for i in range(count):
            out.append({"ts": ts, "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1.0})
            ts += step_ms
        return out
    return fetch

def test_backfill_resume_without_duplicates():
    db = SessionLocal()
    try:
        # START: ustaw czasy
        start = int((datetime.now(tz=UTC) - timedelta(hours=1)).timestamp() * 1000)
        end = start + 30 * 60_000  # 30 świec minute
        step = 60_000

        # 1. Pierwszy bieg (wypełni część danych)
        fetcher = fake_fetcher_factory(step_ms=step, total_points=10)
        res1 = run_local(fetcher, tf="1m", pairs=["BTCUSDT"], start_ts_ms=start, end_ts_ms=end, batch_limit=10)
        assert res1["BTCUSDT"]["status"] == "done"

        # 2. Sprawdź postęp
        row = db.query(BackfillProgress).filter_by(symbol="BTCUSDT", tf="1m").first()
        assert row is not None
        first_completed = row.last_ts_completed

        # 3. Drugi bieg (resume) — generuje kolejne dane bez duplikatów
        fetcher2 = fake_fetcher_factory(step_ms=step, total_points=10)
        res2 = run_local(fetcher2, tf="1m", pairs=["BTCUSDT"], start_ts_ms=start, end_ts_ms=end, batch_limit=10)
        assert res2["BTCUSDT"]["status"] == "done"

        # 4. W bazie powinno być <= 30 wpisów (bo część mogła nie być pokryta z powodu total_points)
        cnt = db.query(OHLCV).filter_by(symbol="BTCUSDT", tf="1m").count()
        assert cnt <= 30

        # 5. last_ts_completed powinien pójść do przodu lub pozostać równy (nigdy wstecz)
        row2 = db.query(BackfillProgress).filter_by(symbol="BTCUSDT", tf="1m").first()
        assert row2.last_ts_completed >= first_completed
    finally:
        db.close()
