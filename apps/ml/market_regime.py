"""Market regime detection heuristics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

REGIME_TREND_UP = "trend_wzrostowy"
REGIME_TREND_DOWN = "trend_spadkowy"
REGIME_SIDEWAYS = "boczniak"
REGIME_HIGH_VOL = "wysoka_zmiennosc"

@dataclass(frozen=True)
class RegimeConfig:
    slope_threshold: float = 0.0  # in price units per bar
    slope_bias: float = 0.0
    high_vol_threshold: float = 0.04  # ATR/price ratio
    elevated_vol_threshold: float = 0.025

DEFAULT_CONFIG = RegimeConfig(
    slope_threshold=0.0001,
    slope_bias=0.0,
    high_vol_threshold=0.05,
    elevated_vol_threshold=0.03,
)


def _avg(values: Dict[str, float], keys: tuple[str, ...]) -> float:
    present = [float(values[k]) for k in keys if values.get(k) is not None]
    return sum(present) / len(present) if present else 0.0


def detect_market_regime(
    close: float,
    atr: float,
    ctx: Dict[str, float],
    *,
    config: RegimeConfig = DEFAULT_CONFIG,
) -> str:
    """Return human-readable market regime label."""
    vol_ratio = abs(atr / close) if close else 0.0
    if vol_ratio >= config.high_vol_threshold:
        return REGIME_HIGH_VOL

    slope_avg = _avg(ctx, ("1h_slope", "4h_slope"))
    slope_1h = float(ctx.get("1h_slope", 0.0))
    slope_4h = float(ctx.get("4h_slope", 0.0))
    slope_weighted = 0.6 * slope_1h + 0.4 * slope_4h
    slope_effective = slope_weighted + config.slope_bias

    baseline = abs(close) * 1e-5 if close else 1e-6
    threshold = max(1e-8, config.slope_threshold or baseline)

    if slope_effective > threshold:
        return REGIME_TREND_UP
    if slope_effective < -threshold:
        return REGIME_TREND_DOWN

    if vol_ratio >= config.elevated_vol_threshold:
        return REGIME_HIGH_VOL

    return REGIME_SIDEWAYS
