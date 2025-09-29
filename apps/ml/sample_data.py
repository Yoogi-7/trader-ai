# apps/ml/sample_data.py
from __future__ import annotations

import math
import time
from typing import List, Optional
from random import Random

DEFAULT_BASE_PRICE = {
    "BTC": 40_000.0,
    "ETH": 2_500.0,
    "BNB": 350.0,
    "ADA": 0.35,
    "SOL": 80.0,
}


def _tf_to_ms(tf: str) -> int:
    mapping = {
        "1m": 60_000,
        "3m": 3 * 60_000,
        "5m": 5 * 60_000,
        "15m": 15 * 60_000,
        "30m": 30 * 60_000,
        "1h": 60 * 60_000,
        "4h": 4 * 60 * 60_000,
        "1d": 24 * 60 * 60_000,
    }
    return mapping.get(tf, 60_000)


def _base_price_for_symbol(symbol: str) -> float:
    prefix = symbol.split("/", 1)[0].upper()
    return DEFAULT_BASE_PRICE.get(prefix, 100.0)


def generate_ohlcv(
    symbol: str,
    timeframe: str,
    since_ms: Optional[int],
    until_ms: Optional[int],
    limit: int,
) -> List[List[float]]:
    """Generate a synthetic OHLCV slice for offline/demo usage."""
    step_ms = _tf_to_ms(timeframe)
    now_ms = int(time.time() * 1000)
    end_ms = until_ms if until_ms is not None else now_ms
    start_ms = since_ms if since_ms is not None else end_ms - step_ms * (limit - 1)
    if start_ms >= end_ms:
        start_ms = end_ms - step_ms * (limit + 5)
    count = max(1, min(limit, int((end_ms - start_ms) / step_ms) + 1))

    base_price = _base_price_for_symbol(symbol)
    rng = Random(f"{symbol}-{timeframe}-{start_ms}")
    price = base_price
    candles: List[List[float]] = []

    for idx in range(count):
        ts = start_ms + idx * step_ms
        seasonal = 0.004 * math.sin(idx / 16.0)
        shock = rng.uniform(-0.003, 0.003)
        drift = 0.0008 * math.sin(idx / 48.0)
        price *= 1.0 + seasonal + shock + drift
        price = max(price, base_price * 0.2)

        close = price
        open_price = close * (1.0 + rng.uniform(-0.0015, 0.0015))
        high = max(open_price, close) * (1.0 + rng.uniform(0.0, 0.002))
        low = min(open_price, close) * (1.0 - rng.uniform(0.0, 0.002))
        volume = abs(rng.gauss(1_000, 150))

        candles.append([
            float(ts),
            float(open_price),
            float(high),
            float(low),
            float(close),
            float(volume),
        ])

    return candles

