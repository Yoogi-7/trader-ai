# apps/api/services/risk.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any

RiskProfile = Literal["LOW", "MED", "HIGH"]

@dataclass(frozen=True)
class RiskParams:
    risk_per_trade_pct: float   # ile % kapitału ryzykujemy na trade
    max_leverage: int
    max_parallel_positions: int
    per_symbol_cap_pct: float   # cap ekspozycji na symbol (względem kapitału)
    global_cap_pct: float       # cap ekspozycji łącznej
    slippage_bps_cap: int       # maks. poślizg dla fallback taker
    maker_first: bool           # domyślnie post-only
    default_margin_mode: str    # isolated/cross

RISK_PRESETS: Dict[RiskProfile, RiskParams] = {
    "LOW" : RiskParams( risk_per_trade_pct=0.005, max_leverage=5,  max_parallel_positions=2, per_symbol_cap_pct=0.10, global_cap_pct=0.25, slippage_bps_cap=5,  maker_first=True,  default_margin_mode="isolated"),
    "MED" : RiskParams( risk_per_trade_pct=0.010, max_leverage=10, max_parallel_positions=4, per_symbol_cap_pct=0.20, global_cap_pct=0.50, slippage_bps_cap=10, maker_first=True,  default_margin_mode="isolated"),
    "HIGH": RiskParams( risk_per_trade_pct=0.015, max_leverage=20, max_parallel_positions=6, per_symbol_cap_pct=0.30, global_cap_pct=0.75, slippage_bps_cap=15, maker_first=False, default_margin_mode="isolated"),
}

def map_profile(profile: RiskProfile) -> RiskParams:
    return RISK_PRESETS[profile]

def validate_position_open(params: RiskParams, capital_usd: float, current_open_count: int, desired_symbol_exposure: float, current_symbol_exposure: float, current_global_exposure: float) -> tuple[bool, str]:
    """Waliduje czy możemy otworzyć nową pozycję dla danego profilu i ekspozycji.
    Zwraca (ok, reason_if_not_ok)."""
    if current_open_count >= params.max_parallel_positions:
        return False, f"parallel_cap_violation: {current_open_count}/{params.max_parallel_positions}"
    if desired_symbol_exposure + current_symbol_exposure > params.per_symbol_cap_pct * capital_usd:
        return False, "symbol_cap_violation"
    if desired_symbol_exposure + current_global_exposure > params.global_cap_pct * capital_usd:
        return False, "global_cap_violation"
    return True, ""
