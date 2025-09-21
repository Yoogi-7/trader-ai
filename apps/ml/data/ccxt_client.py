# apps/ml/data/ccxt_client.py
"""
Prosty wrapper CCXT dla Binance USDT-M Futures (domyślnie).
- fetch_ohlcv_paginated: pobiera świeczki 1m z paginacją i rate-limit sleep.
- normalize_symbol: mapowanie "BTCUSDT" -> "BTC/USDT:USDT" (binanceusdm).
"""
from __future__ import annotations
import os, time, math, typing as T
import ccxt

EXCHANGE_ID = os.getenv("EXCHANGE", "binanceusdm").lower()
RATE_LIMIT_SLEEP_MS = int(os.getenv("RATE_LIMIT_SLEEP_MS", "200"))
MAX_CANDLES_PER_FETCH = int(os.getenv("MAX_CANDLES_PER_FETCH", "1500"))

def _build_exchange() -> ccxt.Exchange:
    klass = getattr(ccxt, EXCHANGE_ID)
    ex = klass({
        "options": {"defaultType": "future"},
        "enableRateLimit": True,
    })
    return ex

def normalize_symbol(sym: str) -> str:
    # Binance futures USDT-M oczekuje "BTC/USDT:USDT"
    if EXCHANGE_ID.startswith("binance"):
        if sym.endswith("USDT"):
            base = sym[:-4]
            return f"{base}/USDT:USDT"
    return sym

def fetch_ohlcv_paginated(symbol: str, timeframe: str, since_ms: int, until_ms: int) -> T.Iterator[T.List]:
    """
    Generator zwracający listy [ts, o, h, l, c, v] (CCXT shape).
    Paginacja po limit=MAX_CANDLES_PER_FETCH.
    """
    ex = _build_exchange()
    market_symbol = normalize_symbol(symbol)
    tf = timeframe

    cur = since_ms
    last_ts = -1
    while True:
        # stop jeśli przekroczono until
        if cur > until_ms:
            break
        data = ex.fetch_ohlcv(market_symbol, timeframe=tf, since=cur, limit=MAX_CANDLES_PER_FETCH)
        if not data:
            break
        for row in data:
            ts = int(row[0])
            if ts <= last_ts:
                continue
            last_ts = ts
            yield row
        # next window
        # CCXT zwraca równomiernie co timeframe; przesuwamy na + last_tf
        cur = last_ts + ex.parse_timeframe(tf) * 1000
        time.sleep(RATE_LIMIT_SLEEP_MS/1000.0)
