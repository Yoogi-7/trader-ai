
from celery import shared_task
from apps.api.config import settings
from apps.api.db.session import SessionLocal
from apps.api.db.models import OHLCV, BackfillProgress
from datetime import datetime, timedelta
import time, random

@shared_task
def run_backfill(pairs: list[str] | None = None, tf: str = "1m"):
    pairs = pairs or settings.pairs
    db = SessionLocal()
    try:
        now_ms = int(time.time()*1000)
        for sym in pairs:
            # demo: insert a few candles
            for i in range(10):
                ts = now_ms - i*60_000
                o = 60000 + random.uniform(-500, 500)
                c = o + random.uniform(-100, 100)
                h = max(o, c) + random.uniform(0, 80)
                l = min(o, c) - random.uniform(0, 80)
                v = random.uniform(10, 50)
                db.merge(OHLCV(symbol=sym, tf=tf, ts=ts, o=o, h=h, l=l, c=c, v=v))
            db.merge(BackfillProgress(symbol=sym, tf=tf, last_ts_completed=now_ms, status="done"))
        db.commit()
        return {"ok": True, "pairs": pairs, "tf": tf}
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill.delay()
