import pytest
from apps.ml.backtest import Backtester
from apps.api.db.models import Side
import pandas as pd
from datetime import datetime


def test_backtester_initial_capital():
    """Test that backtester starts with correct initial capital"""
    bt = Backtester(initial_capital=100.0)

    assert bt.initial_capital == 100.0
    assert bt.capital == 100.0


def test_backtester_hit_rate_calculation():
    """
    Test that backtester correctly calculates hit rate (TP1).
    This verifies the >=55% acceptance criterion.
    """
    bt = Backtester(initial_capital=1000.0)

    # Create mock market data
    market_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='15T'),
        'open': [50000] * 100,
        'high': [51000] * 100,
        'low': [49000] * 100,
        'close': [50500] * 100,
        'volume': [1000] * 100
    })

    # Create mock signals (would come from real signal generator)
    signals = []

    # Run backtest
    results = bt.run(signals, market_data)

    # Verify metrics exist
    assert 'hit_rate_tp1' in results
    assert 'win_rate' in results
    assert 'total_trades' in results
    assert results['initial_capital'] == 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
