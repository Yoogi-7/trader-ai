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
    trailing_offset_pct: float = 0.002  # 0.2% default trail distance

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
    qty_total = float(qty)
    fee_open = entry * qty_total * (FEE_TAKER if p.taker_only else 0.0)
    slip = entry * qty_total * bps(p.slippage_bps if p.taker_only else 0.0)
    remain = qty_total
    got1 = got2 = got3 = False
    cur_sl = sl
    entry_ts = bars[0]["ts"] if bars else 0
    direction_mult = 1 if side == "LONG" else -1
    realized_pnl = -(fee_open + slip)
    total_fees = fee_open + slip
    best_price = entry
    trail_active = False
    trail_offset = max(0.0, float(p.trailing_offset_pct))

    max_bars = max(1, p.time_stop_min)
    tp_targets = tp[:3]

    # Iterate bars (approx 1 bar = 1 minute)
    for idx, b in enumerate(bars[:max_bars], start=1):
        high = float(b["h"])
        low = float(b["l"])
        tp_hit_this_bar = False

        if trail_active:
            if side == "LONG":
                best_price = max(best_price, high)
                cur_sl = max(cur_sl, best_price * (1.0 - trail_offset))
            else:
                best_price = min(best_price, low)
                cur_sl = min(cur_sl, best_price * (1.0 + trail_offset))

        # Take profit levels
        for k, target in enumerate(tp_targets, start=1):
            if remain <= 0:
                break
            if (k == 1 and got1) or (k == 2 and got2) or (k == 3 and got3):
                continue
            hit = (high >= target) if side == "LONG" else (low <= target)
            if not hit:
                continue

            desired_part = p.tp_split[k-1] * qty_total if k-1 < len(p.tp_split) else 0.0
            part = min(remain, desired_part if desired_part > 0 else remain)
            if part <= 0:
                continue

            exit_px = target
            fee_part = exit_px * part * (FEE_TAKER if p.taker_only else 0.0)
            pnl_part = ((exit_px - entry) * direction_mult * part) - fee_part
            realized_pnl += pnl_part
            total_fees += fee_part
            remain -= part
            tp_hit_this_bar = True

            if k == 1:
                got1 = True
                if p.trailing_after_tp1 and not trail_active:
                    trail_active = True
                    if side == "LONG":
                        best_price = max(best_price, exit_px)
                    else:
                        best_price = min(best_price, exit_px)
                    if side == "LONG":
                        cur_sl = max(cur_sl, best_price * (1.0 - trail_offset))
                    else:
                        cur_sl = min(cur_sl, best_price * (1.0 + trail_offset))
            elif k == 2:
                got2 = True
            elif k == 3:
                got3 = True

            if remain <= 0:
                return TradeResult(entry_ts, b["ts"], entry, exit_px, side, total_fees, realized_pnl, got1, got2, got3)

        if remain <= 0:
            break

        # Stop-loss / trailing stop check after TP handling
        if tp_hit_this_bar:
            continue

        sl_hit = (low <= cur_sl) if side == "LONG" else (high >= cur_sl)
        if sl_hit:
            exit_px = cur_sl
            fee_close = exit_px * remain * (FEE_TAKER if p.taker_only else 0.0)
            funding = (entry * qty_total * p.funding_rate_hourly * (p.time_stop_min / 60.0)) if FUNDING_ON else 0.0
            pnl_close = ((exit_px - entry) * direction_mult * remain) - fee_close - funding
            realized_pnl += pnl_close
            total_fees += fee_close + funding
            remain = 0.0
            return TradeResult(entry_ts, b["ts"], entry, exit_px, side, total_fees, realized_pnl, got1, got2, got3)

    # Time-stop close if trade still open
    if bars and remain > 0:
        last_index = min(len(bars) - 1, max_bars - 1)
        last = bars[last_index]
        exit_px = float(last["c"])
        fee_close = exit_px * remain * (FEE_TAKER if p.taker_only else 0.0)
        funding = (entry * qty_total * p.funding_rate_hourly * (p.time_stop_min / 60.0)) if FUNDING_ON else 0.0
        pnl_close = ((exit_px - entry) * direction_mult * remain) - fee_close - funding
        realized_pnl += pnl_close
        total_fees += fee_close + funding
        remain = 0.0
        return TradeResult(entry_ts, last["ts"], entry, exit_px, side, total_fees, realized_pnl, got1, got2, got3)

    return TradeResult(entry_ts, entry_ts, entry, entry, side, total_fees, realized_pnl, got1, got2, got3)
