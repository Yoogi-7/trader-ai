# apps/ml/risk.py
# PL: Sizing, dźwignia, capy korelacyjne i globalne; estymacja likwidacji.
# EN: Position sizing, leverage caps, correlation/global caps; liquidation estimate.

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Literal, Optional, Tuple, Dict

RISK_PROFILE_LOW = float(os.getenv("RISK_PROFILE_LOW", "0.01"))
RISK_PROFILE_MED = float(os.getenv("RISK_PROFILE_MED", "0.02"))
RISK_PROFILE_HIGH = float(os.getenv("RISK_PROFILE_HIGH", "0.05"))

MAX_EXPOSURE_GLOBAL = float(os.getenv("MAX_EXPOSURE_GLOBAL", "0.3"))
MAX_EXPOSURE_PER_SYMBOL = float(os.getenv("MAX_EXPOSURE_PER_SYMBOL", "0.1"))
MAX_EXPOSURE_BTC_ETH = float(os.getenv("MAX_EXPOSURE_BTC_ETH", "0.2"))

CONFIDENCE_MIN = float(os.getenv("CONFIDENCE_MIN", "0.55"))
DEFAULT_CAPITAL = float(os.getenv("DEFAULT_CAPITAL", "100"))

MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))

LEVERAGE_CAP_LOW = float(os.getenv("LEVERAGE_CAP_LOW", "3"))
LEVERAGE_CAP_MED = float(os.getenv("LEVERAGE_CAP_MED", "5"))
LEVERAGE_CAP_HIGH = float(os.getenv("LEVERAGE_CAP_HIGH", "10"))

MIN_NOTIONAL = float(os.getenv("MIN_NOTIONAL", "5"))  # minimalny notional np. 5 USDT

@dataclass
class RiskProfile:
    risk_per_trade: float
    max_leverage: float

def profile_of(risk: Literal["LOW","MED","HIGH"]) -> RiskProfile:
    if risk == "LOW":
        return RiskProfile(RISK_PROFILE_LOW, LEVERAGE_CAP_LOW)
    if risk == "MED":
        return RiskProfile(RISK_PROFILE_MED, LEVERAGE_CAP_MED)
    return RiskProfile(RISK_PROFILE_HIGH, LEVERAGE_CAP_HIGH)

def position_size(
    capital: float,
    risk: Literal["LOW","MED","HIGH"],
    entry: float,
    sl: float,
    min_notional: float = MIN_NOTIONAL,
) -> Tuple[float, float]:
    """
    Returns (qty, risk_$). risk_$ = capital * risk_per_trade.
    qty = risk_$ / |entry - sl|
    Enforces min_notional.
    """
    rp = profile_of(risk)
    risk_dollar = max(0.0, capital * rp.risk_per_trade)
    if risk_dollar <= 0 or abs(entry - sl) <= 0:
        return 0.0, 0.0
    qty = risk_dollar / abs(entry - sl)
    # Ensure min notional
    if entry * qty < min_notional:
        qty = min_notional / entry
    return float(qty), float(risk_dollar)

def leverage_for(
    desired_leverage: float,
    risk: Literal["LOW","MED","HIGH"],
) -> float:
    cap = profile_of(risk).max_leverage
    return float(min(desired_leverage, cap))

def estimate_liquidation_price(
    direction: Literal["LONG","SHORT"],
    entry: float,
    lev: float,
    maintenance_margin_frac: float = 0.005,
) -> float:
    """
    Very rough estimate for USDT-margined perp with isolated margin.
    LONG liq approx: entry * (1 - (1/lev) + mm)
    SHORT liq approx: entry * (1 + (1/lev) - mm)
    """
    if lev <= 1.0:
        return 0.0
    mm = maintenance_margin_frac
    if direction == "LONG":
        return float(entry * max(0.0, 1.0 - (1.0 / lev) + mm))
    else:
        return float(entry * (1.0 + (1.0 / lev) - mm))

# ---- Exposure / Correlation caps ----

def symbol_bucket(symbol: str) -> str:
    # group major correlations (e.g., BTC, ETH)
    if symbol.upper().startswith("BTC"):
        return "BTC"
    if symbol.upper().startswith("ETH"):
        return "ETH"
    return "ALT"

def check_caps(
    open_exposures: Dict[str, float],  # symbol -> fraction of capital
    new_exposure_frac: float,
    symbol: str,
    capital: float,
) -> Optional[str]:
    """
    Returns reason if cap violated, else None.
    """
    # Per symbol cap
    per_sym = open_exposures.get(symbol, 0.0) + new_exposure_frac
    if per_sym > MAX_EXPOSURE_PER_SYMBOL:
        return f"cap_per_symbol_exceeded ({per_sym:.2%} > {MAX_EXPOSURE_PER_SYMBOL:.2%})"

    # Global cap
    total = sum(open_exposures.values()) + new_exposure_frac
    if total > MAX_EXPOSURE_GLOBAL:
        return f"cap_global_exceeded ({total:.2%} > {MAX_EXPOSURE_GLOBAL:.2%})"

    # BTC+ETH combined
    bucket = symbol_bucket(symbol)
    btc_eth = 0.0
    for s, v in open_exposures.items():
        if symbol_bucket(s) in ("BTC","ETH"):
            btc_eth += v
    if bucket in ("BTC","ETH"):
        btc_eth += new_exposure_frac
    if btc_eth > MAX_EXPOSURE_BTC_ETH:
        return f"cap_btc_eth_exceeded ({btc_eth:.2%} > {MAX_EXPOSURE_BTC_ETH:.2%})"

    # OK
    return None
