# Minimal worker that periodically logs and could consume Kafka in real deploy.
import time, os, json, random
from apps.ml.signal_engine import generate_signal_candidates
from apps.api.db import SessionLocal
from apps.api.models import Signal

def main():
    print("ML worker started (demo loop).")
    while True:
        try:
            db = SessionLocal()
            candidates = generate_signal_candidates(["BTCUSDT","ETHUSDT"])
            for c in candidates:
                if c["status"]=="published":
                    s = Signal(**c)
                    db.add(s)
            db.commit(); db.close()
        except Exception as e:
            print("Worker error:", e)
        time.sleep(10)

if __name__ == "__main__":
    main()