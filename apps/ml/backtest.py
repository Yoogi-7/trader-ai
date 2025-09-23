# apps/ml/backtest.py
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Dict, Literal, Tuple
import numpy as np

FUNDING_ON = os.getenv("FUNDING_ON", "1") == "1"
FEE_TAKER = float(os.getenv("FEE_TAKER", "0.0005"))
SLIPPAGE_BPS = float(os.getenv("SLIPPAGE_BPS", "10"))

def bps(b: float) -> float:
    return b / 10_000.0

@dataclass
class BTParams:
    capital: float
    risk: Literal["LOW","MED","HIGH"]
    funding_rate_hourly: float = 0.0
    time_stop_min: int = 240
    slippage_bps: float = SLIPPAGE_BPS
    taker_only: bool = True
    tp_split: Tuple[float,float,float] = (0.3,0.4,0.3)
    trailing_after_tp1: bool = True

@dataclass
class TradeResult:
    entry_ts: int
    exit_ts: int
    entry: float
    exit: float
    side: Literal["LONG","SHORT"]
    fee: float
    pnl: float
    hit_tp1: bool
    hit_tp2: bool
    hit_tp3: bool

def simulate_trade(
    bars: List[Dict], side: Literal["LONG","SHORT"], entry: float, tp: List[float], sl: float,
    qty: float, p: BTParams
) -> TradeResult:
    fee_open = entry * qty * (FEE_TAKER if p.taker_only else 0.0)
    slip = entry * qty * bps(p.slippage_bps if p.taker_only else 0.0)
    remain = qty
    got1 = got2 = got3 = False
    cur_sl = sl
    entry_ts = bars[0]["ts"] if bars else 0

    # Iterujemy po barach (przybliżenie: 1 bar = 1 min)
    for i, b in enumerate(bars[: max(1, p.time_stop_min)], start=1):
        # TP
        for k, t in enumerate(tp[:3], start=1):
            if [got1, got2, got3][k-1]:
                continue
            hit = (b["h"] >= t) if side=="LONG" else (b["l"] <= t)
            if hit:
                part = p.tp_split[k-1] * qty
                part = min(part, remain)
                pnl_part = (t - entry) * (1 if side=="LONG" else -1) * part
                remain -= part
                if k==1:
                    got1 = True
                    if p.trailing_after_tp1:
                        cur_sl = entry * (0.999 if side=="LONG" else 1.001)
                elif k==2: got2 = True
                elif k==3: got3 = True

        # SL/trailing
        if remain > 0:
            sl_hit = (b["l"] <= cur_sl) if side=="LONG" else (b["h"] >= cur_sl)
            if sl_hit:
                exit_px = cur_sl
                realized = (exit_px - entry) * (1 if side=="LONG" else -1) * remain
                fee_close = exit_px * qty * (FEE_TAKER if p.taker_only else 0.0)
                funding = (entry * qty * p.funding_rate_hourly * (p.time_stop_min/60.0)) if FUNDING_ON else 0.0
                return TradeResult(entry_ts, b["ts"], entry, exit_px, side, fee_open+fee_close+slip+funding, realized - (fee_open+fee_close+slip+funding), got1, got2, got3)
    # time-stop close @ last
    if bars:
        last = bars[min(len(bars)-1, p.time_stop_min-1 if p.time_stop_min>0 else -1)]
        exit_px = last["c"]
        realized = (exit_px - entry) * (1 if side=="LONG" else -1) * remain
        fee_close = exit_px * qty * (FEE_TAKER if p.taker_only else 0.0)
        funding = (entry * qty * p.funding_rate_hourly * (p.time_stop_min/60.0)) if FUNDING_ON else 0.0
        return TradeResult(entry_ts, last["ts"], entry, exit_px, side, fee_open+fee_close+slip+funding, realized - (fee_open+fee_close+slip+funding), got1, got2, got3)
    return TradeResult(0,0,entry,entry,side,0.0,0.0,False,False,False)
