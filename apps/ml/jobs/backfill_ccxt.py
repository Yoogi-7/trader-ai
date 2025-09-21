from __future__ import annotations
import os, time, typing as T
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from apps.api.db import SessionLocal
from apps.api.models import BackfillProgress
from apps.ml.data.ccxt_client import fetch_ohlcv_paginated
from apps.ml.utils.timescale import upsert_ohlcv_rows
import redis, json

PAIRS = os.getenv("PAIRS", "BTCUSDT,ETHUSDT").split(",")
BACKFILL_SINCE_DAYS = int(os.getenv("BACKFILL_SINCE_DAYS", "1460"))
BACKFILL_TF = os.getenv("BACKFILL_TF", "1m")

rds = redis.from_url(os.getenv("REDIS_URL","redis://redis:6379/0"))

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def run():
    db: Session = SessionLocal()

    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=BACKFILL_SINCE_DAYS)
    since_ms_default = _ms(since_dt)
    until_ms = _ms(now)

    for sym in PAIRS:
        pr = db.query(BackfillProgress).filter_by(symbol=sym, tf=BACKFILL_TF).one_or_none()
        if not pr:
            pr = BackfillProgress(symbol=sym, tf=BACKFILL_TF, last_ts_completed=0, status="queued")
            db.add(pr); db.commit()

        start_ms = max(pr.last_ts_completed or 0, since_ms_default)

        pr.status = "running"
        pr.chunk_start_ts = start_ms
        pr.chunk_end_ts = until_ms
        db.commit()

        print(f"[backfill] {sym} {BACKFILL_TF} from {start_ms} to {until_ms}")

        batch = []
        cnt = 0
        last_checkpoint = start_ms
        t0 = time.time()
        last_report = t0
        processed_since_report = 0

        try:
            for ts, o, h, l, c, v in fetch_ohlcv_paginated(sym, BACKFILL_TF, since_ms=start_ms, until_ms=until_ms):
                batch.append({
                    "symbol": sym, "tf": BACKFILL_TF, "ts": int(ts),
                    "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v),
                    "source_hash": "ccxt"
                })
                cnt += 1; processed_since_report += 1

                if len(batch) >= 10000:
                    upsert_ohlcv_rows(db, batch); db.commit()
                    last_checkpoint = batch[-1]["ts"]
                    pr.last_ts_completed = last_checkpoint; db.commit()
                    # progress
                    pct = min(99.9, 100.0 * (last_checkpoint - start_ms) / max(1, (until_ms - start_ms)))
                    dt = time.time() - last_report
                    speed_cpm = (processed_since_report / dt) * 60.0 if dt > 0 else 0.0
                    rem = max(0, until_ms - last_checkpoint)
                    # przybliżenie: 1m = 60k ms, więc ile świec zostało:
                    candles_left = rem / 60000.0
                    eta_sec = candles_left / max(0.1, speed_cpm) * 60.0
                    rds.publish("progress", json.dumps(dict(
                        type="backfill", symbol=sym, tf=BACKFILL_TF, pct=round(pct,2),
                        processed=cnt, last_ts=last_checkpoint,
                        speed_cpm=round(speed_cpm,2), eta_sec=int(eta_sec)
                    )))
                    last_report = time.time()
                    processed_since_report = 0
                    batch.clear()

            if batch:
                upsert_ohlcv_rows(db, batch); db.commit()
                last_checkpoint = batch[-1]["ts"]
                pr.last_ts_completed = last_checkpoint; db.commit()

            pr.status = "done"; db.commit()
            rds.publish("progress", json.dumps(dict(
                type="backfill", symbol=sym, tf=BACKFILL_TF, pct=100.0,
                processed=cnt, last_ts=last_checkpoint, speed_cpm=0.0, eta_sec=0
            )))
            print(f"[backfill] {sym} done. total_rows~{cnt}")

        except Exception as e:
            pr.status = "error"; pr.retry_count = (pr.retry_count or 0) + 1
            db.commit()
            rds.publish("progress", json.dumps(dict(
                type="backfill", symbol=sym, tf=BACKFILL_TF, pct=-1,
                error=str(e)
            )))
            print(f"[backfill] {sym} ERROR: {e}")
        finally:
            db.close()

if __name__ == "__main__":
    run()
