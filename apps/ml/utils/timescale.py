# apps/ml/utils/timescale.py
"""
Helpery do zapisu OHLCV z upsertem.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

UPSERT_OHLCV_SQL = text("""
INSERT INTO ohlcv (symbol, tf, ts, o, h, l, c, v, source_hash)
VALUES (:symbol, :tf, :ts, :o, :h, :l, :c, :v, :source_hash)
ON CONFLICT (symbol, tf, ts) DO UPDATE
SET o = EXCLUDED.o,
    h = EXCLUDED.h,
    l = EXCLUDED.l,
    c = EXCLUDED.c,
    v = EXCLUDED.v,
    source_hash = EXCLUDED.source_hash
""")

def upsert_ohlcv_rows(db: Session, rows):
    """
    rows: iterable słowników {symbol, tf, ts, o,h,l,c,v, source_hash}
    """
    for r in rows:
        db.execute(UPSERT_OHLCV_SQL, r)
