import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Walk-forward optimization with purge and embargo to prevent data leakage.
    """

    def __init__(
        self,
        train_period_days: int = 180,
        test_period_days: int = 30,
        purge_days: int = 2,
        embargo_days: int = 1
    ):
        """
        Args:
            train_period_days: Training window size
            test_period_days: Testing (OOS) window size
            purge_days: Days to purge after train set (prevent leakage from overlapping labels)
            embargo_days: Days to embargo at start of test set (prevent lookahead bias)
        """
        self.train_period = timedelta(days=train_period_days)
        self.test_period = timedelta(days=test_period_days)
        self.purge = timedelta(days=purge_days)
        self.embargo = timedelta(days=embargo_days)

    def generate_splits(
        self,
        df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Generate walk-forward train/test splits.

        Args:
            df: DataFrame with 'timestamp' column
            start_date: Start date for walk-forward
            end_date: End date for walk-forward

        Returns:
            List of splits: [{'train': (start, end), 'test': (start, end)}, ...]
        """
        splits = []
        current_train_start = start_date

        while current_train_start + self.train_period + self.test_period <= end_date:
            # Train period
            train_start = current_train_start
            train_end = train_start + self.train_period

            # Purge period (excluded)
            purge_end = train_end + self.purge

            # Test period (with embargo at start)
            test_start = purge_end + self.embargo
            test_end = test_start + self.test_period

            if test_end > end_date:
                break

            splits.append({
                'train': (train_start, train_end),
                'test': (test_start, test_end),
                'purge': (train_end, purge_end),
                'embargo': (purge_end, test_start)
            })

            logger.debug(
                f"Split created - Train: {train_start.date()} to {train_end.date()}, "
                f"Test: {test_start.date()} to {test_end.date()}"
            )

            # Slide window forward by test period
            current_train_start = test_start

        logger.info(f"Generated {len(splits)} walk-forward splits")
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
