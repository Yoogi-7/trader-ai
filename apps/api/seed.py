# Demo seed: generate synthetic OHLCV and one demo user
import os, time, random, math, json
from sqlalchemy.orm import Session
from apps.api.db import SessionLocal, engine
from apps.api.models import OHLCV, User
from apps.api.config import settings

def gen_prices(n=1000, start=30000.0):
    px = start
    out = []
    t = int(time.time()*1000) - n*60_000
    for i in range(n):
        # simple random walk with drift
        drift = random.uniform(-0.002, 0.002)
        vol = random.uniform(0.0, 0.01)
        ret = drift + random.uniform(-vol, vol)
        new = max(50.0, px * (1+ret))
        o = px
        c = new
        h = max(o,c) * (1+random.uniform(0,0.002))
        l = min(o,c) * (1-random.uniform(0,0.002))
        v = random.uniform(10, 1000)
        out.append((t, o,h,l,c,v))
        px = new; t += 60_000
    return out

def run():
    db: Session = SessionLocal()
    for sym in os.getenv("PAIRS","BTCUSDT,ETHUSDT").split(","):
        data = gen_prices(settings.DEMO_SEED_ROWS, 30000 if sym.startswith("BTC") else 2000)
        for ts,o,h,l,c,v in data:
            db.add(OHLCV(symbol=sym, tf="1m", ts=ts, o=o,h=h,l=l,c=c,v=v))
    db.add(User(risk_profile="LOW", capital=100.0, prefs={}, api_connected=False))
    db.commit()
    print("Seed done.")

if __name__ == "__main__":
    run()