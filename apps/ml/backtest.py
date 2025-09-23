# apps/ml/backtest.py
# PL: Backtester sygnałów: symulacja TP1/TP2/TP3, SL, time-stop, trailing po TP1, funding, koszty, equity curve.
# EN: Signal backtester: TP1/2/3, SL, time-stop, trailing after TP1, funding, costs, equity.

from __future__ import annotations
import os, math, time
from dataclasses import dataclass
from typing import List, Dict, Literal, Optional, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db import models
from apps.ml.costs import est_entry_cost, est_slippage_cost, est_funding_cost, bps_to_frac, FEE_TAKER
from apps.ml.risk import position_size, leverage_for

MIN_NET_PROFIT = float(os.getenv("MIN_NET_PROFIT", "0.02"))
FUNDING_ON = os.getenv("FUNDING_ON", "1") == "1"

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

@dataclass
class BTParams:
    capital: float
    risk: Literal["LOW","MED","HIGH"]
    taker_only: bool = False
    funding_rate_hourly: float = 0.0
    slippage_bps: float = float(os.getenv("SLIPPAGE_BPS", "10"))
    time_stop_min: int = 240
    trailing_after_tp1: bool = True
    tp_split: Tuple[float,float,float] = (0.3,0.4,0.3)  # shares closed at TP1/2/3

def _price_hits(high: float, low: float, target: float, side: Literal["LONG","SHORT"]) -> bool:
    return (high >= target) if side == "LONG" else (low <= target)

def _simulate_one(
    bars: List[Dict], side: Literal["LONG","SHORT"], entry: float, tp: List[float], sl: float,
    qty: float, params: BTParams
) -> TradeResult:
    """bars: [{'ts','o','h','l','c'}] starting from entry bar+1 forward."""
    fee_open = entry * qty * (FEE_TAKER if params.taker_only else 0.0)
    slip_cost = (entry * qty * bps_to_frac(params.slippage_bps)) if params.taker_only else 0.0
    remain_qty = qty
    got_tp1 = got_tp2 = got_tp3 = False
    realized = 0.0
    entry_ts = bars[0]["ts"] if bars else 0

    # trailing after TP1
    cur_sl = sl

    # iterate forward up to time stop
    max_bars = max(1, params.time_stop_min)  # naive: 1 bar ~ 1 minute for 1m TF; for higher TF przybliżenie
    for i, b in enumerate(bars[:max_bars], start=1):
        # TP sequence
        for k, target in enumerate(tp[:3], start=1):
            if not [got_tp1, got_tp2, got_tp3][k-1] and _price_hits(b["h"], b["l"], target, side):
                close_px = target
                part = params.tp_split[k-1] * qty
                part = min(part, remain_qty)
                realized += (close_px - entry) * (1 if side=="LONG" else -1) * part
                remain_qty -= part
                if k == 1:
                    got_tp1 = True
                    if params.trailing_after_tp1:
                        # move stop to breakeven plus small buffer
                        cur_sl = entry * (0.999 if side=="LONG" else 1.001)
                elif k == 2:
                    got_tp2 = True
                elif k == 3:
                    got_tp3 = True

        # SL check (with trailing)
        if remain_qty > 0 and _price_hits(b["h"], b["l"], cur_sl, "SHORT" if side=="LONG" else "LONG"):
            close_px = cur_sl
            realized += (close_px - entry) * (1 if side=="LONG" else -1) * remain_qty
            remain_qty = 0.0
            exit_ts = b["ts"]
            break
    else:
        # time stop – close at last close
        if bars:
            close_px = bars[min(len(bars)-1, max_bars-1)]["c"]
            realized += (close_px - entry) * (1 if side=="LONG" else -1) * remain_qty
            remain_qty = 0.0
            exit_ts = bars[min(len(bars)-1, max_bars-1)]["ts"]
        else:
            close_px = entry
            exit_ts = entry_ts

    # costs
    fee_close = close_px * qty * (FEE_TAKER if params.taker_only else 0.0)
    funding_cost = est_funding_cost(entry, qty, params.time_stop_min, params.funding_rate_hourly) if FUNDING_ON else 0.0
    total_fee = fee_open + fee_close + slip_cost
    pnl = realized - total_fee - funding_cost

    return TradeResult(
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry=entry,
        exit=close_px,
        side=side,
        fee=total_fee + funding_cost,
        pnl=pnl,
        hit_tp1=got_tp1,
        hit_tp2=got_tp2,
        hit_tp3=got_tp3,
    )

def load_bars(db: Session, symbol: str, tf: str, start_ts: int, end_ts: int) -> List[Dict]:
    q = (
        select(models.OHLCV)
        .where(models.OHLCV.symbol == symbol, models.OHLCV.tf == tf, models.OHLCV.ts >= start_ts, models.OHLCV.ts <= end_ts)
        .order_by(models.OHLCV.ts.asc())
    )
    rows = db.execute(q).scalars().all()
    return [{"ts": r.ts, "o": r.o, "h": r.h, "l": r.l, "c": r.c, "v": r.v} for r in rows]

def backtest_signals(
    db: Session,
    symbol: str,
    tf: str,
    signals: List[models.Signal],
    params: BTParams,
    bars_future: List[Dict],
) -> Tuple[List[TradeResult], Dict[str, float]]:
    trades: List[TradeResult] = []
    capital = params.capital
    eq = capital
    equity = [eq]
    wins = [0,0,0]  # tp1,tp2,tp3
    dd_peak = eq
    for s in signals:
        qty, _risk$ = position_size(capital, s.risk, s.entry, s.sl)
        if qty <= 0:
            continue
        # find future bars from next bar after signal.ts
        fut = [b for b in bars_future if b["ts"] > s.ts]
        if not fut:
            continue
        tr = _simulate_one(fut, s.dir, s.entry, s.tp or [], s.sl, qty, params)
        trades.append(tr)
        eq += tr.pnl
        equity.append(eq)
        dd_peak = max(dd_peak, eq)

        if tr.hit_tp1: wins[0]+=1
        if tr.hit_tp2: wins[1]+=1
        if tr.hit_tp3: wins[2]+=1

    # metrics
    pnl_total = eq - capital
    max_dd = 0.0
    peak = equity[0]
    for e in equity:
        peak = max(peak, e)
        max_dd = max(max_dd, (peak - e))
    max_dd_pct = max_dd / capital if capital>0 else 0.0
    pf = (sum([max(0,t.pnl) for t in trades]) / max(1e-9, abs(sum([min(0,t.pnl) for t in trades]))))
    mar = (pnl_total / max(1e-9, max_dd)) if max_dd>0 else float("inf")
    hr1 = wins[0] / max(1, len(trades))
    hr2 = wins[1] / max(1, len(trades))
    hr3 = wins[2] / max(1, len(trades))

    metrics = {
        "trades": len(trades),
        "pnl_total": pnl_total,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "pf": pf,
        "mar": mar,
        "hit_rate_tp1": hr1,
        "hit_rate_tp2": hr2,
        "hit_rate_tp3": hr3,
        "equity_curve": equity,
    }
    return trades, metrics
