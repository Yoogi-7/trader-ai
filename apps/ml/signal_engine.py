# apps/ml/signal_engine.py
# PL: Generator sygnałów: Entry/TP1-3/SL (ATR/Fibo/S/R), trailing po TP1, time-stop, re-entry.
# EN: Signal generator: Entry/TP1-3/SL (ATR/Fibo/S/R), trailing after TP1, time-stop, re-entry.

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any, List

@dataclass
class Levels:
    entry: float
    tp: list[float]    # up to 3
    sl: float

@dataclass
class SignalProposal:
    symbol: str
    tf_base: str
    ts: int
    direction: Literal["LONG","SHORT"]
    levels: Levels
    lev: float
    risk: Literal["LOW","MED","HIGH"]
    margin_mode: Literal["ISOLATED","CROSS"]
    validity_min: int          # time-stop in minutes
    reentry_max: int           # allowed conditional re-entries
    trailing_after_tp1: bool
    meta: Dict[str, Any]

def atr_based_levels(close: float, atr: float, direction: Literal["LONG","SHORT"]) -> Levels:
    # Simple ATR-multiple strategy
    k_entry = 0.0          # enter at market (or post-only near last)
    k_tp1 = 1.5
    k_tp2 = 2.5
    k_tp3 = 3.5
    k_sl  = 1.0
    if direction == "LONG":
        entry = close + k_entry * atr
        return Levels(entry=entry, tp=[entry + k_tp1*atr, entry + k_tp2*atr, entry + k_tp3*atr], sl=entry - k_sl*atr)
    else:
        entry = close - k_entry * atr
        return Levels(entry=entry, tp=[entry - k_tp1*atr, entry - k_tp2*atr, entry - k_tp3*atr], sl=entry + k_sl*atr)

def fib_pivot_adjust(levels: Levels, fib_levels: Dict[str, float]) -> Levels:
    # Nudge TPs to nearby fib lines to increase confluence.
    def nearest(val: float, candidates: List[float]) -> float:
        if not candidates:
            return val
        return min(candidates, key=lambda x: abs(x - val))
    fibs = [v for k, v in fib_levels.items() if k.startswith("fibo_")]
    if fibs:
        levels.tp = [nearest(tp, fibs) for tp in levels.tp]
    return levels

def build_proposal(
    symbol: str,
    tf_base: str,
    ts: int,
    direction: Literal["LONG","SHORT"],
    close: float,
    atr_val: float,
    fib_levels: Dict[str, float] | None,
    lev: float,
    risk: Literal["LOW","MED","HIGH"],
    margin_mode: Literal["ISOLATED","CROSS"] = "ISOLATED",
    validity_min: int = 240,
    reentry_max: int = 1,
    trailing_after_tp1: bool = True,
) -> SignalProposal:
    levels = atr_based_levels(close, atr_val, direction)
    if fib_levels:
        levels = fib_pivot_adjust(levels, fib_levels)
    return SignalProposal(
        symbol=symbol,
        tf_base=tf_base,
        ts=ts,
        direction=direction,
        levels=levels,
        lev=lev,
        risk=risk,
        margin_mode=margin_mode,
        validity_min=validity_min,
        reentry_max=reentry_max,
        trailing_after_tp1=trailing_after_tp1,
        meta={"source": "atr+fibo", "atr": atr_val}
    )
