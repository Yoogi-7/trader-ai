# Generates signals respecting >=2% net rule, basic risk sizing and TP/SL logic
import time, random
from typing import List, Dict

def _net_ok(entry, tp1, taker_bps=10, slippage_bps=5) -> float:
    gross = (tp1-entry)/entry
    net = gross - 2*(taker_bps/10000) - (slippage_bps/10000)
    return net

def generate_signal_candidates(pairs: List[str]) -> List[Dict]:
    out = []
    now = int(time.time()*1000)
    for sym in pairs:
        entry = 100.0 + random.uniform(-1,1)
        sl = entry * 0.98
        tp = [entry*1.02, entry*1.03, entry*1.04]
        net = _net_ok(entry, tp[0])
        status = "published" if net >= 0.02 else "discarded"
        out.append(dict(
            symbol=sym, tf_base="15m", ts=now, dir="long", entry=entry, sl=sl,
            tp=[round(x,2) for x in tp], lev=5, risk=0.01, margin_mode="isolated",
            expected_net_pct=round(net*100,2), confidence=0.6, model_ver="v1",
            reason_discard=None if status=="published" else "<2% net", status=status
        ))
    return out