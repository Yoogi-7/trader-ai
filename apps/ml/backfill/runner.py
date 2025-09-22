from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apps.api.trader_ai.db.models import BackfillProgress, OHLCV

CHUNK_HOURS = 24

def get_checkpoint(db: Session, symbol: str, tf: str) -> datetime | None:
    bp = db.query(BackfillProgress).filter_by(symbol=symbol, tf=tf).one_or_none()
    return bp.last_ts_completed if bp else None

def save_checkpoint(db: Session, symbol: str, tf: str, last_ts: datetime, chunk_start: datetime, chunk_end: datetime, status: str = "running", retries: int = 0):
    bp = db.query(BackfillProgress).filter_by(symbol=symbol, tf=tf).one_or_none()
    if not bp:
        bp = BackfillProgress(symbol=symbol, tf=tf)
        db.add(bp)
    bp.last_ts_completed = last_ts
    bp.chunk_start_ts = chunk_start
    bp.chunk_end_ts = chunk_end
    bp.status = status
    bp.retry_count = retries
    bp.updated_at = datetime.utcnow()
    db.commit()

def backfill_chunk(db: Session, symbol: str, tf: str, start: datetime, end: datetime, fetch_fn):
    """
    fetch_fn(symbol, tf, start, end) -> list[OHLCV-like]
    """
    data = fetch_fn(symbol, tf, start, end)  # w produkcji: ccxt + retry + upsert
    for d in data:
        db.merge(OHLCV(symbol=symbol, tf=tf, ts=d.ts, o=d.o, h=d.h, l=d.l, c=d.c, v=d.v, source_hash=d.hash))
    db.commit()
    return data[-1].ts if data else start

def run_backfill(db: Session, symbol: str, tf: str, from_ts: datetime, to_ts: datetime, fetch_fn):
    # resume logic
    last = get_checkpoint(db, symbol, tf)
    cursor = max(from_ts, last + timedelta(minutes=1)) if last else from_ts

    while cursor < to_ts:
        chunk_end = min(cursor + timedelta(hours=CHUNK_HOURS), to_ts)
        save_checkpoint(db, symbol, tf, last_ts=cursor, chunk_start=cursor, chunk_end=chunk_end, status="running")
        try:
            last_done = backfill_chunk(db, symbol, tf, cursor, chunk_end, fetch_fn)
            save_checkpoint(db, symbol, tf, last_ts=last_done, chunk_start=cursor, chunk_end=chunk_end, status="ok")
            cursor = last_done + timedelta(minutes=1)
        except Exception:
            # zapisz retry i przerwij — wznawianie od last_ts_completed
            bp = db.query(BackfillProgress).filter_by(symbol=symbol, tf=tf).one()
            save_checkpoint(db, symbol, tf, last_ts=bp.last_ts_completed or cursor, chunk_start=cursor, chunk_end=chunk_end, status="error", retries=bp.retry_count + 1)
            break
