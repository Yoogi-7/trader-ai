from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import ccxt
import time
import hashlib
import os

log = logging.getLogger(__name__)

DB_URL = f"postgresql+psycopg://{os.getenv('DB_USER','trader')}:{os.getenv('DB_PASSWORD','traderpass')}@{os.getenv('DB_HOST','db')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','traderai')}"

def _hash_source(exchange: str, symbol: str, tf: str) -> str:
    return hashlib.sha256(f"{exchange}:{symbol}:{tf}".encode()).hexdigest()[:16]

def backfill_ohlcv(symbol: str, years: int = 4, tf: str = "1m", retry: int = 5):
    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    ex_name = os.getenv("EXCHANGE","binanceusdm")
    ex = getattr(ccxt, ex_name)({"enableRateLimit": True})

    try:
        # resume: odczytaj last_ts_completed
        row = session.execute(
            text("SELECT last_ts_completed FROM backfill_progress WHERE symbol=:s AND tf=:tf"),
            {"s": symbol, "tf": tf}
        ).fetchone()

        start = (datetime.now(timezone.utc) - timedelta(days=365*years))
        if row and row[0]:
            start = row[0]  # resume
        end = datetime.now(timezone.utc)

        since = int(start.timestamp() * 1000)
        limit = 1500
        chunk_ms = int(timedelta(minutes=int(os.getenv("BACKFILL_JOB_CHUNK_MINUTES","720"))).total_seconds() * 1000)
        source_hash = _hash_source(ex_name, symbol, tf)

        while since < int(end.timestamp() * 1000):
            chunk_end = min(since + chunk_ms, int(end.timestamp() * 1000))
            got_any = False
            cursor = since
            tries = 0
            while cursor < chunk_end:
                try:
                    ohlcv = ex.fetch_ohlcv(symbol, timeframe=tf, since=cursor, limit=limit)
                    if not ohlcv:
                        break
                    # insert/upsert
                    ins = []
                    for ts,o,h,l,c,v in ohlcv:
                        ins.append({"symbol":symbol, "tf":tf, "ts": datetime.fromtimestamp(ts/1000, tz=timezone.utc),
                                    "o":o,"h":h,"l":l,"c":c,"v":v,"source_hash":source_hash})
                    # bulk upsert
                    session.execute(text("""
                        INSERT INTO ohlcv(symbol,tf,ts,o,h,l,c,v,source_hash)
                        VALUES(:symbol,:tf,:ts,:o,:h,:l,:c,:v,:source_hash)
                        ON CONFLICT (symbol,tf,ts) DO UPDATE SET
                            o=EXCLUDED.o,h=EXCLUDED.h,l=EXCLUDED.l,c=EXCLUDED.c,v=EXCLUDED.v,source_hash=EXCLUDED.source_hash
                    """), ins)
                    session.commit()
                    got_any = True
                    cursor = ohlcv[-1][0] + 1
                except Exception as e:
                    session.rollback()
                    tries += 1
                    if tries > retry:
                        # zarejestruj lukę
                        session.execute(text("""
                            INSERT INTO backfill_progress(symbol,tf,last_ts_completed,chunk_start_ts,chunk_end_ts,retry_count,status,updated_at)
                            VALUES(:s,:tf, to_timestamp(:last/1000.0), to_timestamp(:cs/1000.0), to_timestamp(:ce/1000.0), :r, 'gap', now())
                            ON CONFLICT(symbol,tf) DO UPDATE SET status='gap', retry_count=:r, updated_at=now()
                        """), {"s":symbol,"tf":tf,"last":cursor,"cs":since,"ce":chunk_end,"r":tries})
                        session.commit()
                        log.exception("Backfill failed permanently, gap recorded")
                        break
                    time.sleep(1.5 * tries)
            # update progress
            session.execute(text("""
                INSERT INTO backfill_progress(symbol,tf,last_ts_completed,chunk_start_ts,chunk_end_ts,retry_count,status,updated_at)
                VALUES(:s,:tf, to_timestamp(:last/1000.0), to_timestamp(:cs/1000.0), to_timestamp(:ce/1000.0), 0, :st, now())
                ON CONFLICT(symbol,tf) DO UPDATE SET last_ts_completed=excluded.last_ts_completed, status=:st, updated_at=now()
            """), {"s":symbol,"tf":tf,"last":cursor if got_any else since, "cs":since, "ce":chunk_end, "st":"ok" if got_any else "idle"})
            session.commit()
            since = chunk_end
    finally:
        session.close()
        engine.dispose()
