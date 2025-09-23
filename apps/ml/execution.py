# apps/ml/execution.py
# PL: Warstwa egzekucji "maker-first": post-only -> jeśli nie fill, fallback taker z capem slippage.
# EN: Execution layer "maker-first": post-only -> fallback taker with slippage cap (simulated).

from __future__ import annotations
import os
from typing import Literal, Tuple

from apps.ml.costs import FEE_MAKER, FEE_TAKER, bps_to_frac

SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "10"))
MAX_SLIPPAGE_BPS = float(os.getenv("MAX_SLIPPAGE_BPS", "20"))  # cap for taker fallback

def maker_first_fill(entry_px: float, book_best_px: float, direction: Literal["LONG","SHORT"]) -> Tuple[bool, float, str]:
    """
    Simulate whether post-only would be filled at/near entry price:
    - If LONG and entry >= best ask => maker fill unlikely; require price retrace; we simulate not filled.
    - For simplicity, we assume maker order does NOT fill immediately; returns (False, entry_px, "maker_placed").
    """
    return (False, entry_px, "maker_placed")

def fallback_taker(entry_px: float, direction: Literal["LONG","SHORT"]) -> Tuple[float, float, str]:
    """
    Simulate taker fill with slippage limited by MAX_SLIPPAGE_BPS.
    Return (fill_px, slip_cost_frac, tag)
    """
    slip_frac = min(bps_to_frac(SLIPPAGE_BPS), bps_to_frac(MAX_SLIPPAGE_BPS))
    if direction == "LONG":
        fill_px = entry_px * (1.0 + slip_frac)
    else:
        fill_px = entry_px * (1.0 - slip_frac)
    return fill_px, slip_frac, "taker_fallback"
