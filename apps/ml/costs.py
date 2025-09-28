# apps/ml/costs.py
# PL: Kalkulacja kosztów (fee, slippage, funding) i netto P&L oczekiwanego sygnału.
# EN: Costs calculation (fee, slippage, funding) and expected net P&L.

from __future__ import annotations
import os
from typing import Literal

FEE_MAKER = float(os.getenv("FEE_MAKER", "0.0002"))
FEE_TAKER = float(os.getenv("FEE_TAKER", "0.0005"))
SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "10"))  # 10 bps = 0.1%
FUNDING_ON = os.getenv("FUNDING_ON", "1") == "1"

def bps_to_frac(bps: float) -> float:
    return bps / 10_000.0

def side_mult(direction: Literal["LONG","SHORT"]) -> int:
    return 1 if direction == "LONG" else -1

def est_entry_cost(entry_px: float, qty: float, maker_first: bool, fill_mode: Literal["maker","taker","mixed"] = "maker") -> float:
    """
    Return absolute cost in quote currency (USDT), fee only (no slippage).
    """
    fee_rate = FEE_MAKER if maker_first and fill_mode != "taker" else FEE_TAKER
    notional = entry_px * qty
    return notional * fee_rate

def est_slippage_cost(entry_px: float, qty: float, fallback_taker: bool) -> float:
    if not fallback_taker:
        return 0.0
    slip = bps_to_frac(SLIPPAGE_BPS)  # fraction
    return entry_px * qty * slip

def est_funding_cost(entry_px: float, qty: float, holding_minutes: float, funding_rate_hourly: float = 0.0) -> float:
    """
    Funding simplified: hourly rate * hours held * notional.
    If FUNDING_ON=0 -> returns 0.
    """
    if not FUNDING_ON or funding_rate_hourly == 0.0:
        return 0.0
    hours = max(0.0, holding_minutes / 60.0)
    notional = entry_px * qty
    return notional * funding_rate_hourly * hours

def expected_net_pct(
    direction: Literal["LONG","SHORT"],
    entry: float,
    tp_targets: list[float],
    sl: float,
    qty: float,
    maker_first: bool,
    fallback_taker: bool,
    funding_minutes: float = 0.0,
    funding_rate_hourly: float = 0.0,
    tp_split: tuple[float,float,float] = (0.3,0.4,0.3),
) -> float:
    """
    PL: Szacuje oczekiwany % zysku netto względem zainwestowanego kapitału (margin).
    EN: Estimates expected net % return vs capital (margin).
    """
    if len(tp_targets) == 0:
        return -1.0
    # Notional P&L (before costs):
    # Assume TP probabilities ~ split weights (conservative).
    w1, w2, w3 = tp_split
    dir_mult = side_mult(direction)
    pnl_tp = 0.0
    for w, tp in zip([w1, w2, w3], tp_targets + [tp_targets[-1]] * (3 - len(tp_targets))):
        pnl_tp += w * ((tp - entry) * dir_mult) * qty
    # SL leg (conservative small weight of 1 - sum(wi) -> already 1.0 total; we don't add explicit SL prob)
    # Costs:
    fee_open = est_entry_cost(entry, qty, maker_first, "maker" if maker_first else "taker")
    slip_cost = est_slippage_cost(entry, qty, fallback_taker)
    fund_cost = est_funding_cost(entry, qty, funding_minutes, funding_rate_hourly)
    costs = fee_open + slip_cost + fund_cost
    # Margin proxy: we treat "risk $" as invested capital (qty * |entry - sl|)
    margin = qty * abs(entry - sl)
    if margin <= 0:
        return -1.0
    net_pct = (pnl_tp - costs) / margin
    return float(net_pct)
