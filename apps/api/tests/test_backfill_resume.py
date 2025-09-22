from sqlalchemy import create_engine, text
from trader_api.config import settings
from datetime import datetime, timezone, timedelta

def test_resume_progress_table():
    engine = create_engine(settings.DB_URL)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM backfill_progress WHERE symbol='BTC/USDT' AND tf='1m'"))
        now = datetime.now(timezone.utc)
        conn.execute(text("""
          INSERT INTO backfill_progress(symbol,tf,last_ts_completed,chunk_start_ts,chunk_end_ts,status)
          VALUES('BTC/USDT','1m', :last, :cs, :ce, 'ok')
        """), {"last": now, "cs": now - timedelta(hours=12), "ce": now})
        row = conn.execute(text("SELECT last_ts_completed FROM backfill_progress WHERE symbol='BTC/USDT' AND tf='1m'")).fetchone()
        assert row and row[0] is not None
