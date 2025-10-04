import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Walk-forward optimization with expanding windows and purge/embargo to prevent data leakage.

    Uses expanding windows: each split trains on ALL historical data up to that point,
    rather than a fixed-size sliding window.
    """

    def __init__(
        self,
        test_period_days: int = 30,
        min_train_days: int = 180,
        purge_days: int = 2,
        embargo_days: int = 1,
        use_expanding_window: bool = True
    ):
        """
        Args:
            test_period_days: Testing (OOS) window size
            min_train_days: Minimum training data required for first split
            purge_days: Days to purge after train set (prevent leakage from overlapping labels)
            embargo_days: Days to embargo at start of test set (prevent lookahead bias)
            use_expanding_window: If True, use expanding windows (train on all history).
                                 If False, use sliding windows (fixed train size)
        """
        self.test_period = timedelta(days=test_period_days)
        self.min_train_period = timedelta(days=min_train_days)
        self.purge = timedelta(days=purge_days)
        self.embargo = timedelta(days=embargo_days)
        self.use_expanding_window = use_expanding_window

    def generate_splits(
        self,
        df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Generate walk-forward train/test splits with expanding or sliding windows.

        Args:
            df: DataFrame with 'timestamp' column
            start_date: Start date for walk-forward (earliest available data)
            end_date: End date for walk-forward (latest available data)

        Returns:
            List of splits: [{'train': (start, end), 'test': (start, end)}, ...]
        """
        splits = []

        # First split: train from start_date to (start + min_train_period)
        # Then test on next test_period
        current_test_start = start_date + self.min_train_period + self.purge + self.embargo

        while current_test_start + self.test_period <= end_date:
            if self.use_expanding_window:
                # EXPANDING WINDOW: Train on ALL data from start to current point
                train_start = start_date
                train_end = current_test_start - self.purge - self.embargo
            else:
                # SLIDING WINDOW: Fixed-size training window
                train_end = current_test_start - self.purge - self.embargo
                train_start = max(start_date, train_end - self.min_train_period)

            # Purge period (excluded)
            purge_start = train_end
            purge_end = purge_start + self.purge

            # Embargo period (excluded)
            embargo_start = purge_end
            embargo_end = embargo_start + self.embargo

            # Test period
            test_start = embargo_end
            test_end = test_start + self.test_period

            if test_end > end_date:
                break

            # Verify we have minimum training data
            train_days = (train_end - train_start).days
            if train_days < self.min_train_period.days:
                logger.warning(
                    f"Insufficient training data: {train_days} days < {self.min_train_period.days} days required"
                )
                current_test_start += self.test_period
                continue

            splits.append({
                'train': (train_start, train_end),
                'test': (test_start, test_end),
                'purge': (purge_start, purge_end),
                'embargo': (embargo_start, embargo_end),
                'train_days': train_days
            })

            window_type = "expanding" if self.use_expanding_window else "sliding"
            logger.debug(
                f"Split created ({window_type}) - "
                f"Train: {train_start.date()} to {train_end.date()} ({train_days} days), "
                f"Test: {test_start.date()} to {test_end.date()}"
            )

            # Move forward by test period
            current_test_start += self.test_period

        logger.info(
            f"Generated {len(splits)} walk-forward splits "
            f"({'expanding' if self.use_expanding_window else 'sliding'} windows)"
        )
        return splits

    def get_train_test_data(
        self,
        df: pd.DataFrame,
        split: Dict
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract train and test data for a given split.

        Args:
            df: Full DataFrame with 'timestamp' column
            split: Split dict from generate_splits

        Returns:
            (train_df, test_df)
        """
        train_start, train_end = split['train']
        test_start, test_end = split['test']

        train_df = df[
            (df['timestamp'] >= train_start) &
            (df['timestamp'] < train_end)
        ].copy()

        test_df = df[
            (df['timestamp'] >= test_start) &
            (df['timestamp'] < test_end)
        ].copy()

        return train_df, test_df

    def validate_no_leakage(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> bool:
        """
        Validate that there's no temporal overlap between train and test.

        Returns:
            True if no leakage, False otherwise
        """
        if train_df.empty or test_df.empty:
            return True

        train_max = train_df['timestamp'].max()
        test_min = test_df['timestamp'].min()

        gap = test_min - train_max

        if gap < self.purge + self.embargo:
            logger.error(
                f"Leakage detected! Gap between train and test: {gap}, "
                f"required: {self.purge + self.embargo}"
            )
            return False

        return True
