# apps/ml/backfill.py
# PL: Worker backfill – pobiera 1m OHLCV (4 lata+), robi UPSERT do Timescale, prowadzi checkpointy, wznowienia i resampling 15m/1h/4h/1d.
# EN: Backfill worker – fetches 1m OHLCV (4y+), UPSERTs to Timescale, keeps checkpoints, resumes, and resamples to 15m/1h/4h/1d.

import os
import sys
import time
import math
from typing import List, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

# Allow running as module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api.db.session import SessionLocal
from apps.api.db import models
from apps.ml.ccxt_client import CcxtClient
from apps.ml.resample import resample_candles

SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,BNB/USDT,ADA/USDT,SOL/USDT,XRP/USDT,DOGE/USDT,MATIC/USDT,ARB/USDT,OP/USDT").split(",")]
BASE_TF = "1m"
RESAMPLE_TFS = [tf.strip() for tf in os.getenv("RESAMPLE_TFS", "15m,1h,4h,1d").split(",") if tf.strip()]
CHUNK_MINUTES = int(os.getenv("CHUNK_MINUTES", "43200"))  # 30 dni chunk (30*24*60)
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))
PRINT_PROGRESS_EVERY = int(os.getenv("PRINT_PROGRESS_EVERY", "20000"))  # co N świec 1m

MS_IN_MIN = 60_000

def now_ms() -> int:
    return int(time.time() * 1000)

# ---------- DB UPSERT HELPERS ----------

def upsert_ohlcv(db: Session, symbol: str, tf: str, rows: List[Dict]) -> int:
    """
    rows: [{"ts": int, "o": float, "h": float, "l": float, "c": float, "v": float}]
    Returns affected row count (approx).
    """
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
    # Timescale returns no rowcount on bulk upsert – we return len(values) as approx
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
    return bp

# ---------- WORKER CORE ----------

