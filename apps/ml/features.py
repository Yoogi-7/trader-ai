import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib not available, will use basic pandas calculations")

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    logger.warning("pandas_ta not available, some indicators will be unavailable")


class FeatureEngineering:
    """
    Comprehensive feature engineering for crypto futures trading.
    Includes: TA indicators, Fibonacci, pivots, microstructure, regime detection.
    """

    def __init__(self):
        self.feature_columns = []

    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features for a given OHLCV DataFrame.

        Args:
            df: DataFrame with columns [timestamp, open, high, low, close, volume]

        Returns:
            DataFrame with all computed features
        """
        df = df.copy()

        # Technical indicators
        df = self._add_emas(df)
        df = self._add_rsi(df)
        df = self._add_stochastic(df)
        df = self._add_macd(df)
        df = self._add_atr(df)
        df = self._add_bollinger_bands(df)
        df = self._add_ichimoku(df)

        # Fibonacci & Pivots
        df = self._add_fibonacci(df)
        df = self._add_pivot_points(df)

        # Market regime
        df = self._add_regime_detection(df)

        # Microstructure (requires market_metrics join in production)
        # Placeholder columns for now
        df['spread_bps'] = 0.0
        df['depth_imbalance'] = 0.0
        df['realized_vol'] = df['close'].pct_change().rolling(20).std() * np.sqrt(365 * 24)

        # Sentiment (plugin interface - placeholder)
        df['sentiment_score'] = 0.0

        return df

    def _add_emas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Exponential Moving Averages"""
        for period in [9, 21, 50, 200]:
            if TALIB_AVAILABLE:
                df[f'ema_{period}'] = talib.EMA(df['close'], timeperiod=period)
            elif PANDAS_TA_AVAILABLE:
                df[f'ema_{period}'] = ta.ema(df['close'], length=period)
            else:
                df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        return df

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add RSI (Relative Strength Index)"""
        if TALIB_AVAILABLE:
            df['rsi_14'] = talib.RSI(df['close'], timeperiod=14)
        elif PANDAS_TA_AVAILABLE:
            df['rsi_14'] = ta.rsi(df['close'], length=14)
        else:
            # Manual RSI calculation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
        return df

    def _add_stochastic(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Stochastic Oscillator"""
        if TALIB_AVAILABLE:
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
        elif PANDAS_TA_AVAILABLE:
            stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3)
            if stoch is not None and not stoch.empty:
                df['stoch_k'] = stoch[f'STOCHk_14_3_3']
                df['stoch_d'] = stoch[f'STOCHd_14_3_3']
            else:
                df['stoch_k'] = np.nan
                df['stoch_d'] = np.nan
        else:
            # Manual Stochastic calculation
            low_14 = df['low'].rolling(window=14).min()
            high_14 = df['high'].rolling(window=14).max()
            df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
            df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        return df

    def _add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD (Moving Average Convergence Divergence)"""
        if TALIB_AVAILABLE:
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
                df['close'], fastperiod=12, slowperiod=26, signalperiod=9
            )
        elif PANDAS_TA_AVAILABLE:
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd is not None and not macd.empty:
                df['macd'] = macd['MACD_12_26_9']
                df['macd_signal'] = macd['MACDs_12_26_9']
                df['macd_hist'] = macd['MACDh_12_26_9']
            else:
                df['macd'] = np.nan
                df['macd_signal'] = np.nan
                df['macd_hist'] = np.nan
        else:
            # Manual MACD calculation
            ema_12 = df['close'].ewm(span=12, adjust=False).mean()
            ema_26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = ema_12 - ema_26
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ATR (Average True Range)"""
        if TALIB_AVAILABLE:
            df['atr_14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        elif PANDAS_TA_AVAILABLE:
            df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        else:
            # Manual ATR calculation
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            df['atr_14'] = pd.Series(true_range).rolling(window=14).mean()
        return df

    def _add_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Bollinger Bands"""
        if TALIB_AVAILABLE:
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
            )
        elif PANDAS_TA_AVAILABLE:
            bbands = ta.bbands(df['close'], length=20, std=2)
            if bbands is not None and not bbands.empty:
                df['bb_lower'] = bbands['BBL_20_2.0']
                df['bb_middle'] = bbands['BBM_20_2.0']
                df['bb_upper'] = bbands['BBU_20_2.0']
            else:
                df['bb_lower'] = np.nan
                df['bb_middle'] = np.nan
                df['bb_upper'] = np.nan
        else:
            # Manual Bollinger Bands calculation
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        return df

    def _add_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Ichimoku Cloud indicators"""
        if PANDAS_TA_AVAILABLE:
            ichimoku = ta.ichimoku(df['high'], df['low'], df['close'])

            if ichimoku is not None and len(ichimoku) == 2:
                ich_df, ich_span = ichimoku
                df['tenkan_sen'] = ich_df['ITS_9']
                df['kijun_sen'] = ich_df['IKS_26']
                df['senkou_a'] = ich_span['ISA_9']
                df['senkou_b'] = ich_span['ISB_26']
                df['chikou_span'] = ich_df['ICS_26']
            else:
                df['tenkan_sen'] = np.nan
                df['kijun_sen'] = np.nan
                df['senkou_a'] = np.nan
                df['senkou_b'] = np.nan
                df['chikou_span'] = np.nan
        else:
            # Manual Ichimoku calculation
            high_9 = df['high'].rolling(window=9).max()
            low_9 = df['low'].rolling(window=9).min()
            df['tenkan_sen'] = (high_9 + low_9) / 2

            high_26 = df['high'].rolling(window=26).max()
            low_26 = df['low'].rolling(window=26).min()
            df['kijun_sen'] = (high_26 + low_26) / 2

            df['senkou_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)

            high_52 = df['high'].rolling(window=52).max()
            low_52 = df['low'].rolling(window=52).min()
            df['senkou_b'] = ((high_52 + low_52) / 2).shift(26)

            df['chikou_span'] = df['close'].shift(-26)

        return df

    def _add_fibonacci(self, df: pd.DataFrame, lookback: int = 100) -> pd.DataFrame:
        """
        Add Fibonacci retracement levels based on recent high/low.
        """
        rolling_high = df['high'].rolling(lookback).max()
        rolling_low = df['low'].rolling(lookback).min()
        diff = rolling_high - rolling_low

        df['fib_618'] = rolling_high - diff * 0.618
        df['fib_50'] = rolling_high - diff * 0.5
        df['fib_382'] = rolling_high - diff * 0.382

        return df

    def _add_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Pivot Points (classic formula).
        """
        # Use previous day's high, low, close for pivot calculation
        df['pivot_point'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        df['resistance_1'] = 2 * df['pivot_point'] - df['low'].shift(1)
        df['support_1'] = 2 * df['pivot_point'] - df['high'].shift(1)

        return df

    def _add_regime_detection(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect market regime: trend (uptrend/downtrend/sideways) and volatility (low/med/high).
        Returns numeric encodings instead of strings.
        """
        # Trend detection using EMA crossovers
        # 1 = uptrend, -1 = downtrend, 0 = sideways
        if 'ema_21' in df.columns and 'ema_50' in df.columns:
            ema_diff = df['ema_21'] - df['ema_50']
            df['regime_trend'] = np.where(
                ema_diff > 0, 1,
                np.where(ema_diff < 0, -1, 0)
            )
        else:
            df['regime_trend'] = 0

        # Volatility regime using ATR percentile
        # 2 = high, 1 = medium, 0 = low
        if 'atr_14' in df.columns and df['close'].notna().any():
            atr_pct = df['atr_14'] / df['close']
            atr_percentile = atr_pct.rolling(100).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5)

            df['regime_volatility'] = np.where(
                atr_percentile > 0.66, 2,
                np.where(atr_percentile > 0.33, 1, 0)
            )
        else:
            df['regime_volatility'] = 1

        return df

    def get_feature_columns(self, df: pd.DataFrame) -> list:
        """Return list of feature column names (only numeric types)"""
        exclude = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'timeframe', 'label']
        # Only return columns that are numeric (int, float, bool)
        feature_cols = []
        for col in df.columns:
            if col not in exclude:
                # Check if column is numeric
                if pd.api.types.is_numeric_dtype(df[col]):
                    feature_cols.append(col)
                else:
                    logger.warning(f"Skipping non-numeric column: {col} (dtype: {df[col].dtype})")
        return feature_cols
