import pandas as pd
import numpy as np
from typing import Tuple


class TripleBarrierLabeling:
    """
    Triple barrier method for labeling trading data.
    Labels outcomes based on which barrier (TP, SL, or Time) is hit first.
    """

    def __init__(
        self,
        tp_pct: float = 0.02,
        sl_pct: float = 0.01,
        time_bars: int = 24
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

    def label_data(self, df: pd.DataFrame, side: str = 'long') -> pd.DataFrame:
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

        for i in range(len(df) - self.time_bars):
            entry_price = df.iloc[i]['close']

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
