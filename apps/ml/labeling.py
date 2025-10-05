import pandas as pd
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class TripleBarrierLabeling:
    """
    Triple barrier method for labeling trading data.
    Labels outcomes based on which barrier (TP, SL, or Time) is hit first.
    """

    def __init__(
        self,
        tp_pct: float = 0.02,
        sl_pct: float = 0.01,
        time_bars: int = 24,
        use_atr: bool = False,
        atr_column: str = 'atr_14',
        tp_atr_multiplier: float = 1.0,
        sl_atr_multiplier: float = 1.5
    ):
        """
        Args:
            tp_pct: Take profit threshold (e.g., 0.02 = 2%)
            sl_pct: Stop loss threshold (e.g., 0.01 = 1%)
            time_bars: Maximum holding period in bars
        """
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.time_bars = time_bars
        self.use_atr = use_atr
        self.atr_column = atr_column
        self.tp_atr_multiplier = tp_atr_multiplier
        self.sl_atr_multiplier = sl_atr_multiplier

    def label_data(self, df: pd.DataFrame, side: str = 'long', progress_callback=None) -> pd.DataFrame:
        """
        Apply triple barrier labeling to OHLCV data.

        Args:
            df: DataFrame with OHLCV data
            side: 'long' or 'short'

        Returns:
            DataFrame with labels: hit_barrier, bars_to_hit, return_pct
        """
        df = df.copy()
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)

        total_rows = max(len(df) - self.time_bars, 0)
        logger.info(f"Computing triple barrier labels for {total_rows} rows...")

        if total_rows == 0:
            logger.warning("Not enough rows to apply triple barrier labeling")
            return pd.DataFrame(columns=[
                'timestamp',
                'side',
                'tp_barrier',
                'sl_barrier',
                'time_barrier',
                'hit_barrier',
                'bars_to_hit',
                'return_pct'
            ])

        timestamps = df['timestamp'].to_numpy()
        close = df['close'].to_numpy()
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        atr = None

        if self.use_atr and self.atr_column in df.columns:
            atr = df[self.atr_column].to_numpy()

        labels = []
        time_bars = self.time_bars
        log_interval = max(1, total_rows // 10)

        for i in range(total_rows):
            if i > 0 and i % log_interval == 0:
                progress = (i / total_rows) * 100
                logger.info(f"Labeling progress: {progress:.1f}% ({i}/{total_rows})")
                if progress_callback:
                    progress_callback(progress)

            entry_price = close[i]

            atr_value = None
            if atr is not None:
                atr_value = atr[i]
                if pd.isna(atr_value) or atr_value <= 0:
                    atr_value = None

            if atr_value is not None:
                if side == 'long':
                    tp_price = entry_price + (atr_value * self.tp_atr_multiplier)
                    sl_price = entry_price - (atr_value * self.sl_atr_multiplier)
                else:
                    tp_price = entry_price - (atr_value * self.tp_atr_multiplier)
                    sl_price = entry_price + (atr_value * self.sl_atr_multiplier)
            else:
                if side == 'long':
                    tp_price = entry_price * (1 + self.tp_pct)
                    sl_price = entry_price * (1 - self.sl_pct)
                else:
                    tp_price = entry_price * (1 - self.tp_pct)
                    sl_price = entry_price * (1 + self.sl_pct)

            future_slice = slice(i + 1, i + 1 + time_bars)
            future_high = high[future_slice]
            future_low = low[future_slice]

            hit_barrier = 'time'
            bars_to_hit = time_bars
            exit_price = close[i + time_bars]

            if side == 'long':
                tp_hits = np.where(future_high >= tp_price)[0]
                sl_hits = np.where(future_low <= sl_price)[0]
            else:
                tp_hits = np.where(future_low <= tp_price)[0]
                sl_hits = np.where(future_high >= sl_price)[0]

            first_tp = tp_hits[0] + 1 if tp_hits.size else None
            first_sl = sl_hits[0] + 1 if sl_hits.size else None

            if first_tp is not None and (first_sl is None or first_tp <= first_sl):
                hit_barrier = 'tp'
                bars_to_hit = first_tp
                exit_price = tp_price
            elif first_sl is not None:
                hit_barrier = 'sl'
                bars_to_hit = first_sl
                exit_price = sl_price

            if side == 'long':
                return_pct = (exit_price - entry_price) / entry_price
            else:
                return_pct = (entry_price - exit_price) / entry_price

            labels.append({
                'timestamp': timestamps[i],
                'side': side,
                'tp_barrier': tp_price,
                'sl_barrier': sl_price,
                'time_barrier': time_bars,
                'hit_barrier': hit_barrier,
                'bars_to_hit': bars_to_hit,
                'return_pct': return_pct
            })

        # Call progress callback with 100% when labeling is complete
        if progress_callback:
            progress_callback(100.0)

        logger.info(f"Labeling complete: {len(labels)} labels created")
        return pd.DataFrame(labels)

    def create_binary_labels(self, labels_df: pd.DataFrame) -> pd.Series:
        """
        Create binary labels: 1 if TP hit, 0 otherwise.
        Used for classification models.
        """
        return (labels_df['hit_barrier'] == 'tp').astype(int)

    def create_meta_labels(self, labels_df: pd.DataFrame, primary_signals: pd.Series) -> pd.Series:
        """
        Meta-labeling: Given a primary signal (direction), should we take the trade?
        Returns 1 if the trade would be profitable, 0 otherwise.
        """
        profitable = labels_df['return_pct'] > 0
        return (profitable & primary_signals).astype(int)
