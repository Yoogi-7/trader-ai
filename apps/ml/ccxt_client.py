# apps/ml/ccxt_client.py
# PL: Wrapper na ccxt z trybem offline generującym syntetyczne dane.
# EN: ccxt wrapper with offline synthetic data fallback.

import logging
import os
import time
from typing import List, Optional

import ccxt  # type: ignore

from apps.ml.sample_data import generate_ohlcv

logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE = os.getenv("EXCHANGE", "binance")
DEFAULT_MARKET_TYPE = os.getenv("MARKET_TYPE", "future")
CCXT_LIMIT = int(os.getenv("CCXT_LIMIT", "1500"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))


class CcxtClient:
    def __init__(self):
        self._offline = False
        try:
            ex_name = DEFAULT_EXCHANGE
            ex_cls = getattr(ccxt, ex_name)
            self.ex = ex_cls(
                {
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": DEFAULT_MARKET_TYPE,
                    },
                }
            )
        except Exception as exc:
            logger.warning(
                "ccxt exchange init failed (%s); using synthetic OHLCV generator", exc
            )
            self.ex = None
            self._offline = True

    def _sleep_backoff(self, attempt: int) -> None:
        delay = RETRY_BASE_SEC * (2 ** attempt)
        time.sleep(delay)

    def _fetch_with_ccxt(
        self, symbol: str, timeframe: str, since_ms: Optional[int], until_ms: Optional[int]
    ) -> List[List[float]]:
        tf = timeframe
        out: List[List[float]] = []
        ms = since_ms

        while True:
            attempt = 0
            while True:
                try:
                    rows = self.ex.fetch_ohlcv(symbol, timeframe=tf, since=ms, limit=CCXT_LIMIT)
                    break
                except Exception as exc:
                    if attempt >= RETRY_MAX:
                        raise exc
                    self._sleep_backoff(attempt)
                    attempt += 1

            if not rows:
                break

            if until_ms is not None:
                rows = [r for r in rows if r[0] < until_ms]
                if not rows:
                    break

            out.extend(rows)

            last_ts = rows[-1][0]
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
                ms = last_ts + 60_000

            if until_ms is not None and ms >= until_ms:
                break

        return out

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, since_ms: Optional[int], until_ms: Optional[int]
    ) -> List[List[float]]:
        """
        Retrieves OHLCV data from ccxt or synthetic generator when offline.
        Returns list of [ts_ms, o, h, l, c, v].
        """
        if self._offline or self.ex is None:
            return generate_ohlcv(symbol, timeframe, since_ms, until_ms, CCXT_LIMIT)

        try:
            rows = self._fetch_with_ccxt(symbol, timeframe, since_ms, until_ms)
            if not rows:
                raise RuntimeError("empty_remote_response")
            return rows
        except Exception as exc:
            logger.warning(
                "ccxt fetch_ohlcv failed for %s %s (%s); switching to synthetic data",
                symbol,
                timeframe,
                exc,
            )
            self._offline = True
            return generate_ohlcv(symbol, timeframe, since_ms, until_ms, CCXT_LIMIT)
