# apps/ml/jobs/backfill_ccxt.py
"""
Backfill OHLCV 1m (domyślnie) przez CCXT z checkpointami w backfill_progress.
- Pobiera parametry z env: EXCHANGE, PAIRS, BACKFILL_SINCE_DAYS, BACKFILL_TF.
- Upsert danych do tabeli ohlcv.
- Aktualizuje last_ts_completed, status; wznawianie po przerwaniu.
"""
from __future__ import annotations
import os, time, math, typing as T
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from apps.api.db import SessionLocal
from apps.api.models import BackfillProgress
from apps.ml.data.ccxt_client import fetch_ohlcv_paginated
from apps.ml.utils.timescale import upsert_ohlcv_rows

PAIRS = os.getenv("PAIRS", "BTCUSDT,ETHUSDT").split(",")
BACKFILL_SINCE_DAYS = int(os.getenv("BACKFILL_SINCE_DAYS", "1460"))
BACKFILL_TF = os.getenv("BACKFILL_TF", "1m")

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def run():
    db: Session = SessionLocal()

    # zakres czasowy
    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=BACKFILL_SINCE_DAYS)
    since_ms_default = _ms(since_dt)
    until_ms = _ms(now)

    for sym in PAIRS:
        # wczytaj/utwórz progress
        pr = db.query(BackfillProgress).filter_by(symbol=sym, tf=BACKFILL_TF).one_or_none()
        if not pr:
            pr = BackfillProgress(symbol=sym, tf=BACKFILL_TF, last_ts_completed=0, status="queued")
            db.add(pr); db.commit()

        # wylicz punkt startowy
        start_ms = max(pr.last_ts_completed or 0, since_ms_default)

        pr.status = "running"
        pr.chunk_start_ts = start_ms
        pr.chunk_end_ts = until_ms
        db.commit()

        print(f"[backfill] {sym} {BACKFILL_TF} from {start_ms} to {until_ms}")

        batch = []
        cnt = 0
        last_checkpoint = start_ms

        try:
            for ts, o, h, l, c, v in fetch_ohlcv_paginated(sym, BACKFILL_TF, since_ms=start_ms, until_ms=until_ms):
                batch.append({
                    "symbol": sym, "tf": BACKFILL_TF, "ts": int(ts),
                    "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v),
                    "source_hash": "ccxt"
                })
                # zapis partiami ~10k
                if len(batch) >= 10000:
                    upsert_ohlcv_rows(db, batch)
                    db.commit()
                    last_checkpoint = batch[-1]["ts"]
                    pr.last_ts_completed = last_checkpoint
                    db.commit()
                    print(f"[backfill] {sym} upserted {len(batch)}; last_ts={last_checkpoint}")
                    batch.clear()
                cnt += 1

            if batch:
                upsert_ohlcv_rows(db, batch)
                db.commit()
                last_checkpoint = batch[-1]["ts"]
                pr.last_ts_completed = last_checkpoint
                db.commit()
                print(f"[backfill] {sym} upserted tail {len(batch)}; last_ts={last_checkpoint}")

            pr.status = "done"; db.commit()
            print(f"[backfill] {sym} done. total_rows~{cnt}")

        except Exception as e:
            pr.status = "error"; pr.retry_count = (pr.retry_count or 0) + 1
            db.commit()
            print(f"[backfill] {sym} ERROR: {e}")
        finally:
            db.close()

if __name__ == "__main__":
    run()
