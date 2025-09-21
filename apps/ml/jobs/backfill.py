# Backfill job with checkpoint resume
import time, random
from apps.api.db import SessionLocal
from apps.api.models import BackfillProgress, OHLCV
from apps.api.config import settings

def run():
    db = SessionLocal()
    pairs = settings.PAIRS.split(",")
    for p in pairs:
        row = db.query(BackfillProgress).filter_by(symbol=p, tf="1m").one_or_none()
        if not row:
            row = BackfillProgress(symbol=p, tf="1m", last_ts_completed=0, status="running")
            db.add(row); db.commit()
        # simulate chunks:
        start = row.last_ts_completed or int(time.time()*1000) - 5*24*60*60*1000
        for _ in range(3):
            # pretend we fetched a chunk, then checkpoint
            start += settings.BACKFILL_CHUNK_MINUTES*60*1000
            row.last_ts_completed = start
            row.status="running"
            db.commit()
        row.status="done"; db.commit()
        print(f"Backfill {p} done at ts={row.last_ts_completed}")

if __name__ == "__main__":
    run()