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

    def compute_all_features(
        self,
        df: pd.DataFrame,
        market_metrics: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Compute all features for a given OHLCV DataFrame.

        Args:
            df: DataFrame with columns [timestamp, open, high, low, close, volume]

        Returns:
            DataFrame with all computed features
        """
        df = df.copy()

        # Technical indicators - Basic
        df = self._add_emas(df)
        df = self._add_rsi(df)
        df = self._add_stochastic(df)
        df = self._add_macd(df)
        df = self._add_atr(df)
        df = self._add_bollinger_bands(df)

        # Note: Ichimoku removed due to look-ahead bias (chikou_span shifts future data)

        # Advanced indicators
        df = self._add_vwap(df)
        df = self._add_stochrsi(df)
        df = self._add_keltner_channels(df)
        df = self._add_supertrend(df)
        df = self._add_adx(df)

        # Price action
        df = self._add_swing_points(df)
        df = self._add_fibonacci_dynamic(df)
        df = self._add_pivot_points(df)

        # Volume analysis
        df = self._add_obv(df)
        df = self._add_volume_profile(df)

        # Market structure
        df = self._add_obi(df)
        df = self._add_bid_ask_spread_dynamic(df)

        # Derivative features
        df = self._add_ema_slopes(df)
        df = self._add_consolidation_zones(df)
        df = self._add_rsi_divergence(df)

        # Market regime
        df = self._add_regime_detection(df)

        # Microstructure & market metrics
        df = self._add_market_metrics(df, market_metrics)

        # Sentiment (plugin interface - placeholder)
        if 'sentiment_score' not in df.columns:
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

    def _add_market_metrics(
        self,
        df: pd.DataFrame,
        market_metrics: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """Join market microstructure metrics when available"""
        df = df.copy()

        if market_metrics is None or market_metrics.empty:
            # Fall back to safe defaults if no external data provided
            df['spread_bps'] = df.get('spread_bps', pd.Series(0.0, index=df.index))
            df['depth_imbalance'] = df.get('depth_imbalance', pd.Series(0.0, index=df.index))
            df['realized_vol'] = df.get(
                'realized_vol',
                df['close'].pct_change().rolling(20).std() * np.sqrt(365 * 24)
            )
            df['funding_rate'] = df.get('funding_rate', pd.Series(0.0, index=df.index))
            df['open_interest'] = df.get('open_interest', pd.Series(0.0, index=df.index))
            return df

        metrics = market_metrics.sort_values('timestamp')
        base = df.sort_values('timestamp')

        merged = pd.merge_asof(
            base,
            metrics,
            on='timestamp',
            direction='backward',
            tolerance=pd.Timedelta(minutes=15)
        )

        # Forward fill to smooth missing values between updates
        for col, default in [
            ('spread_bps', 0.0),
            ('depth_imbalance', 0.0),
            ('realized_volatility', np.nan),
            ('funding_rate', 0.0),
            ('open_interest', np.nan)
        ]:
            if col not in merged:
                merged[col] = default
            merged[col] = merged[col].fillna(method='ffill').fillna(default)

        df['spread_bps'] = merged['spread_bps']
        df['depth_imbalance'] = merged['depth_imbalance']
        df['realized_vol'] = merged['realized_volatility']
        df['funding_rate'] = merged['funding_rate']
        df['open_interest'] = merged['open_interest']

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
        exclude = [
            'timestamp',
            'open',
            'high',
            'low',
            'close',
            'volume',
            'symbol',
            'timeframe',
            'label',
            'hit_barrier',
            'return_pct',
            'bars_to_hit'
        ]
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

    def _add_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Volume Weighted Average Price (VWAP)"""
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        # Rolling VWAP (daily reset simulation using 96 periods for 15m = 24h)
        window = 96
        df['vwap_rolling'] = (
            (df['close'] * df['volume']).rolling(window).sum() / 
            df['volume'].rolling(window).sum()
        )
        df['vwap_distance'] = (df['close'] - df['vwap_rolling']) / df['vwap_rolling']
        return df

    def _add_stochrsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Stochastic RSI - More sensitive momentum indicator"""
        if 'rsi_14' in df.columns:
            rsi = df['rsi_14']
            rsi_min = rsi.rolling(14).min()
            rsi_max = rsi.rolling(14).max()
            df['stochrsi'] = 100 * (rsi - rsi_min) / (rsi_max - rsi_min)
            df['stochrsi_k'] = df['stochrsi'].rolling(3).mean()
            df['stochrsi_d'] = df['stochrsi_k'].rolling(3).mean()
        else:
            df['stochrsi'] = 50.0
            df['stochrsi_k'] = 50.0
            df['stochrsi_d'] = 50.0
        return df

    def _add_keltner_channels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Keltner Channels - Dynamic support/resistance based on EMA + ATR"""
        if 'ema_20' not in df.columns:
            df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        if 'atr_14' in df.columns:
            atr = df['atr_14']
        else:
            # Calculate ATR if not present
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean()
        
        multiplier = 2.0
        df['keltner_upper'] = df['ema_20'] + multiplier * atr
        df['keltner_lower'] = df['ema_20'] - multiplier * atr
        df['keltner_width'] = (df['keltner_upper'] - df['keltner_lower']) / df['ema_20']
        return df

    def _add_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Supertrend indicator - Trend following indicator"""
        if 'atr_14' not in df.columns:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean()
        else:
            atr = df['atr_14']
        
        hl_avg = (df['high'] + df['low']) / 2
        multiplier = 3.0
        
        upper_band = hl_avg + multiplier * atr
        lower_band = hl_avg - multiplier * atr
        
        # Supertrend logic
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1] if i > 0 else 0
            
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
        
        df['supertrend'] = supertrend
        df['supertrend_direction'] = direction
        return df

    def _add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ADX (Average Directional Index) - Trend strength indicator"""
        if TALIB_AVAILABLE:
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        else:
            # Manual ADX calculation
            high_diff = df['high'].diff()
            low_diff = -df['low'].diff()
            
            plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
            minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
            
            if 'atr_14' in df.columns:
                tr = df['atr_14'] * 14  # Approximate
            else:
                high_low = df['high'] - df['low']
                high_close = np.abs(df['high'] - df['close'].shift())
                low_close = np.abs(df['low'] - df['close'].shift())
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            
            plus_di = 100 * (plus_dm.rolling(14).mean() / tr.rolling(14).mean())
            minus_di = 100 * (minus_dm.rolling(14).mean() / tr.rolling(14).mean())
            
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
            df['adx'] = dx.rolling(14).mean()
        
        return df

    def _add_swing_points(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        """Detect swing highs and lows using rolling windows"""
        df['swing_high'] = (
            (df['high'] == df['high'].rolling(window*2+1, center=True).max()).astype(int)
        )
        df['swing_low'] = (
            (df['low'] == df['low'].rolling(window*2+1, center=True).min()).astype(int)
        )
        
        # Distance to nearest swing points
        df['dist_to_swing_high'] = df['close'] / df.loc[df['swing_high'] == 1, 'high'].reindex(df.index).ffill() - 1
        df['dist_to_swing_low'] = df['close'] / df.loc[df['swing_low'] == 1, 'low'].reindex(df.index).ffill() - 1
        
        return df

    def _add_fibonacci_dynamic(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dynamic Fibonacci levels based on detected swings"""
        window = 50
        
        # Find recent swing high/low
        rolling_high = df['high'].rolling(window).max()
        rolling_low = df['low'].rolling(window).min()
        
        diff = rolling_high - rolling_low
        
        # Fibonacci retracements from high to low
        df['fib_0'] = rolling_high
        df['fib_236'] = rolling_high - diff * 0.236
        df['fib_382'] = rolling_high - diff * 0.382
        df['fib_50'] = rolling_high - diff * 0.5
        df['fib_618'] = rolling_high - diff * 0.618
        df['fib_786'] = rolling_high - diff * 0.786
        df['fib_100'] = rolling_low
        
        # Fibonacci extensions
        df['fib_1618'] = rolling_low - diff * 0.618
        df['fib_2618'] = rolling_low - diff * 1.618
        
        return df

    def _add_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add On-Balance Volume (OBV) - Cumulative volume indicator"""
        obv = np.where(df['close'] > df['close'].shift(), df['volume'],
                      np.where(df['close'] < df['close'].shift(), -df['volume'], 0))
        df['obv'] = obv.cumsum()
        df['obv_ema'] = df['obv'].ewm(span=20, adjust=False).mean()
        df['obv_divergence'] = df['obv'] - df['obv_ema']
        return df

    def _add_volume_profile(self, df: pd.DataFrame, window: int = 50) -> pd.DataFrame:
        """Add simplified Volume Profile features"""
        # Calculate price levels and volume distribution
        df['volume_surge'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # High volume nodes (simplified)
        df['high_volume_node'] = (df['volume'] > df['volume'].rolling(window).quantile(0.8)).astype(int)
        
        # Volume-weighted price levels
        df['vwap_std'] = (
            ((df['close'] - df['vwap_rolling'])**2 * df['volume']).rolling(window).sum() / 
            df['volume'].rolling(window).sum()
        ).pow(0.5)
        
        return df

    def _add_obi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Order Book Imbalance (OBI) - Simulated from price/volume action"""
        # Since we don't have real order book data, simulate using price momentum and volume
        price_momentum = df['close'].pct_change()
        volume_ratio = df['volume'] / df['volume'].rolling(20).mean()
        
        # Estimate buy/sell pressure
        buy_pressure = np.where(price_momentum > 0, price_momentum * volume_ratio, 0)
        sell_pressure = np.where(price_momentum < 0, abs(price_momentum) * volume_ratio, 0)
        
        df['obi'] = (buy_pressure - sell_pressure) / (buy_pressure + sell_pressure + 1e-10)
        df['obi_ema'] = pd.Series(df['obi']).ewm(span=10, adjust=False).mean()
        
        return df

    def _add_bid_ask_spread_dynamic(self, df: pd.DataFrame) -> pd.DataFrame:
        """Estimate dynamic bid-ask spread from volatility"""
        # Estimate spread as function of volatility
        returns = df['close'].pct_change()
        rolling_vol = returns.rolling(20).std()
        
        df['estimated_spread_bps'] = rolling_vol * 10000  # Convert to basis points
        df['spread_percentile'] = df['estimated_spread_bps'].rolling(100).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5
        )
        
        return df

    def _add_ema_slopes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA slope indicators to detect trend acceleration"""
        for period in [20, 50]:
            ema_col = f'ema_{period}'
            if ema_col in df.columns:
                # Calculate slope over 3 periods (3 hours for 15m timeframe)
                df[f'{ema_col}_slope'] = df[ema_col].diff(3) / df[ema_col].shift(3)
                
                # Slope acceleration (2nd derivative)
                df[f'{ema_col}_accel'] = df[f'{ema_col}_slope'].diff(3)
        
        return df

    def _add_consolidation_zones(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect consolidation zones using Bollinger Band width"""
        if 'bb_width' in df.columns:
            bb_width = df['bb_width']
        elif 'bb_upper' in df.columns and 'bb_lower' in df.columns:
            bb_width = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_width'] = bb_width
        else:
            bb_width = pd.Series([0.05] * len(df), index=df.index)
        
        # Consolidation when BB width is in lower 30th percentile
        consolidation_threshold = bb_width.rolling(100).quantile(0.30)
        df['is_consolidation'] = (bb_width < consolidation_threshold).astype(int)
        
        # Time in consolidation
        df['consolidation_duration'] = df.groupby(
            (df['is_consolidation'] != df['is_consolidation'].shift()).cumsum()
        )['is_consolidation'].cumsum()
        
        return df

    def _add_rsi_divergence(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """Detect RSI divergences vs price"""
        if 'rsi_14' not in df.columns:
            return df
        
        rsi = df['rsi_14']
        price = df['close']
        
        # Detect higher highs in price but lower highs in RSI (bearish divergence)
        price_higher_high = (price > price.shift(window)) & (price > price.shift(1))
        rsi_lower_high = (rsi < rsi.shift(window)) & (rsi < rsi.shift(1))
        df['bearish_divergence'] = (price_higher_high & rsi_lower_high).astype(int)
        
        # Detect lower lows in price but higher lows in RSI (bullish divergence)
        price_lower_low = (price < price.shift(window)) & (price < price.shift(1))
        rsi_higher_low = (rsi > rsi.shift(window)) & (rsi > rsi.shift(1))
        df['bullish_divergence'] = (price_lower_low & rsi_higher_low).astype(int)
        
        return df
