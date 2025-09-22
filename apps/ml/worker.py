
import time, json, os
import redis
from datetime import datetime, timezone
from apps.api.config import get_settings
from apps.api.tools.filters import net_pct_after_costs, should_publish_signal
from apps.api.tools.sizing import position_size, liquidation_price

s = get_settings()
rds = redis.from_url(s.REDIS_URL)

def generate_dummy_candidates():
    # Sztuczne sygnały (pokaz live feedu)
    now = datetime.now(timezone.utc).isoformat()
    base = {"tf_base":"15m", "leverage":5, "risk_pct":0.01, "margin_mode":"isolated", "confidence":0.6, "model_ver":"v1"}
    return [
        {"symbol":"BTCUSDT","direction":"LONG","entry":60000, "tp":[60600,61200,62000], "sl":59400, **base, "ts": now},
        {"symbol":"ETHUSDT","direction":"SHORT","entry":2300, "tp":[2260,2240,2200], "sl":2340, **base, "ts": now},
    ]

def main():
    print("ML worker (demo) started.")
    while True:
        try:
            for c in generate_dummy_candidates():
                expected = net_pct_after_costs(c["direction"], c["entry"], c["tp"][0], c["sl"], c["leverage"],
                                               s.MAKER_FEE_BPS, s.SLIPPAGE_BPS, s.FUNDING_BPS)
                ok, reason = should_publish_signal(expected, s.MIN_NET_PCT, c.get("confidence"), s.CONFIDENCE_THRESHOLD)
                status = "published" if ok else "rejected"
                qty = position_size(100.0, c["risk_pct"], c["entry"], c["sl"], c["leverage"]) if ok else 0.0
                liq = liquidation_price(c["direction"], c["entry"], c["leverage"])
                payload = {
                    "symbol": c["symbol"], "direction": c["direction"], "entry": c["entry"], "sl": c["sl"],
                    "tp": c["tp"], "leverage": c["leverage"], "risk_pct": c["risk_pct"], "margin_mode": c["margin_mode"],
                    "expected_net_pct": expected, "confidence": c["confidence"], "status": status, "reason": reason,
                    "qty": qty, "estimated_liq": liq, "ts": c["ts"]
                }
                rds.publish("signals", json.dumps(payload))
            time.sleep(5)
        except Exception as e:
            print("Worker error:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
