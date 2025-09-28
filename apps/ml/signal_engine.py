# apps/ml/signal_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Literal, Optional

@dataclass
class Levels:
    entry: float
    tp: List[float]
    sl: float

def atr_levels(close: float, atr: float, direction: Literal["LONG","SHORT"]) -> Levels:
    k_tp = (1.5, 2.5, 3.5); k_sl = 1.0
    if direction == "LONG":
        e = close
        return Levels(e, [e + k*atr for k in k_tp], e - k_sl*atr)
    else:
        e = close
        return Levels(e, [e - k*atr for k in k_tp], e + k_sl*atr)

def fib_adjust(levels: Levels, fibs: Optional[Dict[str,float]]) -> Levels:
    if not fibs: return levels
    vals = [v for k,v in fibs.items() if k.startswith("fibo_")]
    if not vals: return levels
    def nearest(x, cand): return min(cand, key=lambda c: abs(c-x))
    levels.tp = [nearest(t, vals) for t in levels.tp]
    return levels
