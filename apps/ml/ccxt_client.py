# apps/ml/ccxt_client.py
# PL: Prosty wrapper na ccxt dla Binance USDT-M futures z retry.
# EN: Simple ccxt wrapper for Binance USDT-M futures with retry.

import os
import time
from typing import List, Optional

import ccxt  # type: ignore

DEFAULT_EXCHANGE = os.getenv("EXCHANGE", "binance")
DEFAULT_MARKET_TYPE = os.getenv("MARKET_TYPE", "future")  # 'spot' | 'future'
CCXT_LIMIT = int(os.getenv("CCXT_LIMIT", "1500"))         # typical binance limit
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))

class CcxtClient:
    def __init__(self):
        ex_name = DEFAULT_EXCHANGE
        ex_cls = getattr(ccxt, ex_name)
        self.ex = ex_cls({
            "enableRateLimit": True,
            "options": {
                "defaultType": DEFAULT_MARKET_TYPE,  # to use futures on binance
            },
        })

    def _sleep_backoff(self, attempt: int):
        delay = RETRY_BASE_SEC * (2 ** attempt)
        time.sleep(delay)

    def fetch_ohlcv(self, symbol: str, timeframe: str, since_ms: Optional[int], until_ms: Optional[int]) -> List[List[float]]:
        """
        PL: Pobiera OHLCV w zakresie [since_ms, until_ms) chunkując po CCXT_LIMIT.
        EN: Fetches OHLCV in [since_ms, until_ms) with chunking by CCXT_LIMIT.
        Returns list of [ts_ms, o, h, l, c, v].
        """
        tf = timeframe
        out: List[List[float]] = []
        ms = since_ms
        # ccxt standard: fetchOHLCV(symbol, timeframe='1m', since=None, limit=None)
        # Binance ignores 'until', so we'll loop until we reach it.

        while True:
            attempt = 0
            while True:
                try:
                    rows = self.ex.fetch_ohlcv(symbol, timeframe=tf, since=ms, limit=CCXT_LIMIT)
                    break
                except Exception:
                    if attempt >= RETRY_MAX:
                        raise
                    self._sleep_backoff(attempt)
                    attempt += 1

            if not rows:
                break

            # ccxt returns [ts, open, high, low, close, volume]
            # Filter by until_ms if provided
            if until_ms is not None:
                rows = [r for r in rows if r[0] < until_ms]
                if not rows:
                    break

            out.extend(rows)

            last_ts = rows[-1][0]
            # Move to next candle
            # For 1m we add 60_000; for others ccxt handles since internally if using 'since'
            if tf == "1m":
                ms = last_ts + 60_000
            elif tf == "5m":
                ms = last_ts + 5 * 60_000
            elif tf == "15m":
                ms = last_ts + 15 * 60_000
            elif tf == "1h":
                ms = last_ts + 60 * 60_000
            elif tf == "4h":
                ms = last_ts + 4 * 60 * 60_000
            elif tf == "1d":
                ms = last_ts + 24 * 60 * 60_000
            else:
                # default next step ~ 1m
                ms = last_ts + 60_000

            # Stop if we passed until_ms
            if until_ms is not None and ms >= until_ms:
                break

        return out
