from __future__ import annotations
import os, time, typing as T
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from apps.api.db import SessionLocal
from apps.api.models import FundingRate, OpenInterest
from apps.ml.data.ccxt_client import _build_exchange, normalize_symbol

PAIRS = os.getenv("PAIRS", "BTCUSDT,ETHUSDT").split(",")
BACKFILL_SINCE_DAYS = int(os.getenv("BACKFILL_SINCE_DAYS", "60"))  # krótszy zakres dla funding/OI

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def upsert_funding(db: Session, symbol: str, rows: T.List[dict]):
    sql = text("""
    INSERT INTO funding_rates(symbol, ts, rate_bps)
    VALUES (:symbol, :ts, :rate_bps)
    ON CONFLICT (symbol, ts) DO UPDATE SET rate_bps = EXCLUDED.rate_bps
    """)
    for r in rows:
        db.execute(sql, r)

def upsert_oi(db: Session, symbol: str, rows: T.List[dict]):
    sql = text("""
    INSERT INTO open_interest(symbol, ts, oi)
    VALUES (:symbol, :ts, :oi)
    ON CONFLICT (symbol, ts) DO UPDATE SET oi = EXCLUDED.oi
    """)
    for r in rows:
        db.execute(sql, r)

def run():
    ex = _build_exchange()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=BACKFILL_SINCE_DAYS)
    since_ms = _ms(since)
    db: Session = SessionLocal()

    for sym in PAIRS:
        mkt = normalize_symbol(sym)

        # FUNDING
        try:
            fr = ex.fetchFundingRateHistory(code=None, symbol=mkt, since=since_ms, limit=1000)
            rows = []
            for x in fr or []:
                ts = int(x.get('timestamp') or x.get('info',{}).get('time', 0))
                rate = float(x.get('fundingRate')) if x.get('fundingRate') is not None else float(x.get('info',{}).get('fundingRate',0))
                rows.append({"symbol": sym, "ts": ts, "rate_bps": rate*10000.0})
            upsert_funding(db, sym, rows)
            db.commit()
            print(f"[funding] {sym}: {len(rows)} rows")
        except Exception as e:
            print(f"[funding] {sym} ERROR: {e}")

        # OPEN INTEREST (nie wszystkie giełdy udostępniają — try/except)
        try:
            if hasattr(ex, "fetchOpenInterestHistory"):
                oih = ex.fetchOpenInterestHistory(symbol=mkt, timeframe='5m', since=since_ms, limit=1000)
                rows = []
                for x in oih or []:
                    ts = int(x.get('timestamp') or x.get('info',{}).get('time', 0))
                    oi = float(x.get('openInterest')) if x.get('openInterest') is not None else float(x.get('info',{}).get('sumOpenInterest', 0))
                    rows.append({"symbol": sym, "ts": ts, "oi": oi})
                upsert_oi(db, sym, rows)
                db.commit()
                print(f"[oi] {sym}: {len(rows)} rows")
        except Exception as e:
            print(f"[oi] {sym} ERROR: {e}")

    db.close()

if __name__ == "__main__":
    run()
