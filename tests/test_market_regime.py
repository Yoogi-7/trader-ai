from apps.ml.market_regime import (
    detect_market_regime,
    REGIME_TREND_UP,
    REGIME_TREND_DOWN,
    REGIME_SIDEWAYS,
    REGIME_HIGH_VOL,
)


def test_detect_high_volatility():
    ctx = {"1h_slope": 0.0, "4h_slope": 0.0}
    regime = detect_market_regime(close=100.0, atr=8.0, ctx=ctx)
    assert regime == REGIME_HIGH_VOL


def test_detect_trend_up():
    ctx = {"1h_slope": 2.0, "4h_slope": 1.5}
    regime = detect_market_regime(close=100.0, atr=1.0, ctx=ctx)
    assert regime == REGIME_TREND_UP


def test_detect_trend_down():
    ctx = {"1h_slope": -2.0, "4h_slope": -1.0}
    regime = detect_market_regime(close=100.0, atr=1.0, ctx=ctx)
    assert regime == REGIME_TREND_DOWN


def test_detect_sideways_default():
    ctx = {"1h_slope": 0.00005, "4h_slope": -0.00004}
    regime = detect_market_regime(close=100.0, atr=1.0, ctx=ctx)
    assert regime == REGIME_SIDEWAYS
