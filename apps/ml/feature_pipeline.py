# apps/ml/feature_pipeline.py
from __future__ import annotations
import numpy as np
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from apps.api.db import models

def load_bars(db: Session, symbol: str, tf: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    q = (select(models.OHLCV)
         .where(models.OHLCV.symbol==symbol, models.OHLCV.tf==tf,
                models.OHLCV.ts >= start_ts, models.OHLCV.ts <= end_ts)
         .order_by(models.OHLCV.ts.asc()))
    rows = db.execute(q).scalars().all()
    return [{"ts": r.ts, "o": r.o, "h": r.h, "l": r.l, "c": r.c, "v": r.v} for r in rows]

def ta_trend(close: np.ndarray, win: int = 50) -> float:
    if len(close) < win + 1:
        return 0.0
    x = close[-win:]
    return float(np.polyfit(np.arange(win), x, 1)[0])

def momentum(close: np.ndarray, win: int = 14) -> float:
    if len(close) < win + 1:
        return 0.0
    return float((close[-1] - close[-win]) / (close[-win] + 1e-9))

def build_mtf_context(db: Session, symbol: str, ts: int) -> Dict[str, float]:
    # 1h / 4h / 1d – we take last 300 bars each and compute slope + momentum
    ctx = {}
    for tf in ("1h","4h","1d"):
        bars = load_bars(db, symbol, tf, ts - 400*60_000*60, ts)  # okienko (heur.)
        if not bars:
            continue
        close = np.array([b["c"] for b in bars], dtype=float)
        ctx[f"{tf}_slope"] = ta_trend(close, win=min(100, len(close)-1))
        ctx[f"{tf}_mom"] = momentum(close, win=min(50, len(close)-1))
    return ctx

def multi_tf_confirm(ctx: Dict[str, float], direction: str, slope_thr: float = 0.0, mom_thr: float = 0.0) -> bool:
    """
    Simple rule: for LONG, slopes & momentum >= thresholds; for SHORT, <= -thresholds on majority TFs.
    """
    keys = [("1h_slope","1h_mom"), ("4h_slope","4h_mom")]
    votes = 0
    for s_key, m_key in keys:
        s = ctx.get(s_key, 0.0)
        m = ctx.get(m_key, 0.0)
        if direction == "LONG":
            if s >= slope_thr and m >= mom_thr:
                votes += 1
        else:
            if s <= -slope_thr and m <= -mom_thr:
                votes += 1
    return votes >= 2  # wymagana zgodność 1h & 4h
