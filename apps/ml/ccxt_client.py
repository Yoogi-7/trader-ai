# apps/ml/ccxt_client.py
# PL: Wrapper na ccxt (bez trybu demo).
# EN: ccxt wrapper without demo/synthetic fallbacks.

import logging
import os
import time
from typing import List, Optional

try:
    import ccxt  # type: ignore
except Exception as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "Package 'ccxt' is required for market data fetching. Install it to run Trader AI."
    ) from exc

logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE = os.getenv("EXCHANGE", "binance")
DEFAULT_MARKET_TYPE = os.getenv("MARKET_TYPE", "future")
CCXT_LIMIT = int(os.getenv("CCXT_LIMIT", "1500"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "5"))
RETRY_BASE_SEC = float(os.getenv("RETRY_BASE_SEC", "1.0"))


class CcxtClient:
    def __init__(self):
        try:
            ex_name = DEFAULT_EXCHANGE
            ex_cls = getattr(ccxt, ex_name)
        except AttributeError as exc:  # pragma: no cover - config error
            raise RuntimeError(f"Exchange '{DEFAULT_EXCHANGE}' is not available in ccxt.") from exc
        try:
            self.ex = ex_cls(
                {
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": DEFAULT_MARKET_TYPE,
                    },
                }
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise ccxt exchange '{DEFAULT_EXCHANGE}': {exc}"
            ) from exc

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
        Retrieves OHLCV data via ccxt. Returns list of [ts_ms, o, h, l, c, v].
        """
        if self.ex is None:  # pragma: no cover - defensive
            raise RuntimeError("ccxt exchange instance is not initialised")

        try:
            rows = self._fetch_with_ccxt(symbol, timeframe, since_ms, until_ms)
        except Exception as exc:
            logger.error(
                "ccxt fetch_ohlcv failed for %s %s: %s",
                symbol,
                timeframe,
                exc,
            )
            raise RuntimeError(f"ccxt fetch_ohlcv failed for {symbol} {timeframe}") from exc

        if not rows:
            logger.debug(
                "ccxt fetch returned no rows symbol=%s tf=%s since=%s until=%s",
                symbol,
                timeframe,
                since_ms,
                until_ms,
            )
            return []

        return rows
