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
        labels = []

        total_rows = len(df) - self.time_bars
        logger.info(f"Computing triple barrier labels for {total_rows} rows...")

        # Log progress every 10%
        log_interval = max(1, total_rows // 10)

        for i in range(total_rows):
            # Log progress
            if i > 0 and i % log_interval == 0:
                progress = (i / total_rows) * 100
                logger.info(f"Labeling progress: {progress:.1f}% ({i}/{total_rows})")

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(progress)

            entry_price = df.iloc[i]['close']

            atr_value = None
            if self.use_atr and self.atr_column in df.columns:
                atr_value = df.iloc[i][self.atr_column]
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
                else:  # short
                    tp_price = entry_price * (1 - self.tp_pct)
                    sl_price = entry_price * (1 + self.sl_pct)

            # Look forward to find which barrier is hit first
            hit_barrier = 'time'
            bars_to_hit = self.time_bars
            exit_price = df.iloc[i + self.time_bars]['close']

            for j in range(1, self.time_bars + 1):
                if i + j >= len(df):
                    break

                high = df.iloc[i + j]['high']
                low = df.iloc[i + j]['low']

                if side == 'long':
                    if high >= tp_price:
                        hit_barrier = 'tp'
                        bars_to_hit = j
                        exit_price = tp_price
                        break
                    elif low <= sl_price:
                        hit_barrier = 'sl'
                        bars_to_hit = j
                        exit_price = sl_price
                        break
                else:  # short
                    if low <= tp_price:
                        hit_barrier = 'tp'
                        bars_to_hit = j
                        exit_price = tp_price
                        break
                    elif high >= sl_price:
                        hit_barrier = 'sl'
                        bars_to_hit = j
                        exit_price = sl_price
                        break

            # Calculate return
            if side == 'long':
                return_pct = (exit_price - entry_price) / entry_price
            else:
                return_pct = (entry_price - exit_price) / entry_price

            labels.append({
                'timestamp': df.iloc[i]['timestamp'],
                'side': side,
                'tp_barrier': tp_price,
                'sl_barrier': sl_price,
                'time_barrier': self.time_bars,
                'hit_barrier': hit_barrier,
                'bars_to_hit': bars_to_hit,
                'return_pct': return_pct
            })

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
