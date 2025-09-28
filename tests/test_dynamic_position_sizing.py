import math

from apps.ml.risk import dynamic_risk_fraction


def test_dynamic_fraction_boosts_when_low_vol():
    base = 0.01
    frac = dynamic_risk_fraction(base, volatility_ratio=0.002)
    assert frac > base
    assert math.isclose(frac, min(frac, base * 1.5))


def test_dynamic_fraction_reduces_when_high_vol():
    base = 0.02
    frac = dynamic_risk_fraction(base, volatility_ratio=0.08)
    assert frac < base
    assert frac >= base * 0.25  # floor enforced


def test_dynamic_fraction_respects_max():
    base = 0.015
    frac = dynamic_risk_fraction(base, volatility_ratio=0.003, max_portfolio_fraction=0.01)
    assert math.isclose(frac, 0.01)
