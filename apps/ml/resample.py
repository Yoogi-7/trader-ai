# apps/ml/resample.py
# PL: Resampling 1m -> 15m/1h/4h/1d bez zewnętrznych serwisów.
# EN: Local resampling from 1m to 15m/1h/4h/1d.

from typing import List, Dict

# We accept list of dicts: {"ts": int, "o": float, "h": float, "l": float, "c": float, "v": float}
# Return same structure aggregated to target tf.

TF_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

def _bucket_start(ts_ms: int, tf_ms: int) -> int:
    return (ts_ms // tf_ms) * tf_ms

def resample_candles(rows_1m: List[Dict], target_tf: str) -> List[Dict]:
    if target_tf not in TF_MS:
        raise ValueError(f"Unsupported TF {target_tf}")
    if target_tf == "1m":
        return rows_1m

    tf_ms = TF_MS[target_tf]
    buckets: Dict[int, Dict] = {}

    for r in rows_1m:
        b = _bucket_start(r["ts"], tf_ms)
        agg = buckets.get(b)
        if not agg:
            buckets[b] = {
                "ts": b,
                "o": r["o"],
                "h": r["h"],
                "l": r["l"],
                "c": r["c"],
                "v": r["v"],
            }
        else:
            agg["h"] = max(agg["h"], r["h"])
            agg["l"] = min(agg["l"], r["l"])
            agg["c"] = r["c"]
            agg["v"] += r["v"]

    # Return sorted by ts
    out = list(buckets.values())
    out.sort(key=lambda x: x["ts"])
    return out
