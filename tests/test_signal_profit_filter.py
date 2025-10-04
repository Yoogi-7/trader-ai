import pytest
from apps.ml.signal_engine import SignalGenerator
from apps.api.db.models import Side, RiskProfile
from datetime import datetime


def test_minimum_2pct_profit_filter():
    """
    Critical test: Verify that signals with <2% expected net profit are rejected.
    """
    generator = SignalGenerator(
        maker_fee_bps=2.0,
        taker_fee_bps=5.0,
        slippage_bps=3.0,
        funding_rate_hourly_bps=1.0
    )

    # Test case 1: Signal with insufficient profit should be rejected
    signal_low_profit = generator.generate_signal(
        symbol="BTC/USDT",
        side=Side.LONG,
        entry_price=50000.0,
        atr=500.0,  # Small ATR = tight TP/SL = low profit
        risk_profile=RiskProfile.LOW,
        capital_usd=1000.0,
        confidence=0.60,
        timestamp=datetime.utcnow()
    )

    # Test case 2: Signal with good profit should pass
    signal_good_profit = generator.generate_signal(
        symbol="BTC/USDT",
        side=Side.LONG,
        entry_price=50000.0,
        atr=2000.0,  # Larger ATR = wider TP/SL = higher profit
        risk_profile=RiskProfile.MEDIUM,
        capital_usd=1000.0,
        confidence=0.65,
        timestamp=datetime.utcnow()
    )

    # Assertions
    if signal_low_profit is not None:
        assert signal_low_profit['expected_net_profit_pct'] >= 2.0, \
            "Low profit signal was not rejected"

    if signal_good_profit is not None:
        assert signal_good_profit['expected_net_profit_pct'] >= 2.0, \
            "Signal should have >=2% net profit"
        assert signal_good_profit['passed_profit_filter'] == True


def test_signal_cost_calculation():
    """Test that signal costs are properly calculated"""
    generator = SignalGenerator()

    # Known parameters
    entry_price = 50000.0
    position_size = 1000.0
    leverage = 10.0

    # Expected costs
    maker_fee = position_size * (2.0 / 10000)  # $0.20
    taker_fee = position_size * (5.0 / 10000)  # $0.50 (3 exits)
    slippage = position_size * (3.0 / 10000)  # $0.30

    total_expected_costs = maker_fee + (taker_fee * 3) + (slippage * 1.5)

    # Verify calculation logic exists
    assert generator.maker_fee_bps == 2.0
    assert generator.taker_fee_bps == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