def _fetch_chunk_1m(client: CcxtClient, symbol: str, start_ms: int, end_ms: int) -> List[Dict]:
    # ccxt fetchOHLCV zwraca [ts, o, h, l, c, v]
    raw = client.fetch_ohlcv(symbol, timeframe="1m", since_ms=start_ms, until_ms=end_ms)
    out = [{"ts": r[0], "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "c": float(r[4]), "v": float(r[5])} for r in raw]
    return out

def _iter_chunks(start_ms: int, end_ms: int, chunk_minutes: int):
    chunk_ms = chunk_minutes * MS_IN_MIN
    cur = start_ms
    while cur < end_ms:
        nxt = min(cur + chunk_ms, end_ms)
        yield (cur, nxt)
        cur = nxt

def _detect_gap(expected_start: int, fetched_rows: List[Dict]) -> Optional[Tuple[int, int]]:
    # Zakładamy ciągłość co 60_000 ms; jeśli brakuje, zwracamy zakres luki.
    if not fetched_rows:
        return (expected_start, expected_start + MS_IN_MIN)  # minimalna luka
    ts_sorted = [r["ts"] for r in fetched_rows]
    prev = ts_sorted[0]
    for t in ts_sorted[1:]:
        if t - prev > MS_IN_MIN:
            return (prev + MS_IN_MIN, t - MS_IN_MIN)
        prev = t
    return None

def backfill_symbol(db: Session, client: CcxtClient, symbol: str, tf: str, from_ts: Optional[int], to_ts: Optional[int]) -> None:
    # Ustal zakres
    start_ms = from_ts if from_ts else (now_ms() - 4 * 365 * 24 * 60 * MS_IN_MIN)  # 4 lata temu
    end_ms = to_ts if to_ts else now_ms()

    # Resume – pobierz istniejący checkpoint
    bp = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one_or_none()
    if bp and bp.last_ts_completed:
        start_ms = max(start_ms, bp.last_ts_completed + MS_IN_MIN)

    update_progress(db, symbol, tf, chunk_start_ts=start_ms, chunk_end_ts=end_ms, status="running")

    total_written = 0
    fetched_total = 0

    for a, b in _iter_chunks(start_ms, end_ms, CHUNK_MINUTES):
        attempt = 0
        while True:
            try:
                rows = _fetch_chunk_1m(client, symbol, a, b)
                fetched_total += len(rows)

                # Luki: jeśli mniej niż oczekiwane lub wykryta dziura, NIE przesuwamy last_ts_completed poza ostatni ciągły ts.
                gap = _detect_gap(a, rows)
                if gap:
                    # Zachowujemy konserwatywnie last_ts_completed do ostatniego ciągłego elementu
                    last_cont_ts = rows[0]["ts"]
                    prev_ts = last_cont_ts
                    for r in rows[1:]:
                        if r["ts"] - prev_ts > MS_IN_MIN:
                            break
                        prev_ts = r["ts"]
                    last_cont_ts = prev_ts
                    # Upsert tylko część ciągłą do last_cont_ts
                    cont_rows = [r for r in rows if r["ts"] <= last_cont_ts]
                    if cont_rows:
                        upsert_ohlcv(db, symbol, BASE_TF, cont_rows)
                        total_written += len(cont_rows)
                        update_progress(db, symbol, tf, last_ts_completed=last_cont_ts, status="running")
                    # Log luki i przerwij chunk – przy następnym przebiegu wrócimy po brakujące
                    print(f"[{symbol} {tf}] GAP detected {gap[0]}..{gap[1]} – will retry next run")
                    # Mała przerwa, by nie hammerować API, i wyjście z while -> kolejny chunk
                    time.sleep(0.2)
                else:
                    # Brak luki – upsert całość i przesuwamy checkpoint do ostatniej świecy
                    if rows:
                        upsert_ohlcv(db, symbol, BASE_TF, rows)
                        total_written += len(rows)
                        update_progress(db, symbol, tf, last_ts_completed=rows[-1]["ts"], status="running")
                break
            except Exception as e:
                if attempt >= RETRY_MAX:
                    # Oznaczamy błąd, ale nie przerywamy całego procesu dla innych symboli
                    update_progress(db, symbol, tf, status="error", retry_count=(bp.retry_count + 1 if bp else 1))
                    print(f"[{symbol} {tf}] ERROR after retries: {e}")
                    return
                sleep_s = RETRY_BASE_SEC * (2 ** attempt)
                print(f"[{symbol} {tf}] fetch retry {attempt+1}/{RETRY_MAX} in {sleep_s:.1f}s – error: {e}")
                time.sleep(sleep_s)
                attempt += 1

        if total_written and total_written % PRINT_PROGRESS_EVERY == 0:
            print(f"[{symbol} {tf}] written: {total_written} rows, fetched: {fetched_total}")

    # Po dowiezieniu 1m – resampling i zapis
    # Optymalizacja: resamplujemy tylko nowy zakres: od (start_ms .. last_ts_completed)
    checkpoint = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.symbol == symbol, models.BackfillProgress.tf == tf)).scalar_one()
    last_ts = checkpoint.last_ts_completed if checkpoint else None
    if last_ts:
        # Pobierz świeżo zapisane 1m z DB do resamplingu
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
                print(f"[{symbol}] resampled -> {tf_target}: {len(agg)} rows")

    update_progress(db, symbol, tf, status="done")
    print(f"[{symbol} {tf}] DONE – total written 1m: {total_written}, fetched: {fetched_total}")

def run_backfill_once():
    client = CcxtClient()
    with SessionLocal() as db:
        # Zlecenia uruchomione przez API: status=running
        jobs = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.status == "running")).scalars().all()
        if not jobs:
            # Jeśli nie ma zleceń – możemy opcjonalnie zasilić domyślnymi (symbole z env)
            for s in SYMBOLS:
                update_progress(db, s, "15m", status="running", chunk_start_ts=None, chunk_end_ts=None)
            jobs = db.execute(select(models.BackfillProgress).where(models.BackfillProgress.status == "running")).scalars().all()

        for j in jobs:
            # Wymaganie: bazowy TF to 1m – ale użytkownik uruchamia z tf=15m.
            # Interpretujemy j.tf jako TF docelowy do potwierdzeń; ściągamy 1m ZAWSZE.
            from_ts = j.chunk_start_ts
            to_ts = j.chunk_end_ts
            print(f"=== Backfill {j.symbol} ({BASE_TF} base) range {from_ts}..{to_ts}")
            backfill_symbol(db, client, j.symbol, j.tf, from_ts, to_ts)

def run_loop():
    # Prosty pętla – co X sekund sprawdza zlecenia backfill status=running
    interval_sec = int(os.getenv("BACKFILL_LOOP_SEC", "10"))
    print(f"[backfill] starting loop every {interval_sec}s")
    while True:
        try:
            run_backfill_once()
        except Exception as e:
            print(f"[backfill] loop error: {e}")
        time.sleep(interval_sec)

if __name__ == "__main__":
    mode = os.getenv("BACKFILL_MODE", "once")  # 'once' | 'loop'
    if mode == "loop":
        run_loop()
    else:
        run_backfill_once()
