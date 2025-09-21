# apps/ml/risk/engine.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List

from apps.ml.risk.config import load_env, RiskEnv, Profile, ExchangeCaps

@dataclass
class SizingResult:
    qty: float
    leverage: int
    exposure_usd: float
    liquidation_est: Optional[float]
    reason_block: Optional[str] = None

def _round_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.floor(x / step) * step

def select_profile(env: RiskEnv, name: Optional[str]) -> Profile:
    key = (name or env.profile_default or "LOW").upper()
    return env.profiles.get(key, env.profiles["LOW"])

def select_leverage(env: RiskEnv, profile: Profile, requested: Optional[int]) -> int:
    req = int(requested or profile.max_leverage)
    return max(1, min(req, profile.max_leverage))

def _exchange_caps(env: RiskEnv, symbol: str) -> ExchangeCaps:
    return env.exchange_caps.get(symbol, env.exchange_caps["DEFAULT"])

def estimate_liquidation_price(side: str, entry: float, lev: int, maintenance_margin_ratio: float = 0.005) -> float:
    """
    Bardzo uproszczona estymacja likwidacji dla USDT-margined perp:
      - przy wysokim lev i niskim MM, cena likwidacji ~ entry * (1 -/+ 1/lev) z bufforem MM
    """
    lev = max(1, lev)
    if side.lower() == "long":
        return entry * (1.0 - (1.0 / lev) - maintenance_margin_ratio)
    else:
        return entry * (1.0 + (1.0 / lev) + maintenance_margin_ratio)

def expected_net_gain_pct(entry: float, tp1: float, *,
                          maker_first: bool,
                          maker_fee_bps: float,
                          taker_fee_bps: float,
                          slippage_bps: float,
                          funding_bps_per_day: float,
                          expected_holding_hours: float = 8.0) -> float:
    gross = (tp1 - entry) / entry
    # koszty: wejście + wyjście
    fee_bps = maker_fee_bps if maker_first else taker_fee_bps
    fees = 2.0 * (fee_bps / 10000.0)
    slippage = (slippage_bps / 10000.0)
    funding = (funding_bps_per_day / 10000.0) * (expected_holding_hours / 24.0)
    net = gross - fees - slippage - funding
    return net

def apply_caps_and_sizing(
    *,
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    capital_usd: float,
    profile_name: Optional[str],
    existing_parallel_positions: int,
    current_exposure_by_symbol: Dict[str, float],
    requested_leverage: Optional[int] = None,
) -> SizingResult:
    """
    Zwraca SizingResult z powodem blokady (reason_block) jeśli naruszamy limity.
    """
    env = load_env()
    prof = select_profile(env, profile_name)
    exch = _exchange_caps(env, symbol)
    lev = select_leverage(env, prof, requested_leverage)
    lev = min(lev, exch.max_leverage)

    # limit równoległych pozycji
    if existing_parallel_positions >= prof.max_parallel_positions:
        return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=None,
                            reason_block="too_many_parallel_positions")

    # podstawowy sizing po ryzyku
    risk_cash = capital_usd * prof.risk_per_trade
    dist = max(1e-9, abs(entry - sl))
    qty = (risk_cash / dist) * lev / entry  # qty w jednostce base (np. BTC)
    qty = _round_step(qty, exch.lot_step)

    exposure = qty * entry
    # cap per symbol
    cap_sym = prof.cap_per_symbol_pct / 100.0 * capital_usd
    if exposure > cap_sym:
        # obetnij do capu
        qty_cap = _round_step(cap_sym / entry, exch.lot_step)
        exposure = qty_cap * entry
        qty = qty_cap

    # cap global (z istniejącą ekspozycją)
    total_existing = sum(abs(v) for v in current_exposure_by_symbol.values())
    cap_global = prof.cap_global_pct / 100.0 * capital_usd
    if total_existing + exposure > cap_global:
        return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=None,
                            reason_block="global_exposure_cap")

    # korelacyjny cap BTC/ETH razem
    if symbol.upper() in ("BTCUSDT", "ETHUSDT"):
        btc = abs(current_exposure_by_symbol.get("BTCUSDT", 0.0))
        eth = abs(current_exposure_by_symbol.get("ETHUSDT", 0.0))
        new_btc = btc + (exposure if symbol.upper() == "BTCUSDT" else 0.0)
        new_eth = eth + (exposure if symbol.upper() == "ETHUSDT" else 0.0)
        if (new_btc + new_eth) > (env.btc_eth_corr_cap_pct / 100.0) * capital_usd:
            return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=None,
                                reason_block="btc_eth_corr_cap")

    # min notional
    if exposure < exch.min_notional:
        return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=None,
                            reason_block="below_min_notional")

    liq = estimate_liquidation_price(side, entry, lev)
    # sanity: likwidacja „daleko” od SL
    if side.lower() == "long":
        if liq >= sl:
            return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=liq,
                                reason_block="liq_too_close_to_sl")
    else:
        if liq <= sl:
            return SizingResult(qty=0.0, leverage=lev, exposure_usd=0.0, liquidation_est=liq,
                                reason_block="liq_too_close_to_sl")

    return SizingResult(qty=qty, leverage=lev, exposure_usd=exposure, liquidation_est=liq)

def quality_filter_2pct(
    entry: float, tp1: float, *, maker_first: bool, holding_hours: float = 8.0
) -> Tuple[bool, float]:
    env = load_env()
    net = expected_net_gain_pct(
        entry, tp1,
        maker_first=maker_first,
        maker_fee_bps=env.maker_fee_bps,
        taker_fee_bps=env.taker_fee_bps,
        slippage_bps=env.default_slippage_bps,
        funding_bps_per_day=env.funding_bps_per_day,
        expected_holding_hours=holding_hours,
    )
    return (net >= 0.02), net * 100.0
