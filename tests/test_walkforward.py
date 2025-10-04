import pytest
import pandas as pd
from apps.ml.walkforward import WalkForwardValidator
from datetime import datetime, timedelta


def test_walkforward_no_leakage():
    """
    Test that walk-forward splits have proper purge and embargo to prevent data leakage.
    """
    validator = WalkForwardValidator(
        train_period_days=180,
        test_period_days=30,
        purge_days=2,
        embargo_days=1
    )

    # Create sample data
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2021, 1, 1)

    dates = pd.date_range(start_date, end_date, freq='1H')
    df = pd.DataFrame({'timestamp': dates})

    # Generate splits
    splits = validator.generate_splits(df, start_date, end_date)

    assert len(splits) > 0, "Should generate at least one split"

    # Verify purge and embargo gaps
    for split in splits:
        train_end = split['train'][1]
        test_start = split['test'][0]

        gap = test_start - train_end
        expected_gap = timedelta(days=2 + 1)  # purge + embargo

        assert gap >= expected_gap, f"Insufficient gap between train and test: {gap}"


def test_walkforward_split_validation():
    """Test that train/test data doesn't overlap"""
    validator = WalkForwardValidator()

    # Create train and test dataframes
    train_df = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', '2020-06-30', freq='1H')
    })

    test_df = pd.DataFrame({
        'timestamp': pd.date_range('2020-07-03', '2020-08-02', freq='1H')
    })

    # Validate no leakage
    no_leakage = validator.validate_no_leakage(train_df, test_df)

    assert no_leakage == True, "Train and test data should not overlap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
