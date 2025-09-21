from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import text

UPSERT_OHLCV_SQL = text("""
INSERT INTO ohlcv (symbol, tf, tstz, ts, o, h, l, c, v, source_hash)
VALUES (:symbol, :tf, to_timestamp(:ts/1000.0), :ts, :o, :h, :l, :c, :v, :source_hash)
ON CONFLICT (symbol, tf, tstz) DO UPDATE SET
 ts = EXCLUDED.ts, o = EXCLUDED.o, h = EXCLUDED.h, l = EXCLUDED.l, c = EXCLUDED.c,
 v = EXCLUDED.v, source_hash = EXCLUDED.source_hash
""")

def upsert_ohlcv_rows(db: Session, rows: list[dict]):
    for r in rows:
        db.execute(UPSERT_OHLCV_SQL, r)
