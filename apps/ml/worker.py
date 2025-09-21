import time
import json
import redis
from sqlalchemy.orm import Session
from apps.ml.signal_engine import generate_signal_candidates
from apps.api.db import SessionLocal
from apps.api.models import Signal, Position
from apps.ml.validators import (
    get_kill_switch, in_cooldown, basic_market_checks, correlation_cap, risk_profile_limits
)

rds = redis.from_url("redis://redis:6379/0")

def _size_position(capital: float, risk: float, entry: float, sl: float, lev: int) -> float:
    risk_$ = capital * risk
    dist = max(1e-6, abs(entry - sl))
    qty = (risk_$ / dist) * lev / entry
    return max(0.0, qty)

def main():
    print("ML worker started (live publisher with validators + paper positions).")
    while True:
        try:
            if get_kill_switch() or in_cooldown():
                time.sleep(5); continue

            db: Session = SessionLocal()
            candidates = generate_signal_candidates(["BTCUSDT","ETHUSDT"])
            profile = "LOW"
            parallel_now = 0
            capital = 100.0

            for c in candidates:
                ok, reason = risk_profile_limits(profile, requested_lev=c.get("lev",5), current_parallel=parallel_now)
                if not ok:
                    c["status"]="discarded"; c["reason_discard"]=reason
                if c["status"]=="published":
                    ok, reason = basic_market_checks(db, c["symbol"])
                    if not ok:
                        c["status"]="discarded"; c["reason_discard"]=reason
                if c["status"]=="published":
                    ok, reason = correlation_cap(db, user_capital=capital)
                    if not ok:
                        c["status"]="discarded"; c["reason_discard"]=reason

                s = Signal(**c)
                db.add(s); db.flush()

                # paper position, jeśli opublikowany
                if c["status"]=="published":
                    qty = _size_position(capital=capital, risk=c["risk"], entry=c["entry"], sl=c["sl"], lev=c["lev"])
                    exposure = qty * c["entry"]
                    pos = Position(symbol=c["symbol"], side=c["dir"], entry_px=c["entry"], qty=qty, lev=c["lev"],
                                   margin_mode=c["margin_mode"], exposure_usd=exposure, opened_ts=c["ts"], status="open", pnl=0.0)
                    db.add(pos); db.flush()

                payload = dict(
                    id=s.id, symbol=c["symbol"], dir=c["dir"], entry=c["entry"], sl=c["sl"],
                    tp=c["tp"], lev=c["lev"], risk=c["risk"], margin_mode=c["margin_mode"],
                    expected_net_pct=c["expected_net_pct"], confidence=c["confidence"],
                    status=c["status"], reason_discard=c.get("reason_discard"), ts=c["ts"], source="ml"
                )
                rds.publish("signals", json.dumps(payload))
            db.commit(); db.close()
        except Exception as e:
            print("Worker error:", e)
        time.sleep(5)

if __name__ == "__main__":
    main()
