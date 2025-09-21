# apps/ml/risk/config.py
from __future__ import annotations
import os
from dataclasses import dataclass

def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _s(name: str, default: str) -> str:
    return os.getenv(name, default)

@dataclass
class Profile:
    name: str
    risk_per_trade: float
    max_leverage: int
    max_parallel_positions: int
    cap_per_symbol_pct: float   # % kapitału
    cap_global_pct: float       # % kapitału

@dataclass
class ExchangeCaps:
    min_notional: float
    lot_step: float
    max_leverage: int

@dataclass
class RiskEnv:
    profile_default: str
    profiles: dict[str, Profile]
    btc_eth_corr_cap_pct: float
    maker_fee_bps: float
    taker_fee_bps: float
    default_slippage_bps: float
    funding_bps_per_day: float
    exchange_caps: dict[str, ExchangeCaps]  # per-symbol domyślne (np. "BTCUSDT")

def load_env() -> RiskEnv:
    # Profile
    p_low = Profile(
        name="LOW",
        risk_per_trade=_f("RISK_LOW_RISK_PER_TRADE", 0.005),
        max_leverage=_i("RISK_LOW_MAX_LEV", 5),
        max_parallel_positions=_i("RISK_LOW_MAX_PARALLEL", 2),
        cap_per_symbol_pct=_f("RISK_LOW_CAP_PER_SYMBOL_PCT", 20.0),
        cap_global_pct=_f("RISK_LOW_CAP_GLOBAL_PCT", 40.0),
    )
    p_med = Profile(
        name="MED",
        risk_per_trade=_f("RISK_MED_RISK_PER_TRADE", 0.01),
        max_leverage=_i("RISK_MED_MAX_LEV", 10),
        max_parallel_positions=_i("RISK_MED_MAX_PARALLEL", 3),
        cap_per_symbol_pct=_f("RISK_MED_CAP_PER_SYMBOL_PCT", 30.0),
        cap_global_pct=_f("RISK_MED_CAP_GLOBAL_PCT", 60.0),
    )
    p_high = Profile(
        name="HIGH",
        risk_per_trade=_f("RISK_HIGH_RISK_PER_TRADE", 0.02),
        max_leverage=_i("RISK_HIGH_MAX_LEV", 20),
        max_parallel_positions=_i("RISK_HIGH_MAX_PARALLEL", 4),
        cap_per_symbol_pct=_f("RISK_HIGH_CAP_PER_SYMBOL_PCT", 40.0),
        cap_global_pct=_f("RISK_HIGH_CAP_GLOBAL_PCT", 80.0),
    )

    # Caps giełdowe (prosto, konfigurowalne z ENV)
    exch_default = ExchangeCaps(
        min_notional=_f("EXCH_MIN_NOTIONAL", 5.0),
        lot_step=_f("EXCH_LOT_STEP", 0.001),    # np. 0.001 BTC
        max_leverage=_i("EXCH_MAX_LEV", 50),
    )

    profile_default = _s("RISK_PROFILE_DEFAULT", "LOW").upper()
    btc_eth_corr_cap_pct = _f("RISK_BTC_ETH_CORR_CAP_PCT", 50.0)

    return RiskEnv(
        profile_default=profile_default,
        profiles={"LOW": p_low, "MED": p_med, "HIGH": p_high},
        btc_eth_corr_cap_pct=btc_eth_corr_cap_pct,
        maker_fee_bps=_f("MAKER_FEE_BPS", 1.0),     # 1 bps = 0.01%
        taker_fee_bps=_f("TAKER_FEE_BPS", 5.0),
        default_slippage_bps=_f("DEFAULT_SLIPPAGE_BPS", 5.0),
        funding_bps_per_day=_f("FUNDING_BPS_PER_DAY", 1.0),
        exchange_caps={"DEFAULT": exch_default},
    )
