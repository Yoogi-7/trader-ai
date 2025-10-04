import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import asyncio
import logging
from apps.api.config import settings

logger = logging.getLogger(__name__)


class CCXTClient:
    """
    CCXT client for fetching OHLCV data with resumable backfill support.
    """

    def __init__(self, exchange_id: str = None):
        self.exchange_id = exchange_id or settings.EXCHANGE_ID
        self.exchange = self._initialize_exchange()

    def _initialize_exchange(self):
        """Initialize CCXT exchange instance"""
        exchange_class = getattr(ccxt, self.exchange_id)

        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        }

        if settings.EXCHANGE_API_KEY and settings.EXCHANGE_SECRET:
            config['apiKey'] = settings.EXCHANGE_API_KEY
            config['secret'] = settings.EXCHANGE_SECRET

        if settings.EXCHANGE_SANDBOX:
            config['sandbox'] = True

        exchange = exchange_class(config)
        exchange.load_markets()

        logger.info(f"Initialized {self.exchange_id} exchange (sandbox={settings.EXCHANGE_SANDBOX})")
        return exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> List[List]:
        """
        Fetch OHLCV data from exchange.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1m', '5m', '15m', '1h', '4h', '1d')
            since: Timestamp in milliseconds
            limit: Number of candles to fetch

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            return ohlcv
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching {symbol} {timeframe}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching {symbol} {timeframe}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} {timeframe}: {e}")
            raise

    def fetch_ohlcv_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a date range with pagination.

        Args:
            symbol: Trading pair
            timeframe: Timeframe
            start_date: Start datetime
            end_date: End datetime
            limit: Candles per request

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        all_candles = []
        current_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)

        while current_ts < end_ts:
            try:
                candles = self.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=limit)

                if not candles:
                    break

                all_candles.extend(candles)

                # Update current timestamp to last candle + 1
                last_ts = candles[-1][0]
                current_ts = last_ts + self._timeframe_to_ms(timeframe)

                # Rate limiting handled by ccxt enableRateLimit
                logger.debug(f"Fetched {len(candles)} candles for {symbol} {timeframe}, last_ts={datetime.fromtimestamp(last_ts/1000)}")

            except Exception as e:
                logger.error(f"Error in fetch_ohlcv_range: {e}")
                break

        if not all_candles:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp').sort_values('timestamp').reset_index(drop=True)

        return df

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Fetch current funding rate for a futures symbol"""
        try:
            funding = self.exchange.fetch_funding_rate(symbol)
            return funding.get('fundingRate', 0.0)
        except Exception as e:
            logger.warning(f"Could not fetch funding rate for {symbol}: {e}")
            return None

    def fetch_open_interest(self, symbol: str) -> Optional[float]:
        """Fetch current open interest for a futures symbol"""
        try:
            oi = self.exchange.fetch_open_interest(symbol)
            return oi.get('openInterest', 0.0)
        except Exception as e:
            logger.warning(f"Could not fetch open interest for {symbol}: {e}")
            return None

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[dict]:
        """Fetch order book (depth)"""
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
            return orderbook
        except Exception as e:
            logger.warning(f"Could not fetch order book for {symbol}: {e}")
            return None

    def detect_gaps(self, df: pd.DataFrame, timeframe: str) -> List[Tuple[datetime, datetime]]:
        """
        Detect gaps in OHLCV data.

        Args:
            df: DataFrame with 'timestamp' column
            timeframe: Expected timeframe

        Returns:
            List of (gap_start, gap_end) tuples
        """
        if df.empty:
            return []

        expected_delta = self._timeframe_to_timedelta(timeframe)
        gaps = []

        for i in range(len(df) - 1):
            current_ts = df.iloc[i]['timestamp']
            next_ts = df.iloc[i + 1]['timestamp']

            actual_delta = next_ts - current_ts

            if actual_delta > expected_delta * 1.5:  # Allow 50% tolerance
                gaps.append((current_ts, next_ts))

        return gaps

    @staticmethod
    def _timeframe_to_ms(timeframe: str) -> int:
        """Convert timeframe string to milliseconds"""
        units = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        return value * units[unit] * 1000

    @staticmethod
    def _timeframe_to_timedelta(timeframe: str) -> timedelta:
        """Convert timeframe string to timedelta"""
        units = {'m': 'minutes', 'h': 'hours', 'd': 'days', 'w': 'weeks'}
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        return timedelta(**{units[unit]: value})

    def get_available_pairs(self, quote: str = 'USDT', contract_type: str = 'future') -> List[str]:
        """Get list of available trading pairs"""
        markets = self.exchange.markets

        pairs = [
            symbol for symbol, market in markets.items()
            if market.get('quote') == quote
            and market.get('type') == contract_type
            and market.get('active', False)
        ]

        return sorted(pairs)

    def get_earliest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Get earliest available timestamp for a symbol by fetching the first candle.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '15m')

        Returns:
            Earliest available datetime (UTC, timezone-naive) or None if unable to fetch
        """
        try:
            # Try fetching from a very early timestamp (2010-01-01)
            # Most exchanges will return the earliest available data if we go too far back
            early_timestamp = int(datetime(2010, 1, 1).timestamp() * 1000)

            candles = self.fetch_ohlcv(symbol, timeframe, since=early_timestamp, limit=1)

            if candles and len(candles) > 0:
                earliest_ts_ms = candles[0][0]
                # Use utcfromtimestamp to get timezone-naive UTC datetime
                earliest_dt = datetime.utcfromtimestamp(earliest_ts_ms / 1000)
                logger.info(f"Earliest available data for {symbol} {timeframe}: {earliest_dt}")
                return earliest_dt
            else:
                logger.warning(f"No data available for {symbol} {timeframe}")
                return None

        except Exception as e:
            logger.error(f"Error getting earliest timestamp for {symbol} {timeframe}: {e}")
            return None
