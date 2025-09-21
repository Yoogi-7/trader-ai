from __future__ import annotations
import os, time
from sqlalchemy.orm import Session
from sqlalchemy import text
from apps.api.db import SessionLocal
from apps.api.models import OrderBookSnapshot
from apps.ml.data.orderbook_ccxt import fetch_orderbook_snapshot

PAIRS = os.getenv("PAIRS", "BTCUSDT,ETHUSDT").split(",")

UPSERT_SQL = text("""
INSERT INTO orderbook_snapshots (symbol, ts, bid_px, bid_qty, ask_px, ask_qty, mid_px, spread_bps, depth_usd_1pct)
VALUES (:symbol, :ts, :bid_px, :bid_qty, :ask_px, :ask_qty, :mid_px, :spread_bps, :depth_usd_1pct)
ON CONFLICT (symbol, ts) DO UPDATE SET
 bid_px=EXCLUDED.bid_px, bid_qty=EXCLUDED.bid_qty,
 ask_px=EXCLUDED.ask_px, ask_qty=EXCLUDED.ask_qty,
 mid_px=EXCLUDED.mid_px, spread_bps=EXCLUDED.spread_bps,
 depth_usd_1pct=EXCLUDED.depth_usd_1pct
""")

def run_once():
    db: Session = SessionLocal()
    for sym in PAIRS:
        try:
            snap = fetch_orderbook_snapshot(sym)
            db.execute(UPSERT_SQL, snap)
            db.commit()
            print(f"[orderbook] {sym} ts={snap['ts']} spread_bps={snap['spread_bps']:.2f} depth1%=${snap['depth_usd_1pct']:.0f}")
        except Exception as e:
            print(f"[orderbook] {sym} ERROR: {e}")
    db.close()

def run_loop(sleep_s: int = 30):
    while True:
        run_once()
        time.sleep(sleep_s)

if __name__ == "__main__":
    run_loop(30)
