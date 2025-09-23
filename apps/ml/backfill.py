# apps/ml/backfill.py
# (fragment header bez zmian opisowych)
import os
import sys
import time
import math
from typing import List, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.ml.ccxt_client import CcxtClient
from apps.ml.resample import resample_candles
from apps.common.event_bus import publish  # NEW

SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,BNB/USDT,ADA/USDT,SOL/USDT,XRP/USDT,DOGE/USDT,MATIC/USDT,ARB/USDT,OP/USDT").split(",")]
BASE_TF = "1m"
RESAMPLE_TFS = [tf.strip() for tf in os.getenv("RESAMPLE_TFS", "15m,1h,4h,1d").split(",") if tf.strip()]
CHUNK_MINUTES = int(os.getenv("CHUNK_MINUTES", "43200"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))
PRINT_PROGRESS_EVERY = int(os.getenv("PRINT_PROGRESS_EVERY", "20000"))
MS_IN_MIN = 60_000

def now_ms() -> int:
    return int(time.time() * 1000)

def upsert_ohlcv(db: Session, symbol: str, tf: str, rows: List[Dict]) -> int:
    if not rows:
        return 0
    values = [{"symbol": symbol, "tf": tf, "ts": r["ts"], "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r["v"], "source_hash": None} for r in rows]
    stmt = pg_insert(models.OHLCV.__table__).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "tf", "ts"],
        set_={
            "o": stmt.excluded.o,
            "h": stmt.excluded.h,
            "l": stmt.excluded.l,
            "c": stmt.excluded.c,
            "v": stmt.excluded.v,
            "source_hash": stmt.excluded.source_hash,
        },
    )
    db.execute(stmt)
    return len(values)

def update_progress(db: Session, symbol: str, tf: str, **fields) -> models.BackfillProgress:
    bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one_or_none()
    if not bp:
        bp = models.BackfillProgress(symbol=symbol, tf=tf, last_ts_completed=None, chunk_start_ts=None, chunk_end_ts=None, retry_count=0, status="idle", updated_at=now_ms())
        db.add(bp)
        db.commit()
        db.refresh(bp)
    for k, v in fields.items():
        setattr(bp, k, v)
    bp.updated_at = now_ms()
    db.commit()
    db.refresh(bp)
    # publish progress event
    try:
        publish("backfill_progress", {
            "symbol": bp.symbol, "tf": bp.tf, "status": bp.status,
            "last_ts_completed": bp.last_ts_completed, "updated_at": bp.updated_at
        })
    except Exception:
        pass
    return bp

def _fetch_chunk_1m(client: CcxtClient, symbol: str, start_ms: int, end_ms: int) -> List[Dict]:
    raw = client.fetch_ohlcv(symbol, timeframe="1m", since_ms=start_ms, until_ms=end_ms)
    return [{"ts": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "c": float(r[4]), "v": float(r[5])} for r in raw]

def _iter_chunks(start_ms: int, end_ms: int, chunk_minutes: int):
    chunk_ms = chunk_minutes * MS_IN_MIN
    cur = start_ms
    while cur < end_ms:
        nxt = min(cur + chunk_ms, end_ms)
        yield (cur, nxt)
        cur = nxt

def _detect_gap(expected_start: int, fetched_rows: List[Dict]) -> Optional[Tuple[int, int]]:
    if not fetched_rows:
        return (expected_start, expected_start + MS_IN_MIN)
    ts_sorted = [r["ts"] for r in fetched_rows]
    prev = ts_sorted[0]
    for t in ts_sorted[1:]:
        if t - prev > MS_IN_MIN:
            return (prev + MS_IN_MIN, t - MS_IN_MIN)
        prev = t
    return None

def backfill_symbol(db: Session, client: CcxtClient, symbol: str, tf: str, from_ts: Optional[int], to_ts: Optional[int]) -> None:
    start_ms = from_ts if from_ts else (now_ms() - 4 * 365 * 24 * 60 * MS_IN_MIN)
    end_ms = to_ts if to_ts else now_ms()

    bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one_or_none()
    if bp and bp.last_ts_completed:
        start_ms = max(start_ms, bp.last_ts_completed + MS_IN_MIN)

    update_progress(db, symbol, tf, chunk_start_ts=start_ms, chunk_end_ts=end_ms, status="running")
    # event: start
    publish("backfill_started", {"symbol": symbol, "tf": tf, "start_ts": start_ms, "end_ts": end_ms})

    total_written = 0
    fetched_total = 0

    for a, b in _iter_chunks(start_ms, end_ms, CHUNK_MINUTES):
        attempt = 0
        while True:
            try:
                rows = _fetch_chunk_1m(client, symbol, a, b)
                fetched_total += len(rows)

                gap = _detect_gap(a, rows)
                if gap:
                    last_cont_ts = rows[0]["ts"] if rows else a - MS_IN_MIN
                    prev_ts = last_cont_ts
                    for r in rows[1:]:
                        if r["ts"] - prev_ts > MS_IN_MIN:
                            break
                        prev_ts = r["ts"]
                    last_cont_ts = prev_ts
                    cont_rows = [r for r in rows if r["ts"] <= last_cont_ts]
                    if cont_rows:
                        upsert_ohlcv(db, symbol, BASE_TF, cont_rows)
                        total_written += len(cont_rows)
                        update_progress(db, symbol, tf, last_ts_completed=last_cont_ts, status="running")
                    publish("backfill_gap", {"symbol": symbol, "tf": tf, "gap_from": gap[0], "gap_to": gap[1]})
                    time.sleep(0.2)
                else:
                    if rows:
                        upsert_ohlcv(db, symbol, BASE_TF, rows)
                        total_written += len(rows)
                        update_progress(db, symbol, tf, last_ts_completed=rows[-1]["ts"], status="running")
                break
            except Exception as e:
                if attempt >= RETRY_MAX:
                    update_progress(db, symbol, tf, status="error", retry_count=(bp.retry_count + 1 if bp else 1))
                    publish("backfill_error", {"symbol": symbol, "tf": tf, "error": str(e)})
                    return
                sleep_s = RETRY_BASE_SEC * (2 ** attempt)
                time.sleep(sleep_s)
                attempt += 1

        if total_written and total_written % PRINT_PROGRESS_EVERY == 0:
            publish("backfill_progress", {"symbol": symbol, "tf": tf, "written": total_written, "fetched": fetched_total})

    checkpoint = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one()
    last_ts = checkpoint.last_ts_completed if checkpoint else None
    if last_ts:
        q = select(models.OHLCV).where(
            models.OHLCV.symbol == symbol,
            models.OHLCV.tf == BASE_TF,
            models.OHLCV.ts >= start_ms,
            models.OHLCV.ts <= last_ts,
        ).order_by(models.OHLCV.ts.asc())
        rows_db = db.execute(q).scalars().all()
        rows_1m = [{"ts": r.ts, "o": r.o, "h": r.h, "l": r.l, "c": r.c, "v": r.v} for r in rows_db]

        for tf_target in RESAMPLE_TFS:
            agg = resample_candles(rows_1m, tf_target)
            if agg:
                upsert_ohlcv(db, symbol, tf_target, agg)
                publish("backfill_resampled", {"symbol": symbol, "tf_target": tf_target, "rows": len(agg)})

    update_progress(db, symbol, tf, status="done")
    publish("backfill_finished", {"symbol": symbol, "tf": tf, "written": total_written, "fetched": fetched_total})
